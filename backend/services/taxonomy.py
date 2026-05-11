import sqlite3

from models.schemas import PreventionItem
from services.db import get_connection

ACCIDENT_TYPE_MAP: dict[str, str] = {
    "몸이 삐끗함": "strain",
    "미끄러짐": "slip",
    "넘어짐": "fall",
    "떨어짐": "fall_from_height",
    "차량 사고": "traffic",
    "화재": "fire",
    "베임": "cut",
    "충돌": "collision",
    "기타": "other",
}

HAZARD_MAP: dict[str, str] = {
    "보호구": "protective_equipment_missing",
    "보호구 미착용": "protective_equipment_missing",
    "사전 점검": "pre_check_missing",
    "단독 작업": "working_alone",
    "통제": "work_control_missing",
    "장비 불량": "equipment_defect",
    "기타": "other",
}


def map_user_label(label: str) -> str:
    normalized = label.strip()
    for keyword, taxonomy_value in ACCIDENT_TYPE_MAP.items():
        if keyword in normalized:
            return taxonomy_value

    for keyword, taxonomy_value in HAZARD_MAP.items():
        if keyword in normalized:
            return taxonomy_value

    return normalized or "unknown"


def map_labels(labels: list[str]) -> list[str]:
    return [map_user_label(label) for label in labels]


def _like_term(value: str) -> str:
    return f"%{value.strip()}%"


def _row_to_prevention_item(row: sqlite3.Row, priority: int) -> PreventionItem:
    return PreventionItem(
        prevention_id=row["prevention_id"],
        major_category=row["예방대책_대분류"] or "",
        middle_category=row["예방대책_중분류"] or "",
        content=row["원문예방대책"] or "",
        expected_action_result={
            "effect_summary": row["기대효과"] or "",
            "expected_effect": row["기대효과"] or "",
            "applicable_situation": row["적용상황"] or "",
        },
        priority=priority,
    )


def find_prevention_candidates(
    hazard_major_category: str | None,
    hazard_middle_category: str | None,
    environment_factors: list[str],
    human_factors: list[str],
    limit: int = 3,
) -> list[PreventionItem]:
    search_values = [
        hazard_major_category,
        hazard_middle_category,
        *environment_factors,
        *human_factors,
    ]
    terms = [value.strip() for value in search_values if value and value.strip()]

    try:
        with get_connection() as connection:
            rows = _query_prevention_candidates(connection, terms, limit)
            if not rows:
                rows = connection.execute(
                    """
                    SELECT
                        prevention_id,
                        "원문예방대책",
                        "예방대책_대분류",
                        "예방대책_중분류",
                        "적용상황",
                        "기대효과",
                        "관련키워드"
                    FROM prevention_taxonomy
                    ORDER BY prevention_id
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to query prevention_taxonomy: {exc}") from exc

    return [_row_to_prevention_item(row, index + 1) for index, row in enumerate(rows)]


def _query_prevention_candidates(
    connection: sqlite3.Connection,
    terms: list[str],
    limit: int,
) -> list[sqlite3.Row]:
    if not terms:
        return []

    term_clause = """(
        "관련키워드" LIKE ?
        OR "적용상황" LIKE ?
        OR "예방대책_대분류" LIKE ?
        OR "예방대책_중분류" LIKE ?
    )"""
    where_clause = " OR ".join([term_clause] * len(terms))
    params: list[str | int] = []
    for term in terms:
        params.extend([_like_term(term)] * 4)
    params.append(limit)

    return connection.execute(
        f"""
        SELECT
            prevention_id,
            "원문예방대책",
            "예방대책_대분류",
            "예방대책_중분류",
            "적용상황",
            "기대효과",
            "관련키워드"
        FROM prevention_taxonomy
        WHERE {where_clause}
        ORDER BY prevention_id
        LIMIT ?
        """,
        params,
    ).fetchall()
