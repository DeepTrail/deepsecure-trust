"""
Tests for OAuth 2.1 token validation via Keycloak JWKS (WS-C3).
"""

import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from jose import jwt as jose_jwt, jwk
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from app.middleware.oauth_validation import (
    OAuthTokenValidator,
    OAuthTokenClaims,
    OAuthValidationError,
    JWKSCache,
)


# ─────────────────────────────────────────────────────────────────────
# Fixtures: RSA key generation for test token signing
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def rsa_private_key():
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )


@pytest.fixture(scope="module")
def rsa_public_key(rsa_private_key):
    return rsa_private_key.public_key()


@pytest.fixture(scope="module")
def rsa_private_key_pem(rsa_private_key):
    return rsa_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@pytest.fixture(scope="module")
def jwks_response(rsa_public_key):
    """Build a JWKS response containing the test RSA public key."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    import base64, json, struct

    pub_numbers = rsa_public_key.public_numbers()

    def _int_to_base64url(n: int) -> str:
        data = n.to_bytes((n.bit_length() + 7) // 8, byteorder="big")
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": "test-key-1",
                "n": _int_to_base64url(pub_numbers.n),
                "e": _int_to_base64url(pub_numbers.e),
            }
        ]
    }


@pytest.fixture
def make_oauth_token(rsa_private_key_pem):
    """Factory to create signed OAuth tokens."""

    def _make(claims: dict | None = None, algorithm: str = "RS256"):
        now = int(time.time())
        payload = {
            "sub": "user-123",
            "iss": "http://localhost:8080/realms/mcp",
            "aud": "mcp-gateway",
            "scope": "mcp_tools mcp_resources",
            "preferred_username": "testuser",
            "email": "test@example.com",
            "realm_access": {"roles": ["mcp_user"]},
            "exp": now + 3600,
            "iat": now,
        }
        if claims:
            payload.update(claims)
        return jose_jwt.encode(payload, rsa_private_key_pem, algorithm=algorithm, headers={"kid": "test-key-1"})

    return _make


@pytest.fixture
def validator():
    return OAuthTokenValidator(
        keycloak_url="http://localhost:8080",
        realm="mcp",
        audience="mcp-gateway",
    )


# ─────────────────────────────────────────────────────────────────────
# JWKSCache
# ─────────────────────────────────────────────────────────────────────


class TestJWKSCache:
    def test_initial_state_is_stale(self):
        cache = JWKSCache()
        assert cache.is_stale()
        assert cache.get() is None

    def test_set_and_get(self):
        cache = JWKSCache(ttl_seconds=60)
        keys = {"keys": [{"kid": "1"}]}
        cache.set(keys)
        assert not cache.is_stale()
        assert cache.get() == keys

    def test_expired_cache_is_stale(self):
        cache = JWKSCache(ttl_seconds=1)
        cache.set({"keys": []})
        cache._fetched_at = time.time() - 10  # force expiry
        assert cache.is_stale()
        assert cache.get() is None


# ─────────────────────────────────────────────────────────────────────
# OAuthTokenValidator
# ─────────────────────────────────────────────────────────────────────


class TestOAuthTokenValidator:

    @pytest.mark.asyncio
    async def test_validate_valid_token(self, validator, make_oauth_token, jwks_response):
        with patch.object(validator, "fetch_jwks", new_callable=AsyncMock, return_value=jwks_response):
            token = make_oauth_token()
            claims = await validator.validate_token(token)
            assert claims.sub == "user-123"
            assert claims.iss == "http://localhost:8080/realms/mcp"
            assert "mcp_tools" in claims.scopes
            assert "mcp_resources" in claims.scopes
            assert claims.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, validator, make_oauth_token, jwks_response):
        token = make_oauth_token({"exp": int(time.time()) - 600})
        with patch.object(validator, "fetch_jwks", new_callable=AsyncMock, return_value=jwks_response):
            with pytest.raises(OAuthValidationError, match="Token validation failed"):
                await validator.validate_token(token)

    @pytest.mark.asyncio
    async def test_wrong_audience_rejected(self, validator, make_oauth_token, jwks_response):
        token = make_oauth_token({"aud": "wrong-audience"})
        with patch.object(validator, "fetch_jwks", new_callable=AsyncMock, return_value=jwks_response):
            with pytest.raises(OAuthValidationError, match="Token validation failed"):
                await validator.validate_token(token)

    @pytest.mark.asyncio
    async def test_wrong_issuer_rejected(self, validator, make_oauth_token, jwks_response):
        token = make_oauth_token({"iss": "http://evil.example.com/realms/mcp"})
        with patch.object(validator, "fetch_jwks", new_callable=AsyncMock, return_value=jwks_response):
            with pytest.raises(OAuthValidationError, match="Token validation failed"):
                await validator.validate_token(token)

    @pytest.mark.asyncio
    async def test_jwks_fetch_failure(self, validator, make_oauth_token):
        with patch.object(validator, "fetch_jwks", new_callable=AsyncMock, side_effect=OAuthValidationError("Cannot fetch JWKS: connection refused")):
            with pytest.raises(OAuthValidationError, match="Cannot fetch JWKS"):
                await validator.validate_token(make_oauth_token())

    def test_is_oauth_token_rs256(self, make_oauth_token):
        validator = OAuthTokenValidator()
        token = make_oauth_token()
        assert validator.is_oauth_token(token) is True

    def test_is_oauth_token_hs256_returns_false(self):
        """DeepSecure HS256 tokens should not be classified as OAuth."""
        validator = OAuthTokenValidator()
        hs_token = jose_jwt.encode(
            {"sub": "agent", "iss": "deeptrail-control", "aud": "deeptrail-gateway"},
            "test-secret",
            algorithm="HS256",
        )
        assert validator.is_oauth_token(hs_token) is False

    def test_is_oauth_token_garbage_returns_false(self):
        validator = OAuthTokenValidator()
        assert validator.is_oauth_token("not-a-jwt") is False

    @pytest.mark.asyncio
    async def test_fetch_jwks_caches_result(self, validator, jwks_response):
        mock_response = MagicMock()
        mock_response.json.return_value = jwks_response
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.middleware.oauth_validation.httpx.AsyncClient", return_value=mock_client):
            result1 = await validator.fetch_jwks()
            result2 = await validator.fetch_jwks()
            assert result1 == result2
            mock_client.get.assert_called_once()


# ─────────────────────────────────────────────────────────────────────
# OAuthTokenClaims
# ─────────────────────────────────────────────────────────────────────


class TestOAuthTokenClaims:
    def test_scopes_parsing(self):
        claims = OAuthTokenClaims(
            sub="u1", iss="iss", aud="aud", scope="mcp_tools mcp_resources"
        )
        assert claims.scopes == ["mcp_tools", "mcp_resources"]

    def test_empty_scope(self):
        claims = OAuthTokenClaims(sub="u1", iss="iss", aud="aud")
        assert claims.scopes == []

    def test_raw_payload_stored(self):
        claims = OAuthTokenClaims(
            sub="u1", iss="iss", aud="aud", raw={"custom": "value"}
        )
        assert claims.raw["custom"] == "value"
