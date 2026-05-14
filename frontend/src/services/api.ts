import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { message } from 'antd';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

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
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response) {
      const { status, data } = error.response;
      switch (status) {
        case 401:
          localStorage.removeItem('access_token');
          window.location.href = '/login';
          break;
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
  provider: 'aliyun' | 'openai' | 'local' | 'vllm';
  model_id: string;
  temperature: number;
  top_p: number;
  max_tokens: number;
  context_window: number;
  timeout_seconds: number;
  max_concurrent_requests: number;
  api_endpoint: string;
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
  status: 'running' | 'stopped' | 'deploying' | 'error';
  gpu_type: string;
  gpu_count: number;
  replicas: number;
  ready_replicas: number;
  cpu_usage: number;
  memory_usage: number;
  created_at: string;
}

export interface ABTest {
  id: string;
  name: string;
  status: 'draft' | 'running' | 'completed' | 'stopped';
  model_a: string;
  model_b: string;
  traffic_split: number;
  metrics: {
    model_a_score: number;
    model_b_score: number;
    model_a_latency: number;
    model_b_latency: number;
    sample_count: number;
  };
  created_at: string;
}

function mapDeployment(item: Record<string, unknown>): DeploymentInfo {
  return {
    id: String(item.id || ''),
    model_id: String(item.model_config_id || item.model_id || ''),
    model_name: String(item.deployment_name || item.model_name || ''),
    status: (item.status as DeploymentInfo['status']) || 'running',
    gpu_type: String(item.gpu_type || ''),
    gpu_count: Number(item.gpu_count || 0),
    replicas: Number(item.replicas || 1),
    ready_replicas: Number(item.ready_replicas || item.replicas || 1),
    cpu_usage: Number(item.cpu_usage || 0),
    memory_usage: Number(item.memory_usage || 0),
    created_at: String(item.created_at || ''),
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
  created_at: string;
  author?: string;
}

export interface PromptTestResult {
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

export default api;
