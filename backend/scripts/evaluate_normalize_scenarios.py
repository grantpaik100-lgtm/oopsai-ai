from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"
load_dotenv(ENV_PATH)

sys.path.insert(0, str(BACKEND_DIR))

from models.schemas import NormalizeFields, NormalizeRequest, NormalizedInput
from services.classification_rules import build_rule_hints
from services.llm_engine import normalize_with_llm

STANDARD_EQUIPMENT_VALUES = {
    "차량·트럭",
    "총기류",
    "크레인·지게차",
    "조리기구",
    "전동공구·절단기",
    "해당 없음",
    "기타",
}

STANDARD_WORK_TYPES = {
    "차량운전·이동",
    "장비점검·정비",
    "운반작업",
    "훈련·사격",
    "취사",
    "공사·보수",
    "체력단련",
    "기타",
}

STANDARD_AI_RECOMMENDATIONS = {
    "accident_type": {
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
    },
    "work_type": STANDARD_WORK_TYPES,
    "hazard": {
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
        "확인미흡",
        "안전수칙미준수",
        "장비결함",
        "부품이탈",
        "낙하물",
        "환기부족",
        "기타",
    },
    "environment_factors": {
        "야간/조도불량",
        "우천/강설",
        "고소작업환경",
        "협소공간",
        "미끄럼/지면불량",
        "고온/저온",
        "환기부족",
        "해당 없음",
        "기타",
    },
    "human_factors": {
        "확인미흡",
        "숙련도부족",
        "부주의",
        "안전수칙미준수",
        "무리한작업",
        "단독작업",
        "해당 없음",
        "기타",
    },
    "equipment": STANDARD_EQUIPMENT_VALUES,
}


@dataclass
class EvaluationResult:
    scenario: dict[str, Any]
    actual: NormalizedInput
    passed: bool
    failures: list[str]
    reason: str


SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "S001",
        "name": "사격 중 총기 부품 튐",
        "situation_text": "사격훈련 중 총기 부품이 튕겨 눈을 다칠 뻔했습니다. 보호안경을 착용하지 않았고 주변 통제가 부족했습니다.",
        "fields": {
            "work_type_raw": "훈련·사격 중",
            "hazard_raw": ["보호장비를 안 했다", "통제나 감독이 없었다"],
            "environment_factor_raw": ["해당 없음"],
            "human_factor_raw": ["확인을 안 했다"],
            "equipment_raw": "총기류",
        },
        "expected": {
            "accident_type": "충격",
            "work_type": "훈련·사격",
            "hazard_major_category": "보호구요인",
            "hazard_middle_category": "보호장비미착용",
            "equipment": "총기류",
            "ai_recommendations": {
                "accident_type": ["충격"],
                "work_type": ["훈련·사격"],
                "hazard": ["보호장비미착용", "작업통제부족"],
                "equipment": ["총기류"],
            },
        },
    },
    {
        "id": "S002",
        "name": "취사 중 뜨거운 기름 튐",
        "situation_text": "취사 중 프라이팬의 뜨거운 기름이 손에 튀어 데일 뻔했다.",
        "fields": {"work_type_raw": "밥 하다가·취사 중", "equipment_raw": "조리기구"},
        "expected": {
            "accident_type": "화재·화상",
            "hazard_major_category": ["환경요인", "절차요인"],
            "equipment": "조리기구",
        },
    },
    {
        "id": "S003",
        "name": "복도에서 물기 때문에 미끄러짐",
        "situation_text": "복도 바닥에 물기가 있어 이동 중 미끄러져 넘어질 뻔했다.",
        "fields": {"environment_factor_raw": ["경사지거나 미끄러웠다"]},
        "expected": {
            "accident_type": "낙상",
            "hazard_major_category": "작업환경요인",
            "hazard_middle_category": "미끄럼/지면불량",
            "equipment": None,
        },
    },
    {
        "id": "S004",
        "name": "사다리 위 작업 중 발 헛디딤",
        "situation_text": "사다리 위에서 보수작업 중 발을 헛디뎌 아래로 떨어질 뻔했다.",
        "fields": {"work_type_raw": "공사·보수작업 중"},
        "expected": {
            "accident_type": "추락",
            "hazard_major_category": ["작업환경요인", "절차요인"],
            "equipment": None,
        },
    },
    {
        "id": "S005",
        "name": "차량 후진 중 충돌할 뻔함",
        "situation_text": "차량 후진 중 신호수 부재로 뒤쪽 인원과 충돌할 뻔했다.",
        "fields": {"work_type_raw": "차량 운전·이동 중", "equipment_raw": "차량·트럭"},
        "expected": {
            "accident_type": "교통",
            "hazard_major_category": "통제요인",
            "equipment": "차량·트럭",
        },
    },
    {
        "id": "S006",
        "name": "절단기 작업 중 손가락 베일 뻔함",
        "situation_text": "절단기 작업 중 장갑을 착용하지 않아 손가락이 날에 베일 뻔했다.",
        "fields": {"work_type_raw": "장비 점검·정비 중", "equipment_raw": "전동공구·절단기"},
        "expected": {
            "accident_type": "절단·베임",
            "hazard_major_category": ["장비요인", "보호구요인"],
            "equipment": "전동공구·절단기",
        },
    },
    {
        "id": "S007",
        "name": "정비 중 손이 장비 사이에 끼일 뻔함",
        "situation_text": "정비 중 작동부와 프레임 사이에 손이 끼일 뻔했다.",
        "fields": {"work_type_raw": "장비 점검·정비 중"},
        "expected": {
            "accident_type": "끼임",
            "hazard_major_category": "장비요인",
            "equipment": None,
        },
    },
    {
        "id": "S008",
        "name": "야간 경계 중 어두운 길에서 넘어질 뻔함",
        "situation_text": "야간 경계 이동 중 시야가 어두워 길의 장애물을 보지 못하고 넘어질 뻔했다.",
        "fields": {"work_type_raw": "훈련·사격 중", "environment_factor_raw": ["밤이거나 어두웠다"]},
        "expected": {
            "accident_type": "낙상",
            "hazard_major_category": ["기상요인", "작업환경요인"],
            "equipment": None,
        },
    },
    {
        "id": "S009",
        "name": "전선 피복 손상 부위를 만질 뻔함",
        "situation_text": "정비 중 전선 피복 손상 부위를 모르고 만질 뻔해 감전 위험이 있었다.",
        "fields": {"work_type_raw": "장비 점검·정비 중"},
        "expected": {
            "accident_type": "감전",
            "hazard_major_category": ["정비요인", "장비요인"],
            "equipment": None,
        },
    },
    {
        "id": "S010",
        "name": "밀폐공간 작업 중 환기 부족",
        "situation_text": "밀폐공간 작업 중 환기 부족으로 숨이 답답해 질식 위험을 느꼈다.",
        "fields": {"environment_factor_raw": ["좁은 공간이었다"]},
        "expected": {
            "accident_type": "질식·익사",
            "hazard_major_category": "작업환경요인",
            "equipment": None,
        },
    },
    {
        "id": "S011",
        "name": "무거운 탄약 박스 운반 중 허리 통증 위험",
        "situation_text": "무거운 탄약 박스를 혼자 운반하다 허리에 무리가 올 뻔했다.",
        "fields": {"work_type_raw": "물건 옮기다가", "human_factor_raw": ["무리하게 작업했다"]},
        "expected": {
            "accident_type": "과부하·온열",
            "hazard_major_category": ["인적요인", "절차요인"],
            "equipment": None,
        },
    },
    {
        "id": "S012",
        "name": "폭발물 취급 중 신관 파손 위험",
        "situation_text": "폭발물 취급 중 신관이 파손되어 폭발 또는 파열 위험이 있었다.",
        "fields": {"work_type_raw": "훈련·사격 중"},
        "expected": {
            "accident_type": "폭발·파열",
            "hazard_major_category": ["장비요인", "절차요인"],
            "equipment": None,
        },
    },
    {
        "id": "S013",
        "name": "정비 중 볼트가 튀어 얼굴에 맞을 뻔함",
        "situation_text": "장비 정비 중 조여 둔 볼트가 튀어 얼굴에 맞을 뻔했다.",
        "fields": {"work_type_raw": "장비 점검·정비 중"},
        "expected": {
            "accident_type": "충격",
            "hazard_major_category": "장비요인",
            "equipment": None,
        },
    },
    {
        "id": "S014",
        "name": "창고에서 상자가 떨어져 머리에 맞을 뻔함",
        "situation_text": "창고 선반 위 상자가 떨어져 머리에 맞을 뻔했다.",
        "fields": {"work_type_raw": "물건 옮기다가"},
        "expected": {
            "accident_type": "충격",
            "hazard_major_category": ["작업환경요인", "절차요인"],
            "hazard_middle_category": "낙하물",
            "equipment": None,
        },
    },
    {
        "id": "S015",
        "name": "작업 중 파편이 날아와 팔에 맞을 뻔함",
        "situation_text": "금속 작업 중 작은 파편이 날아와 팔에 맞을 뻔했다.",
        "fields": {"work_type_raw": "공사·보수작업 중"},
        "expected": {
            "accident_type": "충격",
            "hazard_major_category": ["장비요인", "보호구요인"],
            "equipment": None,
        },
    },
    {
        "id": "S016",
        "name": "취사 중 뜨거운 물이 손에 쏟아질 뻔함",
        "situation_text": "취사 중 냄비의 뜨거운 물이 손에 쏟아질 뻔했다.",
        "fields": {"work_type_raw": "밥 하다가·취사 중", "equipment_raw": "조리기구"},
        "expected": {
            "accident_type": "화재·화상",
            "hazard_major_category": ["환경요인", "절차요인"],
            "equipment": "조리기구",
        },
    },
    {
        "id": "S017",
        "name": "엔진 정비 중 뜨거운 배기부 접촉 위험",
        "situation_text": "엔진 정비 중 뜨거운 배기부에 손이 닿을 뻔했다.",
        "fields": {"work_type_raw": "장비 점검·정비 중"},
        "expected": {
            "accident_type": "화재·화상",
            "hazard_major_category": ["장비요인", "절차요인", "환경요인"],
            "equipment": None,
        },
    },
    {
        "id": "S018",
        "name": "난방기 주변 종이가 탈 뻔함",
        "situation_text": "난방기 주변에 둔 종이가 열로 인해 탈 뻔했다.",
        "fields": {"environment_factor_raw": ["추웠거나 더웠다"]},
        "expected": {
            "accident_type": "화재·화상",
            "hazard_major_category": ["환경요인", "작업환경요인"],
            "equipment": None,
        },
    },
    {
        "id": "S019",
        "name": "젖은 계단에서 미끄러져 넘어질 뻔함",
        "situation_text": "젖은 계단에서 발이 미끄러져 넘어질 뻔했다.",
        "fields": {"environment_factor_raw": ["비나 눈이 왔다"]},
        "expected": {
            "accident_type": "낙상",
            "hazard_major_category": ["작업환경요인", "기상요인"],
            "hazard_middle_category": "미끄럼/지면불량",
            "equipment": None,
        },
    },
    {
        "id": "S020",
        "name": "차량 위 적재물 정리 중 추락 위험",
        "situation_text": "차량 위에서 적재물을 정리하던 중 아래로 떨어질 뻔했다.",
        "fields": {"work_type_raw": "물건 옮기다가", "equipment_raw": "차량·트럭"},
        "expected": {
            "accident_type": "추락",
            "hazard_major_category": ["작업환경요인", "절차요인"],
            "equipment": "차량·트럭",
        },
    },
    {
        "id": "S021",
        "name": "사다리에서 균형을 잃고 떨어질 뻔함",
        "situation_text": "사다리에서 균형을 잃고 바닥으로 떨어질 뻔했다.",
        "fields": {"work_type_raw": "공사·보수작업 중"},
        "expected": {
            "accident_type": "추락",
            "hazard_major_category": ["작업환경요인", "절차요인"],
            "equipment": None,
        },
    },
    {
        "id": "S022",
        "name": "차량 문에 손이 끼일 뻔함",
        "situation_text": "차량 문을 닫는 과정에서 손이 문틈에 끼일 뻔했다.",
        "fields": {"work_type_raw": "차량 운전·이동 중", "equipment_raw": "차량·트럭"},
        "expected": {
            "accident_type": "끼임",
            "hazard_major_category": ["장비요인", "인적요인"],
            "equipment": "차량·트럭",
        },
    },
    {
        "id": "S023",
        "name": "정비 중 회전체에 장갑이 말려 들어갈 뻔함",
        "situation_text": "정비 중 회전체에 장갑이 말려 들어갈 뻔했다.",
        "fields": {"work_type_raw": "장비 점검·정비 중"},
        "expected": {
            "accident_type": "끼임",
            "hazard_major_category": ["장비요인", "보호구요인"],
            "equipment": None,
        },
    },
    {
        "id": "S024",
        "name": "적재물 사이에 발이 끼일 뻔함",
        "situation_text": "적재물을 옮기던 중 발이 적재물 사이에 끼일 뻔했다.",
        "fields": {"work_type_raw": "물건 옮기다가"},
        "expected": {
            "accident_type": "끼임",
            "hazard_major_category": ["작업환경요인", "절차요인"],
            "equipment": None,
        },
    },
    {
        "id": "S025",
        "name": "취사 중 칼에 손가락을 벨 뻔함",
        "situation_text": "취사 중 칼질을 하다가 손가락을 벨 뻔했다.",
        "fields": {"work_type_raw": "밥 하다가·취사 중", "equipment_raw": "조리기구"},
        "expected": {
            "accident_type": "절단·베임",
            "hazard_major_category": ["인적요인", "절차요인"],
            "equipment": "조리기구",
        },
    },
    {
        "id": "S026",
        "name": "그라인더 절단날에 손이 닿을 뻔함",
        "situation_text": "그라인더 작업 중 회전하는 절단날에 손이 닿을 뻔했다.",
        "fields": {"work_type_raw": "공사·보수작업 중", "equipment_raw": "전동공구·절단기"},
        "expected": {
            "accident_type": "절단·베임",
            "hazard_major_category": ["장비요인", "보호구요인"],
            "equipment": "전동공구·절단기",
        },
    },
    {
        "id": "S027",
        "name": "철판 모서리에 팔이 베일 뻔함",
        "situation_text": "철판을 옮기다가 날카로운 모서리에 팔이 베일 뻔했다.",
        "fields": {"work_type_raw": "물건 옮기다가"},
        "expected": {
            "accident_type": "절단·베임",
            "hazard_major_category": ["작업환경요인", "절차요인"],
            "equipment": None,
        },
    },
    {
        "id": "S028",
        "name": "후진 차량 뒤에 신호수 없이 접근",
        "situation_text": "후진 차량 뒤쪽에 신호수 없이 접근해 충돌할 뻔했다.",
        "fields": {"work_type_raw": "차량 운전·이동 중", "equipment_raw": "차량·트럭"},
        "expected": {
            "accident_type": "교통",
            "hazard_major_category": "통제요인",
            "equipment": "차량·트럭",
        },
    },
    {
        "id": "S029",
        "name": "운전 중 사각지대 병사 미인지",
        "situation_text": "차량 운전 중 시야 사각지대에 있던 병사를 보지 못해 접촉할 뻔했다.",
        "fields": {"work_type_raw": "차량 운전·이동 중", "equipment_raw": "차량·트럭"},
        "expected": {
            "accident_type": "교통",
            "hazard_major_category": ["통제요인", "인적요인"],
            "equipment": "차량·트럭",
        },
    },
    {
        "id": "S030",
        "name": "차량 이동 중 차륜 근처에 발이 들어갈 뻔함",
        "situation_text": "차량 이동 중 차륜 근처에 발이 들어가 치일 뻔했다.",
        "fields": {"work_type_raw": "차량 운전·이동 중", "equipment_raw": "차량·트럭"},
        "expected": {
            "accident_type": "교통",
            "hazard_major_category": ["통제요인", "인적요인"],
            "equipment": "차량·트럭",
        },
    },
    {
        "id": "S031",
        "name": "젖은 손으로 전기 콘센트 접촉 위험",
        "situation_text": "젖은 손으로 전기 콘센트를 만질 뻔해 감전 위험이 있었다.",
        "fields": {"environment_factor_raw": ["비나 눈이 왔다"]},
        "expected": {
            "accident_type": "감전",
            "hazard_major_category": ["절차요인", "인적요인", "장비요인"],
            "equipment": None,
        },
    },
    {
        "id": "S032",
        "name": "누전 의심 장비를 점검 없이 만질 뻔함",
        "situation_text": "누전이 의심되는 장비를 사전점검 없이 만질 뻔했다.",
        "fields": {"work_type_raw": "장비 점검·정비 중"},
        "expected": {
            "accident_type": "감전",
            "hazard_major_category": ["정비요인", "장비요인", "절차요인"],
            "equipment": None,
        },
    },
    {
        "id": "S033",
        "name": "밀폐된 정화조 주변 어지러움",
        "situation_text": "밀폐된 정화조 주변에서 작업하다 어지러움을 느껴 질식 위험이 있었다.",
        "fields": {"environment_factor_raw": ["좁은 공간이었다"]},
        "expected": {
            "accident_type": "질식·익사",
            "hazard_major_category": "작업환경요인",
            "equipment": None,
        },
    },
    {
        "id": "S034",
        "name": "수중 작업 중 안전줄 없이 진입 위험",
        "situation_text": "수중 작업 중 안전줄 없이 물에 들어갈 뻔해 익사 위험이 있었다.",
        "fields": {"work_type_raw": "공사·보수작업 중"},
        "expected": {
            "accident_type": "질식·익사",
            "hazard_major_category": ["절차요인", "작업환경요인"],
            "equipment": None,
        },
    },
    {
        "id": "S035",
        "name": "폭염 속 장시간 작업 중 어지러움",
        "situation_text": "폭염 속에서 장시간 작업하다 어지러움을 느껴 쓰러질 뻔했다.",
        "fields": {"environment_factor_raw": ["추웠거나 더웠다"]},
        "expected": {
            "accident_type": "과부하·온열",
            "hazard_major_category": ["기상요인", "작업환경요인"],
            "equipment": None,
        },
    },
    {
        "id": "S036",
        "name": "무거운 물자 반복 운반 중 허리 부상 위험",
        "situation_text": "무거운 물자를 반복해서 운반하다 허리를 다칠 뻔했다.",
        "fields": {"work_type_raw": "물건 옮기다가", "human_factor_raw": ["무리하게 작업했다"]},
        "expected": {
            "accident_type": "과부하·온열",
            "hazard_major_category": ["인적요인", "절차요인"],
            "equipment": None,
        },
    },
    {
        "id": "S037",
        "name": "압력 용기 밸브 이상 파열 위험",
        "situation_text": "압력 용기 밸브 이상으로 용기가 파열될 위험이 있었다.",
        "fields": {"work_type_raw": "장비 점검·정비 중"},
        "expected": {
            "accident_type": "폭발·파열",
            "hazard_major_category": ["장비요인", "정비요인"],
            "equipment": None,
        },
    },
    {
        "id": "S038",
        "name": "탄약 취급 중 충격으로 폭발 위험",
        "situation_text": "탄약 취급 중 상자에 강한 충격을 줘 폭발 위험이 있었다.",
        "fields": {"work_type_raw": "훈련·사격 중"},
        "expected": {
            "accident_type": "폭발·파열",
            "hazard_major_category": ["절차요인", "장비요인"],
            "equipment": None,
        },
    },
]


