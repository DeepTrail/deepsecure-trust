"""
Gateway Configuration Module

Provides externalized configuration for the Gateway service using Pydantic Settings.
Configuration can be overridden via environment variables.

Usage:
    from app.core.config import get_settings

    settings = get_settings()
    print(settings.notion.base_url)  # https://api.notion.com/v1
    print(settings.control_plane_url)  # http://localhost:8000

Environment Variables:
    GATEWAY_CONTROL_PLANE_URL: Control Plane API URL
    NOTION_BASE_URL: Notion API base URL
    NOTION_API_VERSION: Notion API version header value
    SLACK_BASE_URL: Slack API base URL
    HUBSPOT_BASE_URL: HubSpot API base URL
    GDRIVE_BASE_URL: Google Drive API base URL
    GCALENDAR_BASE_URL: Google Calendar API base URL
    GMAIL_BASE_URL: Gmail API base URL
"""

from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings

from app.backends.connection_manager import BackendConfig


# =============================================================================
# Backend API Configuration Classes
# =============================================================================


class BackendAPIConfig(BaseSettings):
    """
    Base configuration for a backend API.

    Provides common settings that apply to all backend services.
    Subclasses can override defaults and add service-specific settings.

    Attributes:
        base_url: Base URL for the API
        api_version: API version string (if applicable)
        version_header: Header name for API version (if applicable)
        timeout_seconds: Request timeout in seconds
        retry_attempts: Number of retry attempts on failure
        retry_backoff_factor: Base factor for exponential backoff
        health_endpoint: Endpoint path for health checks
    """
    base_url: str
    api_version: str | None = None
    version_header: str | None = None
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_backoff_factor: float = 0.5
    health_endpoint: str = "/health"


class NotionConfig(BackendAPIConfig):
    """
    Notion API configuration.

    Notion requires a version header (Notion-Version) with each request.

    Environment Variables:
        NOTION_BASE_URL: Base URL (default: https://api.notion.com/v1)
        NOTION_API_VERSION: API version (default: 2022-06-28)
        NOTION_TIMEOUT_SECONDS: Request timeout
        NOTION_RETRY_ATTEMPTS: Number of retries
        NOTION_HEALTH_ENDPOINT: Health check endpoint
    """
    base_url: str = Field(default="https://api.notion.com/v1")
    api_version: str = Field(default="2022-06-28")
    version_header: str = "Notion-Version"

    model_config = {"env_prefix": "NOTION_"}


class SlackConfig(BackendAPIConfig):
    """
    Slack API configuration.

    Environment Variables:
        SLACK_BASE_URL: Base URL (default: https://slack.com/api)
        SLACK_TIMEOUT_SECONDS: Request timeout
        SLACK_RETRY_ATTEMPTS: Number of retries
        SLACK_HEALTH_ENDPOINT: Health check endpoint
    """
    base_url: str = Field(default="https://slack.com/api")

    model_config = {"env_prefix": "SLACK_"}


class HubSpotConfig(BackendAPIConfig):
    """
    HubSpot API configuration.

    Environment Variables:
        HUBSPOT_BASE_URL: Base URL (default: https://api.hubapi.com)
        HUBSPOT_TIMEOUT_SECONDS: Request timeout
        HUBSPOT_RETRY_ATTEMPTS: Number of retries
        HUBSPOT_HEALTH_ENDPOINT: Health check endpoint
    """
    base_url: str = Field(default="https://api.hubapi.com")

    model_config = {"env_prefix": "HUBSPOT_"}


class GDriveConfig(BackendAPIConfig):
    """
    Google Drive API configuration.

    Environment Variables:
        GDRIVE_BASE_URL: Base URL (default: https://www.googleapis.com/drive/v3)
        GDRIVE_TIMEOUT_SECONDS: Request timeout
        GDRIVE_RETRY_ATTEMPTS: Number of retries
        GDRIVE_HEALTH_ENDPOINT: Health check endpoint
    """
    base_url: str = Field(default="https://www.googleapis.com/drive/v3")

    model_config = {"env_prefix": "GDRIVE_"}


class GCalendarConfig(BackendAPIConfig):
    """
    Google Calendar API configuration.

    Environment Variables:
        GCALENDAR_BASE_URL: Base URL (default: https://www.googleapis.com/calendar/v3)
        GCALENDAR_TIMEOUT_SECONDS: Request timeout
        GCALENDAR_RETRY_ATTEMPTS: Number of retries
        GCALENDAR_HEALTH_ENDPOINT: Health check endpoint
    """
    base_url: str = Field(default="https://www.googleapis.com/calendar/v3")

    model_config = {"env_prefix": "GCALENDAR_"}


