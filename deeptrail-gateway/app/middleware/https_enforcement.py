"""
HTTPS enforcement middleware.

Rejects non-TLS requests in production by inspecting the scheme and
``X-Forwarded-Proto`` header (for reverse-proxy deployments).

Disabled by default in development (``HTTPS_REQUIRED=false``).
"""

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

HTTPS_REQUIRED = os.environ.get("HTTPS_REQUIRED", "false").lower() == "true"
BYPASS_PATHS = {"/health", "/ready", "/metrics"}


class HTTPSEnforcementMiddleware(BaseHTTPMiddleware):
    """Rejects non-TLS requests when ``HTTPS_REQUIRED`` is set."""

    def __init__(self, app: ASGIApp, *, required: bool = HTTPS_REQUIRED):
        super().__init__(app)
        self._required = required
        if self._required:
            logger.info("HTTPS enforcement ENABLED")
        else:
            logger.info("HTTPS enforcement DISABLED (development mode)")

    async def dispatch(self, request: Request, call_next):
        if not self._required:
            return await call_next(request)

        if request.url.path in BYPASS_PATHS:
            return await call_next(request)

        proto = (
            request.headers.get("X-Forwarded-Proto", "")
            or request.url.scheme
        )
        if proto != "https":
            logger.warning(
                "Rejected non-TLS request: %s %s (proto=%s)",
                request.method,
                request.url.path,
                proto,
            )
            return JSONResponse(
                status_code=421,
                content={
                    "error": "https_required",
                    "detail": "This endpoint requires HTTPS",
                },
            )

        return await call_next(request)
