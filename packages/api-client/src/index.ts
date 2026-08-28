/**
 * Typed API client for AIREX (spec §64).
 * Handles authentication headers, standard envelopes, and error parsing.
 * Frontend components must not construct arbitrary HTTP requests.
 */
import type {
  ApiError,
  ApiListResponse,
  ApiResponse,
  DatasetResponse,
  DatasetVersionFromCandidatesResponse,
  DatasetVersionResponse,
  EnvironmentResponse,
  EvaluationConfiguration,
  EvaluationResponse,
  EvaluationResultResponse,
  GeneratedCandidateResponse,
  GenerationResponse,
  HealthResponse,
  MemberResponse,
  MeResponse,
  ModelInvokeResponse,
  ModelResponse,
  OrganizationResponse,
  ProjectResponse,
  ProviderResponse,
  ProviderTestResult,
  RubricResponse,
  TestCaseResponse,
  TokenResponse,
  VariantCreate,
  VariantResponse,
  QualityGateCreate,
  QualityGateResponse,
  ExperimentCreate,
  ExperimentUpdate,
  ExperimentResponse,
  ExperimentRunResponse,
  ComparisonResponse,
  RegressionResponse,
  QualityGateResultResponse,
  ServiceTokenResponse,
  CIRunResponse,
  ObservabilityOverviewResponse,
  ObservabilityCostResponse,
  ObservabilityLatencyResponse,
  TraceListResponse,
  TraceDetailResponse,
  ObservabilitySettingsResponse,
  AlertRuleResponse,
  AlertResponse,
  PricingResponse,
  BenchmarkSuiteResponse,
  BenchmarkVersionResponse,
  BenchmarkRunResponse,
  BenchmarkResultResponse,
  ReliabilityEvidenceResponse,
  FailureClusterResponse,
  RootCauseRecommendationResponse,
  BenchmarkRunDetailResponse,
} from "@airex/shared-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "airex.access_token";
const ORG_KEY = "airex.organization_id";

export class ApiClientError extends Error {
  code: string;
  requestId: string | null;
  status: number;

  constructor(message: string, code: string, status: number, requestId: string | null) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export function setOrganizationId(orgId: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ORG_KEY, orgId);
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; auth?: boolean; org?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, auth = true, org = false } = options;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  if (org) {
    const orgId = typeof window !== "undefined" ? window.localStorage.getItem(ORG_KEY) : null;
    if (orgId) headers["X-Organization-Id"] = orgId;
  }

  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const err = payload as ApiError | null;
    throw new ApiClientError(
      err?.error?.message ?? `Request failed (${response.status})`,
      err?.error?.code ?? "HTTP_ERROR",
      response.status,
      err?.error?.request_id ?? null,
    );
  }
  return payload as T;
}

/** POST multipart/form-data (used for dataset file upload, Phase 2). */
async function requestMultipart<T>(path: string, formData: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const orgId = typeof window !== "undefined" ? window.localStorage.getItem(ORG_KEY) : null;
  if (orgId) headers["X-Organization-Id"] = orgId;
  const response = await fetch(`${API_URL}${path}`, { method: "POST", headers, body: formData });
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }
  if (!response.ok) {
    const err = payload as ApiError | null;
    throw new ApiClientError(
      err?.error?.message ?? `Request failed (${response.status})`,
      err?.error?.code ?? "HTTP_ERROR",
      response.status,
      err?.error?.request_id ?? null,
    );
  }
  return payload as T;
}

/** Fetch a binary response (used for dataset export, Phase 2). */
async function requestBlob(path: string): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const orgId = typeof window !== "undefined" ? window.localStorage.getItem(ORG_KEY) : null;
  if (orgId) headers["X-Organization-Id"] = orgId;
  const response = await fetch(`${API_URL}${path}`, { headers });
  if (!response.ok) {
    const text = await response.text();
    let err: ApiError | null = null;
    try {
      err = JSON.parse(text) as ApiError;
    } catch {
      err = null;
    }
    throw new ApiClientError(
      err?.error?.message ?? `Request failed (${response.status})`,
      err?.error?.code ?? "HTTP_ERROR",
      response.status,
      err?.error?.request_id ?? null,
    );
  }
  return response;
}

