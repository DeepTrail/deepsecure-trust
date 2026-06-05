"""
Tests for HTTPS enforcement middleware (WS-D6).
"""

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.responses import JSONResponse

from app.middleware.https_enforcement import HTTPSEnforcementMiddleware


def _make_app(required: bool = True):
    app = FastAPI()

    @app.get("/mcp/test")
    async def test_endpoint():
        return JSONResponse({"ok": True})

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "healthy"})

    return HTTPSEnforcementMiddleware(app, required=required)


class TestHTTPSEnforcement:
    def test_enabled_rejects_http(self):
        client = TestClient(_make_app(required=True))
        resp = client.get("/mcp/test")
        assert resp.status_code == 421
        assert resp.json()["error"] == "https_required"

    def test_enabled_allows_https_via_forwarded_proto(self):
        client = TestClient(_make_app(required=True))
        resp = client.get("/mcp/test", headers={"X-Forwarded-Proto": "https"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_health_bypasses_enforcement(self):
        client = TestClient(_make_app(required=True))
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_disabled_allows_http(self):
        client = TestClient(_make_app(required=False))
        resp = client.get("/mcp/test")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_error_body_has_detail(self):
        client = TestClient(_make_app(required=True))
        resp = client.get("/mcp/test")
        body = resp.json()
        assert "detail" in body
        assert "HTTPS" in body["detail"]
