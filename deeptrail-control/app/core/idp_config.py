"""IdP configuration for OIDC identity provider integration.

Supports environment-variable-based configuration for swapping between
identity providers (Keycloak dev, Okta/Entra production).

Environment variables:
    IDP_PROVIDER: Provider type (keycloak, okta, entra). Default: keycloak
    IDP_ISSUER_URL: OIDC issuer URL
    IDP_CLIENT_ID: OIDC client ID registered at the IdP
    IDP_CLIENT_SECRET: OIDC client secret (optional for public clients)
    IDP_REALM: Keycloak realm name (only for keycloak provider)
    IDP_REDIRECT_URI: Default redirect URI after authentication
"""

from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings


class IdPProviderType(str, Enum):
    KEYCLOAK = "keycloak"
    OKTA = "okta"
    ENTRA = "entra"


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

    model_config = {
        "env_prefix": "",
        "case_sensitive": True,
        "populate_by_name": True,
    }
