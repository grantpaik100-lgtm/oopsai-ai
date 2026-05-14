export interface NormalizeFields {
  accident_type_raw?: string | null;
  work_type_raw?: string | null;
  hazard_raw: string[];
  environment_factor_raw: string[];
  human_factor_raw: string[];
  equipment_raw?: string | null;
}

export interface NormalizeRequest {
  situation_text: string;
  fields: NormalizeFields;
  case_id?: string | null;
  occurred_at?: string | null;
  occurred_location?: string | null;
  selected_accident_type?: string | null;
  stt_text?: string | null;
  images?: unknown[];
  missing_info_answers?: unknown[];
}

export interface NormalizedInput {
  case_id?: string | null;
  accident_type: string;
  work_type: string;
  hazard_major_category: string;
  hazard_middle_category: string;
  environment_factors: string[];
  human_factors: string[];
  equipment?: string | null;
  confidence: number;
  ai_recommendations: AiRecommendations;
  secondary_hazards?: SecondaryHazard[];
  missing_info_questions?: MissingInfoQuestion[];
  is_ready_for_recommendation?: boolean;
  recommendation_context?: Record<string, unknown>;
  image_edit_targets?: ImageEditTarget[];
}

export interface AiRecommendations {
  accident_type: string[];
  work_type: string[];
  hazard: string[];
  environment_factors: string[];
  human_factors: string[];
  equipment: string[];
  hazard_raw_matched: string;
  reason: string;
}

export interface MissingInfoQuestion {
  field: string;
  question: string;
  reason: string;
}

export interface SecondaryHazard {
  major: string;
  middle: string;
  evidence: string;
}

export interface AnalyzeMeta {
  submitted_by: string;
  occurred_at?: string | null;
  occurred_location?: string | null;
}

export interface AnalyzeRequest {
  case_id?: string | null;
  raw_input?: string | null;
  normalized: NormalizedInput;
  meta: AnalyzeMeta;
  recommendation_context?: Record<string, unknown>;
}

export interface CaseStartRequest {
  submitted_by?: string | null;
  occurred_at?: string | null;
  occurred_location?: string | null;
  selected_accident_type?: string | null;
  situation_text?: string | null;
  stt_text?: string | null;
  photo_metadata?: unknown[];
}

export interface CaseStartResponse {
  case_id: string;
  status: string;
  step_status: Record<string, string>;
  created_at: string;
}

export interface PreventionItem {
  prevention_id: string;
  major_category: string;
  middle_category: string;
  content: string;
  expected_action_result: Record<string, string>;
  priority: number;
  recommended_reason?: string | null;
}

export interface SimilarCase {
  case_id: string;
  similarity: number;
  accident_summary: string;
  accident_type: string;
}

export interface RiskScore {
  level: string;
  score: number;
  reasons?: string[];
}

export interface ActionGuide {
  summary: string;
  immediate_actions: string[];
  follow_up_actions: string[];
  expected_result_example: string;
}

export interface PredictedSeverity {
  grade: "A" | "B" | "C" | "D" | "E" | null;
  label: string;
  is_actual_damage: false;
  confidence: "high" | "medium" | "low";
  prediction_reason: string[];
  why_not_higher: string;
  why_not_lower: string;
  missing_information: string[];
  validation_warnings: string[];
}

export interface AnalyzeResponse {
  meta: Record<string, string>;
  input_summary: Record<string, string | null>;
  prevention_list: PreventionItem[];
  similar_cases: SimilarCase[];
  risk_score: RiskScore;
  predicted_severity?: PredictedSeverity | null;
  action_guide?: ActionGuide | null;
  analysis_reason?: string | null;
  debug?: Record<string, string> | null;
}

export interface ImageEditTarget {
  target_id?: string | null;
  image_id?: string | null;
  source_image_url?: string | null;
  description?: string;
  action_after_text?: string | null;
  mask_hint?: string | null;
  metadata?: Record<string, unknown>;
}

export interface SourceImage {
  image_id?: string | null;
  filename?: string | null;
  mime_type?: string | null;
  base64_data?: string | null;
  preview_url?: string | null;
  metadata?: Record<string, unknown>;
}

export interface SelectedAction {
  prevention_id?: string | null;
  content: string;
  expected_action_result?: Record<string, string>;
  selected_reason?: string | null;
}

export interface GenerateActionImageRequest {
  case_id?: string | null;
  source_image?: SourceImage | null;
  image_edit_target: ImageEditTarget;
  selected_action: SelectedAction;
  recommendation_context?: Record<string, unknown>;
}

export interface GeneratedImage {
  image_id?: string | null;
  url?: string | null;
  base64_data?: string | null;
  mime_type: string;
  prompt_summary?: string | null;
}

export interface GenerateActionImageResponse {
  case_id?: string | null;
  image_purpose: "action_after_example";
  is_actual_evidence: false;
  images: GeneratedImage[];
  safety_notice: string;
  limitations: string[];
}

export interface DbSummary {
  database_path: string;
  row_counts: Record<string, number>;
  pending_cases_by_status: Record<string, number>;
}
