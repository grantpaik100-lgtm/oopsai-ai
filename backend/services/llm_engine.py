from models.schemas import NormalizeRequest, NormalizedInput
from services.taxonomy import map_labels, map_user_label


def mock_normalize(request: NormalizeRequest) -> NormalizedInput:
    accident_raw = request.fields.accident_type_raw or request.situation_text
    work_raw = request.fields.work_type_raw or "general_work"
    hazard_raw = request.fields.hazard_raw or ["보호구 미착용"]
    environment_raw = request.fields.environment_factor_raw or ["해당 없음"]
    human_raw = request.fields.human_factor_raw or ["안전수칙 미준수"]

    hazard_middle = map_user_label(hazard_raw[0]) if hazard_raw else "unknown"

    return NormalizedInput(
        accident_type=map_user_label(accident_raw),
        work_type=map_user_label(work_raw),
        hazard_major_category="protective_equipment"
        if hazard_middle == "protective_equipment_missing"
        else "human_or_environment",
        hazard_middle_category=hazard_middle,
        environment_factors=map_labels(environment_raw),
        human_factors=map_labels(human_raw),
        equipment=request.fields.equipment_raw,
        confidence=0.91,
        ai_recommendations={
            "accident_type": map_user_label(accident_raw),
            "hazard_raw_matched": hazard_raw[0] if hazard_raw else "",
        },
    )
