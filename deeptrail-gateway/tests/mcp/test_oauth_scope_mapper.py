"""Tests for gateway OAuth scope mapper (E4)."""

from app.mcp.oauth_scope_mapper import (
    permission_to_scope,
    scopes_to_permissions,
)


class TestOAuthScopeMapper:
    def test_fine_grained_scope(self):
        assert permission_to_scope("slack:messages:send") == "mcp:slack:messages:send"

    def test_oauth_token_scopes_to_permissions(self):
        perms = scopes_to_permissions(
            ["mcp:notion:pages:search", "mcp_tools"]
        )
        assert "notion:pages:search" in perms
        assert "mcp:tools:call" in perms
