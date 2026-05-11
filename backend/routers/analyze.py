import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    NormalizeRequest,
    NormalizedInput,
    RiskScore,
)
from routers.cases import find_similar_cases
from services.db import get_connection
from services.llm_engine import mock_normalize
from services.taxonomy import find_prevention_candidates

router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/normalize", response_model=NormalizedInput)
def normalize(request: NormalizeRequest) -> NormalizedInput:
    return mock_normalize(request)


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    now = datetime.now(timezone.utc).isoformat()
    normalized = request.normalized
    hazard = f"{normalized.hazard_major_category} / {normalized.hazard_middle_category}"

    try:
        prevention_list = find_prevention_candidates(
            hazard_major_category=normalized.hazard_major_category,
            hazard_middle_category=normalized.hazard_middle_category,
            environment_factors=normalized.environment_factors,
            human_factors=normalized.human_factors,
        )
        similar_cases = find_similar_cases(
            accident_type=normalized.accident_type,
            hazard=normalized.hazard_middle_category or normalized.hazard_major_category,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response = AnalyzeResponse(
        meta={
            "case_id": "",
            "timestamp": now,
            "status": "pending_review",
        },
        input_summary={
            "accident_type": normalized.accident_type,
            "work_type": normalized.work_type,
            "hazard": hazard,
            "environment_factors": ", ".join(normalized.environment_factors),
            "human_factors": ", ".join(normalized.human_factors),
            "equipment": normalized.equipment or "not_applicable",
            "occurred_at": request.meta.occurred_at,
            "occurred_location": request.meta.occurred_location,
        },
        prevention_list=prevention_list,
        similar_cases=similar_cases,
        risk_score=RiskScore(level="medium", score=62),
    )

    try:
        case_id = _insert_pending_case(request, response)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (RuntimeError, sqlite3.Error) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save pending case: {exc}") from exc

    response.meta["case_id"] = case_id
    return response


def _insert_pending_case(request: AnalyzeRequest, response: AnalyzeResponse) -> str:
    with get_connection() as connection:
        count = connection.execute("SELECT COUNT(*) FROM pending_cases").fetchone()[0]
        case_id = f"PENDING_{count + 1:03d}"
        response.meta["case_id"] = case_id

        raw_input = request.raw_input or json.dumps(
            request.model_dump(),
            ensure_ascii=False,
            default=str,
        )

        connection.execute(
            """
            INSERT INTO pending_cases (
                case_id,
                raw_input,
                normalized,
                output_json,
                submitted_by,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                raw_input,
                json.dumps(request.normalized.model_dump(), ensure_ascii=False, default=str),
                json.dumps(response.model_dump(), ensure_ascii=False, default=str),
                request.meta.submitted_by,
                "pending",
            ),
        )
        connection.commit()

    return case_id
