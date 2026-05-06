"""IdP configuration for OIDC identity provider integration.

Supports environment-variable-based configuration for swapping between
identity providers (Keycloak dev, Google Workspace, Okta/Entra production).

Environment variables (primary / Keycloak):
    IDP_PROVIDER: Provider type (keycloak, okta, entra, google). Default: keycloak
    IDP_ISSUER_URL: OIDC issuer URL
    IDP_CLIENT_ID: OIDC client ID registered at the IdP
    IDP_CLIENT_SECRET: OIDC client secret (optional for public clients)
    IDP_REALM: Keycloak realm name (only for keycloak provider)
    IDP_REDIRECT_URI: Default redirect URI after authentication
    IDP_HD: Google Workspace hosted domain for login restriction (optional)
    IDP_FETCH_GROUPS: When true and provider is Google, fetch user groups from
        Directory API during SSO callback. Default: false

Per-provider overrides (used when IdP differs from IDP_PROVIDER):
    GOOGLE_CLIENT_ID: Google OAuth client ID
    GOOGLE_CLIENT_SECRET: Google OAuth client secret
    GOOGLE_HD: Google Workspace hosted domain (e.g. deeptrail.com)
"""

import os
from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings


class IdPProviderType(str, Enum):
    KEYCLOAK = "keycloak"
    OKTA = "okta"
    ENTRA = "entra"
    GOOGLE = "google"


class IdPConfig(BaseSettings):
    """IdP configuration loaded from environment variables."""

    provider: IdPProviderType = Field(
        default=IdPProviderType.KEYCLOAK,
        alias="IDP_PROVIDER",
    )
    issuer_url: str = Field(
        default="http://localhost:8080/realms/deepsecure",
        alias="IDP_ISSUER_URL",
    )
    client_id: str = Field(
        default="deepsecure-control",
        alias="IDP_CLIENT_ID",
    )
    client_secret: str | None = Field(
        default=None,
        alias="IDP_CLIENT_SECRET",
    )
    realm: str = Field(
        default="deepsecure",
        alias="IDP_REALM",
    )
    browser_url: str | None = Field(
        default=None,
        alias="IDP_BROWSER_URL",
        description="Browser-facing IdP URL. Required when issuer_url uses a Docker-internal "
        "hostname (e.g. http://keycloak:8080) that browsers cannot resolve. "
        "Defaults to issuer_url when not set.",
    )
    redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/sso/callback",
        alias="IDP_REDIRECT_URI",
    )
    hd: str | None = Field(
        default=None,
        alias="IDP_HD",
    )
    fetch_groups: bool = Field(
        default=False,
        alias="IDP_FETCH_GROUPS",
        description="When true and provider is Google, fetch user groups from Directory API during SSO callback",
    )

    model_config = {
        "env_prefix": "",
        "case_sensitive": True,
        "populate_by_name": True,
    }


def get_idp_config_for_provider(idp: str) -> IdPConfig:
    """Return an IdPConfig resolved for a specific provider.

    When the requested provider differs from the primary IDP_PROVIDER,
    applies per-provider env var overrides (e.g. GOOGLE_CLIENT_ID).
    """
    config = IdPConfig()

    if idp == config.provider.value:
        return config

    config.provider = IdPProviderType(idp)

    if idp == "google":
        google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
        google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        google_hd = os.environ.get("GOOGLE_HD")

        if google_client_id:
            config.client_id = google_client_id
        if google_client_secret:
            config.client_secret = google_client_secret
        if google_hd:
            config.hd = google_hd

        config.issuer_url = "https://accounts.google.com"
        config.fetch_groups = os.environ.get("IDP_FETCH_GROUPS", "").lower() in (
            "true",
            "1",
            "yes",
        )

    return config
