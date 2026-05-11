from fastapi import APIRouter, Query

from models.schemas import SimilarCase

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("/similar", response_model=list[SimilarCase])
def get_similar_cases(
    type: str | None = Query(default=None, description="Accident type filter"),
    hazard: str | None = Query(default=None, description="Hazard filter"),
) -> list[SimilarCase]:
    accident_type = type or "slip"
    hazard_hint = f" / hazard: {hazard}" if hazard else ""

    return [
        SimilarCase(
            case_id="CASE_001",
            similarity=0.94,
            accident_summary=f"보행 중 미끄러짐으로 넘어질 뻔한 사례{hazard_hint}",
            accident_type=accident_type,
        ),
        SimilarCase(
            case_id="CASE_002",
            similarity=0.89,
            accident_summary="보호구 미착용 상태에서 작업 중 발생한 아차사고",
            accident_type=accident_type,
        ),
        SimilarCase(
            case_id="CASE_003",
            similarity=0.83,
            accident_summary="정리되지 않은 작업장 통로에서 발생한 충돌 위험 사례",
            accident_type=accident_type,
        ),
    ]
