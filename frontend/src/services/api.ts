import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
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
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response) {
      const { status, data } = error.response;
      switch (status) {
        case 401:
          localStorage.removeItem('access_token');
          window.location.href = '/login';
          break;
        case 403:
          message.error('权限不足');
          break;
        case 404:
          message.error('请求的资源不存在');
          break;
        case 422:
          message.error('请求参数错误');
          break;
        case 500:
          message.error('服务器内部错误');
          break;
        default:
          message.error(data?.detail || '请求失败');
      }
    } else if (error.request) {
      message.error('网络连接失败，请检查网络');
    }
    return Promise.reject(error);
  },
);

// ===================== 模型配置 API =====================

export interface ModelConfig {
  id: string;
  name: string;
  provider: 'aliyun' | 'openai' | 'local' | 'vllm';
  model_id: string;
  temperature: number;
  top_p: number;
  max_tokens: number;
  context_window: number;
  timeout: number;
  max_concurrency: number;
  api_endpoint: string;
  api_key_ref?: string;
  status: 'active' | 'inactive' | 'error';
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

export const modelApi = {
  list: (params?: Record<string, unknown>) => api.get<ModelConfig[]>('/models', { params }),
  get: (id: string) => api.get<ModelConfig>(`/models/${id}`),
  create: (data: Partial<ModelConfig>) => api.post<ModelConfig>('/models', data),
  update: (id: string, data: Partial<ModelConfig>) => api.put<ModelConfig>(`/models/${id}`, data),
  delete: (id: string) => api.delete(`/models/${id}`),
  getMetrics: (id: string, period?: string) =>
    api.get<ModelMetrics>(`/models/${id}/metrics`, { params: { period } }),
  getDeployments: () => api.get<DeploymentInfo[]>('/models/deployments'),
  deploy: (id: string, config: Record<string, unknown>) =>
    api.post(`/models/${id}/deploy`, config),
  undeploy: (id: string) => api.post(`/models/${id}/undeploy`),
  listABTests: () => api.get<ABTest[]>('/models/ab-tests'),
  createABTest: (data: Partial<ABTest>) => api.post<ABTest>('/models/ab-tests', data),
  stopABTest: (id: string) => api.post(`/models/ab-tests/${id}/stop`),
};

// ===================== 提示词 API =====================

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
  category: 'system' | 'task' | 'dynamic' | 'evaluation';
  status: 'draft' | 'published' | 'deprecated';
  tags: string[];
  system_prompt: string;
  user_prompt_template: string;
  variables: PromptVariable[];
  output_format: 'json' | 'markdown' | 'text';
  validation_rules: string[];
  version: number;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

export interface PromptVersion {
  version: number;
  system_prompt: string;
  user_prompt_template: string;
  variables: PromptVariable[];
  change_log: string;
  created_at: string;
  author: string;
}

export interface PromptTestResult {
  output: string;
  tokens_used: number;
  latency_ms: number;
  score: number;
  model_used: string;
}

export const promptApi = {
  list: (params?: Record<string, unknown>) => api.get<PromptTemplate[]>('/prompts', { params }),
  get: (id: string) => api.get<PromptTemplate>(`/prompts/${id}`),
  create: (data: Partial<PromptTemplate>) => api.post<PromptTemplate>('/prompts', data),
  update: (id: string, data: Partial<PromptTemplate>) =>
    api.put<PromptTemplate>(`/prompts/${id}`, data),
  delete: (id: string) => api.delete(`/prompts/${id}`),
  getVersions: (id: string) => api.get<PromptVersion[]>(`/prompts/${id}/versions`),
  test: (id: string, variables: Record<string, unknown>) =>
    api.post<PromptTestResult>(`/prompts/${id}/test`, { variables }),
};

// ===================== 监控 API =====================

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

export const dashboardApi = {
  getSystemMetrics: (period?: string) =>
    api.get<SystemMetrics>('/dashboard/system', { params: { period } }),
  getTrace: (traceId: string) => api.get<AgentTrace>(`/dashboard/traces/${traceId}`),
  getRetrievalMetrics: () => api.get<RetrievalMetrics>('/dashboard/retrieval'),
};

export default api;
