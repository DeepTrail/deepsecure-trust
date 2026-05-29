"""Tests for multi-user tools/call runtime (WS-C5→C8).

Validates:
  - _extract_user_id extracts user_id from MCP _meta field
  - Missing _meta returns None (backward compatible)
  - Invalid _meta types return None (safe fallback)
"""

import pytest

from app.mcp.handlers.tools_call import _extract_user_id


class TestExtractUserId:
    def test_extracts_user_id_from_meta(self):
        params = {
            "name": "notion.search_pages",
            "arguments": {"query": "test"},
            "_meta": {"user_id": "sarah@acme.com"},
        }
        assert _extract_user_id(params) == "sarah@acme.com"

    def test_returns_none_when_no_meta(self):
        params = {"name": "notion.search_pages", "arguments": {}}
        assert _extract_user_id(params) is None

    def test_returns_none_when_meta_has_no_user_id(self):
        params = {
            "name": "notion.search_pages",
            "arguments": {},
            "_meta": {"other_field": "value"},
        }
        assert _extract_user_id(params) is None

    def test_returns_none_when_meta_is_not_dict(self):
        params = {
            "name": "notion.search_pages",
            "arguments": {},
            "_meta": "invalid",
        }
        assert _extract_user_id(params) is None

    def test_returns_none_when_meta_is_none(self):
        params = {
            "name": "notion.search_pages",
            "arguments": {},
            "_meta": None,
        }
        assert _extract_user_id(params) is None

    def test_returns_none_for_empty_meta(self):
        params = {
            "name": "notion.search_pages",
            "arguments": {},
            "_meta": {},
        }
        assert _extract_user_id(params) is None

    def test_different_user_ids(self):
        for user_id in ["victor@acme.com", "admin@corp.io", "user-123"]:
            params = {"_meta": {"user_id": user_id}}
            assert _extract_user_id(params) == user_id
