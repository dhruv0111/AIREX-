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

// ---- Phase 6: experiments / benchmarking / quality gates ----
export interface VariantCreate {
  model_id?: string | null;
  prompt_version_id?: string | null;
  prompt_content?: string | null;
  dataset_version_id?: string | null;
  configuration?: Record<string, unknown> | null;
}

export interface VariantResponse {
  id: string;
  experiment_id: string;
  variant_type: string;
  model_id: string | null;
  prompt_version_id: string | null;
  dataset_version_id: string | null;
  configuration: Record<string, unknown> | null;
}

export interface QualityGateCreate {
  metric_name: string;
  gate_type?: string;
  operator: string;
  threshold: number;
  severity?: string;
  is_required?: boolean;
}

export interface QualityGateResponse {
  id: string;
  experiment_id: string;
  metric_name: string;
  gate_type: string;
  operator: string;
  threshold: number;
  severity: string;
  is_required: boolean;
}

export interface ExperimentCreate {
  project_id: string;
  name: string;
  description?: string | null;
  experiment_type?: string;
  dataset_version_id?: string | null;
  model_id?: string | null;
  configuration?: Record<string, unknown> | null;
  baseline: VariantCreate;
  candidate: VariantCreate;
  quality_gates?: QualityGateCreate[];
}

export interface ExperimentUpdate {
  name?: string | null;
  description?: string | null;
}

export interface ExperimentResponse {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  dataset_version_id: string | null;
  model_id: string | null;
  configuration: Record<string, unknown> | null;
  status: string;
  experiment_type: string;
  fingerprint: string | null;
  duplicate_of: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  baseline?: VariantResponse | null;
  candidate?: VariantResponse | null;
  quality_gates: QualityGateResponse[];
}

