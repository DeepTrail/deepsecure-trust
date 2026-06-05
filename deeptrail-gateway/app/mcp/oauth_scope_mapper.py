"""Bidirectional OAuth scope ↔ DeepSecure permission mapping (gateway copy).

Mirrors ``deepsecure/_core/scope_mapper.py`` — services deploy independently.
"""

from __future__ import annotations

MCP_SCOPE_PREFIX = "mcp:"
BROAD_OAUTH_SCOPE = "mcp:tools"
WILDCARD_PERMISSION = "*:*"

CATEGORY_SCOPE_MAP: dict[str, list[str]] = {
    "mcp_tools": ["mcp:tools:list", "mcp:tools:call"],
    "mcp_resources": ["mcp:resources:list", "mcp:resources:read"],
    "mcp_prompts": ["mcp:prompts:list", "mcp:prompts:get"],
}

# Standard OIDC scopes — not mapped to DeepSecure permissions
OIDC_STANDARD_SCOPES = frozenset(
    {"openid", "profile", "email", "address", "phone", "offline_access"}
)


def permission_to_scope(permission: str) -> str:
    if permission == WILDCARD_PERMISSION:
        return BROAD_OAUTH_SCOPE
    if permission.startswith(MCP_SCOPE_PREFIX):
        return permission
    return f"{MCP_SCOPE_PREFIX}{permission}"


def scope_to_permission(scope: str) -> str:
    if scope == BROAD_OAUTH_SCOPE:
        return WILDCARD_PERMISSION
    if scope in CATEGORY_SCOPE_MAP:
        return scope
    if scope.startswith(MCP_SCOPE_PREFIX):
        return scope[len(MCP_SCOPE_PREFIX) :]
    return scope


def scopes_to_permissions(scopes: list[str]) -> list[str]:
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


def permissions_to_scopes(permissions: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for perm in permissions:
        scope = permission_to_scope(perm)
        if scope not in seen:
            seen.add(scope)
            result.append(scope)
    return result
