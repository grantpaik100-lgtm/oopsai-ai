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