def main() -> None:
    use_llm = os.getenv("OPENAI_API_KEY") and os.getenv("LLM_PROVIDER", "openai").lower() == "openai"
    print("Normalize scenario evaluation")
    print(f"Env file: {ENV_PATH}")
    print(f"has_key={bool(os.getenv('OPENAI_API_KEY'))}")
    print(f"Mode: {'OpenAI normalize_with_llm' if use_llm else 'mock fallback via normalize_with_llm'}")
    if not use_llm:
        print("OPENAI_API_KEY is not set or LLM_PROVIDER is not openai; results show fallback behavior.")
    print()

    results = [evaluate_scenario(scenario) for scenario in SCENARIOS]
    for result in results:
        print_result(result)

    passed = sum(1 for result in results if result.passed)
    total = len(results)
    accuracy = (passed / total) * 100 if total else 0
    print("Summary")
    print(f"Total: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Accuracy: {accuracy:.1f}%")
    failed_ids = [result.scenario["id"] for result in results if not result.passed]
    print(f"Failed IDs: {', '.join(failed_ids) if failed_ids else '-'}")

    print()
    print_fail_case_summary(results)

    s001 = next(result for result in results if result.scenario["id"] == "S001")
    if s001.actual.accident_type != "충격":
        print()
        print("S001 regression warning")
        print("S001 did not classify as 충격.")
        print("Likely missing rule: make 부품 튐/파편/눈에 맞을 뻔 stronger than 사격-related fire/heat cues.")


