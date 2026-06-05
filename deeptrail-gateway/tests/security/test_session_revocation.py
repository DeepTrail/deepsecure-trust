"""Tests for gateway session revocation checks (WS-D5)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.security.session_revocation import (
    SessionRevocationChecker,
    configure_session_revocation_checker,
    reset_session_revocation_checker,
)


@pytest.fixture(autouse=True)
def _reset_checker():
    reset_session_revocation_checker()
    yield
    reset_session_revocation_checker()


class TestSessionRevocationChecker:
    @pytest.mark.asyncio
    async def test_no_session_id_not_revoked(self):
        checker = SessionRevocationChecker(redis_url=None)
        assert await checker.is_revoked(None) is False

    @pytest.mark.asyncio
    async def test_revoked_session_detected(self):
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock()
        mock_client.exists = AsyncMock(return_value=1)

        checker = SessionRevocationChecker(redis_url="redis://localhost:6379")
        checker._client = mock_client

        assert await checker.is_revoked("asess-revoked") is True
        mock_client.exists.assert_awaited_once_with(
            "revoked_agent_session:asess-revoked"
        )

    @pytest.mark.asyncio
    async def test_active_session_not_revoked(self):
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock()
        mock_client.exists = AsyncMock(return_value=0)

        checker = SessionRevocationChecker(redis_url="redis://localhost:6379")
        checker._client = mock_client

        assert await checker.is_revoked("asess-active") is False

    @pytest.mark.asyncio
    async def test_redis_error_fails_closed(self):
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock()
        mock_client.exists = AsyncMock(side_effect=RuntimeError("redis down"))

        checker = SessionRevocationChecker(redis_url="redis://localhost:6379")
        checker._client = mock_client

        assert await checker.is_revoked("asess-x") is True


class TestJwtMiddlewareRevocationIntegration:
    def test_revoked_session_returns_401(self):
        from datetime import datetime, timedelta, timezone

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from jose import jwt as jose_jwt

        from app.middleware.jwt_validation import JWTValidationMiddleware

        app = FastAPI()

        @app.get("/mcp/test")
        async def test_endpoint():
            return {"ok": True}

        middleware = JWTValidationMiddleware(app)
        client = TestClient(middleware)

        now = datetime.now(timezone.utc)
        payload = {
            "sub": "agent-revoke-test",
            "owner": "test@example.com",
            "delegated_permissions": ["notion:pages:search"],
            "delegation_id": "del-revoke",
            "session_id": "asess-revoked-1",
            "iss": "deeptrail-control",
            "aud": "deeptrail-gateway",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        }
        token = jose_jwt.encode(payload, "your-secret-key-for-jwt", algorithm="HS256")

        configure_session_revocation_checker(redis_url="redis://localhost:6379")
        checker = MagicMock()
        checker.is_revoked = AsyncMock(return_value=True)

        with patch(
            "app.security.session_revocation.get_session_revocation_checker",
            return_value=checker,
        ):
            resp = client.get(
                "/mcp/test",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 401
        assert resp.json()["error"] == "session_revoked"
