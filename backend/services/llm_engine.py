import json
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv

from models.schemas import NormalizeRequest, NormalizedInput
from services.classification_rules import build_rule_hints
from services.taxonomy import map_user_label

ACCIDENT_TYPES = [
    "끼임",
    "추락",
    "낙상",
    "충격",
    "교통",
    "화재·화상",
    "절단·베임",
    "폭발·파열",
    "감전",
    "과부하·온열",
    "질식·익사",
    "기타",
]

HAZARD_MAJOR_CATEGORIES = [
    "장비요인",
    "보호구요인",
    "환경요인",
    "인적요인",
    "절차요인",
    "통제요인",
    "숙련도요인",
    "정비요인",
    "기상요인",
    "작업환경요인",
    "기타",
]

HAZARD_MIDDLE_CATEGORIES = [
    "보호장비미착용",
    "사전점검미흡",
    "작업통제부족",
    "숙련도부족",
    "미끄럼/지면불량",
    "차량운행위험",
    "고소작업위험",
    "단독작업",
    "야간/조도불량",
    "장비노후화",
    "장비결함",
    "부품이탈",
    "낙하물",
    "환기부족",
    "확인미흡",
    "안전수칙미준수",
    "기타",
]

STANDARD_EQUIPMENT_VALUES = [
    "차량·트럭",
    "총기류",
    "크레인·지게차",
    "조리기구",
    "전동공구·절단기",
    "해당 없음",
    "기타",
]

NORMALIZED_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "accident_type": {"type": "string", "enum": ACCIDENT_TYPES},
        "work_type": {"type": "string"},
        "hazard_major_category": {
            "type": "string",
            "enum": HAZARD_MAJOR_CATEGORIES,
            "description": "rule_hints.hazard_major_candidates를 우선 고려하되, generic한 인적요인/환경요인으로 과하게 쏠리지 않게 선택한다.",
        },
        "hazard_middle_category": {
            "type": "string",
            "enum": HAZARD_MIDDLE_CATEGORIES,
            "description": "반드시 표준 중분류 후보 중 하나만 사용한다. 세부 보호구명이나 설명형 문구는 쓰지 않는다.",
        },
        "environment_factors": {"type": "array", "items": {"type": "string"}},
        "human_factors": {"type": "array", "items": {"type": "string"}},
        "equipment": {
            "anyOf": [{"type": "string", "enum": STANDARD_EQUIPMENT_VALUES}, {"type": "null"}],
            "description": "반드시 표준 장비값 중 하나만 사용한다. 세부 장비명이나 설명형 값은 금지한다.",
        },
        "confidence": {"type": "number"},
        "ai_recommendations": {
            "type": "object",
            "properties": {
                "accident_type": {"type": "string"},
                "work_type": {"type": "string"},
                "hazard_raw_matched": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["accident_type", "work_type", "hazard_raw_matched", "reason"],
            "additionalProperties": False,
        },
    },
    "required": [
        "accident_type",
        "work_type",
        "hazard_major_category",
        "hazard_middle_category",
        "environment_factors",
        "human_factors",
        "equipment",
        "confidence",
        "ai_recommendations",
    ],
    "additionalProperties": False,
}

