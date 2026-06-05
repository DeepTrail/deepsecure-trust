"""Tests for SDK bidirectional scope mapper (E4)."""

from deepsecure._core.scope_mapper import (
    merge_scopes,
    permission_to_scope,
    permissions_to_scopes,
    scope_to_permission,
    scopes_to_permissions,
)


class TestPermissionToScope:
    def test_adds_mcp_prefix(self):
        assert permission_to_scope("notion:pages:search") == "mcp:notion:pages:search"

    def test_wildcard_maps_to_mcp_tools(self):
        assert permission_to_scope("*:*") == "mcp:tools"

    def test_idempotent_for_prefixed(self):
        assert permission_to_scope("mcp:tools") == "mcp:tools"


class TestScopeToPermission:
    def test_strips_mcp_prefix(self):
        assert scope_to_permission("mcp:notion:pages:search") == "notion:pages:search"

    def test_mcp_tools_maps_to_wildcard(self):
        assert scope_to_permission("mcp:tools") == "*:*"


class TestBatchMapping:
    def test_permissions_to_scopes_dedupes(self):
        scopes = permissions_to_scopes(
            ["notion:pages:search", "notion:pages:search"]
        )
        assert scopes == ["mcp:notion:pages:search"]

    def test_scopes_to_permissions_category(self):
        perms = scopes_to_permissions(["mcp_tools"])
        assert "mcp:tools:list" in perms
        assert "mcp:tools:call" in perms

    def test_merge_scopes(self):
        merged = merge_scopes(["mcp:a"], ["mcp:b", "mcp:a"])
        assert merged == ["mcp:a", "mcp:b"]
