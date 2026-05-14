import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from models.schemas import (
    ActionGuide,
    AnalyzeRequest,
    AnalyzeResponse,
    NormalizeRequest,
    NormalizedInput,
    PreventionItem,
    RiskScore,
)
from routers.cases import find_similar_cases
from services.db import get_connection
from services.llm_engine import analyze_with_llm, normalize_with_llm
from services.severity_engine import predict_severity
from services.taxonomy import find_prevention_candidates

router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/normalize", response_model=NormalizedInput)
def normalize(request: NormalizeRequest) -> NormalizedInput:
    try:
        normalized = normalize_with_llm(request)
    except Exception as exc:
        _save_backend1_failure(request, exc)
        raise

    response = _prepare_backend1_response(request, normalized)
    _save_backend1_snapshot(request, response)
    return response


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    response = build_analyze_response(request)

    if request.case_id:
        response.meta["case_id"] = request.case_id
        _update_pending_case_backend2(request, response)
        return response

    try:
        case_id = _insert_pending_case(request, response)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (RuntimeError, sqlite3.Error) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save pending case: {exc}") from exc

    response.meta["case_id"] = case_id
    return response


def build_analyze_response(request: AnalyzeRequest) -> AnalyzeResponse:
    now = datetime.now(timezone.utc).isoformat()
    normalized = request.normalized
    hazard = f"{normalized.hazard_major_category} / {normalized.hazard_middle_category}"

    try:
        prevention_list = find_prevention_candidates(
            hazard_major_category=normalized.hazard_major_category,
            hazard_middle_category=normalized.hazard_middle_category,
            environment_factors=normalized.environment_factors,
            human_factors=normalized.human_factors,
            secondary_hazards=[(item.major, item.middle) for item in normalized.secondary_hazards],
        )
        similar_cases = find_similar_cases(
            accident_type=normalized.accident_type,
            hazard=normalized.hazard_middle_category or normalized.hazard_major_category,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    risk_reasons = build_risk_reasons(normalized)
    risk_score = RiskScore(level="medium", score=62, reasons=risk_reasons)
    llm_result = analyze_with_llm(
        normalized=normalized,
        prevention_candidates=prevention_list,
        similar_cases=similar_cases,
        meta=request.meta,
        raw_input=request.raw_input,
    )
    action_guide = build_fallback_action_guide(normalized, prevention_list)
    analysis_reason = "DB 후보 기반 규칙 결과를 반환했습니다."

    if llm_result:
        prevention_list = apply_llm_prevention_ranking(prevention_list, llm_result)
        risk_score.reasons = merge_risk_reasons(llm_result.get("risk_reasons"), risk_reasons)
        action_guide = build_action_guide(llm_result.get("action_guide")) or action_guide
        analysis_reason = "DB 예방대책 후보를 LLM이 정렬하고 설명했습니다."

    predicted_severity = predict_severity(
        normalized=normalized.model_dump(),
        situation_text=request.raw_input,
    )

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
            "secondary_hazards": summarize_secondary_hazards(normalized),
            "environment_factors": ", ".join(normalized.environment_factors),
            "human_factors": ", ".join(normalized.human_factors),
            "equipment": normalized.equipment or "not_applicable",
            "occurred_at": request.meta.occurred_at,
            "occurred_location": request.meta.occurred_location,
        },
        prevention_list=prevention_list,
        similar_cases=similar_cases,
        risk_score=risk_score,
        predicted_severity=predicted_severity,
        action_guide=action_guide,
        analysis_reason=analysis_reason,
    )

    return response


def _prepare_backend1_response(
    request: NormalizeRequest,
    normalized: NormalizedInput,
) -> NormalizedInput:
    recommendation_context = _build_recommendation_context(normalized)
    is_ready_for_recommendation = _is_ready_for_recommendation(request, normalized)

    return normalized.model_copy(
        update={
            "case_id": normalized.case_id or request.case_id,
            "is_ready_for_recommendation": is_ready_for_recommendation,
            "recommendation_context": recommendation_context,
            "image_edit_targets": [],
        }
    )


def _build_recommendation_context(normalized: NormalizedInput) -> dict:
    hazard_major = normalized.hazard_major_category or ""
    hazard_middle = normalized.hazard_middle_category or ""
    return {
        "accident_type": normalized.accident_type or "",
        "work_type": normalized.work_type or "",
        "primary_hazard": hazard_middle or hazard_major,
        "hazard_major_category": hazard_major,
        "hazard_middle_category": hazard_middle,
        "secondary_hazards": [
            item.model_dump(mode="json") for item in normalized.secondary_hazards
        ],
        "environment_factors": normalized.environment_factors or [],
        "human_factors": normalized.human_factors or [],
        "equipment": normalized.equipment,
        "confidence": normalized.confidence,
    }


