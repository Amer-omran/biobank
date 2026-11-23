export type LabelName = "SUPPORTED" | "MISLEADING" | "NEEDS_REVIEW";
export const LABELS: LabelName[] = ["SUPPORTED", "MISLEADING", "NEEDS_REVIEW"];
export type Role = "admin" | "reviewer" | "researcher";

export interface User {
  id: number;
  email: string;
  display_name: string;
  reviewer_code: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at?: string | null;
}

export interface ModelSlot {
  language: "ar" | "en";
  base_model: string;
  display_name: { en: string; ar: string };
  state: string;
  active_version: null | {
    id: number;
    version_tag: string;
    is_calibrated: boolean;
    temperature: number | null;
    abstention_threshold: number | null;
    test_macro_f1: number | null;
    test_accuracy: number | null;
  };
}

export interface ModelVersion {
  id: number;
  version_tag: string;
  language: string;
  base_model: string;
  status: string;
  is_calibrated: boolean;
  test_metrics: Record<string, number | null>;
  created_at: string;
}

export interface ModelsResponse {
  runtime_available: boolean;
  slots: ModelSlot[];
  versions: ModelVersion[];
}

export interface Prediction {
  label: number;
  label_name: LabelName;
  display_label: LabelName;
  raw_scores: Record<LabelName, number>;
  calibrated_probabilities: Record<LabelName, number> | null;
  confidence: number | null;
  is_calibrated: boolean;
  abstained: boolean;
  abstention_threshold: number | null;
}

export interface SimilarClaim {
  sample_id: number;
  text: string;
  original_label: string | null;
  fact_check_url: string | null;
  dataset: string;
  source_key: string;
  similarity: number;
}

export interface ReviewItem {
  id: number;
  reviewer_code: string;
  label_name: LabelName;
  agrees_with_model: boolean | null;
  evidence_urls: string[];
  notes: string | null;
  is_adjudication: boolean;
  created_at: string;
}

export interface Analysis {
  id: number;
  created_at: string;
  status: "completed" | "model_not_trained" | "model_unavailable" | "unsupported_language";
  model_state: string | null;
  language: { detected: string; confidence: number; used: string | null; details: Record<string, number> };
  warnings: string[];
  model: { id: number; version_tag: string; base_model: string } | null;
  prediction: Prediction | null;
  explanation: { method?: string; tokens?: { token: string; importance: number }[]; note?: string; target_label?: string };
  similar_claims: SimilarClaim[];
  verification_resources: { name: { en: string; ar: string }; url: string }[];
  health_topic: string | null;
  review_status: string;
  final_label_name: LabelName | null;
  text: string | null;
  redactions: Record<string, number>;
  disclaimer: { en: string; ar: string };
  reviews: ReviewItem[] | null;
}

export interface AnalysisSummary {
  id: number;
  created_at: string;
  status: string;
  language_detected: string;
  language_used: string | null;
  predicted_label_name: LabelName | null;
  confidence: number | null;
  is_calibrated: boolean;
  abstained: boolean;
  review_status: string;
  final_label_name: LabelName | null;
  model_version: string | null;
  text_preview: string | null;
}

export interface PageOf<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface DatasetRow {
  id: number;
  name: string;
  version: string;
  language: string;
  kind: string;
  status: string;
  is_synthetic: boolean;
  source_key: string | null;
  source_name: string | null;
  license_status: string;
  file_name: string | null;
  file_sha256: string | null;
  label_mapping_version: string | null;
  row_count: number;
  imported_count: number;
  rejected_count: number;
  duplicate_count: number;
  eligible: number | null;
  created_at: string;
  notes: string | null;
}

export interface Progress {
  target: number;
  eligible: number;
  eligible_human_reviewed: number;
  imported: number;
  shortfall: number;
}

export interface DatasetsResponse {
  items: DatasetRow[];
  progress: Record<"ar" | "en", Progress>;
}

export interface Source {
  key: string;
  name: string;
  languages: string[];
  official_url: string | null;
  paper_url: string | null;
  access_method: string | null;
  license_name: string | null;
  license_url: string | null;
  license_evidence: string | null;
  license_status: string;
  commercial_use_allowed: boolean | null;
  redistribution_allowed: string | null;
  text_available: boolean;
  citation: string | null;
  training_use_status: string;
  notes: string[];
  label_mapping: { mapping_version?: string; entries?: number; entry_status_counts?: Record<string, number>; error?: string } | null;
}
