/** Shared API types for AIREX (mirrors apps/api schemas). */

export interface ApiMeta {
  request_id: string;
}

export interface ApiResponse<T> {
  data: T;
  meta: ApiMeta;
}

export interface ListMeta extends ApiMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface ApiListResponse<T> {
  data: T[];
  meta: ListMeta;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  details: Record<string, unknown>;
  request_id: string;
}

export interface ApiError {
  error: ApiErrorDetail;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserResponse {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
}

export interface OrganizationMembership {
  organization_id: string;
  role: string;
}

export interface MeResponse {
  user: UserResponse;
  memberships: OrganizationMembership[];
}

export interface OrganizationResponse {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface ProjectResponse {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description: string | null;
  application_type: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface HealthResponse {
  status: string;
  service?: string;
  version?: string;
}

// ---- Phase 1 types ----
export interface ProviderResponse {
  id: string;
  organization_id: string;
  provider_type: string;
  name: string;
  masked_key: string | null;
  base_url: string | null;
  status: string;
  last_connection_status: string | null;
  last_checked_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProviderTestResult {
  status: string;
  provider: string;
  model: string | null;
  latency_ms: number | null;
  error: string | null;
}

export interface ModelResponse {
  id: string;
  project_id: string;
  provider_id: string;
  environment_id: string | null;
  name: string;
  model_identifier: string;
  configuration: Record<string, unknown> | null;
  status: string;
  last_health_status: string | null;
  last_checked_at: string | null;
  last_latency_ms: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ModelInvokeResponse {
  id: string;
  provider: string;
  model: string;
  content: string;
  finish_reason: string;
  usage: { input_tokens: number; output_tokens: number; total_tokens: number };
  latency_ms: number;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface EnvironmentResponse {
  id: string;
  project_id: string;
  name: string;
  environment_type: string;
  status: string;
  default_model_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemberResponse {
  membership_id: string;
  user_id: string;
  email: string | null;
  name: string | null;
  role: string;
  joined_at: string;
}

// ---- Phase 2: datasets / versions / test cases ----
export interface DatasetResponse {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  status: string;
  metadata: Record<string, unknown> | null;
  version_count: number;
  latest_version: number | null;
  record_count: number;
  created_at: string;
  updated_at: string;
}

export interface DatasetVersionResponse {
  id: string;
  dataset_id: string;
  version_number: number;
  record_count: number;
  checksum: string;
  format: string;
  status: string;
  created_by: string | null;
  created_at: string;
}

export interface TestCaseResponse {
  id: string;
  dataset_version_id: string;
  row_number: number | null;
  input: string;
  expected_output: string | null;
  context: Record<string, unknown> | null;
  category: string | null;
  difficulty: string | null;
  metadata: Record<string, unknown> | null;
  status: string;
  created_at: string;
}

export interface ValidationIssue {
  row: number | null;
  field: string | null;
  code: string;
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  record_count: number;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}

// ---- Phase 3: evaluation engine ----
export interface EvaluationScoreEntry {
  evaluator: string;
  version: string;
  score: number;
  passed: boolean;
  reason: string;
  metadata: Record<string, unknown>;
}

export interface EvaluationConfiguration {
  evaluators: Array<{
    type: string;
    enabled?: boolean;
    params?: Record<string, unknown>;
    judge_model_id?: string;
    rubric_id?: string;
    threshold?: number;
    reference_required?: boolean;
    weight?: number;
  }>;
  execution?: {
    max_concurrency?: number;
    timeout_seconds?: number;
    stop_on_error?: boolean;
    pass_policy?: "ANY" | "ALL" | "WEIGHTED";
    threshold?: number;
  };
}

export interface EvaluationRunMetrics {
  total_tests: number;
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
  pass_rate: number;
  fail_rate: number;
  error_rate: number;
  average_latency_ms: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  evaluators?: Record<string, unknown>;
  average_judge_score?: number | null;
  judge_pass_rate?: number;
  average_confidence?: number | null;
  judge_criteria?: Record<string, number>;
}

export interface EvaluationResponse {
  id: string;
  project_id: string;
  environment_id: string | null;
  dataset_version_id: string | null;
  model_id: string | null;
  status: string;
  configuration: Record<string, unknown> | null;
  model_snapshot: Record<string, unknown> | null;
  dataset_checksum: string | null;
  evaluator_versions: Record<string, unknown> | null;
  judge_model_id: string | null;
  judge_rubric_id: string | null;
  judge_model_snapshot: Record<string, unknown> | null;
  judge_rubric_snapshot: Record<string, unknown> | null;
  judge_prompt_version: string | null;
  total_tests: number;
  completed_tests: number;
  passed_tests: number;
  failed_tests: number;
  error_tests: number;
  metrics: EvaluationRunMetrics | null;
  created_by: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface EvaluationResultResponse {
  id: string;
  evaluation_run_id: string;
  test_case_id: string | null;
  actual_output: string | null;
  score: EvaluationScoreEntry[] | null;
  status: string;
  failure_type: string | null;
  failure_message: string | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  estimated_cost: number | null;
  explanation: string | null;
  judge_score: number | null;
  judge_confidence: number | null;
  judge_reasoning: string | null;
  judge_criteria_scores: Record<string, number> | null;
  judge_model_snapshot: Record<string, unknown> | null;
  judge_rubric_snapshot: Record<string, unknown> | null;
  judge_prompt_version: string | null;
  combined_score: number | null;
  created_at: string;
}

// ---- Phase 4: rubrics ----
export interface RubricCriterion {
  name: string;
  description: string;
  weight: number;
  min_score?: number;
  max_score?: number;
}

export interface RubricResponse {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  version: number;
  criteria: RubricCriterion[];
  status: string;
  created_by: string | null;
  created_at: string;
  updated_at: string | null;
}

// ---- Phase 5: AI test generation ----
export interface GenerationConfiguration {
  count?: number;
  generation_types?: string[];
  difficulty_distribution?: Record<string, number> | null;
}

export interface GenerationResponse {
  id: string;
  project_id: string;
  environment_id: string | null;
  source_type: string;
  source_reference: Record<string, unknown> | null;
  generation_type: string;
  instruction: string | null;
  count: number;
  configuration: GenerationConfiguration | null;
  status: string;
  generator_model_snapshot: Record<string, unknown> | null;
  prompt_version: string | null;
  source_snapshot: Record<string, unknown> | null;
  candidate_count: number;
  approved_count: number;
  rejected_count: number;
  created_by: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface GeneratedCandidateResponse {
  id: string;
  generation_request_id: string;
  project_id: string;
  input: string;
  expected_output: string | null;
  context: Record<string, unknown> | null;
  category: string | null;
  generation_type: string;
  difficulty: string | null;
  status: string;
  quality_score: number | null;
  fingerprint: string;
  duplicate_of: string | null;
  dataset_version_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface DatasetVersionFromCandidatesResponse {
  dataset_version_id: string;
  dataset_id: string;
  version_number: number;
  record_count: number;
  checksum: string;
}
