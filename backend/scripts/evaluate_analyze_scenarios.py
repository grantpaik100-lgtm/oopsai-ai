from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"
load_dotenv(ENV_PATH)

sys.path.insert(0, str(BACKEND_DIR))

from models.schemas import AnalyzeMeta, AnalyzeRequest, NormalizedInput
from routers.analyze import build_analyze_response
from services.db import get_database_path


@dataclass
class AnalyzeEvaluationResult:
    scenario_id: str
    name: str
    passed: bool
    failures: list[str]
    response: Any | None = None


BASE_AI_RECOMMENDATIONS = {
    "accident_type": [],
    "work_type": [],
    "hazard": [],
    "environment_factors": [],
    "human_factors": [],
    "equipment": [],
    "hazard_raw_matched": "",
    "reason": "",
}


SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "A001",
        "name": "사격 중 총기 부품 튐",
        "raw_input": "사격훈련 중 총기 부품이 튕겨 눈을 다칠 뻔했습니다. 보호안경을 착용하지 않았고 주변 통제가 부족했습니다.",
        "normalized": {
            "accident_type": "충격",
            "work_type": "훈련·사격",
            "hazard_major_category": "보호구요인",
            "hazard_middle_category": "보호장비미착용",
            "secondary_hazards": [
                {"major": "통제요인", "middle": "작업통제부족", "evidence": "주변 통제가 부족했습니다."}
            ],
            "environment_factors": [],
            "human_factors": [],
            "equipment": "총기류",
            "confidence": 0.93,
            "ai_recommendations": {
                **BASE_AI_RECOMMENDATIONS,
                "accident_type": ["충격"],
                "work_type": ["훈련·사격"],
                "hazard": ["보호장비미착용", "작업통제부족"],
                "environment_factors": ["해당 없음"],
                "equipment": ["총기류"],
                "hazard_raw_matched": "보호안경 미착용, 주변 통제 부족",
                "reason": "총기 부품이 튕긴 상황이며 보호안경 미착용과 주변 통제 부족이 위험요인입니다.",
            },
            "missing_info_questions": [],
        },
        "expected": {
            "expected_prevention_keywords": ["보호", "통제", "안전"],
            "expected_min_prevention_count": 1,
            "expected_min_similar_case_count": 0,
            "expected_risk_reason_keywords": ["보호장비미착용", "작업통제부족", "총기류"],
            "expected_action_guide_keywords": ["보호장비미착용", "통제", "보호"],
        },
    },
    {
        "id": "A002",
        "name": "복도 물기 낙상 위험",
        "raw_input": "복도 바닥에 물기가 있어 이동 중 미끄러져 넘어질 뻔했습니다.",
        "normalized": {
            "accident_type": "낙상",
            "work_type": "기타",
            "hazard_major_category": "작업환경요인",
            "hazard_middle_category": "미끄럼/지면불량",
            "secondary_hazards": [],
            "environment_factors": ["미끄럼/지면불량"],
            "human_factors": [],
            "equipment": None,
            "confidence": 0.88,
            "ai_recommendations": {
                **BASE_AI_RECOMMENDATIONS,
                "accident_type": ["낙상"],
                "hazard": ["미끄럼/지면불량"],
                "environment_factors": ["미끄럼/지면불량"],
                "reason": "복도 바닥의 물기로 낙상 위험이 있었습니다.",
            },
            "missing_info_questions": [],
        },
        "expected": {
            "expected_prevention_keywords": ["미끄럼", "지면", "환경"],
            "expected_min_prevention_count": 1,
            "expected_min_similar_case_count": 0,
            "expected_risk_reason_keywords": ["미끄럼/지면불량", "환경요인"],
            "expected_action_guide_keywords": ["미끄럼", "지면", "환경"],
        },
    },
    {
        "id": "A003",
        "name": "취사 중 기름 화상 위험",
        "raw_input": "취사 중 뜨거운 기름이 손에 튀어 화상을 입을 뻔했습니다.",
        "normalized": {
            "accident_type": "화재·화상",
            "work_type": "취사",
            "hazard_major_category": "환경요인",
            "hazard_middle_category": "기타",
            "secondary_hazards": [],
            "environment_factors": [],
            "human_factors": [],
            "equipment": "조리기구",
            "confidence": 0.82,
            "ai_recommendations": {
                **BASE_AI_RECOMMENDATIONS,
                "accident_type": ["화재·화상"],
                "work_type": ["취사"],
                "equipment": ["조리기구"],
                "reason": "뜨거운 기름 접촉으로 화상 위험이 있었습니다.",
            },
            "missing_info_questions": [],
        },
        "expected": {
            "expected_prevention_keywords": ["화상", "조리", "기름", "안전"],
            "expected_min_prevention_count": 1,
            "expected_min_similar_case_count": 0,
            "expected_risk_reason_keywords": ["기타", "조리기구"],
            "expected_action_guide_keywords": ["기타", "조리", "안전"],
        },
    },
    {
        "id": "A004",
        "name": "차량 후진 신호수 부재",
        "raw_input": "차량 후진 중 신호수가 없어 뒤쪽 인원과 충돌할 뻔했습니다.",
        "normalized": {
            "accident_type": "교통",
            "work_type": "차량운전·이동",
            "hazard_major_category": "통제요인",
            "hazard_middle_category": "작업통제부족",
            "secondary_hazards": [],
            "environment_factors": [],
            "human_factors": [],
            "equipment": "차량·트럭",
            "confidence": 0.9,
            "ai_recommendations": {
                **BASE_AI_RECOMMENDATIONS,
                "accident_type": ["교통", "충격"],
                "work_type": ["차량운전·이동"],
                "hazard": ["작업통제부족"],
                "equipment": ["차량·트럭"],
                "reason": "차량 후진 중 신호수 부재로 충돌 위험이 있었습니다.",
            },
            "missing_info_questions": [],
        },
        "expected": {
            "expected_prevention_keywords": ["통제", "차량", "안전"],
            "expected_min_prevention_count": 1,
            "expected_min_similar_case_count": 0,
            "expected_risk_reason_keywords": ["작업통제부족", "차량·트럭"],
            "expected_action_guide_keywords": ["작업통제부족", "차량", "통제"],
        },
    },
    {
        "id": "A005",
        "name": "전선 피복 손상 감전 위험",
        "raw_input": "정비 중 전선 피복 손상 부위를 만질 뻔해 감전 위험이 있었습니다.",
        "normalized": {
            "accident_type": "감전",
            "work_type": "장비점검·정비",
            "hazard_major_category": "장비요인",
            "hazard_middle_category": "장비결함",
            "secondary_hazards": [],
            "environment_factors": [],
            "human_factors": [],
            "equipment": "전동공구·절단기",
            "confidence": 0.86,
            "ai_recommendations": {
                **BASE_AI_RECOMMENDATIONS,
                "accident_type": ["감전"],
                "work_type": ["장비점검·정비"],
                "hazard": ["장비결함"],
                "equipment": ["전동공구·절단기"],
                "reason": "전선 피복 손상으로 감전 위험이 있었습니다.",
            },
            "missing_info_questions": [],
        },
        "expected": {
            "expected_prevention_keywords": ["장비", "점검", "감전", "안전"],
            "expected_min_prevention_count": 1,
            "expected_min_similar_case_count": 0,
            "expected_risk_reason_keywords": ["장비결함", "전동공구·절단기"],
            "expected_action_guide_keywords": ["장비결함", "장비", "점검"],
        },
    },
]


