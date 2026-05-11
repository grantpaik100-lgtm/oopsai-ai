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


class NormalizedInput(BaseModel):
    accident_type: str
    work_type: str
    hazard_major_category: str
    hazard_middle_category: str
    environment_factors: list[str]
    human_factors: list[str]
    equipment: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    ai_recommendations: dict[str, str] = Field(default_factory=dict)


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


class SimilarCase(BaseModel):
    case_id: str
    similarity: float = Field(ge=0.0, le=1.0)
    accident_summary: str
    accident_type: str


class RiskScore(BaseModel):
    level: str
    score: int = Field(ge=0, le=100)


class AnalyzeResponse(BaseModel):
    meta: dict[str, str]
    input_summary: dict[str, str | None]
    prevention_list: list[PreventionItem]
    similar_cases: list[SimilarCase]
    risk_score: RiskScore