SYSTEM_INSTRUCTION = """
당신은 군 안전관리 아차사고 입력을 표준 taxonomy로 정제하는 분류 엔진입니다.
반드시 JSON만 반환하세요. 설명, 마크다운, 코드블록을 출력하지 마세요.

사고유형 후보:
끼임, 추락, 낙상, 충격, 교통, 화재·화상, 절단·베임, 폭발·파열, 감전, 과부하·온열, 질식·익사, 기타

위험요인_대분류 후보:
장비요인, 보호구요인, 환경요인, 인적요인, 절차요인, 통제요인, 숙련도요인, 정비요인, 기상요인, 작업환경요인, 기타

위험요인_중분류 예시:
보호장비미착용, 사전점검미흡, 작업통제부족, 숙련도부족, 미끄럼/지면불량, 차량운행위험,
고소작업위험, 단독작업, 야간/조도불량, 장비노후화, 확인미흡, 안전수칙미준수
위험요인_중분류는 반드시 위 표준 후보 또는 장비결함, 부품이탈, 낙하물, 환기부족, 기타 중 하나로만 반환하세요.

equipment 허용값:
차량·트럭, 총기류, 크레인·지게차, 조리기구, 전동공구·절단기, 해당 없음, 기타, null

사용자가 선택한 칩은 참고하되, 상황 서술과 맞지 않으면 더 적절한 표준값을 선택하세요.
rule_hints.accident_type_candidates를 우선 고려하세요.
rule_hints.hazard_major_candidates가 있으면 인적요인/환경요인 같은 일반 범주보다 우선 고려하세요.
rule_hints.equipment_candidates가 있으면 그 표준 장비값을 우선 고려하세요.
rule_hints.excluded_accident_types에 포함된 사고유형은 선택하지 마세요.
상황 서술에 없는 위험을 추정하지 마세요.
"사격"이라는 단어만으로 화재·화상을 선택하지 마세요.
"부품 튐", "파편", "눈에 맞을 뻔함"은 충격을 우선 선택하세요.
보호안경/보호구 미착용이 핵심이면 보호구요인을 우선 선택하세요.
equipment에는 설명형 값을 쓰지 마세요.
"개인화기", "소총", "총기 부품", "탄피", "노리쇠"는 모두 "총기류"로 반환하세요.
"프라이팬", "칼", "냄비", "뜨거운 물", "기름"은 상황에 따라 "조리기구"로 반환하세요.
"그라인더", "드릴", "톱", "절단날", "절단기"는 "전동공구·절단기"로 반환하세요.
"차량", "트럭", "후진", "차륜"은 "차량·트럭"으로 반환하세요.
"지게차", "크레인", "인양장비"는 "크레인·지게차"로 반환하세요.
위 표준 장비군에 없으면 무리하게 세부 장비명을 만들지 말고 "기타" 또는 null을 사용하세요.
"폭발물", "신관", "회전체"처럼 현재 표준 장비군에 없는 값은 equipment에 세부명으로 쓰지 말고, 필요 시 "기타" 또는 null로 두세요.
명확한 장비 단서가 있으면 equipment를 null로 두지 말고 표준 장비명으로 채우되, 표준 장비군에 없는 단서만으로 과하게 추론하지 마세요.

위험요인 중분류 표준 표현:
- 보호안경, 장갑, 안전모 등 보호구 미착용은 세부 보호구명을 그대로 쓰지 말고 "보호장비미착용"을 우선 사용하세요.
- 선반, 상자, 적재물이 위에서 떨어져 맞을 뻔한 경우는 "낙하물"을 우선 사용하세요.
- 물기, 젖은 계단, 미끄러운 바닥은 "미끄럼/지면불량"을 우선 사용하세요.
- 신호수 부재, 후진 유도 부재, 주변 통제 미흡은 "작업통제부족"을 우선 사용하세요.
- 점검 없이 만짐, 작업 전 확인 부족은 "사전점검미흡" 또는 "확인미흡"을 우선 사용하세요.

위험요인 대분류 우선순위:
- 보호안경, 안전모, 장갑, 보호구 미착용이 직접 원인이면 보호구요인을 선택하세요.
- 신호수 부재, 안전거리 미확보, 주변 통제 미흡, 후진 유도 부재, 시야 사각지대 관리는 통제요인을 우선 고려하세요.
- 장비 결함, 부품 이탈, 볼트 튐, 파편 비산, 전선/누전, 밸브 이상, 회전체, 절단날 위험은 장비요인을 우선 고려하세요.
- 사전점검 미흡, 점검 없이 만짐, 안전수칙 미준수, 폭발물/탄약 취급 절차 문제는 절차요인을 우선 고려하세요.
- 물기, 젖은 계단, 장애물, 창고 적재물, 선반 낙하, 차량 위 작업, 밀폐공간, 환기 부족은 작업환경요인을 우선 고려하세요.
- 비, 눈, 결빙, 강풍, 폭염, 혹한, 야간 시야 제한처럼 기상이나 시간대가 직접 원인이면 기상요인을 선택하세요.
- 감전 상황에서 "젖은 손으로 콘센트를 만짐"은 기상요인보다 절차요인/인적요인/장비요인을 우선 고려하세요. 비나 눈 칩이 있어도 원문의 직접 원인이 접촉 행동이면 기상요인을 선택하지 마세요.
- 차량 문, 문틈, 회전체, 절단날처럼 장비의 물리적 구조에 끼이거나 닿는 위험은 통제요인보다 장비요인을 우선 고려하세요.
- 철판 모서리, 날카로운 모서리, 정리되지 않은 적재물처럼 현장 물체 배치나 표면이 직접 원인이면 인적요인보다 작업환경요인을 우선 고려하세요.
- 작업자가 등장한다는 이유만으로 인적요인을 선택하지 마세요. 방심, 무리한 운반, 혼자 작업처럼 사람의 행동이 핵심일 때만 인적요인을 선택하세요.
- 열, 불, 연기, 뜨거운 액체 등 물리적 환경 자체가 직접 원인이면 환경요인을 고려하되, 장비 고온부나 배기부 접촉은 장비요인도 함께 강하게 고려하세요.
단, 원문 근거가 부족하면 confidence를 낮추세요.
confidence는 0부터 1 사이 숫자로 산정하세요.
""".strip()