export interface ExperimentRunResponse {
  id: string;
  experiment_id: string;
  status: string;
  baseline_run_id: string | null;
  candidate_run_id: string | null;
  created_by: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export interface ComparisonResponse {
  id: string;
  run_id: string;
  metric_name: string;
  baseline_value: number | null;
  candidate_value: number | null;
  absolute_difference: number | null;
  relative_difference: number | null;
  classification: string;
  statistical_metadata: Record<string, unknown> | null;
}

export interface RegressionResponse {
  id: string;
  comparison_id: string;
  metric_name: string;
  severity: string;
  baseline_value: number | null;
  candidate_value: number | null;
  threshold: number | null;
  explanation: string | null;
}

export interface QualityGateResultResponse {
  id: string;
  run_id: string;
  quality_gate_id: string;
  metric_name: string;
  actual_value: number | null;
  status: string;
}

// ---- Phase 7 types ----
export interface ServiceTokenResponse {
  id: string;
  project_id: string;
  organization_id: string;
  name: string;
  token_prefix: string;
  scopes: string[];
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  last_used_at: string | null;
  raw_token?: string;
}

export interface CIRunResponse {
  id: string;
  project_id: string;
  experiment_id: string | null;
  experiment_run_id: string | null;
  commit_sha: string;
  branch: string;
  repository: string;
  pull_request_number: number | null;
  pull_request_url: string | null;
  ci_provider: string;
  ci_run_id: string;
  ci_job_id: string | null;
  status: string;
  outcome: string | null;
  duration_seconds: number | null;
  completed_at: string | null;
  created_at: string;
}

// ---- Phase 8 Observability types ----
export interface TraceResponse {
  id: string;
  project_id: string;
  organization_id: string;
  trace_id: string;
  environment: string;
  service_name: string | null;
  operation_name: string | null;
  status: string | null;
  duration_ms: number | null;
  error: string | null;
  user_id: string | null;
  session_id: string | null;
  deployment_version: string | null;
  git_commit: string | null;
  quality_score: number | null;
  metadata: Record<string, unknown> | null;
  start_time: string;
  end_time: string | null;
  created_at: string;
}

export interface SpanResponse {
  id: string;
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  name: string;
  span_type: string;
  status: string;
  error: string | null;
  attributes: Record<string, unknown> | null;
  provider: string | null;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  estimated_cost: number | null;
  temperature: number | null;
  max_tokens: number | null;
  error_category: string | null;
  duration_ms: number | null;
  start_time: string;
  end_time: string | null;
}

export interface ModelBreakdown {
  model: string;
  requests: number;
  success_rate: number | null;
  error_rate: number | null;
  tokens: number;
  cost: number;
  latency_avg: number | null;
}

export interface ProviderBreakdown {
  provider: string;
  requests: number;
  success_rate: number | null;
  error_rate: number | null;
  tokens: number;
  cost: number;
  latency_avg: number | null;
}

export interface ObservabilityOverviewResponse {
  total_requests: number;
  success_rate: number | null;
  error_rate: number | null;
  errors: number;
  total_cost: number | null;
  total_tokens: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_p50: number | null;
  latency_p90: number | null;
  latency_p95: number | null;
  latency_p99: number | null;
  latency_avg: number | null;
  latency_max: number | null;
  models: ModelBreakdown[];
  providers: ProviderBreakdown[];
  environments: Array<{
    environment: string;
    requests: number;
    success_rate: number | null;
    error_rate: number | null;
    tokens: number;
    cost: number;
  }>;
}

export interface ObservabilityCostResponse {
  total_cost: number | null;
  cost_per_request: number | null;
  cost_by_model: Array<{ model: string; cost: number }>;
  cost_by_provider: Array<{ provider: string; cost: number }>;
  cost_by_environment: Array<{ environment: string; cost: number }>;
}

export interface ObservabilityLatencyResponse {
  total_requests: number;
  latency_p50: number | null;
  latency_p90: number | null;
  latency_p95: number | null;
  latency_p99: number | null;
  latency_avg: number | null;
  latency_max: number | null;
}

export interface TraceListResponse {
  traces: TraceResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface TraceDetailResponse {
  trace: TraceResponse;
  spans: SpanResponse[];
}

export interface ObservabilitySettingsResponse {
  observability_mode: string;
  retention_days: number | null;
  sample_rate: number;
  capture_errors: boolean;
  capture_quality_signals: boolean;
  error_bypass_sampling: boolean;
}

// ---- Phase 8 Alert types ----
export interface AlertRuleResponse {
  id: string;
  project_id: string;
  name: string;
  metric: string;
  operator: string;
  threshold: number;
  duration_seconds: number;
  cooldown_seconds: number;
  severity: string;
  environment: string | null;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AlertResponse {
  id: string;
  alert_rule_id: string;
  project_id: string;
  status: string;
  severity: string;
  message: string | null;
  observed_value: number | null;
  occurrence_count: number;
  triggered_at: string;
  last_seen_at: string;
  resolved_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  notification_status: string | null;
  notification_error: string | null;
  created_at: string;
}

// ---- Phase 8 Pricing types ----
export interface PricingResponse {
  id: string;
  model_pattern: string;
  provider: string;
  input_price_per_1k: number;
  output_price_per_1k: number;
  currency: string;
  effective_from: string | null;
  effective_until: string | null;
  created_at: string;
  updated_at: string;
}

// ---- Phase 9 Benchmarking types ----
export interface BenchmarkSuiteResponse {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface BenchmarkVersionResponse {
  id: string;
  benchmark_suite_id: string;
  version: number;
  configuration: Record<string, any>;
  configuration_hash: string;
  dataset_version_id: string;
  created_at: string;
}

export interface BenchmarkRunResponse {
  id: string;
  benchmark_suite_id: string;
  benchmark_version_id: string;
  status: string;
  error_message: string | null;
  reliability_score: number | null;
  methodology_version: string;
  configuration_hash: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface BenchmarkResultResponse {
  id: string;
  benchmark_run_id: string;
  evaluation_run_id: string;
  baseline_run_id: string;
  model_id: string;
  reliability_score: number;
}

export interface ReliabilityEvidenceResponse {
  id: string;
  benchmark_run_id: string;
  benchmark_result_id: string | null;
  metric_name: string;
  baseline_value: number;
  candidate_value: number;
  absolute_change: number;
  relative_change: number;
  sample_size: number;
  p_value: number | null;
  effect_size: number | null;
  confidence_interval_low: number | null;
  confidence_interval_high: number | null;
  significance: boolean;
  confidence: string;
}

export interface FailureClusterResponse {
  id: string;
  benchmark_run_id: string;
  benchmark_result_id: string | null;
  failure_type: string;
  error_message_pattern: string;
  cluster_count: number;
  cluster_percentage: number;
  severity: string;
}

export interface RootCauseRecommendationResponse {
  id: string;
  benchmark_run_id: string;
  benchmark_result_id: string | null;
  regression_attribution: string | null;
  root_cause_analysis: string;
  root_cause_confidence: string;
  recommendation: string;
}

export interface BenchmarkRunDetailResponse {
  run: BenchmarkRunResponse;
  results: BenchmarkResultResponse[];
  evidences: ReliabilityEvidenceResponse[];
  clusters: FailureClusterResponse[];
  recommendation: RootCauseRecommendationResponse | null;
}
