"""
中间件 #18: 全局异常处理中间件
统一错误响应格式，异常分类处理，错误链路关联
"""

import traceback
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from loguru import logger

from app.middleware.request_id import get_request_id


class AppException(Exception):
    """应用自定义异常基类"""

    def __init__(self, code: int, message: str, detail: str = "", data: dict | None = None):
        self.code = code
        self.message = message
        self.detail = detail
        self.data = data or {}


class ValidationError(AppException):
    def __init__(self, message: str = "请求参数验证失败", detail: str = ""):
        super().__init__(422, message, detail or "VALIDATION_ERROR")


class NotFoundError(AppException):
    def __init__(self, message: str = "资源不存在", detail: str = ""):
        super().__init__(404, message, detail or "NOT_FOUND")


class ConflictError(AppException):
    def __init__(self, message: str = "资源冲突", detail: str = ""):
        super().__init__(409, message, detail or "CONFLICT")


class LLMError(AppException):
    def __init__(self, message: str = "大模型调用失败", detail: str = ""):
        super().__init__(502, message, detail or "LLM_ERROR")


class RetrievalError(AppException):
    def __init__(self, message: str = "检索服务异常", detail: str = ""):
        super().__init__(502, message, detail or "RETRIEVAL_ERROR")


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """全局异常处理"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except AppException as exc:
            request_id = get_request_id()
            logger.warning(
                f"AppException: {exc.code} {exc.message} | request_id={request_id} | detail={exc.detail}"
            )
            return JSONResponse(
                status_code=exc.code,
                content={
                    "code": exc.code,
                    "message": exc.message,
                    "detail": exc.detail,
                    "data": exc.data,
                    "request_id": request_id,
                },
            )
        except Exception as exc:
            request_id = get_request_id()
            tb = traceback.format_exc()
            logger.error(
                f"Unhandled exception: {type(exc).__name__}: {exc} | "
                f"request_id={request_id} | path={request.url.path}\n{tb}"
            )
            # 生产环境不暴露内部错误详情
            return JSONResponse(
                status_code=500,
                content={
                    "code": 500,
                    "message": "服务内部错误",
                    "detail": "INTERNAL_SERVER_ERROR",
                    "request_id": request_id,
                },
            )