def mock_normalize(request: NormalizeRequest) -> NormalizedInput:
    rule_hints = build_rule_hints(request.situation_text, request.fields)
    accident_raw = request.fields.accident_type_raw or request.situation_text
    work_raw = request.fields.work_type_raw or "일반작업"
    hazard_raw = request.fields.hazard_raw or ["보호구 미착용"]
    environment_raw = request.fields.environment_factor_raw or ["해당 없음"]
    human_raw = request.fields.human_factor_raw or ["안전수칙 미준수"]
    hazard_middle_source = [
        *(request.fields.hazard_raw or []),
        *(request.fields.environment_factor_raw or []),
        *(request.fields.human_factor_raw or []),
    ] or hazard_raw

    accident_type = _first_hint(rule_hints, "accident_type_candidates") or _to_korean_taxonomy(
        map_user_label(accident_raw),
        default=accident_raw,
    )
    hazard_major = _first_hint(rule_hints, "hazard_major_candidates") or _infer_mock_hazard_major(hazard_raw)
    hazard_middle = _infer_mock_hazard_middle(hazard_middle_source)
    equipment = request.fields.equipment_raw or _first_hint(rule_hints, "equipment_candidates")

    return NormalizedInput(
        accident_type=accident_type,
        work_type=_to_korean_taxonomy(map_user_label(work_raw), default=work_raw),
        hazard_major_category=hazard_major,
        hazard_middle_category=hazard_middle,
        environment_factors=[_to_korean_taxonomy(map_user_label(value), default=value) for value in environment_raw],
        human_factors=[_to_korean_taxonomy(map_user_label(value), default=value) for value in human_raw],
        equipment=equipment,
        confidence=0.91,
        ai_recommendations={
            "accident_type": accident_type,
            "work_type": _to_korean_taxonomy(map_user_label(work_raw), default=work_raw),
            "hazard_raw_matched": hazard_raw[0] if hazard_raw else "",
            "reason": str(rule_hints["rule_reason"]),
        },
    )


