"""OIDC identity provider implementations.

Currently available:
- GoogleProvider: Google Workspace / Google account OIDC provider
- KeycloakProvider: Dev-time and default OIDC provider

Future (raise NotImplementedError):
- OktaProvider: Enterprise SSO via Okta
- EntraIDProvider: Enterprise SSO via Microsoft Entra ID
"""

from app.services.providers.google import GoogleProvider
from app.services.providers.keycloak import KeycloakProvider

__all__ = ["GoogleProvider", "KeycloakProvider"]
