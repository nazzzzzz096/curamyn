"""
Middleware to capture request details for audit logging.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Captures request metadata for audit logging.

    Attaches IP address and user agent to request state.
    """

    async def dispatch(self, request: Request, call_next):
        # Extract client IP (handle proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
        else:
            ip_address = request.client.host if request.client else "unknown"

        # Extract user agent
        user_agent = request.headers.get("User-Agent", "unknown")

        # Attach to request state
        request.state.ip_address = ip_address
        request.state.user_agent = user_agent

        response = await call_next(request)
        return response
