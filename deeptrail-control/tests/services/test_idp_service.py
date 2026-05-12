"""Unit tests for IdP service: factory, config, data models, provisioning."""

import pytest

from app.core.idp_config import IdPConfig, IdPProviderType
from app.services.idp_service import (
    OIDCClaims,
    OIDCError,
    OIDCProviderUnavailableError,
    OIDCTokenExpiredError,
    OIDCTokenInvalidError,
    OIDCTokens,
    UserInfo,
    _provisioned_users,
    create_oidc_provider,
    provision_user_from_claims,
)
from app.services.providers.keycloak import KeycloakProvider


# ============================================================================
# Data Model Tests
# ============================================================================


class TestOIDCTokens:
    def test_defaults(self):
        tokens = OIDCTokens(id_token="id", access_token="access")
        assert tokens.id_token == "id"
        assert tokens.access_token == "access"
        assert tokens.refresh_token is None
        assert tokens.expires_at is None
        assert tokens.token_type == "Bearer"

    def test_full_construction(self):
        from datetime import datetime

        now = datetime.utcnow()
        tokens = OIDCTokens(
            id_token="id",
            access_token="access",
            refresh_token="refresh",
            expires_at=now,
            token_type="DPoP",
        )
        assert tokens.refresh_token == "refresh"
        assert tokens.expires_at == now
        assert tokens.token_type == "DPoP"


class TestOIDCClaims:
    def test_minimal(self):
        claims = OIDCClaims(sub="user-123", email="user@example.com")
        assert claims.sub == "user-123"
        assert claims.email == "user@example.com"
        assert claims.email_verified is False
        assert claims.name is None
        assert claims.groups is None
        assert claims.roles is None
        assert claims.raw_claims is None

    def test_full_construction(self):
        claims = OIDCClaims(
            sub="user-123",
            email="sarah@acme.com",
            email_verified=True,
            name="Sarah Chen",
            given_name="Sarah",
            family_name="Chen",
            groups=["acme-org"],
            roles=["user"],
            issuer="http://localhost:8080/realms/deepsecure",
            audience="deepsecure-control",
            raw_claims={"sub": "user-123"},
        )
        assert claims.name == "Sarah Chen"
        assert claims.groups == ["acme-org"]
        assert claims.roles == ["user"]
        assert claims.issuer == "http://localhost:8080/realms/deepsecure"


class TestUserInfo:
    def test_minimal(self):
        info = UserInfo(sub="user-123", email="user@example.com")
        assert info.sub == "user-123"
        assert info.email == "user@example.com"
        assert info.organization_id is None


# ============================================================================
# Error Hierarchy Tests
# ============================================================================


class TestOIDCErrors:
    def test_base_error(self):
        err = OIDCError("something failed", error_code="fail_001")
        assert str(err) == "something failed"
        assert err.error_code == "fail_001"
        assert err.details == {}

    def test_error_with_details(self):
        err = OIDCError("bad", details={"reason": "expired"})
        assert err.details == {"reason": "expired"}

    def test_token_expired_is_oidc_error(self):
        err = OIDCTokenExpiredError("expired")
        assert isinstance(err, OIDCError)

    def test_token_invalid_is_oidc_error(self):
        err = OIDCTokenInvalidError("invalid sig")
        assert isinstance(err, OIDCError)

    def test_provider_unavailable_is_oidc_error(self):
        err = OIDCProviderUnavailableError("down")
        assert isinstance(err, OIDCError)


# ============================================================================
# IdPConfig Tests
# ============================================================================


