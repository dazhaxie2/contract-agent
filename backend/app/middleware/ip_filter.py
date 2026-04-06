"""
中间件 #13: IP黑白名单过滤中间件
支持CIDR子网匹配、动态更新
"""

import ipaddress
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings


class IPFilterMiddleware(BaseHTTPMiddleware):
    """IP黑白名单过滤"""

    def __init__(self, app):
        super().__init__(app)
        self._whitelist = self._parse_ip_list(settings.security.ip_whitelist)
        self._blacklist = self._parse_ip_list(settings.security.ip_blacklist)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else None
        if not client_ip:
            return await call_next(request)

        try:
            ip = ipaddress.ip_address(client_ip)
        except ValueError:
            return await call_next(request)

        # 黑名单检查
        if self._blacklist and self._ip_in_list(ip, self._blacklist):
            return JSONResponse(
                status_code=403,
                content={"code": 403, "message": "访问被拒绝", "detail": "IP_BLOCKED"},
            )

        # 白名单检查 (如果配置了白名单，只允许白名单内IP)
        if self._whitelist and not self._ip_in_list(ip, self._whitelist):
            return JSONResponse(
                status_code=403,
                content={"code": 403, "message": "访问被拒绝", "detail": "IP_NOT_ALLOWED"},
            )

        return await call_next(request)

    @staticmethod
    def _parse_ip_list(ip_str: str) -> list:
        if not ip_str:
            return []
        networks = []
        for item in ip_str.split(","):
            item = item.strip()
            if not item:
                continue
            try:
                networks.append(ipaddress.ip_network(item, strict=False))
            except ValueError:
                pass
        return networks

    @staticmethod
    def _ip_in_list(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, networks: list) -> bool:
        return any(ip in network for network in networks)
