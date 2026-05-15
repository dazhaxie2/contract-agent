"""
中间件 #17: Prometheus指标采集中间件
采集QPS、延迟、错误率、活跃连接数等核心监控指标
"""

import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

try:
    from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

if HAS_PROMETHEUS:
    # 请求计数器
    REQUEST_COUNT = Counter(
        "contract_agent_requests_total",
        "总请求数",
        ["method", "path", "status_code", "tenant_id"],
    )

    # 请求延迟直方图
    REQUEST_LATENCY = Histogram(
        "contract_agent_request_duration_seconds",
        "请求延迟分布",
        ["method", "path"],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
    )

    # 活跃请求数
    ACTIVE_REQUESTS = Gauge(
        "contract_agent_active_requests",
        "当前活跃请求数",
        ["method"],
    )

    # LLM调用指标
    LLM_REQUEST_COUNT = Counter(
        "contract_agent_llm_requests_total",
        "大模型调用次数",
        ["model", "status"],
    )
    LLM_TOKEN_COUNT = Counter(
        "contract_agent_llm_tokens_total",
        "大模型Token消耗",
        ["model", "type"],  # type: input/output
    )
    LLM_LATENCY = Histogram(
        "contract_agent_llm_duration_seconds",
        "大模型调用延迟",
        ["model"],
        buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
    )

    # 检索指标
    RETRIEVAL_COUNT = Counter(
        "contract_agent_retrieval_total",
        "检索请求数",
        ["retrieval_type", "status"],  # vector/keyword/graph
    )
    RETRIEVAL_LATENCY = Histogram(
        "contract_agent_retrieval_duration_seconds",
        "检索延迟",
        ["retrieval_type"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    )

    # Agent执行指标
    AGENT_EXECUTION_COUNT = Counter(
        "contract_agent_agent_executions_total",
        "Agent执行次数",
        ["agent_type", "status"],
    )

    # 缓存命中率
    CACHE_HIT = Counter(
        "contract_agent_cache_hits_total",
        "缓存命中数",
        ["cache_level"],  # L1/L2
    )
    CACHE_MISS = Counter(
        "contract_agent_cache_misses_total",
        "缓存未命中数",
        ["cache_level"],
    )

    # 系统信息
    SYSTEM_INFO = Info(
        "contract_agent_system",
        "系统信息",
    )


class MetricsMiddleware(BaseHTTPMiddleware):
    """Prometheus指标采集"""

    SKIP_PATHS = {"/metrics", "/health", "/ready"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not HAS_PROMETHEUS:
            return await call_next(request)

        # /metrics端点直接返回指标
        if request.url.path == "/metrics":
            return Response(
                content=generate_latest(),
                media_type=CONTENT_TYPE_LATEST,
            )

        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        method = request.method
        # 归一化路径(将UUID替换为{id})
        path = self._normalize_path(request.url.path)
        tenant_id = getattr(request.state, "tenant_id", "unknown")

        ACTIVE_REQUESTS.labels(method=method).inc()
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time

            REQUEST_COUNT.labels(
                method=method, path=path,
                status_code=response.status_code, tenant_id=tenant_id,
            ).inc()
            REQUEST_LATENCY.labels(method=method, path=path).observe(duration)

            return response
        except Exception:
            duration = time.perf_counter() - start_time
            REQUEST_COUNT.labels(
                method=method, path=path, status_code=500, tenant_id=tenant_id,
            ).inc()
            REQUEST_LATENCY.labels(method=method, path=path).observe(duration)
            raise
        finally:
            ACTIVE_REQUESTS.labels(method=method).dec()

    @staticmethod
    def _normalize_path(path: str) -> str:
        import re
        # UUID -> {id}
        return re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '{id}', path
        )