class TestIdPConfig:
    def test_defaults(self):
        config = IdPConfig()
        assert config.provider == IdPProviderType.KEYCLOAK
        assert config.issuer_url == "http://localhost:8080/realms/deepsecure"
        assert config.client_id == "deepsecure-control"
        assert config.client_secret is None
        assert config.realm == "deepsecure"
        assert config.redirect_uri == "http://localhost:8000/api/v1/auth/sso/callback"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("IDP_PROVIDER", "keycloak")
        monkeypatch.setenv("IDP_ISSUER_URL", "http://kc.example.com/realms/test")
        monkeypatch.setenv("IDP_CLIENT_ID", "my-client")
        monkeypatch.setenv("IDP_CLIENT_SECRET", "my-secret")
        monkeypatch.setenv("IDP_REALM", "test")
        monkeypatch.setenv("IDP_REDIRECT_URI", "http://example.com/callback")

        config = IdPConfig()
        assert config.provider == IdPProviderType.KEYCLOAK
        assert config.issuer_url == "http://kc.example.com/realms/test"
        assert config.client_id == "my-client"
        assert config.client_secret == "my-secret"
        assert config.realm == "test"
        assert config.redirect_uri == "http://example.com/callback"

    def test_provider_enum(self):
        assert IdPProviderType.KEYCLOAK.value == "keycloak"
        assert IdPProviderType.OKTA.value == "okta"
        assert IdPProviderType.ENTRA.value == "entra"
        assert IdPProviderType.GOOGLE.value == "google"

    def test_hd_defaults_to_none(self):
        config = IdPConfig()
        assert config.hd is None

    def test_hd_from_kwarg(self):
        config = IdPConfig(hd="acme.com")
        assert config.hd == "acme.com"

    def test_hd_from_env(self, monkeypatch):
        monkeypatch.setenv("IDP_HD", "acme.com")
        config = IdPConfig()
        assert config.hd == "acme.com"


# ============================================================================
# Factory Tests
# ============================================================================


class TestCreateOIDCProvider:
    def test_keycloak_provider(self):
        config = IdPConfig(
            provider=IdPProviderType.KEYCLOAK,
            issuer_url="http://localhost:8080/realms/deepsecure",
            client_id="deepsecure-control",
            client_secret="secret",
            realm="deepsecure",
        )
        provider = create_oidc_provider(config)
        assert isinstance(provider, KeycloakProvider)
        assert provider._issuer_url == "http://localhost:8080/realms/deepsecure"
        assert provider._client_id == "deepsecure-control"

    def test_keycloak_provider_with_browser_url(self):
        config = IdPConfig(
            provider=IdPProviderType.KEYCLOAK,
            issuer_url="http://keycloak:8080/realms/deepsecure",
            browser_url="http://localhost:8080/realms/deepsecure",
            client_id="deepsecure-control",
            client_secret="secret",
            realm="deepsecure",
        )
        provider = create_oidc_provider(config)
        assert isinstance(provider, KeycloakProvider)
        assert provider._auth_endpoint.startswith("http://localhost:8080/")
        assert provider._token_endpoint.startswith("http://keycloak:8080/")

    def test_okta_not_implemented(self):
        config = IdPConfig(
            provider=IdPProviderType.OKTA,
            issuer_url="https://dev-123.okta.com",
            client_id="okta-client",
        )
        with pytest.raises(NotImplementedError, match="OktaProvider"):
            create_oidc_provider(config)

    def test_entra_not_implemented(self):
        config = IdPConfig(
            provider=IdPProviderType.ENTRA,
            issuer_url="https://login.microsoftonline.com/tenant",
            client_id="entra-client",
        )
        with pytest.raises(NotImplementedError, match="EntraIDProvider"):
            create_oidc_provider(config)

    def test_google_provider(self):
        config = IdPConfig(
            provider=IdPProviderType.GOOGLE,
            issuer_url="https://accounts.google.com",
            client_id="google-client-id",
            client_secret="google-secret",
            hd="acme.com",
        )
        provider = create_oidc_provider(config)
        from app.services.providers.google import GoogleProvider

        assert isinstance(provider, GoogleProvider)
        assert provider._client_id == "google-client-id"
        assert provider._hd == "acme.com"

    def test_google_provider_passes_hd_none(self):
        config = IdPConfig(
            provider=IdPProviderType.GOOGLE,
            issuer_url="https://accounts.google.com",
            client_id="google-client-id",
        )
        provider = create_oidc_provider(config)
        assert provider._hd is None

    def test_default_config(self):
        provider = create_oidc_provider()
        assert isinstance(provider, KeycloakProvider)


