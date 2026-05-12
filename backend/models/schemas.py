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


class NormalizedInput(BaseModel):
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


class AnalyzeMeta(BaseModel):
    submitted_by: str
    occurred_at: str | None = None
    occurred_location: str | None = None


class AnalyzeRequest(BaseModel):
    raw_input: str | None = None
    normalized: NormalizedInput
    meta: AnalyzeMeta


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