def evaluate_scenario(scenario: dict[str, Any]) -> EvaluationResult:
    fields = NormalizeFields(**scenario.get("fields", {}))
    request = NormalizeRequest(situation_text=scenario["situation_text"], fields=fields)
    actual = normalize_with_llm(request)
    expected = scenario["expected"]
    failures = compare_expected(expected, actual)
    hints = build_rule_hints(request.situation_text, request.fields)
    return EvaluationResult(
        scenario=scenario,
        actual=actual,
        passed=not failures,
        failures=failures,
        reason=str(hints["rule_reason"]),
    )


def compare_expected(expected: dict[str, Any], actual: NormalizedInput) -> list[str]:
    failures: list[str] = []

    if actual.work_type not in STANDARD_WORK_TYPES:
        failures.append(f"work_type non-standard actual={actual.work_type}")

    if actual.equipment is not None and actual.equipment not in STANDARD_EQUIPMENT_VALUES:
        failures.append(f"equipment non-standard actual={actual.equipment}")

    failures.extend(compare_ai_recommendations(actual))

    if actual.accident_type != expected["accident_type"]:
        failures.append(f"accident_type expected={expected['accident_type']} actual={actual.accident_type}")

    if "work_type" in expected and actual.work_type != expected["work_type"]:
        failures.append(f"work_type expected={expected['work_type']} actual={actual.work_type}")

    if "hazard_major_category" in expected and not matches_expected(
        expected["hazard_major_category"], actual.hazard_major_category
    ):
        failures.append(
            "hazard_major_category "
            f"expected={expected['hazard_major_category']} actual={actual.hazard_major_category}"
        )

    if expected.get("hazard_middle_category") and not matches_expected(
        expected["hazard_middle_category"], actual.hazard_middle_category
    ):
        failures.append(
            "hazard_middle_category "
            f"expected={expected['hazard_middle_category']} actual={actual.hazard_middle_category}"
        )

    if "equipment" in expected and actual.equipment != expected["equipment"]:
        failures.append(f"equipment expected={expected['equipment']} actual={actual.equipment}")

    expected_ai = expected.get("ai_recommendations")
    if isinstance(expected_ai, dict):
        actual_ai = actual.ai_recommendations.model_dump()
        for key, expected_values in expected_ai.items():
            actual_values = actual_ai.get(key, [])
            for expected_value in expected_values:
                if expected_value not in actual_values:
                    failures.append(
                        f"ai_recommendations.{key} missing expected={expected_value} actual={actual_values}"
                    )

    return failures