def _is_ready_for_recommendation(
    request: NormalizeRequest,
    normalized: NormalizedInput,
) -> bool:
    has_accident_type = bool(normalized.accident_type.strip())
    has_hazard = bool(
        normalized.hazard_major_category.strip()
        or normalized.hazard_middle_category.strip()
    )
    has_work_context = bool(
        normalized.equipment
        or normalized.work_type.strip()
        or request.situation_text.strip()
    )
    return has_accident_type and has_hazard and has_work_context


def _backend_step_status(backend1_status: str) -> str:
    return json.dumps(
        {
            "backend1": backend1_status,
            "backend2": "not_started",
            "backend3": "not_started",
        },
        ensure_ascii=False,
    )


def _json_dumps_model(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, default=str)


def _load_step_status(value: str | None) -> dict[str, str]:
    default_status = {
        "backend1": "completed",
        "backend2": "not_started",
        "backend3": "not_started",
    }
    if not value:
        return default_status

    try:
        loaded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default_status

    if not isinstance(loaded, dict):
        return default_status

    merged = default_status.copy()
    for key in ("backend1", "backend2", "backend3"):
        existing = loaded.get(key)
        if isinstance(existing, str) and existing:
            merged[key] = existing
    return merged


def _backend2_step_status(existing_step_status: str | None) -> str:
    step_status = _load_step_status(existing_step_status)
    step_status["backend2"] = "completed"
    step_status.setdefault("backend3", "not_started")
    return json.dumps(step_status, ensure_ascii=False)


def _update_pending_case_backend2(
    request: AnalyzeRequest,
    response: AnalyzeResponse,
) -> None:
    if not request.case_id:
        return

    try:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT step_status FROM pending_cases WHERE case_id = ?",
                (request.case_id,),
            ).fetchone()
            if row is None:
                print(f"Backend 2 snapshot skipped: case_id not found: {request.case_id}")
                return

            connection.execute(
                """
                UPDATE pending_cases
                SET raw_input = COALESCE(?, raw_input),
                    normalized = ?,
                    output_json = ?,
                    backend2_input = ?,
                    backend2_output = ?,
                    step_status = ?,
                    status = ?
                WHERE case_id = ?
                """,
                (
                    request.raw_input,
                    _json_dumps_model(request.normalized),
                    _json_dumps_model(response),
                    _json_dumps_model(request),
                    _json_dumps_model(response),
                    _backend2_step_status(row["step_status"]),
                    "pending",
                    request.case_id,
                ),
            )
            connection.commit()
    except Exception as exc:
        _record_backend2_snapshot_error(request.case_id, exc)


def _record_backend2_snapshot_error(case_id: str, exc: Exception) -> None:
    try:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE pending_cases
                SET error_log = ?
                WHERE case_id = ?
                """,
                (f"Backend 2 snapshot failed: {exc}", case_id),
            )
            connection.commit()
    except Exception as log_exc:
        print(f"Backend 2 snapshot failed: {exc}; error_log update failed: {log_exc}")


def _save_backend1_snapshot(
    request: NormalizeRequest,
    response: NormalizedInput,
) -> None:
    if not request.case_id:
        return

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE pending_cases
                SET backend1_input = ?,
                    backend1_output = ?,
                    missing_info_questions = ?,
                    step_status = ?
                WHERE case_id = ?
                """,
                (
                    _json_dumps_model(request),
                    _json_dumps_model(response),
                    _json_dumps_model(response.missing_info_questions),
                    _backend_step_status("completed"),
                    request.case_id,
                ),
            )
            connection.commit()
            if cursor.rowcount == 0:
                print(f"Backend 1 snapshot skipped: case_id not found: {request.case_id}")
    except Exception as exc:
        _record_backend1_snapshot_error(request.case_id, exc)


def _save_backend1_failure(request: NormalizeRequest, exc: Exception) -> None:
    if not request.case_id:
        return

    try:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE pending_cases
                SET backend1_input = ?,
                    step_status = ?,
                    error_log = ?
                WHERE case_id = ?
                """,
                (
                    _json_dumps_model(request),
                    _backend_step_status("failed"),
                    str(exc),
                    request.case_id,
                ),
            )
            connection.commit()
    except Exception as log_exc:
        print(f"Backend 1 failure snapshot failed: {log_exc}")


def _record_backend1_snapshot_error(case_id: str, exc: Exception) -> None:
    try:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE pending_cases
                SET error_log = ?
                WHERE case_id = ?
                """,
                (f"Backend 1 snapshot failed: {exc}", case_id),
            )
            connection.commit()
    except Exception as log_exc:
        print(f"Backend 1 snapshot failed: {exc}; error_log update failed: {log_exc}")


