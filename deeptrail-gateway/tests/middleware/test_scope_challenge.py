"""Tests for scope-aware 403 responses (E2)."""

from app.middleware.jwt_validation import (
    build_insufficient_scope_body,
    build_insufficient_scope_header,
)


class TestInsufficientScopeHeaders:
    def test_www_authenticate_format(self):
        header = build_insufficient_scope_header(
            ["notion:pages:search", "notion:pages:create"]
        )
        assert 'error="insufficient_scope"' in header
        assert "mcp:notion:pages:search" in header
        assert "mcp:notion:pages:create" in header
        assert "resource_metadata=" in header

    def test_body_includes_scopes_and_request_id(self):
        body = build_insufficient_scope_body(
            ["notion:pages:search"],
            "Permission denied",
            request_id="req-abc",
        )
        assert body["error"] == "insufficient_scope"
        assert body["required_scopes"] == ["mcp:notion:pages:search"]
        assert body["request_id"] == "req-abc"
