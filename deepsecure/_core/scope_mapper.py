"""Bidirectional OAuth scope ↔ DeepSecure permission mapping.

Used by the SDK for authorization requests (permissions → scopes) and
step-up flows (scopes from WWW-Authenticate → permissions).

Convention:
  - OAuth scopes use ``mcp:`` prefix: ``mcp:notion:pages:search``
  - DeepSecure permissions omit prefix: ``notion:pages:search``
  - Wildcard ``*:*`` maps to broad ``mcp:tools`` scope
"""

from __future__ import annotations

MCP_SCOPE_PREFIX = "mcp:"
BROAD_OAUTH_SCOPE = "mcp:tools"
WILDCARD_PERMISSION = "*:*"

# Category scopes from Keycloak MCP realm (coarse-grained)
CATEGORY_SCOPE_MAP: dict[str, list[str]] = {
    "mcp_tools": ["mcp:tools:list", "mcp:tools:call"],
    "mcp_resources": ["mcp:resources:list", "mcp:resources:read"],
    "mcp_prompts": ["mcp:prompts:list", "mcp:prompts:get"],
}

OIDC_STANDARD_SCOPES = frozenset(
    {"openid", "profile", "email", "address", "phone", "offline_access"}
)


def permission_to_scope(permission: str) -> str:
    """Map a DeepSecure permission to an OAuth scope string."""
    if permission == WILDCARD_PERMISSION:
        return BROAD_OAUTH_SCOPE
    if permission.startswith(MCP_SCOPE_PREFIX):
        return permission
    return f"{MCP_SCOPE_PREFIX}{permission}"


def scope_to_permission(scope: str) -> str:
    """Map an OAuth scope to a DeepSecure permission string."""
    if scope == BROAD_OAUTH_SCOPE:
        return WILDCARD_PERMISSION
    if scope in CATEGORY_SCOPE_MAP:
        # Category scopes don't map to a single permission
        return scope
    if scope.startswith(MCP_SCOPE_PREFIX):
        return scope[len(MCP_SCOPE_PREFIX) :]
    return scope


def permissions_to_scopes(permissions: list[str]) -> list[str]:
    """Convert permission list to deduplicated OAuth scopes."""
    seen: set[str] = set()
    result: list[str] = []
    for perm in permissions:
        scope = permission_to_scope(perm)
        if scope not in seen:
            seen.add(scope)
            result.append(scope)
    return result


def scopes_to_permissions(scopes: list[str]) -> list[str]:
    """Convert OAuth scopes to deduplicated DeepSecure permissions."""
    seen: set[str] = set()
    result: list[str] = []
    for scope in scopes:
        if scope in OIDC_STANDARD_SCOPES:
            continue
        if scope in CATEGORY_SCOPE_MAP:
            for perm in CATEGORY_SCOPE_MAP[scope]:
                if perm not in seen:
                    seen.add(perm)
                    result.append(perm)
            continue
        if scope.startswith(MCP_SCOPE_PREFIX):
            perm = scope_to_permission(scope)
            if perm not in seen:
                seen.add(perm)
                result.append(perm)
    return result


def merge_scopes(existing: list[str], additional: list[str]) -> list[str]:
    """Merge scope lists preserving order, deduplicating."""
    seen = set(existing)
    merged = list(existing)
    for scope in additional:
        if scope not in seen:
            seen.add(scope)
            merged.append(scope)
    return merged
