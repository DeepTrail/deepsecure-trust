"""
Tests for Gateway Configuration Module

Tests the externalized configuration system using Pydantic Settings.
"""

import os
from unittest.mock import patch

import pytest

from app.core.config import (
    GatewaySettings,
    GCalendarConfig,
    GDriveConfig,
    GmailConfig,
    NotionConfig,
    SlackConfig,
    create_backend_config_from_settings,
    get_backend_extra_headers,
    get_settings,
    reset_settings,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_settings_fixture():
    """Reset settings singleton before and after each test."""
    reset_settings()
    yield
    reset_settings()


# =============================================================================
# Default Values Tests
# =============================================================================


class TestDefaultValues:
    """Tests that default values work without environment variables."""

    def test_notion_defaults(self):
        """Test NotionConfig has correct defaults."""
        config = NotionConfig()
        assert config.base_url == "https://api.notion.com/v1"
        assert config.api_version == "2022-06-28"
        assert config.version_header == "Notion-Version"
        assert config.timeout_seconds == 30.0
        assert config.retry_attempts == 3
        assert config.health_endpoint == "/health"

    def test_slack_defaults(self):
        """Test SlackConfig has correct defaults."""
        config = SlackConfig()
        assert config.base_url == "https://slack.com/api"
        assert config.api_version is None
        assert config.version_header is None
        assert config.timeout_seconds == 30.0
        assert config.retry_attempts == 3

    def test_gateway_settings_defaults(self):
        """Test GatewaySettings has correct defaults."""
        settings = GatewaySettings()
        assert settings.control_plane_url == "http://localhost:8000"
        assert settings.max_connections_per_backend == 10
        assert settings.health_check_interval_seconds == 30.0
        assert settings.health_check_timeout_seconds == 5.0

    def test_gateway_settings_nested_configs(self):
        """Test GatewaySettings contains nested configurations."""
        settings = GatewaySettings()
        assert isinstance(settings.notion, NotionConfig)
        assert isinstance(settings.slack, SlackConfig)
        assert isinstance(settings.gdrive, GDriveConfig)
        assert isinstance(settings.gcalendar, GCalendarConfig)
        assert isinstance(settings.gmail, GmailConfig)

    def test_gdrive_defaults(self):
        """Test GDriveConfig has correct defaults."""
        config = GDriveConfig()
        assert config.base_url == "https://www.googleapis.com/drive/v3"
        assert config.api_version is None
        assert config.version_header is None
        assert config.timeout_seconds == 30.0
        assert config.retry_attempts == 3
        assert config.retry_backoff_factor == 0.5
        assert config.health_endpoint == "/health"

    def test_gcalendar_defaults(self):
        """Test GCalendarConfig has correct defaults."""
        config = GCalendarConfig()
        assert config.base_url == "https://www.googleapis.com/calendar/v3"
        assert config.api_version is None
        assert config.version_header is None
        assert config.timeout_seconds == 30.0
        assert config.retry_attempts == 3
        assert config.retry_backoff_factor == 0.5
        assert config.health_endpoint == "/health"

    def test_gmail_defaults(self):
        """Test GmailConfig has correct defaults."""
        config = GmailConfig()
        assert config.base_url == "https://gmail.googleapis.com/gmail/v1"
        assert config.api_version is None
        assert config.version_header is None
        assert config.timeout_seconds == 30.0
        assert config.retry_attempts == 3
        assert config.retry_backoff_factor == 0.5
        assert config.health_endpoint == "/health"

    def test_gateway_settings_google_defaults(self):
        """Test GatewaySettings exposes Google config defaults."""
        settings = GatewaySettings()
        assert settings.gdrive.base_url == "https://www.googleapis.com/drive/v3"
        assert settings.gcalendar.base_url == "https://www.googleapis.com/calendar/v3"
        assert settings.gmail.base_url == "https://gmail.googleapis.com/gmail/v1"


# =============================================================================
# Environment Variable Override Tests
# =============================================================================


class TestEnvironmentOverrides:
    """Tests that environment variables correctly override defaults."""

    def test_notion_base_url_override(self):
        """Test NOTION_BASE_URL environment variable."""
        with patch.dict(os.environ, {"NOTION_BASE_URL": "https://custom.notion.api/v1"}):
            config = NotionConfig()
            assert config.base_url == "https://custom.notion.api/v1"

    def test_notion_api_version_override(self):
        """Test NOTION_API_VERSION environment variable."""
        with patch.dict(os.environ, {"NOTION_API_VERSION": "2023-01-01"}):
            config = NotionConfig()
            assert config.api_version == "2023-01-01"

    def test_slack_base_url_override(self):
        """Test SLACK_BASE_URL environment variable."""
        with patch.dict(os.environ, {"SLACK_BASE_URL": "https://custom.slack.api"}):
            config = SlackConfig()
            assert config.base_url == "https://custom.slack.api"

    def test_gateway_control_plane_url_override(self):
        """Test GATEWAY_CONTROL_PLANE_URL environment variable."""
        with patch.dict(os.environ, {"GATEWAY_CONTROL_PLANE_URL": "http://control:9000"}):
            settings = GatewaySettings()
            assert settings.control_plane_url == "http://control:9000"

    def test_timeout_override(self):
        """Test timeout environment variable override."""
        with patch.dict(os.environ, {"NOTION_TIMEOUT_SECONDS": "60.0"}):
            config = NotionConfig()
            assert config.timeout_seconds == 60.0

    def test_retry_attempts_override(self):
        """Test retry attempts environment variable override."""
        with patch.dict(os.environ, {"SLACK_RETRY_ATTEMPTS": "5"}):
            config = SlackConfig()
            assert config.retry_attempts == 5

    def test_gdrive_base_url_override(self):
        """Test GDRIVE_BASE_URL environment variable."""
        with patch.dict(os.environ, {"GDRIVE_BASE_URL": "http://mock-gdrive:8080"}):
            config = GDriveConfig()
            assert config.base_url == "http://mock-gdrive:8080"

    def test_gcalendar_base_url_override(self):
        """Test GCALENDAR_BASE_URL environment variable."""
        with patch.dict(os.environ, {"GCALENDAR_BASE_URL": "http://mock-gcal:8080"}):
            config = GCalendarConfig()
            assert config.base_url == "http://mock-gcal:8080"

    def test_gmail_base_url_override(self):
        """Test GMAIL_BASE_URL environment variable."""
        with patch.dict(os.environ, {"GMAIL_BASE_URL": "http://mock-gmail:8080"}):
            config = GmailConfig()
            assert config.base_url == "http://mock-gmail:8080"

    def test_gdrive_timeout_override(self):
        """Test GDRIVE_TIMEOUT_SECONDS environment variable."""
        with patch.dict(os.environ, {"GDRIVE_TIMEOUT_SECONDS": "45.0"}):
            config = GDriveConfig()
            assert config.timeout_seconds == 45.0


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for the singleton settings pattern."""

    def test_get_settings_returns_same_instance(self):
        """Test that get_settings() returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_reset_settings_clears_singleton(self):
        """Test that reset_settings() clears the singleton."""
        settings1 = get_settings()
        reset_settings()
        settings2 = get_settings()
        assert settings1 is not settings2

    def test_settings_persist_across_calls(self):
        """Test that settings values persist across calls."""
        settings = get_settings()
        original_url = settings.control_plane_url
        settings2 = get_settings()
        assert settings2.control_plane_url == original_url


# =============================================================================
# Backend Config Mapping Tests
# =============================================================================


class TestBackendConfigMapping:
    """Tests for creating BackendConfig from settings."""

    def test_create_backend_config_basic(self):
        """Test basic BackendConfig creation."""
        config = SlackConfig()
        backend_config = create_backend_config_from_settings("slack", config)

        assert backend_config.backend_id == "slack"
        assert backend_config.base_url == "https://slack.com/api"
        assert backend_config.health_endpoint == "/health"
        assert backend_config.timeout_seconds == 30.0
        assert backend_config.retry_attempts == 3

    def test_create_backend_config_notion_with_version(self):
        """Test NotionConfig creates BackendConfig correctly."""
        config = NotionConfig()
        backend_config = create_backend_config_from_settings("notion", config)

        assert backend_config.backend_id == "notion"
        assert backend_config.base_url == "https://api.notion.com/v1"
        # Version header mapping is handled separately in extra_headers

    def test_get_backend_extra_headers_notion(self):
        """Test extra headers extraction for Notion."""
        config = NotionConfig()
        headers = get_backend_extra_headers(config)
        assert headers == {"Notion-Version": "2022-06-28"}

    def test_get_backend_extra_headers_slack(self):
        """Test extra headers extraction for Slack (no version header)."""
        config = SlackConfig()
        headers = get_backend_extra_headers(config)
        assert headers == {}

    def test_get_backend_extra_headers_custom_version(self):
        """Test extra headers with custom API version."""
        with patch.dict(os.environ, {"NOTION_API_VERSION": "2023-06-01"}):
            config = NotionConfig()
            headers = get_backend_extra_headers(config)
            assert headers == {"Notion-Version": "2023-06-01"}

    def test_create_backend_config_gdrive(self):
        """Test GDriveConfig creates BackendConfig correctly."""
        config = GDriveConfig()
        backend_config = create_backend_config_from_settings("gdrive", config)
        assert backend_config.backend_id == "gdrive"
        assert backend_config.base_url == "https://www.googleapis.com/drive/v3"
        assert backend_config.timeout_seconds == 30.0
        assert backend_config.retry_attempts == 3

    def test_create_backend_config_gcalendar(self):
        """Test GCalendarConfig creates BackendConfig correctly."""
        config = GCalendarConfig()
        backend_config = create_backend_config_from_settings("gcalendar", config)
        assert backend_config.backend_id == "gcalendar"
        assert backend_config.base_url == "https://www.googleapis.com/calendar/v3"

    def test_create_backend_config_gmail(self):
        """Test GmailConfig creates BackendConfig correctly."""
        config = GmailConfig()
        backend_config = create_backend_config_from_settings("gmail", config)
        assert backend_config.backend_id == "gmail"
        assert backend_config.base_url == "https://gmail.googleapis.com/gmail/v1"

    def test_get_backend_extra_headers_google(self):
        """Test Google configs have no extra headers (no version header)."""
        assert get_backend_extra_headers(GDriveConfig()) == {}
        assert get_backend_extra_headers(GCalendarConfig()) == {}
        assert get_backend_extra_headers(GmailConfig()) == {}


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the configuration module."""

    def test_full_settings_creation(self):
        """Test creating full settings and accessing all properties."""
        settings = get_settings()

        # Gateway level
        assert settings.control_plane_url == "http://localhost:8000"
        assert settings.max_connections_per_backend == 10

        # Notion
        assert settings.notion.base_url == "https://api.notion.com/v1"
        assert settings.notion.api_version == "2022-06-28"

        # Slack
        assert settings.slack.base_url == "https://slack.com/api"


    def test_create_backend_configs_from_settings(self):
        """Test creating all backend configs from settings."""
        settings = get_settings()

        notion_config = create_backend_config_from_settings("notion", settings.notion)
        slack_config = create_backend_config_from_settings("slack", settings.slack)

        assert notion_config.backend_id == "notion"
        assert slack_config.backend_id == "slack"

    def test_settings_with_multiple_env_overrides(self):
        """Test settings with multiple environment variable overrides."""
        env_vars = {
            "GATEWAY_CONTROL_PLANE_URL": "http://custom-control:9000",
            "NOTION_BASE_URL": "https://custom.notion.com/v1",
            "SLACK_BASE_URL": "https://custom.slack.com/api",
        }
        with patch.dict(os.environ, env_vars):
            settings = GatewaySettings()
            assert settings.control_plane_url == "http://custom-control:9000"
            assert settings.notion.base_url == "https://custom.notion.com/v1"
            assert settings.slack.base_url == "https://custom.slack.com/api"


# =============================================================================
# Connection Manager Integration Tests
# =============================================================================


class TestConnectionManagerIntegration:
    """Tests for connection manager integration with settings."""

    def test_create_connection_manager(self):
        """Test creating connection manager from settings."""
        from app.backends.connection_manager import create_connection_manager

        manager = create_connection_manager()

        # Verify all backends are registered
        assert manager.is_backend_registered("notion")
        assert manager.is_backend_registered("slack")

    def test_create_connection_manager_with_custom_urls(self):
        """Test connection manager uses custom URLs from env vars."""
        from app.backends.connection_manager import create_connection_manager

        env_vars = {
            "NOTION_BASE_URL": "https://custom.notion.api/v1",
            "SLACK_BASE_URL": "https://custom.slack.api",
        }
        with patch.dict(os.environ, env_vars):
            reset_settings()  # Clear cached settings
            manager = create_connection_manager()

            # Get backend states to verify URLs
            states = manager.get_all_backend_states()
            assert states["notion"]["base_url"] == "https://custom.notion.api/v1"
            assert states["slack"]["base_url"] == "https://custom.slack.api"

    def test_create_connection_manager_returns_all_backends(self):
        """Test connection manager has all registered backends."""
        from app.backends.connection_manager import create_connection_manager

        manager = create_connection_manager()
        backend_ids = manager.get_backend_ids()
        assert len(backend_ids) == 5
        assert set(backend_ids) == {"notion", "slack", "gdrive", "gcalendar", "gmail"}
