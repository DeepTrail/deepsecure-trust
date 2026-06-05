"""
Protected Resource Metadata (RFC 9728) endpoints.

Enables standard MCP clients to discover:
- The authorization servers that issue tokens for this resource
- Supported OAuth scopes
- Bearer token methods

References:
    https://datatracker.ietf.org/doc/html/rfc9728
    https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
"""

import logging
import os

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["well-known"])

_GATEWAY_RESOURCE = os.environ.get(
    "GATEWAY_CANONICAL_URL", "https://gateway.deepsecure.one/mcp"
)

_KEYCLOAK_ISSUER_URL = os.environ.get(
    "KEYCLOAK_ISSUER_URL",
    os.environ.get("KEYCLOAK_URL", "http://localhost:8080"),
)
_KEYCLOAK_REALM = os.environ.get("KEYCLOAK_MCP_REALM", "mcp")

_AUTHORIZATION_SERVER = f"{_KEYCLOAK_ISSUER_URL}/realms/{_KEYCLOAK_REALM}"

MCP_SCOPES_SUPPORTED = [
    "mcp:tools",
    "mcp:resources",
    "mcp:prompts",
]

BEARER_METHODS_SUPPORTED = [
    "header",
]


def _build_prm_document() -> dict:
    """Build the Protected Resource Metadata document per RFC 9728 §3."""
    return {
        "resource": _GATEWAY_RESOURCE,
        "authorization_servers": [_AUTHORIZATION_SERVER],
        "scopes_supported": MCP_SCOPES_SUPPORTED,
        "bearer_methods_supported": BEARER_METHODS_SUPPORTED,
    }


@router.get(
    "/.well-known/oauth-protected-resource",
    summary="Protected Resource Metadata (RFC 9728)",
)
async def protected_resource_metadata():
    """Return PRM document for OAuth discovery by MCP clients."""
    return _build_prm_document()


@router.get(
    "/.well-known/oauth-protected-resource/mcp",
    summary="Path-based PRM for MCP resource",
)
async def protected_resource_metadata_mcp():
    """Path-based PRM per MCP spec — same content, sub-resource path."""
    return _build_prm_document()
