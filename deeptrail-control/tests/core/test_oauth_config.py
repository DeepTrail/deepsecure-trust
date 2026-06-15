"""Tests for OAuth Configuration Module.

Tests the OAuth provider configuration classes and singleton pattern.
Verifies that:
- Default values are correct for each provider
- Environment variables override defaults properly
- Singleton pattern works correctly
- PKCE flags are set correctly per provider
"""

import os
import pytest
from unittest.mock import patch


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset OAuth settings singleton before each test."""
    from app.core.oauth_config import reset_oauth_settings
    reset_oauth_settings()
    yield
    reset_oauth_settings()


# ─────────────────────────────────────────────────────────────────────────────
# Test: Notion OAuth Configuration
# ─────────────────────────────────────────────────────────────────────────────


class TestNotionOAuthConfig:
    """Test Notion OAuth configuration."""

    def test_default_authorization_url(self):
        """Test Notion has correct authorization URL."""
        from app.core.oauth_config import NotionOAuthConfig
        config = NotionOAuthConfig()
        assert config.authorization_url == "https://api.notion.com/v1/oauth/authorize"

    def test_default_token_url(self):
        """Test Notion has correct token URL."""
        from app.core.oauth_config import NotionOAuthConfig
        config = NotionOAuthConfig()
        assert config.token_url == "https://api.notion.com/v1/oauth/token"

    def test_uses_pkce(self):
        """Test Notion requires PKCE."""
        from app.core.oauth_config import NotionOAuthConfig
        config = NotionOAuthConfig()
        assert config.uses_pkce is True

    def test_empty_scopes_by_default(self):
        """Test Notion has empty scopes (managed via integration)."""
        from app.core.oauth_config import NotionOAuthConfig
        config = NotionOAuthConfig()
        assert config.scopes == []

    def test_default_empty_credentials(self):
        """Test Notion has empty credentials by default."""
        from app.core.oauth_config import NotionOAuthConfig
        config = NotionOAuthConfig()
        assert config.client_id == ""
        assert config.client_secret == ""

    @patch.dict(os.environ, {"NOTION_OAUTH_CLIENT_ID": "test-notion-id"})
    def test_env_override_client_id(self):
        """Test Notion client ID can be overridden via env var."""
        from app.core.oauth_config import NotionOAuthConfig
        config = NotionOAuthConfig()
        assert config.client_id == "test-notion-id"

    @patch.dict(os.environ, {"NOTION_OAUTH_CLIENT_SECRET": "test-notion-secret"})
    def test_env_override_client_secret(self):
        """Test Notion client secret can be overridden via env var."""
        from app.core.oauth_config import NotionOAuthConfig
        config = NotionOAuthConfig()
        assert config.client_secret == "test-notion-secret"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Slack OAuth Configuration
# ─────────────────────────────────────────────────────────────────────────────


class TestSlackOAuthConfig:
    """Test Slack OAuth configuration."""

    def test_default_authorization_url(self):
        """Test Slack has correct authorization URL."""
        from app.core.oauth_config import SlackOAuthConfig
        config = SlackOAuthConfig()
        assert config.authorization_url == "https://slack.com/oauth/v2/authorize"

    def test_default_token_url(self):
        """Test Slack has correct token URL."""
        from app.core.oauth_config import SlackOAuthConfig
        config = SlackOAuthConfig()
        assert config.token_url == "https://slack.com/api/oauth.v2.access"

    def test_does_not_use_pkce(self):
        """Test Slack does not require PKCE."""
        from app.core.oauth_config import SlackOAuthConfig
        config = SlackOAuthConfig()
        assert config.uses_pkce is False

    def test_default_scopes(self):
        """Test Slack has correct default scopes."""
        from app.core.oauth_config import SlackOAuthConfig
        config = SlackOAuthConfig()
        assert "channels:read" in config.scopes
        assert "channels:history" in config.scopes
        assert "chat:write" in config.scopes
        assert "users:read" in config.scopes

    def test_default_empty_credentials(self):
        """Test Slack has empty credentials by default."""
        from app.core.oauth_config import SlackOAuthConfig
        config = SlackOAuthConfig()
        assert config.client_id == ""
        assert config.client_secret == ""

    @patch.dict(os.environ, {"SLACK_OAUTH_CLIENT_ID": "test-slack-id"})
    def test_env_override_client_id(self):
        """Test Slack client ID can be overridden via env var."""
        from app.core.oauth_config import SlackOAuthConfig
        config = SlackOAuthConfig()
        assert config.client_id == "test-slack-id"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Main OAuth Settings
# ─────────────────────────────────────────────────────────────────────────────


class TestOAuthSettings:
    """Test main OAuth settings container."""

    def test_default_redirect_base_url(self):
        """Test default redirect base URL."""
        from app.core.oauth_config import OAuthSettings
        settings = OAuthSettings()
        assert settings.redirect_base_url == "http://localhost:8000"

    def test_default_state_ttl(self):
        """Test default state TTL is 10 minutes."""
        from app.core.oauth_config import OAuthSettings
        settings = OAuthSettings()
        assert settings.state_ttl_seconds == 600

    def test_all_providers_initialized(self):
        """Test all provider configs are initialized."""
        from app.core.oauth_config import OAuthSettings
        settings = OAuthSettings()
        assert settings.notion is not None
        assert settings.slack is not None

    def test_providers_are_correct_type(self):
        """Test provider configs are the correct types."""
        from app.core.oauth_config import (
            OAuthSettings,
            NotionOAuthConfig,
            SlackOAuthConfig,
        )
        settings = OAuthSettings()
        assert isinstance(settings.notion, NotionOAuthConfig)
        assert isinstance(settings.slack, SlackOAuthConfig)

    @patch.dict(os.environ, {"OAUTH_REDIRECT_BASE_URL": "https://prod.example.com"})
    def test_env_override_redirect_url(self):
        """Test redirect base URL can be overridden via env var."""
        from app.core.oauth_config import OAuthSettings
        settings = OAuthSettings()
        assert settings.redirect_base_url == "https://prod.example.com"

    @patch.dict(os.environ, {"OAUTH_STATE_TTL_SECONDS": "300"})
    def test_env_override_state_ttl(self):
        """Test state TTL can be overridden via env var."""
        from app.core.oauth_config import OAuthSettings
        settings = OAuthSettings()
        assert settings.state_ttl_seconds == 300


# ─────────────────────────────────────────────────────────────────────────────
# Test: Singleton Pattern
# ─────────────────────────────────────────────────────────────────────────────


class TestGetOAuthSettings:
    """Test singleton accessor function."""

    def test_returns_oauth_settings_instance(self):
        """Test get_oauth_settings returns OAuthSettings."""
        from app.core.oauth_config import get_oauth_settings, OAuthSettings
        settings = get_oauth_settings()
        assert isinstance(settings, OAuthSettings)

    def test_singleton_returns_same_instance(self):
        """Test get_oauth_settings returns the same instance."""
        from app.core.oauth_config import get_oauth_settings
        settings1 = get_oauth_settings()
        settings2 = get_oauth_settings()
        assert settings1 is settings2

    def test_reset_clears_singleton(self):
        """Test reset_oauth_settings clears the singleton."""
        from app.core.oauth_config import (
            get_oauth_settings,
            reset_oauth_settings,
        )
        settings1 = get_oauth_settings()
        reset_oauth_settings()
        settings2 = get_oauth_settings()
        # After reset, should be a new instance
        assert settings1 is not settings2


# ─────────────────────────────────────────────────────────────────────────────
# Test: PKCE Configuration
# ─────────────────────────────────────────────────────────────────────────────


class TestPKCEConfiguration:
    """Test PKCE is configured correctly per provider."""

    def test_notion_uses_pkce(self):
        """Notion requires PKCE per their API documentation."""
        from app.core.oauth_config import NotionOAuthConfig
        assert NotionOAuthConfig().uses_pkce is True

    def test_slack_does_not_use_pkce(self):
        """Slack does not require PKCE."""
        from app.core.oauth_config import SlackOAuthConfig
        assert SlackOAuthConfig().uses_pkce is False