class GmailConfig(BackendAPIConfig):
    """
    Gmail API configuration.

    Environment Variables:
        GMAIL_BASE_URL: Base URL (default: https://gmail.googleapis.com/gmail/v1)
        GMAIL_TIMEOUT_SECONDS: Request timeout
        GMAIL_RETRY_ATTEMPTS: Number of retries
        GMAIL_HEALTH_ENDPOINT: Health check endpoint
    """
    base_url: str = Field(default="https://gmail.googleapis.com/gmail/v1")

    model_config = {"env_prefix": "GMAIL_"}


# =============================================================================
# Gateway Settings
# =============================================================================


class GatewaySettings(BaseSettings):
    """
    Main Gateway service settings.

    Aggregates all backend configurations and gateway-level settings.

    Environment variables are resolved with GATEWAY_ prefix first (via
    Pydantic env_prefix), then explicit os.getenv fallbacks for vars that
    are set without the prefix in Cloud Run (CONTROL_PLANE_URL,
    GATEWAY_INTERNAL_TOKEN).
    """
    control_plane_url: str = Field(
        default_factory=lambda: os.getenv("CONTROL_PLANE_URL", "http://localhost:8000"),
    )
    notion: NotionConfig = Field(default_factory=NotionConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    hubspot: HubSpotConfig = Field(default_factory=HubSpotConfig)
    gdrive: GDriveConfig = Field(default_factory=GDriveConfig)
    gcalendar: GCalendarConfig = Field(default_factory=GCalendarConfig)
    gmail: GmailConfig = Field(default_factory=GmailConfig)
    max_connections_per_backend: int = Field(default=10)
    health_check_interval_seconds: float = Field(default=30.0)
    health_check_timeout_seconds: float = Field(default=5.0)
    gateway_internal_api_token: str = Field(
        default_factory=lambda: os.getenv(
            "GATEWAY_INTERNAL_API_TOKEN",
            os.getenv("GATEWAY_INTERNAL_TOKEN", "gateway-internal-secret-token"),
        ),
    )
    registry_refresh_interval: int = Field(default=60)
    registry_health_report_interval: int = Field(default=30)

    model_config = {
        "env_prefix": "GATEWAY_",
        "env_nested_delimiter": "__",
    }


# =============================================================================
# Singleton Instance
# =============================================================================


_settings: GatewaySettings | None = None


def get_settings() -> GatewaySettings:
    """
    Get the singleton GatewaySettings instance.

    Creates the instance on first call, subsequent calls return the same instance.
    This ensures consistent configuration throughout the application lifecycle.

    Returns:
        GatewaySettings instance

    Example:
        settings = get_settings()
        assert settings is get_settings()  # Same instance
    """
    global _settings
    if _settings is None:
        _settings = GatewaySettings()
    return _settings


def reset_settings() -> None:
    """
    Reset the singleton settings instance.

    Useful for testing to ensure clean state between tests.
    """
    global _settings
    _settings = None


# =============================================================================
# Helper Functions
# =============================================================================


def create_backend_config_from_settings(
    backend_id: str,
    config: BackendAPIConfig,
) -> BackendConfig:
    """
    Create a BackendConfig from a BackendAPIConfig.

    Maps the Pydantic settings to the dataclass used by BackendConnectionManager.

    Args:
        backend_id: Unique identifier for the backend (e.g., "notion")
        config: Backend API configuration from settings

    Returns:
        BackendConfig dataclass for use with BackendConnectionManager

    Example:
        settings = get_settings()
        notion_config = create_backend_config_from_settings(
            "notion", settings.notion
        )
        manager.register_backend(notion_config)
    """
    extra_headers: dict[str, str] = {}
    if config.version_header and config.api_version:
        extra_headers[config.version_header] = config.api_version

    return BackendConfig(
        backend_id=backend_id,
        base_url=config.base_url,
        health_endpoint=config.health_endpoint,
        timeout_seconds=config.timeout_seconds,
        retry_attempts=config.retry_attempts,
        retry_delay_seconds=config.retry_backoff_factor,
    )


def get_backend_extra_headers(config: BackendAPIConfig) -> dict[str, str]:
    """
    Get extra headers for a backend API configuration.

    Extracts headers like API version headers that need to be sent
    with each request to the backend.

    Args:
        config: Backend API configuration

    Returns:
        Dictionary of extra headers to include in requests
    """
    headers: dict[str, str] = {}
    if config.version_header and config.api_version:
        headers[config.version_header] = config.api_version
    return headers
