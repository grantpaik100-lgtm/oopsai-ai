import sqlite3

from fastapi import APIRouter, HTTPException, Query

from models.schemas import SimilarCase
from services.db import get_connection

router = APIRouter(prefix="/api/cases", tags=["cases"])

SIMILARITY_SCORES = [0.94, 0.89, 0.83]


def _like_term(value: str) -> str:
    return f"%{value.strip()}%"


def find_similar_cases(
    accident_type: str | None = None,
    hazard: str | None = None,
    limit: int = 3,
) -> list[SimilarCase]:
    conditions: list[str] = []
    params: list[str | int] = []

    if accident_type and accident_type.strip():
        conditions.append(
            """(
                "사고유형_표준" LIKE ?
                OR "사고유형_원본" LIKE ?
                OR "사례종류" LIKE ?
                OR "분류근거" LIKE ?
            )"""
        )
        params.extend([_like_term(accident_type)] * 4)

    if hazard and hazard.strip():
        conditions.append(
            """(
                "주요위험키워드" LIKE ?
                OR "위험상황" LIKE ?
                OR "환경요인" LIKE ?
                OR "인적요인" LIKE ?
            )"""
        )
        params.extend([_like_term(hazard)] * 4)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    query = f"""
        SELECT
            case_id,
            "원문사례" AS accident_summary,
            COALESCE("사고유형_표준", "사고유형_원본", '') AS accident_type
        FROM incident_cases
        {where_clause}
        ORDER BY case_id
        LIMIT ?
    """

    try:
        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()
    except FileNotFoundError:
        raise
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to query incident_cases: {exc}") from exc

    return [
        SimilarCase(
            case_id=row["case_id"],
            similarity=SIMILARITY_SCORES[index] if index < len(SIMILARITY_SCORES) else 0.8,
            accident_summary=row["accident_summary"] or "",
            accident_type=row["accident_type"] or "",
        )
        for index, row in enumerate(rows)
    ]


@router.get("/similar", response_model=list[SimilarCase])
def get_similar_cases(
    type: str | None = Query(default=None, description="Accident type filter"),
    hazard: str | None = Query(default=None, description="Hazard filter"),
) -> list[SimilarCase]:
    try:
        return find_similar_cases(accident_type=type, hazard=hazard)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
