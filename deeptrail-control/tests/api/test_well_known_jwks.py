"""
Tests for JWKS endpoint (WS-D2).
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.jwt_signing import reset_jwt_signing_service


@pytest.fixture(autouse=True)
def _reset():
    reset_jwt_signing_service()
    yield
    reset_jwt_signing_service()


@pytest.fixture
def client():
    with patch.dict(os.environ, {"JWT_ALGORITHM": "RS256"}, clear=False):
        reset_jwt_signing_service()
        from app.main import app
        return TestClient(app)


class TestJWKSEndpoint:
    def test_jwks_returns_200(self, client):
        resp = client.get("/.well-known/jwks.json")
        assert resp.status_code == 200

    def test_jwks_has_keys_array(self, client):
        body = client.get("/.well-known/jwks.json").json()
        assert "keys" in body
        assert isinstance(body["keys"], list)

    def test_jwks_key_has_required_fields(self, client):
        body = client.get("/.well-known/jwks.json").json()
        assert len(body["keys"]) >= 1
        key = body["keys"][0]
        assert key["kty"] == "RSA"
        assert key["alg"] == "RS256"
        assert "kid" in key
        assert "n" in key
        assert "e" in key

    def test_jwks_is_json_content_type(self, client):
        resp = client.get("/.well-known/jwks.json")
        assert "application/json" in resp.headers.get("content-type", "")

    def test_jwks_no_auth_required(self, client):
        resp = client.get("/.well-known/jwks.json")
        assert resp.status_code == 200

    def test_jwks_hs256_returns_empty_keys(self):
        with patch.dict(os.environ, {"JWT_ALGORITHM": "HS256"}, clear=False):
            reset_jwt_signing_service()
            from app.main import app
            c = TestClient(app)
            body = c.get("/.well-known/jwks.json").json()
            assert body["keys"] == []