def normalize_with_llm(request: NormalizeRequest) -> NormalizedInput:
    _load_backend_env_if_needed()

    if os.getenv("LLM_PROVIDER", "openai").lower() != "openai":
        return mock_normalize(request)

    if not os.getenv("OPENAI_API_KEY"):
        return mock_normalize(request)

    try:
        response = _create_openai_response(request)
        payload = _parse_json_payload(_extract_response_text(response))
        payload["confidence"] = _clamp_confidence(payload.get("confidence"))
        return NormalizedInput.model_validate(payload)
    except Exception:
        return mock_normalize(request)


def _create_openai_response(request: NormalizeRequest) -> Any:
    client = OpenAI()
    model = os.getenv("LLM_MODEL", "gpt-5.4-nano")
    user_payload = {
        "situation_text": request.situation_text,
        "fields": request.fields.model_dump(),
        "rule_hints": build_rule_hints(request.situation_text, request.fields),
    }

    return client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "normalized_incident",
                "strict": True,
                "schema": NORMALIZED_INPUT_SCHEMA,
            }
        },
        max_output_tokens=700,
        temperature=0,
    )


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)

    chunks: list[str] = []
    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            text = getattr(content_item, "text", None)
            if text:
                chunks.append(str(text))

    return "\n".join(chunks)


def _parse_json_payload(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        payload = json.loads(match.group(0))

    if not isinstance(payload, dict):
        raise ValueError("LLM response JSON is not an object")

    return payload


def _clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence must be numeric") from exc

    return max(0.0, min(1.0, confidence))


def _load_backend_env_if_needed() -> None:
    if os.getenv("OPENAI_API_KEY") is not None:
        return
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(env_path)


def _first_hint(rule_hints: dict[str, Any], key: str) -> str | None:
    values = rule_hints.get(key)
    if isinstance(values, list) and values:
        return str(values[0])
    return None


def _infer_mock_hazard_major(hazard_raw: list[str]) -> str:
    joined = " ".join(hazard_raw)
    if any(keyword in joined for keyword in ["보호", "보호구", "보호장비", "미착용", "안전모", "보호안경"]):
        return "보호구요인"
    if any(keyword in joined for keyword in ["통제", "감독", "신호수", "안전거리"]):
        return "통제요인"
    if any(keyword in joined for keyword in ["장비", "고장", "불량", "노후", "파손"]):
        return "장비요인"
    if any(keyword in joined for keyword in ["점검", "절차", "안전수칙", "확인"]):
        return "절차요인"
    return "기타"


def _infer_mock_hazard_middle(hazard_raw: list[str]) -> str:
    if not hazard_raw:
        return "보호장비미착용"

    mapped = _to_korean_taxonomy(map_user_label(hazard_raw[0]), default=hazard_raw[0])
    if mapped != hazard_raw[0]:
        return mapped

    joined = " ".join(hazard_raw)
    if any(keyword in joined for keyword in ["보호", "미착용", "보호안경", "보호구"]):
        return "보호장비미착용"
    if "점검" in joined:
        return "사전점검미흡"
    if "통제" in joined or "감독" in joined:
        return "작업통제부족"
    if "미끄" in joined or "물기" in joined:
        return "미끄럼/지면불량"
    if "단독" in joined or "혼자" in joined:
        return "단독작업"
    return mapped


def _to_korean_taxonomy(value: str, default: str | None = None) -> str:
    mapping = {
        "strain": "과부하·온열",
        "slip": "낙상",
        "fall": "낙상",
        "fall_from_height": "추락",
        "traffic": "교통",
        "fire": "화재·화상",
        "cut": "절단·베임",
        "collision": "충격",
        "protective_equipment": "보호구요인",
        "protective_equipment_missing": "보호장비미착용",
        "pre_check_missing": "사전점검미흡",
        "working_alone": "단독작업",
        "work_control_missing": "작업통제부족",
        "equipment_defect": "장비노후화",
        "general_work": "일반작업",
        "other": "기타",
        "unknown": "기타",
    }
    return mapping.get(value, default or value)
