"""
中间件 #2: OpenTelemetry分布式链路追踪中间件
集成Jaeger，实现全链路Span采集
"""

import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.middleware.request_id import get_request_id

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace import StatusCode
    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False


def setup_tracing():
    """初始化OpenTelemetry追踪"""
    if not HAS_OTEL or not settings.tracing.enabled:
        return None

    resource = Resource.create({
        "service.name": settings.tracing.service_name,
        "service.version": settings.app_version,
        "deployment.environment": settings.environment,
    })

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.tracing.otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(settings.tracing.service_name)


_tracer = None


def get_tracer():
    global _tracer
    if _tracer is None:
        _tracer = setup_tracing()
    return _tracer


class TracingMiddleware(BaseHTTPMiddleware):
    """OpenTelemetry全链路追踪"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        tracer = get_tracer()
        if not tracer:
            return await call_next(request)

        span_name = f"{request.method} {request.url.path}"
        with tracer.start_as_current_span(span_name) as span:
            request_id = get_request_id()
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.route", request.url.path)
            span.set_attribute("request.id", request_id)
            span.set_attribute("http.client_ip", request.client.host if request.client else "unknown")

            # 记录请求头中的追踪信息
            if "X-Tenant-ID" in request.headers:
                span.set_attribute("tenant.id", request.headers["X-Tenant-ID"])

            start_time = time.perf_counter()
            try:
                response = await call_next(request)
                duration_ms = (time.perf_counter() - start_time) * 1000

                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.duration_ms", duration_ms)

                if response.status_code >= 400:
                    span.set_status(StatusCode.ERROR, f"HTTP {response.status_code}")
                else:
                    span.set_status(StatusCode.OK)

                # 注入Span信息到响应头
                ctx = span.get_span_context()
                response.headers["X-Trace-ID"] = format(ctx.trace_id, "032x")
                response.headers["X-Span-ID"] = format(ctx.span_id, "016x")

                return response
            except Exception as exc:
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                raise