export const api = {
  // Auth
  register: (name: string, email: string, password: string) =>
    request<ApiResponse<TokenResponse>>("/api/v1/auth/register", {
      method: "POST",
      body: { name, email, password },
      auth: false,
    }),
  login: (email: string, password: string) =>
    request<ApiResponse<TokenResponse>>("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    }),
  me: () => request<ApiResponse<MeResponse>>("/api/v1/auth/me"),
  logout: () => request<void>("/api/v1/auth/logout", { method: "POST" }),

  // Health
  health: () => request<HealthResponse>("/health", { auth: false }),

  // Organizations
  listOrganizations: () => request<ApiListResponse<OrganizationResponse>>("/api/v1/organizations"),

  // Projects
  listProjects: () => request<ApiListResponse<ProjectResponse>>("/api/v1/projects", { org: true }),
  getProject: (id: string) => request<ApiResponse<ProjectResponse>>(`/api/v1/projects/${id}`, { org: true }),
  createProject: (payload: { name: string; slug?: string; description?: string; application_type?: string }) =>
    request<ApiResponse<ProjectResponse>>("/api/v1/projects", {
      method: "POST",
      body: payload,
      org: true,
    }),

  // Members
  listMembers: (organizationId: string) =>
    request<ApiListResponse<MemberResponse>>(`/api/v1/organizations/${organizationId}/members`, { org: true }),
  addMember: (organizationId: string, payload: { email: string; role: string }) =>
    request<ApiResponse<MemberResponse>>(`/api/v1/organizations/${organizationId}/members`, {
      method: "POST",
      body: payload,
      org: true,
    }),
  changeMemberRole: (organizationId: string, membershipId: string, role: string) =>
    request<ApiResponse<MemberResponse>>(`/api/v1/organizations/${organizationId}/members/${membershipId}`, {
      method: "PATCH",
      body: { role },
      org: true,
    }),
  removeMember: (organizationId: string, membershipId: string) =>
    request<void>(`/api/v1/organizations/${organizationId}/members/${membershipId}`, {
      method: "DELETE",
      org: true,
    }),

  // Providers
  listProviders: (params?: { provider_type?: string; status?: string }) =>
    request<ApiListResponse<ProviderResponse>>(`/api/v1/providers?${new URLSearchParams(params ?? {}).toString()}`, {
      org: true,
    }),
  createProvider: (payload: {
    provider_type: string;
    name: string;
    api_key?: string;
    base_url?: string;
    configuration?: Record<string, unknown>;
  }) =>
    request<ApiResponse<ProviderResponse>>("/api/v1/providers", { method: "POST", body: payload, org: true }),
  testProvider: (id: string) =>
    request<ApiResponse<ProviderTestResult>>(`/api/v1/providers/${id}/test`, { method: "POST", org: true }),
  rotateProvider: (id: string, apiKey: string) =>
    request<ApiResponse<ProviderResponse>>(`/api/v1/providers/${id}/rotate`, {
      method: "POST",
      body: { api_key: apiKey },
      org: true,
    }),
  deleteProvider: (id: string) =>
    request<void>(`/api/v1/providers/${id}`, { method: "DELETE", org: true }),

  // Models
  listModels: (projectId: string) =>
    request<ApiListResponse<ModelResponse>>(`/api/v1/projects/${projectId}/models`, { org: true }),
  createModel: (
    projectId: string,
    payload: { name: string; model_identifier: string; provider_id: string; environment_id?: string; configuration?: Record<string, unknown> },
  ) =>
    request<ApiResponse<ModelResponse>>(`/api/v1/projects/${projectId}/models`, {
      method: "POST",
      body: payload,
      org: true,
    }),
  testModel: (id: string) =>
    request<ApiResponse<ProviderTestResult>>(`/api/v1/models/${id}/test`, { method: "POST", org: true }),
  invokeModel: (id: string, payload: { messages: Array<{ role: string; content: string }>; temperature?: number; max_tokens?: number }) =>
    request<ApiResponse<ModelInvokeResponse>>(`/api/v1/models/${id}/invoke`, { method: "POST", body: payload, org: true }),
  getModelHealth: (id: string) =>
    request<ApiResponse<{ status: string; provider: string }>>(`/api/v1/models/${id}/health`, { org: true }),
  deleteModel: (id: string) => request<void>(`/api/v1/models/${id}`, { method: "DELETE", org: true }),

  // Environments
  listEnvironments: (projectId: string) =>
    request<ApiListResponse<EnvironmentResponse>>(`/api/v1/projects/${projectId}/environments`, { org: true }),
  createEnvironment: (projectId: string, payload: { name: string; environment_type: string }) =>
    request<ApiResponse<EnvironmentResponse>>(`/api/v1/projects/${projectId}/environments`, {
      method: "POST",
      body: payload,
      org: true,
    }),
  deleteEnvironment: (id: string) =>
    request<void>(`/api/v1/environments/${id}`, { method: "DELETE", org: true }),

  // Datasets (Phase 2)
  listDatasets: (projectId: string, params?: { page?: number; page_size?: number }) =>
    request<ApiListResponse<DatasetResponse>>(
      `/api/v1/projects/${projectId}/datasets?${new URLSearchParams((params ?? {}) as Record<string, string>).toString()}`,
      { org: true },
    ),
  createDataset: (projectId: string, payload: { name: string; description?: string; metadata?: Record<string, unknown> }) =>
    request<ApiResponse<DatasetResponse>>(`/api/v1/projects/${projectId}/datasets`, {
      method: "POST",
      body: payload,
      org: true,
    }),
  getDataset: (datasetId: string) =>
    request<ApiResponse<DatasetResponse>>(`/api/v1/datasets/${datasetId}`, { org: true }),
  updateDataset: (datasetId: string, payload: { name?: string; description?: string; metadata?: Record<string, unknown>; status?: string }) =>
    request<ApiResponse<DatasetResponse>>(`/api/v1/datasets/${datasetId}`, {
      method: "PATCH",
      body: payload,
      org: true,
    }),
  archiveDataset: (datasetId: string) =>
    request<void>(`/api/v1/datasets/${datasetId}`, { method: "DELETE", org: true }),

  // Versions
  createDatasetVersion: (datasetId: string, file: File, format?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (format) form.append("format", format);
    return requestMultipart<ApiResponse<DatasetVersionResponse>>(
      `/api/v1/datasets/${datasetId}/versions`,
      form,
    );
  },
  listDatasetVersions: (datasetId: string, params?: { page?: number; page_size?: number }) =>
    request<ApiListResponse<DatasetVersionResponse>>(
      `/api/v1/datasets/${datasetId}/versions?${new URLSearchParams((params ?? {}) as Record<string, string>).toString()}`,
      { org: true },
    ),
  getDatasetVersion: (versionId: string) =>
    request<ApiResponse<DatasetVersionResponse>>(`/api/v1/dataset-versions/${versionId}`, { org: true }),
  exportDatasetVersion: (versionId: string, format = "jsonl") =>
    requestBlob(`/api/v1/dataset-versions/${versionId}/export?format=${format}`),

  // Test cases
  listTestCases: (
    versionId: string,
    params?: { page?: number; page_size?: number; search?: string; category?: string; status?: string; difficulty?: string },
  ) =>
    request<ApiListResponse<TestCaseResponse>>(
      `/api/v1/dataset-versions/${versionId}/test-cases?${new URLSearchParams(
        Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== "")) as Record<string, string>,
      ).toString()}`,
      { org: true },
    ),
  getTestCase: (id: string) => request<ApiResponse<TestCaseResponse>>(`/api/v1/test-cases/${id}`, { org: true }),
  approveTestCase: (id: string) =>
    request<ApiResponse<TestCaseResponse>>(`/api/v1/test-cases/${id}/approve`, { method: "POST", org: true }),
  rejectTestCase: (id: string) =>
    request<ApiResponse<TestCaseResponse>>(`/api/v1/test-cases/${id}/reject`, { method: "POST", org: true }),

  // Rubrics (Phase 4)
  listRubrics: (projectId: string, params?: { page?: number; page_size?: number; status?: string }) =>
    request<ApiListResponse<RubricResponse>>(
      `/api/v1/rubrics?${new URLSearchParams(
        Object.fromEntries(
          Object.entries({ ...params, project_id: projectId }).filter(([, v]) => v !== undefined && v !== ""),
        ) as Record<string, string>,
      ).toString()}`,
      { org: true },
    ),
  createRubric: (payload: {
    project_id: string;
    name: string;
    description?: string;
    criteria: Array<{ name: string; description: string; weight: number; min_score?: number; max_score?: number }>;
  }) => request<ApiResponse<RubricResponse>>("/api/v1/rubrics", { method: "POST", body: payload, org: true }),
  getRubric: (rubricId: string) =>
    request<ApiResponse<RubricResponse>>(`/api/v1/rubrics/${rubricId}`, { org: true }),
  updateRubric: (rubricId: string, payload: { name?: string; description?: string; criteria?: Array<{ name: string; description: string; weight: number }> }) =>
    request<ApiResponse<RubricResponse>>(`/api/v1/rubrics/${rubricId}`, { method: "PATCH", body: payload, org: true }),
  archiveRubric: (rubricId: string) =>
    request<void>(`/api/v1/rubrics/${rubricId}`, { method: "DELETE", org: true }),

  // Evaluations (Phase 3)
  createEvaluation: (payload: {
    project_id: string;
    environment_id?: string;
    dataset_version_id: string;
    model_id: string;
    configuration: EvaluationConfiguration;
  }) => request<ApiResponse<EvaluationResponse>>("/api/v1/evaluations", { method: "POST", body: payload, org: true }),
  runEvaluation: (evaluationId: string) =>
    request<ApiResponse<EvaluationResponse>>(`/api/v1/evaluations/${evaluationId}/run`, { method: "POST", org: true }),
  listEvaluations: (
    projectId: string,
    params?: {
      page?: number;
      page_size?: number;
      status?: string;
      model_id?: string;
      dataset_version_id?: string;
    },
  ) =>
    request<ApiListResponse<EvaluationResponse>>(
      `/api/v1/evaluations?${new URLSearchParams(
        Object.fromEntries(
          Object.entries({ ...params, project_id: projectId }).filter(([, v]) => v !== undefined && v !== ""),
        ) as Record<string, string>,
      ).toString()}`,
      { org: true },
    ),
  getEvaluation: (evaluationId: string) =>
    request<ApiResponse<EvaluationResponse>>(`/api/v1/evaluations/${evaluationId}`, { org: true }),
  listEvaluationResults: (
    evaluationId: string,
    params?: { page?: number; page_size?: number; status?: string; failure_type?: string },
  ) =>
    request<ApiListResponse<EvaluationResultResponse>>(
      `/api/v1/evaluations/${evaluationId}/results?${new URLSearchParams(
        Object.fromEntries(
          Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== ""),
        ) as Record<string, string>,
      ).toString()}`,
      { org: true },
    ),
  cancelEvaluation: (evaluationId: string) =>
    request<ApiResponse<EvaluationResponse>>(`/api/v1/evaluations/${evaluationId}/cancel`, {
      method: "POST",
      org: true,
    }),

  // Generations (Phase 5)
  listGenerations: (
    projectId: string,
    params?: {
      page?: number;
      page_size?: number;
      status?: string;
      generation_type?: string;
      source_type?: string;
    },
  ) =>
    request<ApiListResponse<GenerationResponse>>(
      `/api/v1/generations?${new URLSearchParams(
        Object.fromEntries(
          Object.entries({ ...params, project_id: projectId }).filter(([, v]) => v !== undefined && v !== ""),
        ) as Record<string, string>,
      ).toString()}`,
      { org: true },
    ),
  createGeneration: (payload: {
    project_id: string;
    environment_id?: string;
    source_type: string;
    source_reference?: Record<string, unknown>;
    generation_type: string;
    instruction?: string;
    count: number;
    configuration: {
      generation_types?: string[];
      difficulty_distribution?: Record<string, number>;
    };
    generator_model_id: string;
  }) => request<ApiResponse<GenerationResponse>>("/api/v1/generations", { method: "POST", body: payload, org: true }),
  getGeneration: (generationId: string) =>
    request<ApiResponse<GenerationResponse>>(`/api/v1/generations/${generationId}`, { org: true }),
  cancelGeneration: (generationId: string) =>
    request<ApiResponse<GenerationResponse>>(`/api/v1/generations/${generationId}/cancel`, { method: "POST", org: true }),
  listCandidates: (
    generationId: string,
    params?: {
      page?: number;
      page_size?: number;
      status?: string;
      category?: string;
      difficulty?: string;
      generation_type?: string;
    },
  ) =>
    request<ApiListResponse<GeneratedCandidateResponse>>(
      `/api/v1/generations/${generationId}/candidates?${new URLSearchParams(
        Object.fromEntries(
          Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== ""),
        ) as Record<string, string>,
      ).toString()}`,
      { org: true },
    ),
  getCandidate: (candidateId: string) =>
    request<ApiResponse<GeneratedCandidateResponse>>(`/api/v1/candidates/${candidateId}`, { org: true }),
  reviewCandidate: (candidateId: string, action: "approve" | "reject") =>
    request<ApiResponse<GeneratedCandidateResponse>>(`/api/v1/candidates/${candidateId}/review`, {
      method: "POST",
      body: { action },
      org: true,
    }),
  createDatasetVersionFromCandidates: (generationId: string, payload: { dataset_id: string; candidate_ids: string[] }) =>
    request<ApiResponse<DatasetVersionFromCandidatesResponse>>(
      `/api/v1/generations/${generationId}/dataset-version`,
      { method: "POST", body: payload, org: true },
    ),

  // Experiments (Phase 6)
  listExperiments: (projectId: string) =>
    request<ApiListResponse<ExperimentResponse>>(`/api/v1/projects/${projectId}/experiments`, { org: true }),
  createExperiment: (projectId: string, payload: ExperimentCreate) =>
    request<ApiResponse<ExperimentResponse>>(`/api/v1/projects/${projectId}/experiments`, {
      method: "POST",
      body: payload,
      org: true,
    }),
  getExperiment: (id: string) =>
    request<ApiResponse<ExperimentResponse>>(`/api/v1/experiments/${id}`, { org: true }),
  updateExperiment: (id: string, payload: ExperimentUpdate) =>
    request<ApiResponse<ExperimentResponse>>(`/api/v1/experiments/${id}`, {
      method: "PATCH",
      body: payload,
      org: true,
    }),
  deleteExperiment: (id: string) =>
    request<void>(`/api/v1/experiments/${id}`, { method: "DELETE", org: true }),
  runExperiment: (id: string) =>
    request<ApiResponse<ExperimentRunResponse>>(`/api/v1/experiments/${id}/run`, { method: "POST", org: true }),
  cancelExperimentRun: (id: string) =>
    request<ApiResponse<ExperimentRunResponse>>(`/api/v1/experiments/${id}/cancel`, { method: "POST", org: true }),
  listExperimentRuns: (id: string) =>
    request<ApiListResponse<ExperimentRunResponse>>(`/api/v1/experiments/${id}/runs`, { org: true }),
  getExperimentResults: (id: string) =>
    request<ApiListResponse<ComparisonResponse>>(`/api/v1/experiments/${id}/results`, { org: true }),
  getExperimentRegressions: (id: string) =>
    request<ApiListResponse<RegressionResponse>>(`/api/v1/experiments/${id}/regressions`, { org: true }),
  getExperimentQualityGates: (id: string) =>
    request<ApiListResponse<QualityGateResultResponse>>(`/api/v1/experiments/${id}/quality-gates`, { org: true }),

  // CI/CD (Phase 7)
  listServiceTokens: (projectId: string) =>
    request<ApiListResponse<ServiceTokenResponse>>(`/api/v1/projects/${projectId}/service-tokens`, { org: true }),
  createServiceToken: (projectId: string, payload: { name: string; scopes: string[]; expires_in_days?: number }) =>
    request<ApiResponse<ServiceTokenResponse>>(`/api/v1/projects/${projectId}/service-tokens`, {
      method: "POST",
      body: payload,
      org: true,
    }),
  revokeServiceToken: (tokenId: string) =>
    request<ApiResponse<{ status: string }>>(`/api/v1/service-tokens/${tokenId}`, { method: "DELETE", org: true }),
  rotateServiceToken: (tokenId: string) =>
    request<ApiResponse<ServiceTokenResponse>>(`/api/v1/service-tokens/${tokenId}/rotate`, { method: "POST", org: true }),
  listCIRuns: (projectId: string, params?: { page?: number; page_size?: number }) =>
    request<ApiListResponse<CIRunResponse>>(
      `/api/v1/projects/${projectId}/ci-runs?${new URLSearchParams(
        Object.entries(params ?? {})
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)])
      ).toString()}`,
      { org: true }
    ),

  // Observability (Phase 8)
  getObservabilityOverview: (
    projectId: string,
    params?: { environment?: string; start_time?: string; end_time?: string },
  ) =>
    request<ObservabilityOverviewResponse>(
      `/api/v1/projects/${projectId}/observability/overview?${new URLSearchParams(
        Object.fromEntries(
          Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== ""),
        ) as Record<string, string>,
      ).toString()}`,
      { org: true },
    ),
  getObservabilityModels: (
    projectId: string,
    params?: { environment?: string; start_time?: string; end_time?: string },
  ) =>
    request<{ total_requests: number; models: Array<{ model: string; requests: number; success_rate: number | null; error_rate: number | null; tokens: number; cost: number; latency_avg: number | null }> }>(
      `/api/v1/projects/${projectId}/observability/models?${new URLSearchParams(
        Object.fromEntries(
          Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== ""),
        ) as Record<string, string>,
      ).toString()}`,
      { org: true },
    ),
  getObservabilityProviders: (
    projectId: string,
    params?: { environment?: string; start_time?: string; end_time?: string },
  ) =>
    request<{ total_requests: number; providers: Array<{ provider: string; requests: number; success_rate: number | null; error_rate: number | null; tokens: number; cost: number; latency_avg: number | null }> }>(
      `/api/v1/projects/${projectId}/observability/providers?${new URLSearchParams(
        Object.fromEntries(
          Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== ""),
        ) as Record<string, string>,
      ).toString()}`,
      { org: true },
    ),
  getObservabilityCost: (
    projectId: string,
    params?: { environment?: string; start_time?: string; end_time?: string },
  ) =>
    request<ObservabilityCostResponse>(
      `/api/v1/projects/${projectId}/observability/cost?${new URLSearchParams(
        Object.fromEntries(
          Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== ""),
        ) as Record<string, string>,
      ).toString()}`,
      { org: true },
    ),
  getObservabilityLatency: (
    projectId: string,
    params?: { environment?: string; start_time?: string; end_time?: string },
  ) =>
    request<ObservabilityLatencyResponse>(
      `/api/v1/projects/${projectId}/observability/latency?${new URLSearchParams(
        Object.fromEntries(
          Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== ""),
        ) as Record<string, string>,
      ).toString()}`,
      { org: true },
    ),
  listTraces: (
    projectId: string,
    params?: {
      environment?: string;
      status?: string;
      model?: string;
      provider?: string;
      trace_id?: string;
      error_category?: string;
      start_time?: string;
      end_time?: string;
      limit?: number;
      offset?: number;
    },
  ) =>
    request<TraceListResponse>(
      `/api/v1/projects/${projectId}/observability/traces?${new URLSearchParams(
        Object.fromEntries(
          Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== ""),
        ) as Record<string, string>,
      ).toString()}`,
      { org: true },
    ),
  getTraceDetail: (traceId: string) =>
    request<TraceDetailResponse>(`/api/v1/observability/traces/${traceId}`, { org: true }),
  getObservabilitySettings: (projectId: string) =>
    request<ObservabilitySettingsResponse>(`/api/v1/projects/${projectId}/observability/settings`, { org: true }),
  updateObservabilitySettings: (
    projectId: string,
    payload: Partial<ObservabilitySettingsResponse>,
  ) =>
    request<ObservabilitySettingsResponse>(`/api/v1/projects/${projectId}/observability/settings`, {
      method: "PUT",
      body: payload,
      org: true,
    }),

  // Alerts (Phase 8)
  listAlerts: (projectId: string, params?: { status?: string }) =>
    request<AlertResponse[]>(
      `/api/v1/projects/${projectId}/alerts?${new URLSearchParams(
        Object.fromEntries(
          Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== ""),
        ) as Record<string, string>,
      ).toString()}`,
      { org: true },
    ),
  getAlert: (projectId: string, alertId: string) =>
    request<AlertResponse>(`/api/v1/projects/${projectId}/alerts/${alertId}`, { org: true }),
  acknowledgeAlert: (projectId: string, alertId: string) =>
    request<AlertResponse>(`/api/v1/projects/${projectId}/alerts/${alertId}/ack`, {
      method: "POST",
      org: true,
    }),
  listAlertRules: (projectId: string) =>
    request<AlertRuleResponse[]>(`/api/v1/projects/${projectId}/alert-rules`, { org: true }),
  createAlertRule: (
    projectId: string,
    payload: {
      name: string;
      metric: string;
      operator: string;
      threshold: number;
      duration_seconds?: number;
      cooldown_seconds?: number;
      severity?: string;
      environment?: string;
      is_enabled?: boolean;
    },
  ) =>
    request<AlertRuleResponse>(`/api/v1/projects/${projectId}/alert-rules`, {
      method: "POST",
      body: payload,
      org: true,
    }),
  updateAlertRule: (ruleId: string, payload: Partial<AlertRuleResponse>) =>
    request<AlertRuleResponse>(`/api/v1/alert-rules/${ruleId}`, {
      method: "PATCH",
      body: payload,
      org: true,
    }),
  deleteAlertRule: (ruleId: string) =>
    request<void>(`/api/v1/alert-rules/${ruleId}`, { method: "DELETE", org: true }),

  // Pricing (Phase 8)
  listPricing: () => request<PricingResponse[]>("/api/v1/pricing", { org: true }),
  createPricing: (payload: {
    model_pattern: string;
    provider: string;
    input_price_per_1k: number;
    output_price_per_1k: number;
    currency?: string;
    effective_from?: string;
    effective_until?: string;
  }) => request<PricingResponse>("/api/v1/pricing", { method: "POST", body: payload, org: true }),
  updatePricing: (pricingId: string, payload: Partial<PricingResponse>) =>
    request<PricingResponse>(`/api/v1/pricing/${pricingId}`, { method: "PATCH", body: payload, org: true }),
  deletePricing: (pricingId: string) =>
    request<void>(`/api/v1/pricing/${pricingId}`, { method: "DELETE", org: true }),

  // Benchmarks (Phase 9)
  createBenchmarkSuite: (
    projectId: string,
    payload: { name: string; description?: string; configuration: Record<string, any> },
  ) =>
    request<ApiResponse<BenchmarkSuiteResponse>>(`/api/v1/projects/${projectId}/benchmarks`, {
      method: "POST",
      body: payload,
      org: true,
    }),
  listBenchmarkSuites: (projectId: string) =>
    request<ApiResponse<BenchmarkSuiteResponse[]>>(`/api/v1/projects/${projectId}/benchmarks`, { org: true }),
  getBenchmarkSuite: (suiteId: string) =>
    request<ApiResponse<BenchmarkSuiteResponse>>(`/api/v1/benchmarks/${suiteId}`, { org: true }),
  createBenchmarkVersion: (suiteId: string, payload: { configuration: Record<string, any> }) =>
    request<ApiResponse<BenchmarkVersionResponse>>(`/api/v1/benchmarks/${suiteId}/versions`, {
      method: "POST",
      body: payload,
      org: true,
    }),
  listBenchmarkVersions: (suiteId: string) =>
    request<ApiResponse<BenchmarkVersionResponse[]>>(`/api/v1/benchmarks/${suiteId}/versions`, { org: true }),
  triggerBenchmarkRun: (suiteId: string, payload: { benchmark_version_id?: string }) =>
    request<ApiResponse<BenchmarkRunResponse>>(`/api/v1/benchmarks/${suiteId}/runs`, {
      method: "POST",
      body: payload,
      org: true,
    }),
  listBenchmarkRuns: (suiteId: string) =>
    request<ApiResponse<BenchmarkRunResponse[]>>(`/api/v1/benchmarks/${suiteId}/runs`, { org: true }),
  getBenchmarkRunDetail: (runId: string) =>
    request<ApiResponse<BenchmarkRunDetailResponse>>(`/api/v1/benchmarks/runs/${runId}`, { org: true }),
};
