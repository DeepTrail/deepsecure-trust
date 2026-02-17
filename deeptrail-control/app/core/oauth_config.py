"""OAuth Provider Configuration Module.

Provides externalized OAuth configuration via environment variables.
Each provider has its own config class with appropriate defaults.

Environment Variables:
    OAUTH_REDIRECT_BASE_URL: Base URL for OAuth callbacks
    OAUTH_STATE_TTL_SECONDS: State token TTL in seconds
    NOTION_OAUTH_CLIENT_ID: Notion app client ID
    NOTION_OAUTH_CLIENT_SECRET: Notion app client secret
    SLACK_OAUTH_CLIENT_ID: Slack app client ID
    SLACK_OAUTH_CLIENT_SECRET: Slack app client secret
    HUBSPOT_OAUTH_CLIENT_ID: HubSpot app client ID
    HUBSPOT_OAUTH_CLIENT_SECRET: HubSpot app client secret

Usage:
    from app.core.oauth_config import get_oauth_settings

    settings = get_oauth_settings()
    notion_auth_url = settings.notion.authorization_url
    slack_scopes = settings.slack.scopes
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OAuthProviderConfig(BaseSettings):
    """Base configuration for a single OAuth provider.

    Attributes:
        client_id: OAuth application client ID.
        client_secret: OAuth application client secret.
        authorization_url: Provider's OAuth authorization endpoint.
        token_url: Provider's OAuth token exchange endpoint.
        scopes: Default scopes to request during authorization.
        redirect_uri: OAuth callback URI (usually set per-request).
        uses_pkce: Whether this provider requires PKCE (RFC 7636).
    """

    client_id: str = ""
    client_secret: str = ""
    authorization_url: str
    token_url: str
    scopes: list[str] = Field(default_factory=list)
    redirect_uri: str = ""
    uses_pkce: bool = False


class NotionOAuthConfig(OAuthProviderConfig):
    """Notion OAuth configuration.

    Notion requires PKCE for public OAuth integrations.
    Scopes are managed via the Notion integration settings,
    not via the OAuth URL parameters.

    Docs: https://developers.notion.com/docs/authorization
    """

    model_config = SettingsConfigDict(env_prefix="NOTION_OAUTH_")

    client_id: str = Field(default="")
    client_secret: str = Field(default="")
    authorization_url: str = "https://api.notion.com/v1/oauth/authorize"
    token_url: str = "https://api.notion.com/v1/oauth/token"
    scopes: list[str] = Field(default_factory=list)  # Notion manages scopes via integration
    uses_pkce: bool = True


class SlackOAuthConfig(OAuthProviderConfig):
    """Slack OAuth configuration.

    Slack uses OAuth 2.0 v2 for bot and user tokens.
    Scopes are specified in the authorization URL.

    Docs: https://api.slack.com/authentication/oauth-v2
    """

    model_config = SettingsConfigDict(env_prefix="SLACK_OAUTH_")

    client_id: str = Field(default="")
    client_secret: str = Field(default="")
    authorization_url: str = "https://slack.com/oauth/v2/authorize"
    token_url: str = "https://slack.com/api/oauth.v2.access"
    scopes: list[str] = Field(
        default=["channels:read", "channels:history", "chat:write", "users:read"]
    )
    uses_pkce: bool = False


class HubSpotOAuthConfig(OAuthProviderConfig):
    """HubSpot OAuth configuration.

    HubSpot uses standard OAuth 2.0.
    Scopes are specified in the authorization URL.

    Docs: https://developers.hubspot.com/docs/api/oauth-quickstart-guide
    """

    model_config = SettingsConfigDict(env_prefix="HUBSPOT_OAUTH_")

    client_id: str = Field(default="")
    client_secret: str = Field(default="")
    authorization_url: str = "https://app.hubspot.com/oauth/authorize"
    token_url: str = "https://api.hubapi.com/oauth/v1/token"
    scopes: list[str] = Field(
        default=["crm.objects.contacts.read", "crm.objects.deals.read"]
    )
    uses_pkce: bool = False


class OAuthSettings(BaseSettings):
    """Main OAuth configuration container.

    Aggregates all provider configurations and global OAuth settings.

    Attributes:
        redirect_base_url: Base URL for OAuth callback redirects.
        state_ttl_seconds: How long state tokens remain valid (default 10 min).
        notion: Notion OAuth provider configuration.
        slack: Slack OAuth provider configuration.
        hubspot: HubSpot OAuth provider configuration.
    """

    model_config = SettingsConfigDict(env_prefix="OAUTH_")

    redirect_base_url: str = Field(default="http://localhost:8000")
    state_ttl_seconds: int = Field(default=600)
    notion: NotionOAuthConfig = Field(default_factory=NotionOAuthConfig)
    slack: SlackOAuthConfig = Field(default_factory=SlackOAuthConfig)
    hubspot: HubSpotOAuthConfig = Field(default_factory=HubSpotOAuthConfig)


# Singleton instance for consistent configuration access
_oauth_settings: OAuthSettings | None = None


def get_oauth_settings() -> OAuthSettings:
    """Get OAuth settings singleton.

    Returns a cached OAuthSettings instance. Configuration is loaded
    from environment variables on first access.

    Returns:
        OAuthSettings: Cached OAuth configuration.

    Example:
        settings = get_oauth_settings()
        print(settings.notion.authorization_url)
    """
    global _oauth_settings
    if _oauth_settings is None:
        _oauth_settings = OAuthSettings()
    return _oauth_settings


def reset_oauth_settings() -> None:
    """Reset OAuth settings singleton (for testing).

    Clears the cached OAuthSettings instance so it will be
    reloaded on next access. Use this in tests when you need
    to change environment variables and have them take effect.
    """
    global _oauth_settings
    _oauth_settings = None
