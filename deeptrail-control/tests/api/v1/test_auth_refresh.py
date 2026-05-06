"""Tests for POST /api/v1/auth/refresh endpoint."""
import time
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from fastapi.testclient import TestClient

from app.core.config import settings


def _create_user_jwt(sub: str = "admin@deepsecure.io", exp_hours: float = 8) -> str:
    """Create a test JWT matching the login endpoint format."""
    return pyjwt.encode(
        {
            "sub": sub,
            "session_id": "usess-test-123",
            "organization_id": "org-deepsecure-001",
            "exp": datetime.now(timezone.utc) + timedelta(hours=exp_hours),
            "iat": datetime.now(timezone.utc),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def _create_expired_jwt(sub: str = "admin@deepsecure.io", expired_seconds_ago: int = 60) -> str:
    """Create a JWT that expired N seconds ago."""
    now = datetime.now(timezone.utc)
    return pyjwt.encode(
        {
            "sub": sub,
            "session_id": "usess-test-expired",
            "organization_id": "org-deepsecure-001",
            "exp": now - timedelta(seconds=expired_seconds_ago),
            "iat": now - timedelta(hours=8),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def test_refresh_valid_token(client: TestClient) -> None:
    """Valid JWT should produce a new token with fresh TTL."""
    token = _create_user_jwt(exp_hours=1)
    response = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["expires_in"] == 28800

    claims = pyjwt.decode(data["token"], settings.SECRET_KEY, algorithms=["HS256"])
    assert claims["sub"] == "admin@deepsecure.io"
    # New token should have 8h TTL (longer than the 1h original)
    assert claims["exp"] > time.time() + 7 * 3600


def test_refresh_recently_expired_token(client: TestClient) -> None:
    """Token expired within the 1-hour grace window should still refresh."""
    token = _create_expired_jwt(expired_seconds_ago=300)
    response = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data

    claims = pyjwt.decode(data["token"], settings.SECRET_KEY, algorithms=["HS256"])
    assert claims["exp"] > time.time()


def test_refresh_long_expired_token(client: TestClient) -> None:
    """Token expired beyond the 1-hour grace window should be rejected."""
    token = _create_expired_jwt(expired_seconds_ago=7200)
    response = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert "grace window" in response.json()["detail"]


def test_refresh_invalid_token(client: TestClient) -> None:
    """Tampered/invalid JWT should be rejected."""
    response = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


def test_refresh_missing_authorization(client: TestClient) -> None:
    """Missing Authorization header should be rejected."""
    response = client.post(f"{settings.API_V1_STR}/auth/refresh")
    assert response.status_code == 401
    assert "Missing" in response.json()["detail"]


def test_refresh_no_bearer_prefix(client: TestClient) -> None:
    """Authorization without Bearer prefix should be rejected."""
    token = _create_user_jwt()
    response = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        headers={"Authorization": token},
    )
    assert response.status_code == 401


def test_refresh_preserves_claims(client: TestClient) -> None:
    """Refreshed token should preserve sub and org claims."""
    token = _create_user_jwt(sub="test@acme.com")
    response = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    claims = pyjwt.decode(data["token"], settings.SECRET_KEY, algorithms=["HS256"])
    assert claims["sub"] == "test@acme.com"
    assert claims["organization_id"] == "org-deepsecure-001"