def compare_ai_recommendations(actual: NormalizedInput) -> list[str]:
    failures: list[str] = []
    recommendations = actual.ai_recommendations.model_dump()
    for key, allowed_values in STANDARD_AI_RECOMMENDATIONS.items():
        values = recommendations.get(key, [])
        if not isinstance(values, list):
            failures.append(f"ai_recommendations.{key} is not a list")
            continue
        for value in values:
            if value not in allowed_values:
                failures.append(f"ai_recommendations.{key} non-standard actual={value}")
    return failures


def matches_expected(expected: str | list[str], actual: str | None) -> bool:
    if isinstance(expected, list):
        return actual in expected
    if actual is None:
        return expected is None
    return actual == expected or expected in actual


def print_result(result: EvaluationResult) -> None:
    expected = result.scenario["expected"]
    actual = result.actual
    status = "PASS" if result.passed else "FAIL"
    print(f"[{status}] {result.scenario['id']} {result.scenario['name']}")
    print(
        "  expected: "
        f"accident_type={expected.get('accident_type')}, "
        f"work_type={expected.get('work_type')}, "
        f"hazard_major_category={expected.get('hazard_major_category')}, "
        f"hazard_middle_category={expected.get('hazard_middle_category')}, "
        f"equipment={expected.get('equipment')}"
    )
    print(
        "  actual:   "
        f"accident_type={actual.accident_type}, "
        f"work_type={actual.work_type}, "
        f"hazard_major_category={actual.hazard_major_category}, "
        f"hazard_middle_category={actual.hazard_middle_category}, "
        f"equipment={actual.equipment}"
    )
    print(f"  confidence: {actual.confidence:.2f}")
    print(f"  ai_recommendations: {actual.ai_recommendations.model_dump()}")
    print(f"  reason: {actual.ai_recommendations.reason or result.reason}")
    if result.failures:
        print(f"  failures: {'; '.join(result.failures)}")
    print()


