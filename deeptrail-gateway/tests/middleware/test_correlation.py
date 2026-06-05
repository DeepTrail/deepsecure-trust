"""Tests for correlation ID middleware (E5)."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.middleware.correlation import CorrelationMiddleware


@pytest.fixture
def correlation_app():
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    @app.get("/error")
    async def error_endpoint():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="bad request")

    return app


@pytest.mark.asyncio
async def test_generates_request_id_when_absent(correlation_app):
    transport = ASGITransport(app=correlation_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) >= 32


@pytest.mark.asyncio
async def test_echoes_provided_request_id(correlation_app):
    transport = ASGITransport(app=correlation_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/test", headers={"X-Request-ID": "custom-id-123"}
        )
    assert response.headers["X-Request-ID"] == "custom-id-123"
