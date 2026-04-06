"""
中间件 #8: 熔断器中间件
基于pybreaker实现服务熔断与降级，防止级联故障
"""

import time
from collections import defaultdict
from enum import Enum
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings


class CircuitState(Enum):
    CLOSED = "closed"       # 正常
    OPEN = "open"           # 熔断
    HALF_OPEN = "half_open" # 半开(试探)


class ServiceCircuitBreaker:
    """服务级熔断器"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._states: dict[str, CircuitState] = defaultdict(lambda: CircuitState.CLOSED)
        self._failure_counts: dict[str, int] = defaultdict(int)
        self._last_failure_time: dict[str, float] = defaultdict(float)
        self._success_count_half_open: dict[str, int] = defaultdict(int)

    def can_execute(self, service: str) -> bool:
        state = self._states[service]

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            if time.time() - self._last_failure_time[service] >= self.recovery_timeout:
                self._states[service] = CircuitState.HALF_OPEN
                self._success_count_half_open[service] = 0
                return True
            return False

        if state == CircuitState.HALF_OPEN:
            return True

        return False

    def record_success(self, service: str):
        state = self._states[service]
        if state == CircuitState.HALF_OPEN:
            self._success_count_half_open[service] += 1
            if self._success_count_half_open[service] >= 3:
                self._states[service] = CircuitState.CLOSED
                self._failure_counts[service] = 0
        elif state == CircuitState.CLOSED:
            self._failure_counts[service] = max(0, self._failure_counts[service] - 1)

    def record_failure(self, service: str):
        self._failure_counts[service] += 1
        self._last_failure_time[service] = time.time()

        if self._states[service] == CircuitState.HALF_OPEN:
            self._states[service] = CircuitState.OPEN
        elif self._failure_counts[service] >= self.failure_threshold:
            self._states[service] = CircuitState.OPEN

    def get_state(self, service: str) -> dict:
        return {
            "service": service,
            "state": self._states[service].value,
            "failure_count": self._failure_counts[service],
            "threshold": self.failure_threshold,
        }


_breaker = ServiceCircuitBreaker(
    failure_threshold=settings.circuit_breaker.failure_threshold,
    recovery_timeout=settings.circuit_breaker.recovery_timeout,
)


def get_circuit_breaker() -> ServiceCircuitBreaker:
    return _breaker


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """服务熔断与降级"""

    # 上游服务路由映射
    SERVICE_MAP = {
        "/api/v1/agents": "llm_service",
        "/api/v1/documents/process": "document_service",
        "/api/v1/retrieval": "retrieval_service",
        "/api/v1/graph": "graph_service",
    }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.circuit_breaker.enabled:
            return await call_next(request)

        service = self._identify_service(request.url.path)
        if not service:
            return await call_next(request)

        if not _breaker.can_execute(service):
            state = _breaker.get_state(service)
            return JSONResponse(
                status_code=503,
                content={
                    "code": 503,
                    "message": f"服务 {service} 暂时不可用，熔断保护中",
                    "detail": "CIRCUIT_BREAKER_OPEN",
                    "circuit_state": state,
                    "retry_after": settings.circuit_breaker.recovery_timeout,
                },
                headers={"Retry-After": str(settings.circuit_breaker.recovery_timeout)},
            )

        try:
            response = await call_next(request)
            if response.status_code < 500:
                _breaker.record_success(service)
            else:
                _breaker.record_failure(service)
            return response
        except Exception:
            _breaker.record_failure(service)
            raise

    def _identify_service(self, path: str) -> str | None:
        for prefix, service in self.SERVICE_MAP.items():
            if path.startswith(prefix):
                return service
        return None
