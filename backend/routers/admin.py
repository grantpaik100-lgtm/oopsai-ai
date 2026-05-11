from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/cases", tags=["admin"])


class ReviewRequest(BaseModel):
    status: Literal["approved", "rejected"]
    reviewed_by: str = Field(default="admin")
    comment: str | None = None


class ActionResultRequest(BaseModel):
    action_result: str = Field(min_length=1)
    action_date: str | None = None
    submitted_by: str = Field(default="user")


@router.get("/pending")
def get_pending_cases() -> list[dict[str, str]]:
    return [
        {
            "case_id": "PENDING_001",
            "status": "pending",
            "submitted_by": "user_001",
            "submitted_at": "2026-05-11T10:42:00+00:00",
            "summary": "보호구 미착용 및 미끄러운 통로 관련 아차사고",
        }
    ]


@router.patch("/{case_id}/review")
def review_case(case_id: str, request: ReviewRequest) -> dict[str, str | None]:
    return {
        "case_id": case_id,
        "status": request.status,
        "reviewed_by": request.reviewed_by,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "comment": request.comment,
    }


@router.patch("/{case_id}/action-result")
def update_action_result(case_id: str, request: ActionResultRequest) -> dict[str, str | None]:
    return {
        "case_id": case_id,
        "status": "action_result_submitted",
        "action_result": request.action_result,
        "action_date": request.action_date,
        "submitted_by": request.submitted_by,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
