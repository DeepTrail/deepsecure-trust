"""Correlation ID middleware — X-Request-ID generation and propagation."""

from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Ensure every request has a correlation ID for tracing."""

    def __init__(self, app: ASGIApp, *, header_name: str = REQUEST_ID_HEADER):
        super().__init__(app)
        self._header = header_name

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(self._header) or str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.correlation_id = request_id

        response = await call_next(request)
        response.headers[self._header] = request_id
        return response


def get_request_id(request: Request) -> str:
    """Return correlation ID from request state, generating if absent."""
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())
