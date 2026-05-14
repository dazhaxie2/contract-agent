import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { message } from 'antd';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

const refreshClient = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

let refreshPromise: Promise<string | null> | null = null;

function clearAuthAndRedirect() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('tenant_id');
  window.location.href = '/login';
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) {
    return null;
  }

  if (!refreshPromise) {
    refreshPromise = refreshClient
      .post<LoginResponse>('/auth/refresh', null, { params: { refresh_token: refreshToken } })
      .then((response) => {
        const token = response.data.access_token;
        localStorage.setItem('access_token', token);
        localStorage.setItem('refresh_token', response.data.refresh_token);
        return token;
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    const tenantId = localStorage.getItem('tenant_id');
    if (tenantId) {
      config.headers['X-Tenant-ID'] = tenantId;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

api.interceptors.response.use(
  (response: AxiosResponse) => {
    const payload = response.data as { code?: number; data?: unknown; message?: string } | undefined;
    if (
      payload &&
      typeof payload === 'object' &&
      'code' in payload &&
      'data' in payload &&
      'message' in payload
    ) {
      response.data = payload.data;
    }
    return response;
  },
  async (error: AxiosError<{ detail?: string }>) => {
    if (error.response) {
      const { status, data } = error.response;
      const originalConfig = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
      const requestUrl = originalConfig?.url || '';
      switch (status) {
        case 401:
          if (
            originalConfig &&
            !originalConfig._retry &&
            !requestUrl.includes('/auth/login') &&
            !requestUrl.includes('/auth/refresh')
          ) {
            const newToken = await refreshAccessToken();
            if (newToken) {
              originalConfig._retry = true;
              originalConfig.headers.Authorization = `Bearer ${newToken}`;
              return api(originalConfig);
            }
          }
          clearAuthAndRedirect();
          return Promise.reject(error);
        case 403:
          message.error('Permission denied');
          break;
        case 404:
          message.error('Resource not found');
          break;
        case 422:
          message.error('Invalid request parameters');
          break;
        case 500:
          message.error('Internal server error');
          break;
        default:
          message.error(data?.detail || 'Request failed');
      }
    } else if (error.request) {
      message.error('Network request failed');
    }
    return Promise.reject(error);
  },
);

export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

function normalizePageResult<T>(
  payload: unknown,
  fallbackPage = 1,
  fallbackPageSize = 20,
): PageResult<T> {
  if (Array.isArray(payload)) {
    const items = payload as T[];
    return {
      items,
      total: items.length,
      page: fallbackPage,
      page_size: fallbackPageSize,
      total_pages: 1,
    };
  }

  const maybePage = payload as Partial<PageResult<T>> | undefined;
  const items = Array.isArray(maybePage?.items) ? maybePage.items : [];
  const total = typeof maybePage?.total === 'number' ? maybePage.total : items.length;
  const page = typeof maybePage?.page === 'number' ? maybePage.page : fallbackPage;
  const pageSize = typeof maybePage?.page_size === 'number' ? maybePage.page_size : fallbackPageSize;
  const totalPages =
    typeof maybePage?.total_pages === 'number'
      ? maybePage.total_pages
      : Math.max(1, Math.ceil(total / Math.max(1, pageSize)));

  return {
    items,
    total,
    page,
    page_size: pageSize,
    total_pages: totalPages,
  };
}

// ===================== Model APIs =====================

export interface ModelConfig {
  id: string;
  name: string;
  display_name: string;
  description?: string;
  model_type: 'generation' | 'embedding' | 'reranker' | 'light';
  provider: 'aliyun' | 'openai' | 'local' | 'vllm';
  model_id: string;
  temperature: number;
  top_p: number;
  max_tokens: number;
  frequency_penalty?: number;
  presence_penalty?: number;
  stop_sequences?: string[];
  context_window: number;
  supports_function_calling?: boolean;
  supports_streaming?: boolean;
  timeout_seconds: number;
  max_retries?: number;
  max_concurrent_requests: number;
  requests_per_minute?: number;
  api_endpoint: string;
  extra_headers?: Record<string, unknown>;
  extra_config?: Record<string, unknown>;
  is_active?: boolean;
  is_default?: boolean;
  version?: number;
  avg_latency_ms?: number | null;
  avg_tokens_per_second?: number | null;
  error_rate?: number | null;
  quality_score?: number | null;
  status?: 'active' | 'inactive' | 'error';
  created_at: string;
  updated_at: string;
}

export interface ModelMetrics {
  timestamps: string[];
  latency_p50: number[];
  latency_p99: number[];
  qps: number[];
  error_rate: number[];
  quality_score: number[];
}

export interface DeploymentInfo {
  id: string;
  model_id: string;
  model_name: string;
  deployment_type: 'cloud_api' | 'vllm' | 'triton' | 'onnx' | string;
  endpoint_url?: string;
  status: 'pending' | 'running' | 'stopped' | 'deploying' | 'failed' | 'unknown';
  health_status?: string;
  gpu_type: string;
  gpu_count: number;
  replicas: number;
  ready_replicas: number;
  current_qps: number;
  max_qps: number;
  avg_latency_ms: number;
  p99_latency_ms: number;
  cpu_usage: number | null;
  memory_usage: number | null;
  created_at: string;
  updated_at?: string;
}

export interface ABTest {
  id: string;
  name: string;
  description?: string;
  test_type?: 'model' | 'prompt' | 'retrieval' | 'rerank';
  status: 'draft' | 'running' | 'completed' | 'stopped';
  model_a?: string;
  model_b?: string;
  control_config_id?: string;
  treatment_config_id?: string;
  traffic_split: number;
  primary_metric?: string;
  metrics?: {
    model_a_score: number;
    model_b_score: number;
    model_a_latency: number;
    model_b_latency: number;
    sample_count: number;
  };
  control_metrics?: Record<string, unknown>;
  treatment_metrics?: Record<string, unknown>;
  winner?: string | null;
  created_at: string;
  started_at?: string;
  ended_at?: string;
}

function mapDeployment(item: Record<string, unknown>): DeploymentInfo {
  const status = (item.status as DeploymentInfo['status']) || 'unknown';
  const healthStatus = String(item.health_status || '');
  const replicas = Number(item.replicas || 1);
  const readyReplicas =
    item.ready_replicas === null || item.ready_replicas === undefined
      ? status === 'running' && healthStatus === 'healthy'
        ? replicas
        : 0
      : Number(item.ready_replicas);
  return {
    id: String(item.id || ''),
    model_id: String(item.model_config_id || item.model_id || ''),
    model_name: String(item.deployment_name || item.model_name || ''),
    deployment_type: String(item.deployment_type || 'cloud_api'),
    endpoint_url: item.endpoint_url ? String(item.endpoint_url) : undefined,
    status,
    health_status: healthStatus || undefined,
    gpu_type: String(item.gpu_type || ''),
    gpu_count: Number(item.gpu_count || 0),
    replicas,
    ready_replicas: readyReplicas,
    current_qps: Number(item.current_qps || 0),
    max_qps: Number(item.max_qps || 0),
    avg_latency_ms: Number(item.avg_latency_ms || 0),
    p99_latency_ms: Number(item.p99_latency_ms || 0),
    cpu_usage: item.cpu_usage === null || item.cpu_usage === undefined ? null : Number(item.cpu_usage),
    memory_usage: item.memory_usage === null || item.memory_usage === undefined ? null : Number(item.memory_usage),
    created_at: String(item.created_at || ''),
    updated_at: item.updated_at ? String(item.updated_at) : undefined,
  };
}

export const modelApi = {
  list: async (params?: Record<string, unknown>) => {
    const response = await api.get<PageResult<ModelConfig>>('/models', { params });
    const page = Number(params?.page || 1);
    const pageSize = Number(params?.page_size || 20);
    return normalizePageResult<ModelConfig>(response.data, page, pageSize);
  },
  get: async (id: string) => (await api.get<ModelConfig>(`/models/${id}`)).data,
  create: async (data: Partial<ModelConfig>) => (await api.post<ModelConfig>('/models', data)).data,
  update: async (id: string, data: Partial<ModelConfig>) =>
    (await api.put<ModelConfig>(`/models/${id}`, data)).data,
  delete: async (id: string) => (await api.delete(`/models/${id}`)).data,
  getMetrics: async (id: string, period?: string) =>
    (await api.get<ModelMetrics>(`/models/${id}/metrics`, { params: { period } })).data,
  getDeployments: async () => {
    const response = await api.get<unknown[]>('/models/deployments');
    return Array.isArray(response.data)
      ? response.data.map((item) => mapDeployment(item as Record<string, unknown>))
      : [];
  },
  deploy: async (id: string, config: Record<string, unknown>) => {
    try {
      const response = await api.post('/models/deployments', {
        model_config_id: id,
        deployment_name: String(config.deployment_name || `${id}-deployment`),
        deployment_type: String(config.deployment_type || 'cloud_api'),
        endpoint_url: String(config.endpoint_url || ''),
        replicas: Number(config.replicas || 1),
        gpu_type: String(config.gpu_type || ''),
        gpu_count: Number(config.gpu_count || 0),
        cpu_limit: String(config.cpu_limit || ''),
        memory_limit: String(config.memory_limit || ''),
        deploy_config: config,
      });
      return mapDeployment(response.data as Record<string, unknown>);
    } catch {
      const fallback = await api.post(`/models/${id}/deploy`, config);
      return mapDeployment(fallback.data as Record<string, unknown>);
    }
  },
  undeploy: async (id: string) => (await api.post(`/models/${id}/undeploy`)).data,
  listABTests: async () => (await api.get<ABTest[]>('/models/ab-tests')).data,
  createABTest: async (data: Partial<ABTest>) => (await api.post<ABTest>('/models/ab-tests', data)).data,
  startABTest: async (id: string) => (await api.post(`/models/ab-tests/${id}/start`)).data,
  stopABTest: async (id: string) => (await api.post(`/models/ab-tests/${id}/stop`)).data,
};

// ===================== Prompt APIs =====================

export interface PromptVariable {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'list' | 'json';
  default_value: string;
  description: string;
  required: boolean;
}

export interface PromptTemplate {
  id: string;
  name: string;
  display_name: string;
  description: string;
  category: 'system' | 'task' | 'dynamic' | 'evaluation';
  status: 'draft' | 'published' | 'deprecated';
  tags: string[];
  system_prompt: string;
  user_prompt_template: string;
  variables: PromptVariable[];
  output_format: 'json' | 'markdown' | 'text';
  validation_rules: unknown[];
  current_version: number;
  usage_count: number;
  avg_quality_score?: number | null;
  created_at: string;
  updated_at: string;
}

export interface PromptVersion {
  id?: string;
  template_id?: string;
  version: number;
  system_prompt: string;
  user_prompt_template: string;
  variables: PromptVariable[];
  change_log?: string;
  changelog?: string;
  output_format?: string;
  quality_score?: number | null;
  evaluation_results?: Record<string, unknown>;
  created_at: string;
  author?: string;
}

export interface PromptTestResult {
  trace_id?: string;
  rendered_prompt?: string;
  output: string;
  tokens_used: number;
  latency_ms: number;
  score: number;
  model_used: string;
}

export const promptApi = {
  list: async (params?: Record<string, unknown>) => {
    const response = await api.get<PageResult<PromptTemplate>>('/prompts', { params });
    const page = Number(params?.page || 1);
    const pageSize = Number(params?.page_size || 20);
    return normalizePageResult<PromptTemplate>(response.data, page, pageSize);
  },
  get: async (id: string) => (await api.get<PromptTemplate>(`/prompts/${id}`)).data,
  create: async (data: Partial<PromptTemplate>) => (await api.post<PromptTemplate>('/prompts', data)).data,
  update: async (id: string, data: Partial<PromptTemplate>) =>
    (await api.put<PromptTemplate>(`/prompts/${id}`, data)).data,
  delete: async (id: string) => (await api.delete(`/prompts/${id}`)).data,
  getVersions: async (id: string) => (await api.get<PromptVersion[]>(`/prompts/${id}/versions`)).data,
  test: async (id: string, variables: Record<string, unknown>) => {
    try {
      const res = await api.post('/prompts/test', { template_id: id, variables });
      const payload = res.data as Record<string, unknown>;
      const usage = (payload.usage as Record<string, unknown>) || {};
      return {
        trace_id: String(payload.trace_id || ''),
        rendered_prompt: String(payload.rendered_prompt || ''),
        output: String(payload.output || ''),
        tokens_used: Number(usage.total_tokens || 0),
        latency_ms: Number(payload.latency_ms || 0),
        score: Number(payload.quality_score || 0),
        model_used: String(payload.model || ''),
      } satisfies PromptTestResult;
    } catch {
      return (await api.post<PromptTestResult>(`/prompts/${id}/test`, { variables })).data;
    }
  },
};

// ===================== Auth APIs =====================

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const authApi = {
  login: async (username: string, password: string) =>
    (await api.post<LoginResponse>('/auth/login', { username, password })).data,
};

// ===================== Document APIs =====================

export interface DocumentItem {
  id: string;
  tenant_id: string;
  title: string;
  doc_type: string;
  file_name: string;
  file_size: number;
  file_hash: string;
  mime_type: string;
  issuing_authority?: string;
  effective_date?: string;
  expiry_date?: string;
  applicable_industry: string[];
  applicable_region: string[];
  version?: string;
  keywords: string[];
  metadata: Record<string, unknown>;
  status: string;
  is_effective: boolean;
  chunk_count: number;
  process_error?: string;
  created_at: string;
  updated_at: string;
}

export interface IngestionJob {
  job_id: string;
  tenant_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed' | string;
  stage: string;
  file_name: string;
  doc_id?: string;
  doc_type: string;
  title?: string;
  error_message?: string;
  retry_count: number;
  dead_letter: boolean;
  events?: { stage: string; status: string; detail: Record<string, unknown>; created_at: string }[];
  created_at: string;
  started_at?: string;
  completed_at?: string;
  updated_at: string;
}

export interface DocumentChunk {
  id: string;
  doc_id: string;
  content: string;
  summary?: string;
  chunk_type: string;
  hierarchy_path?: string;
  hierarchy_level: number;
  chunk_index: number;
  token_count: number;
  legal_priority: number;
  entity_tags: string[];
  vector_status: string;
  graph_status: string;
  created_at: string;
}

export const documentApi = {
  upload: async (file: File, params: { title?: string; doc_type?: string; sync?: boolean }) => {
    const form = new FormData();
    form.append('file', file);
    form.append('title', params.title || file.name);
    form.append('doc_type', params.doc_type || 'contract');
    form.append('sync', String(params.sync ?? false));
    return (
      await api.post<IngestionJob>('/documents/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    ).data;
  },
  list: async (params?: Record<string, unknown>) => {
    const response = await api.get<PageResult<DocumentItem>>('/documents', { params });
    return normalizePageResult<DocumentItem>(
      response.data,
      Number(params?.page || 1),
      Number(params?.page_size || 20),
    );
  },
  get: async (id: string) => (await api.get<DocumentItem>(`/documents/${id}`)).data,
  getChunks: async (id: string, full = false) =>
    (await api.get<DocumentChunk[]>(`/documents/${id}/chunks`, { params: { full } })).data,
  getJob: async (jobId: string) => (await api.get<IngestionJob>(`/documents/jobs/${jobId}`)).data,
  delete: async (id: string) => (await api.delete(`/documents/${id}`)).data,
};

// ===================== Review / Agent APIs =====================

export interface ReviewRiskItem {
  severity: 'high' | 'medium' | 'low' | 'uncertain' | string;
  clause_excerpt: string;
  issue: string;
  legal_basis: string;
  recommendation: string;
  confidence: number;
  references?: {
    ref_id?: number;
    citation_id?: string;
    citation_code?: string;
    doc_title?: string;
    hierarchy?: string;
    chunk_id?: string;
  }[];
}

export interface ReviewReport {
  overall_risk: 'high' | 'medium' | 'low' | 'uncertain' | string;
  summary: string;
  risk_items: ReviewRiskItem[];
  generated_from?: string;
}

export interface PlanStep {
  step_id: string;
  title: string;
  description: string;
  domain: string;
  tool: string;
  action: string;
  mutates_state: boolean;
  status: string;
}

export interface AgentPlan {
  decision_id: string;
  intent_summary: string;
  steps: PlanStep[];
  requires_confirmation: boolean;
  estimated_changes: string[];
  context: Record<string, unknown>;
  created_at: string;
  expires_at: string;
}

export interface ToolResult {
  step_number?: number;
  span_id?: string;
  parent_span_id?: string;
  tool_name?: string;
  status?: string;
  latency_ms?: number;
  tokens_used?: number;
  observation?: string;
}

export interface DecisionRecord {
  decision_id: string;
  intent_summary: string;
  plan?: AgentPlan;
  execution_id?: string;
  trace_id?: string;
  status?: string;
}

export interface AgentExecution {
  execution_id?: string;
  id?: string;
  trace_id: string;
  status: string;
  result: string;
  references: Record<string, unknown>[];
  review_report?: ReviewReport;
  usage: Record<string, unknown>;
  latency_ms: number;
  task_type?: string;
  created_at?: string;
  completed_at?: string;
  decision_id?: string;
  plan?: AgentPlan | Record<string, unknown>;
  tool_results?: ToolResult[];
  user_feedback?: number;
  regression_case_id?: string;
}

export interface SessionInfo {
  id: string;
  tenant_id: string;
  user_id: string;
  title: string;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CitationDetail {
  id: string;
  citation_code: string;
  tenant_id: string;
  session_id?: string;
  execution_id?: string;
  document_id?: string;
  chunk_id?: string;
  source_type: string;
  title?: string;
  excerpt: string;
  locator?: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export const sessionApi = {
  create: async (title: string, metadata: Record<string, unknown> = {}) =>
    (await api.post<SessionInfo>('/sessions', { title, metadata })).data,
};

export const agentApi = {
  plan: async (payload: {
    query: string;
    session_id: string;
    tenant_id: string;
    task_type?: string;
    context?: Record<string, unknown>;
    filters?: Record<string, unknown>;
  }) => (await api.post<AgentPlan>('/agents/plan', payload)).data,
  executeDecision: async (
    decisionId: string,
    payload: {
      confirmed: boolean;
      comment?: string;
    },
  ) => (await api.post<AgentExecution>(`/agents/decisions/${decisionId}/execute`, payload)).data,
  execute: async (payload: {
    query: string;
    task_type: string;
    session_id: string;
    tenant_id: string;
    filters?: Record<string, unknown>;
  }) => (await api.post<AgentExecution>('/agents/execute', payload)).data,
  listExecutions: async (params?: Record<string, unknown>) => {
    const response = await api.get<PageResult<AgentExecution>>('/agents/executions', { params });
    return normalizePageResult<AgentExecution>(
      response.data,
      Number(params?.page || 1),
      Number(params?.page_size || 20),
    );
  },
  getExecution: async (id: string) => (await api.get<AgentExecution>(`/agents/executions/${id}`)).data,
  exportExecution: async (id: string, format: 'markdown' | 'docx' | 'pdf') =>
    (
      await api.get<Blob>(`/agents/executions/${id}/export`, {
        params: { format },
        responseType: 'blob',
      })
    ).data,
  submitFeedback: async (id: string, score: number, comment = '') =>
    (await api.post(`/agents/executions/${id}/feedback`, null, { params: { score, comment } })).data,
};

export const citationApi = {
  get: async (id: string) => (await api.get<CitationDetail>(`/citations/${id}`)).data,
};

// ===================== Dashboard APIs =====================

export interface SystemMetrics {
  qps: { timestamp: string; value: number }[];
  latency_p50: { timestamp: string; value: number }[];
  latency_p99: { timestamp: string; value: number }[];
  error_rate: { timestamp: string; value: number }[];
  active_connections: number;
  services: ServiceHealth[];
  contract_workbench?: {
    plan_success_rate: number;
    planned_executions: number;
    tool_failure_rate: number;
    tool_calls_total: number;
    citation_coverage_rate: number;
    risk_items_total: number;
    low_confidence_rate: number;
    user_feedback_avg: number;
    user_feedback_count: number;
    contract_review_failure_rate: number;
    contract_review_avg_latency_ms: number;
    regression_cases_total: number;
  };
}

export interface ServiceHealth {
  name: string;
  status: 'healthy' | 'degraded' | 'down';
  uptime: number;
  last_check: string;
}

export interface TraceStep {
  step_id: string;
  type: 'thought' | 'action' | 'observation';
  content: string;
  duration_ms: number;
  tokens: number;
  metadata?: Record<string, unknown>;
}

export interface AgentTrace {
  trace_id: string;
  status: 'success' | 'error' | 'timeout';
  total_duration_ms: number;
  total_tokens: number;
  steps: TraceStep[];
  created_at: string;
}

export interface RetrievalMetrics {
  recall_rate: number;
  precision_rate: number;
  channels: {
    name: string;
    top_k_hit_rate: number[];
    k_values: number[];
  }[];
  rerank_comparison: {
    before: number;
    after: number;
  };
}

function mapSystemOverview(payload: Record<string, unknown>): SystemMetrics {
  const timestamp = new Date().toISOString();
  const latency = (payload.latency as Record<string, unknown>) || {};
  const errorRate = (payload.error_rate as Record<string, unknown>) || {};
  const servicesMap = (payload.services as Record<string, Record<string, unknown>>) || {};
  const workbench = (payload.contract_workbench as Record<string, unknown>) || {};
  return {
    qps: [{ timestamp, value: Number((payload.qps as Record<string, unknown>)?.current || 0) }],
    latency_p50: [{ timestamp, value: Number(latency.p50_ms || 0) }],
    latency_p99: [{ timestamp, value: Number(latency.p99_ms || 0) }],
    error_rate: [{ timestamp, value: Number(errorRate.rate_5xx || 0) }],
    active_connections: Number(payload.active_connections || 0),
    services: Object.entries(servicesMap).map(([name, svc]) => ({
      name,
      status: (svc.status as ServiceHealth['status']) || 'healthy',
      uptime: Number(svc.uptime || 1),
      last_check: timestamp,
    })),
    contract_workbench: {
      plan_success_rate: Number(workbench.plan_success_rate || 0),
      planned_executions: Number(workbench.planned_executions || 0),
      tool_failure_rate: Number(workbench.tool_failure_rate || 0),
      tool_calls_total: Number(workbench.tool_calls_total || 0),
      citation_coverage_rate: Number(workbench.citation_coverage_rate || 0),
      risk_items_total: Number(workbench.risk_items_total || 0),
      low_confidence_rate: Number(workbench.low_confidence_rate || 0),
      user_feedback_avg: Number(workbench.user_feedback_avg || 0),
      user_feedback_count: Number(workbench.user_feedback_count || 0),
      contract_review_failure_rate: Number(workbench.contract_review_failure_rate || 0),
      contract_review_avg_latency_ms: Number(workbench.contract_review_avg_latency_ms || 0),
      regression_cases_total: Number(workbench.regression_cases_total || 0),
    },
  };
}

function mapAgentTrace(payload: Record<string, unknown>): AgentTrace {
  const steps = Array.isArray(payload.steps) ? payload.steps : [];
  return {
    trace_id: String(payload.trace_id || ''),
    status: (payload.status as AgentTrace['status']) || 'success',
    total_duration_ms: Number(payload.total_duration_ms || payload.latency_ms || 0),
    total_tokens: Number(payload.total_tokens || (payload.usage as Record<string, unknown>)?.total_tokens || 0),
    steps: steps.map((step) => {
      const data = step as Record<string, unknown>;
      return {
        step_id: String(data.step_id || data.id || data.step_number || ''),
        type: (data.type as TraceStep['type']) || (data.step_type as TraceStep['type']) || 'observation',
        content: String(data.content || ''),
        duration_ms: Number(data.duration_ms || data.latency_ms || 0),
        tokens: Number(data.tokens || data.tokens_used || 0),
        metadata: (data.metadata as Record<string, unknown>) || undefined,
      };
    }),
    created_at: String(payload.created_at || ''),
  };
}

function mapRetrievalMetrics(payload: Record<string, unknown>): RetrievalMetrics {
  if (typeof payload.recall_rate === 'number') {
    return payload as unknown as RetrievalMetrics;
  }
  const recall = (payload.recall as Record<string, unknown>) || {};
  const precision = (payload.precision as Record<string, unknown>) || {};
  const rerank = (payload.rerank_improvement as Record<string, unknown>) || {};
  const contribution = (payload.channel_contribution as Record<string, unknown>) || {};
  return {
    recall_rate: Number(recall.top_10 || 0),
    precision_rate: Number(precision.top_10 || 0),
    channels: [
      {
        name: 'vector',
        k_values: [1, 5, 10],
        top_k_hit_rate: [
          Number(recall.top_1 || 0),
          Number(recall.top_5 || 0),
          Number(contribution.vector || recall.top_10 || 0),
        ],
      },
      {
        name: 'keyword',
        k_values: [10],
        top_k_hit_rate: [Number(contribution.keyword || precision.top_10 || 0)],
      },
      {
        name: 'graph',
        k_values: [10],
        top_k_hit_rate: [Number(contribution.graph || 0)],
      },
    ],
    rerank_comparison: {
      before: Number(rerank.before_mrr || 0),
      after: Number(rerank.after_mrr || 0),
    },
  };
}

export const dashboardApi = {
  getSystemMetrics: async () => {
    try {
      const response = await api.get('/system/metrics/overview');
      return mapSystemOverview(response.data as Record<string, unknown>);
    } catch {
      const fallback = await api.get<SystemMetrics>('/dashboard/system');
      return fallback.data;
    }
  },
  getTrace: async (traceId: string) => {
    try {
      const response = await api.get(`/agents/trace/${traceId}`);
      return mapAgentTrace(response.data as Record<string, unknown>);
    } catch {
      const fallback = await api.get<AgentTrace>(`/dashboard/traces/${traceId}`);
      return fallback.data;
    }
  },
  getRetrievalMetrics: async () => {
    try {
      const response = await api.get('/system/metrics/retrieval');
      return mapRetrievalMetrics(response.data as Record<string, unknown>);
    } catch {
      const fallback = await api.get<RetrievalMetrics>('/dashboard/retrieval');
      return fallback.data;
    }
  },
};

// ===================== Evaluation APIs =====================

export interface EvaluationScores {
  relevance: number;
  factuality: number;
  completeness: number;
  clarity: number;
}

export const evaluationApi = {
  scoreExecution: async (executionId: string) =>
    (await api.post<EvaluationScores & { execution_id: string }>(`/evaluation/score/${executionId}`)).data,
  batchScore: async (limit = 50) =>
    (await api.post<{ scored: number; errors: number; total: number }>('/evaluation/batch', null, { params: { limit } }))
      .data,
  getMetrics: async () =>
    (await api.get<{ total_scored: number; avg_relevance: number; avg_factuality: number }>('/evaluation/metrics')).data,
};

export default api;
