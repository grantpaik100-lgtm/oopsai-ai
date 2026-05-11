from datetime import datetime, timezone

from fastapi import APIRouter

from models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    NormalizeRequest,
    NormalizedInput,
    PreventionItem,
    RiskScore,
    SimilarCase,
)
from services.llm_engine import mock_normalize

router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/normalize", response_model=NormalizedInput)
def normalize(request: NormalizeRequest) -> NormalizedInput:
    return mock_normalize(request)


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    now = datetime.now(timezone.utc).isoformat()
    normalized = request.normalized

    return AnalyzeResponse(
        meta={
            "case_id": "PENDING_001",
            "timestamp": now,
            "status": "pending_review",
        },
        input_summary={
            "accident_type": normalized.accident_type,
            "work_type": normalized.work_type,
            "hazard": f"{normalized.hazard_major_category} / {normalized.hazard_middle_category}",
            "environment_factors": ", ".join(normalized.environment_factors),
            "human_factors": ", ".join(normalized.human_factors),
            "equipment": normalized.equipment or "not_applicable",
            "occurred_at": request.meta.occurred_at,
            "occurred_location": request.meta.occurred_location,
        },
        prevention_list=[
            PreventionItem(
                prevention_id="PRV_001",
                major_category="protective_equipment",
                middle_category="safety_equipment_required",
                content="작업 전 보호구 착용 상태를 확인하고 미착용 시 작업을 중지합니다.",
                expected_action_result={
                    "effect_summary": "부상 위험 감소",
                    "expected_effect": "보호구 미착용으로 인한 사고 가능성을 낮춥니다.",
                    "applicable_situation": "일반 작업, 운반 작업, 정비 작업",
                },
                priority=1,
            ),
            PreventionItem(
                prevention_id="PRV_002",
                major_category="work_control",
                middle_category="supervision_required",
                content="단독 작업을 제한하고 작업 전 위험요인을 공유합니다.",
                expected_action_result={
                    "effect_summary": "작업 통제 강화",
                    "expected_effect": "위험 상황 발견과 대응 속도를 높입니다.",
                    "applicable_situation": "고위험 또는 반복 작업",
                },
                priority=2,
            ),
        ],
        similar_cases=[
            SimilarCase(
                case_id="CASE_001",
                similarity=0.94,
                accident_summary="보행 중 미끄러짐으로 넘어질 뻔한 사례",
                accident_type=normalized.accident_type,
            ),
            SimilarCase(
                case_id="CASE_002",
                similarity=0.88,
                accident_summary="보호구 미착용 상태에서 작업 중 발생한 아차사고",
                accident_type=normalized.accident_type,
            ),
        ],
        risk_score=RiskScore(level="medium", score=62),
    )
