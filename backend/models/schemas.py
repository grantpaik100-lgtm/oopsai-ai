from typing import Any, Literal

from pydantic import BaseModel, Field


class NormalizeFields(BaseModel):
    accident_type_raw: str | None = None
    work_type_raw: str | None = None
    hazard_raw: list[str] = Field(default_factory=list)
    environment_factor_raw: list[str] = Field(default_factory=list)
    human_factor_raw: list[str] = Field(default_factory=list)
    equipment_raw: str | None = None


class NormalizeRequest(BaseModel):
    situation_text: str = Field(min_length=1)
    fields: NormalizeFields = Field(default_factory=NormalizeFields)
    case_id: str | None = None
    occurred_at: str | None = None
    occurred_location: str | None = None
    selected_accident_type: str | None = None
    stt_text: str | None = None
    images: list[Any] = Field(default_factory=list)
    missing_info_answers: list[Any] = Field(default_factory=list)


class AiRecommendations(BaseModel):
    accident_type: list[str] = Field(default_factory=list)
    work_type: list[str] = Field(default_factory=list)
    hazard: list[str] = Field(default_factory=list)
    environment_factors: list[str] = Field(default_factory=list)
    human_factors: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    hazard_raw_matched: str = ""
    reason: str = ""


class SecondaryHazard(BaseModel):
    major: str
    middle: str
    evidence: str


class MissingInfoQuestion(BaseModel):
    field: str
    question: str
    reason: str


class ImageEditTarget(BaseModel):
    target_id: str | None = None
    image_id: str | None = None
    source_image_url: str | None = None
    description: str = ""
    action_after_text: str | None = None
    mask_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedInput(BaseModel):
    case_id: str | None = None
    accident_type: str
    work_type: str
    hazard_major_category: str
    hazard_middle_category: str
    environment_factors: list[str]
    human_factors: list[str]
    equipment: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    ai_recommendations: AiRecommendations = Field(default_factory=AiRecommendations)
    secondary_hazards: list[SecondaryHazard] = Field(default_factory=list)
    missing_info_questions: list[MissingInfoQuestion] = Field(default_factory=list)
    is_ready_for_recommendation: bool = False
    recommendation_context: dict[str, Any] = Field(default_factory=dict)
    image_edit_targets: list[ImageEditTarget] = Field(default_factory=list)


class AnalyzeMeta(BaseModel):
    submitted_by: str
    occurred_at: str | None = None
    occurred_location: str | None = None


class AnalyzeRequest(BaseModel):
    case_id: str | None = None
    raw_input: str | None = None
    normalized: NormalizedInput
    meta: AnalyzeMeta
    recommendation_context: dict[str, Any] = Field(default_factory=dict)


class CaseStartRequest(BaseModel):
    submitted_by: str | None = None
    occurred_at: str | None = None
    occurred_location: str | None = None
    selected_accident_type: str | None = None
    situation_text: str | None = None
    stt_text: str | None = None
    photo_metadata: list[Any] = Field(default_factory=list)


class CaseStartResponse(BaseModel):
    case_id: str
    status: str = "draft"
    step_status: dict[str, str] = Field(default_factory=dict)
    created_at: str


class PreventionItem(BaseModel):
    prevention_id: str
    major_category: str
    middle_category: str
    content: str
    expected_action_result: dict[str, str]
    priority: int
    recommended_reason: str | None = None


class SimilarCase(BaseModel):
    case_id: str
    similarity: float = Field(ge=0.0, le=1.0)
    accident_summary: str
    accident_type: str


class RiskScore(BaseModel):
    level: str
    score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)


class ActionGuide(BaseModel):
    summary: str
    immediate_actions: list[str] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)
    expected_result_example: str


class PredictedSeverity(BaseModel):
    grade: str | None = None
    label: str
    is_actual_damage: bool = False
    confidence: str
    prediction_reason: list[str] = Field(default_factory=list)
    why_not_higher: str = ""
    why_not_lower: str = ""
    missing_information: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    meta: dict[str, str]
    input_summary: dict[str, str | None]
    prevention_list: list[PreventionItem]
    similar_cases: list[SimilarCase]
    risk_score: RiskScore
    predicted_severity: PredictedSeverity | None = None
    action_guide: ActionGuide | None = None
    analysis_reason: str | None = None
    debug: dict[str, str] | None = None


class SelectedAction(BaseModel):
    prevention_id: str | None = None
    content: str
    expected_action_result: dict[str, str] = Field(default_factory=dict)
    selected_reason: str | None = None


class SourceImage(BaseModel):
    image_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    base64_data: str | None = None
    preview_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenerateActionImageRequest(BaseModel):
    case_id: str | None = None
    source_image: SourceImage | None = None
    image_edit_target: ImageEditTarget
    selected_action: SelectedAction
    recommendation_context: dict[str, Any] = Field(default_factory=dict)


class GeneratedImage(BaseModel):
    image_id: str | None = None
    url: str | None = None
    base64_data: str | None = None
    mime_type: str = "image/png"
    prompt_summary: str | None = None


class GenerateActionImageResponse(BaseModel):
    case_id: str | None = None
    image_purpose: Literal["action_after_example"] = "action_after_example"
    is_actual_evidence: Literal[False] = False
    images: list[GeneratedImage] = Field(default_factory=list)
    safety_notice: str = (
        "Generated images are illustrative prevention examples and are not actual incident evidence."
    )
    limitations: list[str] = Field(
        default_factory=lambda: [
            "The generated image may omit site-specific hazards or constraints.",
            "Use it only as a reference for prevention planning and review.",
        ]
    )
