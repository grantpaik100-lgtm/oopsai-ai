import json
import os
import re
from typing import Any

from openai import OpenAI

from models.schemas import NormalizeRequest, NormalizedInput
from services.taxonomy import map_labels, map_user_label

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

NORMALIZED_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "accident_type": {"type": "string", "enum": ACCIDENT_TYPES},
        "work_type": {"type": "string"},
        "hazard_major_category": {"type": "string", "enum": HAZARD_MAJOR_CATEGORIES},
        "hazard_middle_category": {"type": "string"},
        "environment_factors": {"type": "array", "items": {"type": "string"}},
        "human_factors": {"type": "array", "items": {"type": "string"}},
        "equipment": {"anyOf": [{"type": "string"}, {"type": "null"}]},
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

사용자가 선택한 칩은 참고하되, 상황 서술과 맞지 않으면 더 적절한 표준값을 선택하세요.
confidence는 0부터 1 사이 숫자로 산정하세요.
""".strip()


def mock_normalize(request: NormalizeRequest) -> NormalizedInput:
    accident_raw = request.fields.accident_type_raw or request.situation_text
    work_raw = request.fields.work_type_raw or "general_work"
    hazard_raw = request.fields.hazard_raw or ["보호구 미착용"]
    environment_raw = request.fields.environment_factor_raw or ["해당 없음"]
    human_raw = request.fields.human_factor_raw or ["안전수칙 미준수"]

    hazard_middle = map_user_label(hazard_raw[0]) if hazard_raw else "unknown"

    return NormalizedInput(
        accident_type=map_user_label(accident_raw),
        work_type=map_user_label(work_raw),
        hazard_major_category="protective_equipment"
        if hazard_middle == "protective_equipment_missing"
        else "human_or_environment",
        hazard_middle_category=hazard_middle,
        environment_factors=map_labels(environment_raw),
        human_factors=map_labels(human_raw),
        equipment=request.fields.equipment_raw,
        confidence=0.91,
        ai_recommendations={
            "accident_type": map_user_label(accident_raw),
            "hazard_raw_matched": hazard_raw[0] if hazard_raw else "",
        },
    )


def normalize_with_llm(request: NormalizeRequest) -> NormalizedInput:
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