def apply_llm_prevention_ranking(
    candidates: list[PreventionItem],
    llm_result: dict,
) -> list[PreventionItem]:
    by_id = {item.prevention_id: item for item in candidates}
    ranked_items: list[PreventionItem] = []
    used_ids: set[str] = set()

    for ranked in llm_result.get("ranked_preventions", []):
        if not isinstance(ranked, dict):
            continue
        prevention_id = str(ranked.get("prevention_id") or "")
        candidate = by_id.get(prevention_id)
        if not candidate or prevention_id in used_ids:
            continue
        updated = candidate.model_copy(
            update={"recommended_reason": str(ranked.get("recommended_reason") or "").strip() or None}
        )
        ranked_items.append(updated)
        used_ids.add(prevention_id)

    for candidate in candidates:
        if candidate.prevention_id not in used_ids:
            ranked_items.append(candidate)

    return [
        item.model_copy(update={"priority": index + 1})
        for index, item in enumerate(ranked_items)
    ]


def build_risk_reasons(normalized: NormalizedInput) -> list[str]:
    reasons: list[str] = []
    if normalized.hazard_middle_category:
        reasons.append(f"{normalized.hazard_middle_category}이 확인되었습니다.")
    for hazard in normalized.secondary_hazards:
        reasons.append(f"{hazard.major} / {hazard.middle}이 부가 위험요인으로 확인되었습니다.")
    if normalized.equipment:
        reasons.append(f"{normalized.equipment} 사용 상황이 확인되었습니다.")
    if normalized.environment_factors:
        reasons.append(f"환경요인으로 {', '.join(normalized.environment_factors)}이 확인되었습니다.")
    if normalized.human_factors:
        reasons.append(f"인적요인으로 {', '.join(normalized.human_factors)}이 확인되었습니다.")
    return reasons or ["정규화된 사고 정보가 확인되었습니다."]


def merge_risk_reasons(llm_reasons: object, fallback_reasons: list[str]) -> list[str]:
    merged: list[str] = []
    if isinstance(llm_reasons, list):
        merged.extend(str(reason).strip() for reason in llm_reasons if str(reason).strip())
    merged.extend(reason for reason in fallback_reasons if reason not in merged)
    return merged or fallback_reasons


def summarize_secondary_hazards(normalized: NormalizedInput) -> str:
    if not normalized.secondary_hazards:
        return ""
    return ", ".join(f"{item.major} / {item.middle}" for item in normalized.secondary_hazards)


def build_action_guide(value: object) -> ActionGuide | None:
    if not isinstance(value, dict):
        return None
    try:
        return ActionGuide.model_validate(value)
    except Exception:
        return None


def build_fallback_action_guide(
    normalized: NormalizedInput,
    prevention_list: list[PreventionItem],
) -> ActionGuide | None:
    if not prevention_list:
        return None

    primary = prevention_list[0]
    secondary_text = summarize_secondary_hazards(normalized)
    summary_parts = [normalized.hazard_middle_category]
    if secondary_text:
        summary_parts.append(secondary_text)
    summary = f"{' 및 '.join(part for part in summary_parts if part)} 관련 예방조치를 우선 확인합니다."

    immediate_actions = [primary.content]
    if len(prevention_list) > 1:
        immediate_actions.append(prevention_list[1].content)

    follow_up_actions = [
        item.content for item in prevention_list[2:4]
    ] or [primary.expected_action_result.get("applicable_situation") or primary.content]

    expected_result = (
        primary.expected_action_result.get("effect_summary")
        or primary.expected_action_result.get("expected_effect")
        or "DB 예방대책 적용으로 동일 유형 위험을 낮춤."
    )

    return ActionGuide(
        summary=summary,
        immediate_actions=immediate_actions,
        follow_up_actions=follow_up_actions,
        expected_result_example=expected_result,
    )


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
                backend2_input,
                backend2_output,
                step_status,
                submitted_by,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                raw_input,
                _json_dumps_model(request.normalized),
                _json_dumps_model(response),
                _json_dumps_model(request),
                _json_dumps_model(response),
                _backend2_step_status(None),
                request.meta.submitted_by,
                "pending",
            ),
        )
        connection.commit()

    return case_id
