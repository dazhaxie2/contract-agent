"""
合同合规Agent系统 - 20+中间件层
覆盖认证、限流、熔断、追踪、日志、安全、缓存、租户隔离、脱敏等全链路中间件
"""

from app.middleware.request_id import RequestIDMiddleware
from app.middleware.tracing import TracingMiddleware
from app.middleware.logging_mw import RequestLoggingMiddleware
from app.middleware.auth import AuthenticationMiddleware
from app.middleware.rbac import RBACMiddleware
from app.middleware.tenant_isolation import TenantIsolationMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.circuit_breaker import CircuitBreakerMiddleware
from app.middleware.timeout import TimeoutMiddleware
from app.middleware.cors_mw import CORSConfigMiddleware
from app.middleware.compression import CompressionMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.ip_filter import IPFilterMiddleware
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.cache_control import CacheControlMiddleware
from app.middleware.data_masking import DataMaskingMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.api_version import APIVersionMiddleware
from app.middleware.request_validation import RequestValidationMiddleware
from app.middleware.audit_trail import AuditTrailMiddleware
from app.middleware.retry_mw import RetryMiddleware
from app.middleware.response_transform import ResponseTransformMiddleware

__all__ = [
    "RequestIDMiddleware",
    "TracingMiddleware",
    "RequestLoggingMiddleware",
    "AuthenticationMiddleware",
    "RBACMiddleware",
    "TenantIsolationMiddleware",
    "RateLimitMiddleware",
    "CircuitBreakerMiddleware",
    "TimeoutMiddleware",
    "CORSConfigMiddleware",
    "CompressionMiddleware",
    "SecurityHeadersMiddleware",
    "IPFilterMiddleware",
    "IdempotencyMiddleware",
    "CacheControlMiddleware",
    "DataMaskingMiddleware",
    "MetricsMiddleware",
    "ErrorHandlerMiddleware",
    "APIVersionMiddleware",
    "RequestValidationMiddleware",
    "AuditTrailMiddleware",
    "RetryMiddleware",
    "ResponseTransformMiddleware",
]


def register_middleware(app):
    """按优先级注册所有中间件 (后添加的先执行)"""
    # 23. 响应转换 (最后处理响应)
    app.add_middleware(ResponseTransformMiddleware)
    # 22. 压缩 (响应压缩)
    app.add_middleware(CompressionMiddleware)
    # 21. 缓存控制
    app.add_middleware(CacheControlMiddleware)
    # 20. 数据脱敏
    app.add_middleware(DataMaskingMiddleware)
    # 19. 审计日志
    app.add_middleware(AuditTrailMiddleware)
    # 18. 重试
    app.add_middleware(RetryMiddleware)
    # 17. 错误处理
    app.add_middleware(ErrorHandlerMiddleware)
    # 16. 请求验证
    app.add_middleware(RequestValidationMiddleware)
    # 15. 幂等性
    app.add_middleware(IdempotencyMiddleware)
    # 14. 超时控制
    app.add_middleware(TimeoutMiddleware)
    # 13. 熔断器
    app.add_middleware(CircuitBreakerMiddleware)
    # 12. 限流
    app.add_middleware(RateLimitMiddleware)
    # 11. RBAC权限
    app.add_middleware(RBACMiddleware)
    # 10. 认证
    app.add_middleware(AuthenticationMiddleware)
    # 9. 租户隔离
    app.add_middleware(TenantIsolationMiddleware)
    # 8. IP过滤
    app.add_middleware(IPFilterMiddleware)
    # 7. 安全头
    app.add_middleware(SecurityHeadersMiddleware)
    # 6. API版本
    app.add_middleware(APIVersionMiddleware)
    # 5. 指标采集
    app.add_middleware(MetricsMiddleware)
    # 4. 请求日志
    app.add_middleware(RequestLoggingMiddleware)
    # 3. 链路追踪
    app.add_middleware(TracingMiddleware)
    # 2. CORS
    app.add_middleware(CORSConfigMiddleware)
    # 1. 请求ID (最先执行)
    app.add_middleware(RequestIDMiddleware)
