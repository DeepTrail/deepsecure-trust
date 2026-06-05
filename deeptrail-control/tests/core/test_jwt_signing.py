"""
Tests for RS256 JWT signing service (WS-D1).
"""

import os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import jwt as pyjwt
import pytest

from app.core.jwt_signing import (
    JWTSigningService,
    JWTKeyPair,
    get_jwt_signing_service,
    reset_jwt_signing_service,
    _compute_kid,
    _int_to_base64url,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_jwt_signing_service()
    yield
    reset_jwt_signing_service()


class TestJWTSigningServiceRS256:
    """D1: RS256 signing mode."""

    @patch.dict(os.environ, {"JWT_ALGORITHM": "RS256"}, clear=False)
    def test_generates_ephemeral_keypair(self):
        svc = JWTSigningService()
        assert svc.algorithm == "RS256"
        assert svc.keypair is not None
        assert svc.keypair.kid  # non-empty

    @patch.dict(os.environ, {"JWT_ALGORITHM": "RS256"}, clear=False)
    def test_sign_produces_rs256_token(self):
        svc = JWTSigningService()
        payload = {
            "sub": "agent-1",
            "iss": "deeptrail-control",
            "aud": "deeptrail-gateway",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        token = svc.sign(payload)
        header = pyjwt.get_unverified_header(token)
        assert header["alg"] == "RS256"
        assert header["kid"] == svc.keypair.kid

    @patch.dict(os.environ, {"JWT_ALGORITHM": "RS256"}, clear=False)
    def test_token_verifiable_with_public_key(self):
        svc = JWTSigningService()
        payload = {
            "sub": "agent-1",
            "iss": "deeptrail-control",
            "aud": "deeptrail-gateway",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        token = svc.sign(payload)
        decoded = pyjwt.decode(
            token,
            svc.get_verification_key(),
            algorithms=["RS256"],
            audience="deeptrail-gateway",
            issuer="deeptrail-control",
        )
        assert decoded["sub"] == "agent-1"

    @patch.dict(os.environ, {"JWT_ALGORITHM": "RS256"}, clear=False)
    def test_jwks_contains_public_key(self):
        svc = JWTSigningService()
        jwks = svc.get_jwks()
        assert len(jwks["keys"]) == 1
        key = jwks["keys"][0]
        assert key["kty"] == "RSA"
        assert key["alg"] == "RS256"
        assert key["kid"] == svc.keypair.kid
        assert "n" in key
        assert "e" in key


class TestJWTSigningServiceHS256:
    """D1: HS256 fallback mode."""

    @patch.dict(os.environ, {"JWT_ALGORITHM": "HS256", "SECRET_KEY": "test-secret"}, clear=False)
    def test_hs256_mode_no_keypair(self):
        svc = JWTSigningService()
        assert svc.algorithm == "HS256"
        assert svc.keypair is None

    @patch.dict(os.environ, {"JWT_ALGORITHM": "HS256", "SECRET_KEY": "test-secret"}, clear=False)
    def test_sign_produces_hs256_token(self):
        svc = JWTSigningService()
        payload = {
            "sub": "agent-1",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        token = svc.sign(payload)
        header = pyjwt.get_unverified_header(token)
        assert header["alg"] == "HS256"

    @patch.dict(os.environ, {"JWT_ALGORITHM": "HS256", "SECRET_KEY": "test-secret"}, clear=False)
    def test_hs256_jwks_is_empty(self):
        svc = JWTSigningService()
        jwks = svc.get_jwks()
        assert jwks["keys"] == []


class TestSingleton:
    @patch.dict(os.environ, {"JWT_ALGORITHM": "RS256"}, clear=False)
    def test_singleton_returns_same_instance(self):
        s1 = get_jwt_signing_service()
        s2 = get_jwt_signing_service()
        assert s1 is s2

    def test_reset_clears_singleton(self):
        _ = get_jwt_signing_service()
        reset_jwt_signing_service()
        s2 = get_jwt_signing_service()
        assert s2 is not None


class TestHelpers:
    def test_int_to_base64url_known_value(self):
        result = _int_to_base64url(65537)
        assert result == "AQAB"

    @patch.dict(os.environ, {"JWT_ALGORITHM": "RS256"}, clear=False)
    def test_compute_kid_is_deterministic(self):
        svc = JWTSigningService()
        kid1 = _compute_kid(svc.keypair.public_key)
        kid2 = _compute_kid(svc.keypair.public_key)
        assert kid1 == kid2
