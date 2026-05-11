import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.db import get_connection, get_database_path

router = APIRouter(prefix="/api/cases", tags=["admin"])
dev_router = APIRouter(prefix="/dev", tags=["dev"])


class ReviewRequest(BaseModel):
    status: Literal["approved", "rejected"]
    reviewed_by: str = Field(default="admin")
    comment: str | None = None


class ActionResultRequest(BaseModel):
    action_result: str = Field(min_length=1)
    action_date: str | None = None
    submitted_by: str = Field(default="user")


def _db_unavailable(exc: FileNotFoundError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


def _load_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {}


def _build_summary(normalized_json: str | None, output_json: str | None) -> str:
    try:
        output = _load_json(output_json)
        input_summary = output.get("input_summary")
        if isinstance(input_summary, dict):
            parts = [
                input_summary.get("accident_type"),
                input_summary.get("work_type"),
                input_summary.get("hazard"),
            ]
            summary = " / ".join(str(part) for part in parts if part)
            if summary:
                return summary

        normalized = _load_json(normalized_json)
        parts = [
            normalized.get("accident_type"),
            normalized.get("work_type"),
            _format_hazard(normalized),
        ]
        summary = " / ".join(str(part) for part in parts if part)
        return summary or "요약 생성 불가"
    except (TypeError, ValueError, json.JSONDecodeError):
        return "요약 생성 불가"


def _format_hazard(normalized: dict[str, Any]) -> str | None:
    major = normalized.get("hazard_major_category")
    middle = normalized.get("hazard_middle_category")
    if major and middle:
        return f"{major} / {middle}"
    if major:
        return str(major)
    if middle:
        return str(middle)
    return None


@router.get("/pending")
def get_pending_cases() -> list[dict[str, str | None]]:
    try:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    case_id,
                    status,
                    submitted_by,
                    submitted_at,
                    normalized,
                    output_json
                FROM pending_cases
                WHERE status = ?
                ORDER BY submitted_at DESC, id DESC
                """,
                ("pending",),
            ).fetchall()
    except FileNotFoundError as exc:
        raise _db_unavailable(exc) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to query pending_cases: {exc}") from exc

    return [
        {
            "case_id": row["case_id"],
            "status": row["status"],
            "submitted_by": row["submitted_by"],
            "submitted_at": row["submitted_at"],
            "summary": _build_summary(row["normalized"], row["output_json"]),
        }
        for row in rows
    ]


@router.patch("/{case_id}/review")
def review_case(case_id: str, request: ReviewRequest) -> dict[str, str | None]:
    reviewed_at = datetime.now(timezone.utc).isoformat()

    try:
        with get_connection() as connection:
            existing = connection.execute(
                "SELECT case_id FROM pending_cases WHERE case_id = ?",
                (case_id,),
            ).fetchone()
            if existing is None:
                raise HTTPException(status_code=404, detail=f"Pending case not found: {case_id}")

            connection.execute(
                """
                UPDATE pending_cases
                SET status = ?, reviewed_by = ?, reviewed_at = ?
                WHERE case_id = ?
                """,
                (request.status, request.reviewed_by, reviewed_at, case_id),
            )
            connection.commit()
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise _db_unavailable(exc) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update pending case review: {exc}") from exc

    return {
        "case_id": case_id,
        "status": request.status,
        "reviewed_by": request.reviewed_by,
        "reviewed_at": reviewed_at,
        "comment": request.comment,
    }


@router.patch("/{case_id}/action-result")
def update_action_result(case_id: str, request: ActionResultRequest) -> dict[str, str | None]:
    action_date = request.action_date or datetime.now(timezone.utc).date().isoformat()

    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT case_id, submitted_by, submitted_at
                FROM pending_cases
                WHERE case_id = ?
                """,
                (case_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail=f"Pending case not found: {case_id}")

            connection.execute(
                """
                UPDATE pending_cases
                SET "조치결과" = ?, "조치일시" = ?, status = ?
                WHERE case_id = ?
                """,
                (request.action_result, action_date, "action_completed", case_id),
            )
            connection.commit()
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise _db_unavailable(exc) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update action result: {exc}") from exc

    return {
        "case_id": case_id,
        "status": "action_completed",
        "조치결과": request.action_result,
        "조치일시": action_date,
        "submitted_by": row["submitted_by"],
        "submitted_at": row["submitted_at"],
    }


@dev_router.get("/db-summary")
def get_db_summary() -> dict[str, Any]:
    tables = ("incident_cases", "hazard_taxonomy", "prevention_taxonomy", "pending_cases")

    try:
        with get_connection() as connection:
            row_counts = {
                table_name: connection.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
                for table_name in tables
            }
            pending_status_counts = {
                row["status"] or "unknown": row["count"]
                for row in connection.execute(
                    """
                    SELECT status, COUNT(*) AS count
                    FROM pending_cases
                    GROUP BY status
                    ORDER BY status
                    """
                ).fetchall()
            }
    except FileNotFoundError as exc:
        raise _db_unavailable(exc) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to summarize database: {exc}") from exc

    return {
        "database_path": str(get_database_path()),
        "row_counts": row_counts,
        "pending_cases_by_status": pending_status_counts,
    }
