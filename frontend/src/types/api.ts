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
}

export interface NormalizedInput {
  accident_type: string;
  work_type: string;
  hazard_major_category: string;
  hazard_middle_category: string;
  environment_factors: string[];
  human_factors: string[];
  equipment?: string | null;
  confidence: number;
  ai_recommendations: Record<string, string>;
}

export interface AnalyzeMeta {
  submitted_by: string;
  occurred_at?: string | null;
  occurred_location?: string | null;
}

export interface AnalyzeRequest {
  raw_input?: string | null;
  normalized: NormalizedInput;
  meta: AnalyzeMeta;
}

export interface PreventionItem {
  prevention_id: string;
  major_category: string;
  middle_category: string;
  content: string;
  expected_action_result: Record<string, string>;
  priority: number;
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
}

export interface AnalyzeResponse {
  meta: Record<string, string>;
  input_summary: Record<string, string | null>;
  prevention_list: PreventionItem[];
  similar_cases: SimilarCase[];
  risk_score: RiskScore;
}

export interface DbSummary {
  database_path: string;
  row_counts: Record<string, number>;
  pending_cases_by_status: Record<string, number>;
}