# ============================================================================
# User Provisioning Tests
# ============================================================================


class TestProvisionUser:
    @pytest.fixture(autouse=True)
    def clear_store(self):
        _provisioned_users.clear()
        yield
        _provisioned_users.clear()

    @pytest.mark.asyncio
    async def test_provision_new_user(self):
        claims = OIDCClaims(
            sub="new-user-001",
            email="sarah@acme.com",
            name="Sarah Chen",
            groups=["acme-org"],
            roles=["user"],
            issuer="http://localhost:8080/realms/deepsecure",
        )
        result = await provision_user_from_claims(claims)
        assert result["is_new_user"] is True
        assert result["email"] == "sarah@acme.com"
        assert result["user_id"] == "new-user-001"
        assert "user" in result["roles"]

    @pytest.mark.asyncio
    async def test_provision_existing_user(self):
        claims = OIDCClaims(
            sub="existing-001",
            email="sarah@acme.com",
            name="Sarah Chen",
            groups=["acme-org"],
            roles=["user"],
            issuer="http://localhost:8080/realms/deepsecure",
        )
        first = await provision_user_from_claims(claims)
        assert first["is_new_user"] is True

        second = await provision_user_from_claims(claims)
        assert second["is_new_user"] is False

    @pytest.mark.asyncio
    async def test_group_to_role_mapping(self):
        claims = OIDCClaims(
            sub="group-user",
            email="user@acme.com",
            groups=["engineering"],
            roles=[],
        )
        result = await provision_user_from_claims(claims)
        assert "engineer" in result["roles"]

    @pytest.mark.asyncio
    async def test_no_groups_no_extra_roles(self):
        claims = OIDCClaims(
            sub="no-group",
            email="lonely@example.com",
            groups=None,
            roles=None,
        )
        result = await provision_user_from_claims(claims)
        assert result["roles"] == []
        assert result["groups"] == []

    @pytest.mark.asyncio
    async def test_hd_fallback_sets_org(self):
        claims = OIDCClaims(
            sub="google-user-1",
            email="sarah@acme.com",
            email_verified=True,
            name="Sarah Chen",
            groups=None,
            roles=None,
            issuer="https://accounts.google.com",
            raw_claims={"hd": "acme.com", "sub": "google-user-1"},
        )
        result = await provision_user_from_claims(claims)
        assert result["organization_id"] == "acme.com"

    @pytest.mark.asyncio
    async def test_hd_takes_precedence_over_groups(self):
        claims = OIDCClaims(
            sub="user-both",
            email="user@acme.com",
            email_verified=True,
            groups=["engineering"],
            roles=None,
            issuer="https://accounts.google.com",
            raw_claims={"hd": "acme.com", "sub": "user-both"},
        )
        result = await provision_user_from_claims(claims)
        assert result["organization_id"] == "acme.com"

    @pytest.mark.asyncio
    async def test_no_groups_no_hd_uses_email_domain(self):
        claims = OIDCClaims(
            sub="personal-user",
            email="user@gmail.com",
            email_verified=True,
            groups=None,
            roles=None,
            issuer="https://accounts.google.com",
            raw_claims={"sub": "personal-user"},
        )
        result = await provision_user_from_claims(claims)
        assert result["organization_id"] == "gmail.com"

    @pytest.mark.asyncio
    async def test_no_groups_no_raw_claims_uses_email_domain(self):
        claims = OIDCClaims(
            sub="minimal-user",
            email="minimal@example.com",
            groups=None,
            roles=None,
        )
        result = await provision_user_from_claims(claims)
        assert result["organization_id"] == "example.com"
