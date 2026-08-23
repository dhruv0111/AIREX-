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
};