def main() -> int:
    database_path = get_database_path()
    if not database_path.exists():
        print("SQLite database not found.")
        print("uv run python scripts/init_db.py를 먼저 실행하라")
        return 1

    use_llm = os.getenv("OPENAI_API_KEY") and os.getenv("LLM_PROVIDER", "openai").lower() == "openai"
    print("Analyze scenario evaluation")
    print(f"Env file: {ENV_PATH}")
    print(f"has_key={bool(os.getenv('OPENAI_API_KEY'))}")
    print(f"Mode: {'OpenAI analyze_with_llm' if use_llm else 'DB/rule fallback'}")

    results = [run_scenario(scenario) for scenario in SCENARIOS]
    for result in results:
        print_result(result)

    passed = sum(1 for result in results if result.passed)
    total = len(results)
    print("\nSummary")
    print(f"Total: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Accuracy: {(passed / total * 100) if total else 0:.1f}%")
    print("Failed IDs:", ", ".join(result.scenario_id for result in results if not result.passed) or "-")
    return 0 if passed == total else 1


def run_scenario(scenario: dict[str, Any]) -> AnalyzeEvaluationResult:
    request = AnalyzeRequest(
        raw_input=scenario["raw_input"],
        normalized=NormalizedInput.model_validate(scenario["normalized"]),
        meta=AnalyzeMeta(
            submitted_by="eval",
            occurred_at="2026-05-12T14:30",
            occurred_location="평가장소",
        ),
    )
    try:
        response = build_analyze_response(request)
    except HTTPException as exc:
        return AnalyzeEvaluationResult(
            scenario_id=scenario["id"],
            name=scenario["name"],
            passed=False,
            failures=[f"HTTPException status={exc.status_code} detail={exc.detail}"],
        )
    except Exception as exc:
        return AnalyzeEvaluationResult(
            scenario_id=scenario["id"],
            name=scenario["name"],
            passed=False,
            failures=[f"Exception: {exc}"],
        )

    failures = compare_expected(scenario["expected"], response)
    return AnalyzeEvaluationResult(
        scenario_id=scenario["id"],
        name=scenario["name"],
        passed=not failures,
        failures=failures,
        response=response,
    )