def print_fail_case_summary(results: list[EvaluationResult]) -> None:
    failed_results = [result for result in results if not result.passed]
    print("FAIL CASE SUMMARY")
    if not failed_results:
        print("No failed cases.")
        return

    for result in failed_results:
        expected = result.scenario["expected"]
        actual = result.actual
        print(f"- {result.scenario['id']} {result.scenario['name']}")
        print(f"  expected accident_type: {expected.get('accident_type')}")
        print(f"  actual accident_type:   {actual.accident_type}")
        print(f"  expected hazard_major_category: {expected.get('hazard_major_category')}")
        print(f"  actual hazard_major_category:   {actual.hazard_major_category}")
        print(f"  expected equipment: {expected.get('equipment')}")
        print(f"  actual equipment:   {actual.equipment}")
        print(f"  confidence: {actual.confidence:.2f}")
        print(f"  reason: {actual.ai_recommendations.reason or '-'}")
        print(f"  rule_reason: {result.reason}")
        print(f"  suggested_rule_gap: {suggest_rule_gap(expected, actual)}")


def suggest_rule_gap(expected: dict[str, Any], actual: NormalizedInput) -> str:
    gaps: list[str] = []
    if actual.equipment is not None and actual.equipment not in STANDARD_EQUIPMENT_VALUES:
        gaps.append("equipment 표준값 enum/schema 지침 강화 필요")
    if actual.accident_type != expected.get("accident_type"):
        gaps.append("사고유형 키워드 또는 제외 규칙 보강 필요")
    if "hazard_major_category" in expected and not matches_expected(
        expected["hazard_major_category"], actual.hazard_major_category
    ):
        gaps.append("위험요인 대분류 키워드/우선순위 보강 필요")
    if expected.get("equipment") and actual.equipment != expected.get("equipment"):
        gaps.append("장비 추론 키워드 보강 필요")
    if expected.get("equipment") is None and actual.equipment is not None:
        gaps.append("장비 추론 과매칭 억제 규칙 필요")
    return "; ".join(gaps) if gaps else "세부 중분류 또는 허용 기준 재검토 필요"


if __name__ == "__main__":
    main()
