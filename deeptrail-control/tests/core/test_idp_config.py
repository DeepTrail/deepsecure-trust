"""Tests for IdP Configuration Module.

Tests the IdPConfig settings class, verifying that:
- Default values are correct for all fields
- Environment variables override defaults properly
- Constructor kwargs work correctly
- The fetch_groups field behaves as a boolean feature flag
"""

import os

import pytest
from unittest.mock import patch


# ─────────────────────────────────────────────────────────────────────────────
# Test: fetch_groups field
# ─────────────────────────────────────────────────────────────────────────────


class TestFetchGroupsField:
    """Test the fetch_groups boolean field on IdPConfig."""

    def test_default_is_false(self):
        """fetch_groups defaults to False when IDP_FETCH_GROUPS is not set."""
        from app.core.idp_config import IdPConfig

        config = IdPConfig()
        assert config.fetch_groups is False

    @patch.dict(os.environ, {"IDP_FETCH_GROUPS": "true"})
    def test_env_var_true(self):
        """Setting IDP_FETCH_GROUPS=true results in fetch_groups == True."""
        from app.core.idp_config import IdPConfig

        config = IdPConfig()
        assert config.fetch_groups is True

    @patch.dict(os.environ, {"IDP_FETCH_GROUPS": "false"})
    def test_env_var_false(self):
        """Setting IDP_FETCH_GROUPS=false results in fetch_groups == False."""
        from app.core.idp_config import IdPConfig

        config = IdPConfig()
        assert config.fetch_groups is False

    def test_constructor_kwarg_true(self):
        """fetch_groups can be set to True via constructor kwarg."""
        from app.core.idp_config import IdPConfig

        config = IdPConfig(fetch_groups=True)
        assert config.fetch_groups is True

    def test_constructor_kwarg_false(self):
        """fetch_groups can be set to False via constructor kwarg."""
        from app.core.idp_config import IdPConfig

        config = IdPConfig(fetch_groups=False)
        assert config.fetch_groups is False

    @patch.dict(os.environ, {"IDP_FETCH_GROUPS": "True"})
    def test_env_var_case_insensitive(self):
        """Pydantic coerces case-insensitive boolean strings."""
        from app.core.idp_config import IdPConfig

        config = IdPConfig()
        assert config.fetch_groups is True

    @patch.dict(os.environ, {"IDP_FETCH_GROUPS": "1"})
    def test_env_var_numeric_truthy(self):
        """Pydantic coerces '1' to True for boolean fields."""
        from app.core.idp_config import IdPConfig

        config = IdPConfig()
        assert config.fetch_groups is True

    @patch.dict(os.environ, {"IDP_FETCH_GROUPS": "0"})
    def test_env_var_numeric_falsy(self):
        """Pydantic coerces '0' to False for boolean fields."""
        from app.core.idp_config import IdPConfig

        config = IdPConfig()
        assert config.fetch_groups is False


# ─────────────────────────────────────────────────────────────────────────────
# Test: Existing fields regression
# ─────────────────────────────────────────────────────────────────────────────


class TestIdPConfigDefaults:
    """Verify existing IdPConfig fields are unchanged by the addition of fetch_groups."""

    def test_default_provider(self):
        from app.core.idp_config import IdPConfig, IdPProviderType

        config = IdPConfig()
        assert config.provider == IdPProviderType.KEYCLOAK

    def test_default_issuer_url(self):
        from app.core.idp_config import IdPConfig

        config = IdPConfig()
        assert config.issuer_url == "http://localhost:8080/realms/deepsecure"

    def test_default_client_id(self):
        from app.core.idp_config import IdPConfig

        config = IdPConfig()
        assert config.client_id == "deepsecure-control"

    def test_default_client_secret_is_none(self):
        from app.core.idp_config import IdPConfig

        config = IdPConfig()
        assert config.client_secret is None

    def test_default_realm(self):
        from app.core.idp_config import IdPConfig

        config = IdPConfig()
        assert config.realm == "deepsecure"

    def test_default_redirect_uri(self):
        from app.core.idp_config import IdPConfig

        config = IdPConfig()
        assert config.redirect_uri == "http://localhost:8000/api/v1/auth/sso/callback"

    def test_default_hd_is_none(self):
        from app.core.idp_config import IdPConfig

        config = IdPConfig()
        assert config.hd is None

    def test_default_browser_url_is_none(self):
        from app.core.idp_config import IdPConfig

        config = IdPConfig()
        assert config.browser_url is None