def compare_expected(expected: dict[str, Any], response: Any) -> list[str]:
    failures: list[str] = []
    if len(response.prevention_list) < expected["expected_min_prevention_count"]:
        failures.append(
            f"prevention count expected>={expected['expected_min_prevention_count']} actual={len(response.prevention_list)}"
        )
    if len(response.similar_cases) < expected["expected_min_similar_case_count"]:
        failures.append(
            f"similar case count expected>={expected['expected_min_similar_case_count']} actual={len(response.similar_cases)}"
        )
    if not response.risk_score.reasons:
        failures.append("risk_score.reasons is empty")
    if not response.action_guide:
        failures.append("action_guide is missing")

    prevention_text = " ".join(
        f"{item.content} {item.recommended_reason or ''}" for item in response.prevention_list
    )
    risk_text = " ".join(response.risk_score.reasons)
    action_text = ""
    if response.action_guide:
        action_text = " ".join(
            [
                response.action_guide.summary,
                *response.action_guide.immediate_actions,
                *response.action_guide.follow_up_actions,
                response.action_guide.expected_result_example,
            ]
        )

    if not contains_any(prevention_text, expected["expected_prevention_keywords"]):
        failures.append(f"prevention keywords not found expected_any={expected['expected_prevention_keywords']}")
    if not contains_any(risk_text, expected["expected_risk_reason_keywords"]):
        failures.append(f"risk reason keywords not found expected_any={expected['expected_risk_reason_keywords']}")
    if not contains_any(action_text, expected["expected_action_guide_keywords"]):
        failures.append(f"action guide keywords not found expected_any={expected['expected_action_guide_keywords']}")
    return failures


def contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def print_result(result: AnalyzeEvaluationResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    print(f"\n[{status}] {result.scenario_id} {result.name}")
    if result.response:
        print(f"  prevention_count: {len(result.response.prevention_list)}")
        print(f"  similar_case_count: {len(result.response.similar_cases)}")
        print(f"  risk_score: {result.response.risk_score.model_dump()}")
        print(f"  action_guide: {result.response.action_guide.model_dump() if result.response.action_guide else None}")
        print(
            "  prevention_ids:",
            [f"{item.prevention_id}:{item.priority}" for item in result.response.prevention_list],
        )
    if result.failures:
        print(f"  failures: {'; '.join(result.failures)}")


if __name__ == "__main__":
    raise SystemExit(main())
