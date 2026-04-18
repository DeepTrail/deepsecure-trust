"""
Unit tests for MCP Permission Mapper.

Tests cover:
- get_permission() for known and unknown tools
- infer_permission() for pattern-based inference
- is_tool_permitted() permission checks
- filter_tools() filtering
- Backend-specific queries
- Dynamic mapping management
"""

import pytest

from app.mcp.permission_mapper import PermissionMapper


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_mappings():
    """Reset any dynamic mappings after each test."""
    # Store original mappings
    original = dict(PermissionMapper.TOOL_TO_PERMISSION)
    yield
    # Restore original mappings
    PermissionMapper.TOOL_TO_PERMISSION = original
    PermissionMapper.PERMISSION_TO_TOOLS = {}


# =============================================================================
# Test get_permission
# =============================================================================


class TestGetPermission:
    """Tests for get_permission method."""
    
    def test_known_notion_tools(self):
        """Test getting permissions for known Notion tools."""
        assert PermissionMapper.get_permission("notion.search_pages") == "notion:pages:search"
        assert PermissionMapper.get_permission("notion.read_page") == "notion:pages:read"
        assert PermissionMapper.get_permission("notion.create_page") == "notion:pages:create"
        assert PermissionMapper.get_permission("notion.update_page") == "notion:pages:update"
        assert PermissionMapper.get_permission("notion.delete_page") == "notion:pages:delete"
    
    def test_known_slack_tools(self):
        """Test getting permissions for known Slack tools."""
        assert PermissionMapper.get_permission("slack.search_messages") == "slack:messages:search"
        assert PermissionMapper.get_permission("slack.send_message") == "slack:messages:send"
        assert PermissionMapper.get_permission("slack.list_channels") == "slack:channels:list"
        assert PermissionMapper.get_permission("slack.join_channel") == "slack:channels:join"
    
    def test_known_hubspot_tools(self):
        """Test getting permissions for known HubSpot tools."""
        assert PermissionMapper.get_permission("hubspot.get_contact") == "hubspot:contacts:read"
        assert PermissionMapper.get_permission("hubspot.list_deals") == "hubspot:deals:list"
        assert PermissionMapper.get_permission("hubspot.create_deal") == "hubspot:deals:create"
    
    def test_unknown_tool_returns_none(self):
        """Test that unknown tools return None."""
        assert PermissionMapper.get_permission("unknown.tool") is None
        assert PermissionMapper.get_permission("notion.unknown_action") is None
        assert PermissionMapper.get_permission("") is None


# =============================================================================
# Test infer_permission
# =============================================================================


class TestInferPermission:
    """Tests for infer_permission method."""
    
    def test_returns_static_mapping_first(self):
        """Test that static mapping takes precedence over inference."""
        # This is in the static mapping
        perm = PermissionMapper.infer_permission("notion.search_pages")
        assert perm == "notion:pages:search"
    
    def test_infers_action_resource_pattern(self):
        """Test inference for backend.action_resource pattern."""
        # Not in static mapping, should infer
        perm = PermissionMapper.infer_permission("github.list_repos")
        assert perm == "github:repos:list"
        
        perm = PermissionMapper.infer_permission("gitlab.create_project")
        assert perm == "gitlab:project:create"
    
    def test_cannot_infer_without_underscore(self):
        """Test that tools without underscore cannot be inferred."""
        perm = PermissionMapper.infer_permission("unknown.singletool")
        assert perm is None
    
    def test_cannot_infer_without_dot(self):
        """Test that tools without namespace separator cannot be inferred."""
        perm = PermissionMapper.infer_permission("notool")
        assert perm is None


# =============================================================================
# Test is_tool_permitted
# =============================================================================


class TestIsToolPermitted:
    """Tests for is_tool_permitted method."""
    
    def test_permitted_tool(self):
        """Test that tool with matching permission is permitted."""
        permissions = ["notion:pages:search", "slack:channels:list"]
        
        assert PermissionMapper.is_tool_permitted(
            "notion.search_pages", permissions
        ) is True
        
        assert PermissionMapper.is_tool_permitted(
            "slack.list_channels", permissions
        ) is True
    
    def test_not_permitted_tool(self):
        """Test that tool without matching permission is denied."""
        permissions = ["notion:pages:search"]
        
        # Different action
        assert PermissionMapper.is_tool_permitted(
            "notion.create_page", permissions
        ) is False
        
        # Different backend
        assert PermissionMapper.is_tool_permitted(
            "slack.list_channels", permissions
        ) is False
    
    def test_unknown_tool_denied_fail_closed(self):
        """Test that unknown tools are denied (fail-closed)."""
        permissions = ["notion:pages:search", "slack:channels:list"]
        
        assert PermissionMapper.is_tool_permitted(
            "unknown.tool", permissions
        ) is False
    
    def test_empty_permissions_denies_all(self):
        """Test that empty permissions list denies all tools."""
        assert PermissionMapper.is_tool_permitted(
            "notion.search_pages", []
        ) is False
    
    def test_wildcard_permission_not_supported(self):
        """Test that wildcard permissions are not supported (explicit only)."""
        permissions = ["notion:*:*"]  # Wildcard not supported
        
        # Should not match - we don't support wildcards
        assert PermissionMapper.is_tool_permitted(
            "notion.search_pages", permissions
        ) is False


# =============================================================================
# Test filter_tools
# =============================================================================


class TestFilterTools:
    """Tests for filter_tools method."""
    
    def test_filters_to_permitted_only(self):
        """Test that only permitted tools are returned."""
        tools = [
            {"name": "notion.search_pages", "description": "Search"},
            {"name": "notion.create_page", "description": "Create"},
            {"name": "slack.list_channels", "description": "List"},
            {"name": "slack.send_message", "description": "Send"},
        ]
        permissions = ["notion:pages:search", "slack:channels:list"]
        
        filtered = PermissionMapper.filter_tools(tools, permissions)
        
        names = [t["name"] for t in filtered]
        assert "notion.search_pages" in names
        assert "slack.list_channels" in names
        assert "notion.create_page" not in names
        assert "slack.send_message" not in names
    
    def test_empty_permissions_returns_empty(self):
        """Test that empty permissions returns empty list."""
        tools = [
            {"name": "notion.search_pages"},
            {"name": "slack.list_channels"},
        ]
        
        filtered = PermissionMapper.filter_tools(tools, [])
        
        assert filtered == []
    
    def test_empty_tools_returns_empty(self):
        """Test that empty tools list returns empty."""
        permissions = ["notion:pages:search"]
        
        filtered = PermissionMapper.filter_tools([], permissions)
        
        assert filtered == []
    
    def test_preserves_tool_schema(self):
        """Test that full tool schema is preserved."""
        tools = [
            {
                "name": "notion.search_pages",
                "description": "Search pages",
                "inputSchema": {"type": "object"},
            },
        ]
        permissions = ["notion:pages:search"]
        
        filtered = PermissionMapper.filter_tools(tools, permissions)
        
        assert len(filtered) == 1
        assert filtered[0]["description"] == "Search pages"
        assert filtered[0]["inputSchema"] == {"type": "object"}
    
    def test_handles_tools_without_name(self):
        """Test graceful handling of tools without name field."""
        tools = [
            {"description": "No name"},
            {"name": "notion.search_pages"},
        ]
        permissions = ["notion:pages:search"]
        
        filtered = PermissionMapper.filter_tools(tools, permissions)
        
        # Tool without name should be filtered out
        assert len(filtered) == 1
        assert filtered[0]["name"] == "notion.search_pages"


# =============================================================================
# Test Backend Queries
# =============================================================================


class TestBackendQueries:
    """Tests for backend-specific query methods."""
    
    def test_get_backend_permissions(self):
        """Test getting all permissions for a backend."""
        notion_perms = PermissionMapper.get_backend_permissions("notion")
        
        assert "notion:pages:search" in notion_perms
        assert "notion:pages:read" in notion_perms
        assert "slack:channels:list" not in notion_perms
    
    def test_get_backend_tools(self):
        """Test getting all tools for a backend."""
        slack_tools = PermissionMapper.get_backend_tools("slack")
        
        assert "slack.search_messages" in slack_tools
        assert "slack.send_message" in slack_tools
        assert "notion.search_pages" not in slack_tools
    
    def test_get_all_permissions(self):
        """Test getting all known permissions."""
        all_perms = PermissionMapper.get_all_permissions()
        
        assert "notion:pages:search" in all_perms
        assert "slack:channels:list" in all_perms
        assert "hubspot:contacts:read" in all_perms
    
    def test_get_all_tools(self):
        """Test getting all known tools."""
        all_tools = PermissionMapper.get_all_tools()
        
        assert "notion.search_pages" in all_tools
        assert "slack.list_channels" in all_tools
        assert "hubspot.get_contact" in all_tools
    
    def test_get_all_tools_for_permission(self):
        """Test getting tools that require a specific permission."""
        tools = PermissionMapper.get_all_tools_for_permission("notion:pages:search")
        
        assert "notion.search_pages" in tools


# =============================================================================
# Test Dynamic Mapping
# =============================================================================


class TestDynamicMapping:
    """Tests for dynamic mapping management."""
    
    def test_add_mapping(self):
        """Test adding a new mapping."""
        PermissionMapper.add_mapping("custom.new_tool", "custom:tools:new")
        
        assert PermissionMapper.get_permission("custom.new_tool") == "custom:tools:new"
    
    def test_add_mapping_overrides_existing(self):
        """Test that add_mapping can override existing mapping."""
        original = PermissionMapper.get_permission("notion.search_pages")
        
        PermissionMapper.add_mapping("notion.search_pages", "notion:pages:full_search")
        
        assert PermissionMapper.get_permission("notion.search_pages") == "notion:pages:full_search"
    
    def test_remove_mapping(self):
        """Test removing a mapping."""
        # Add then remove
        PermissionMapper.add_mapping("temp.tool", "temp:action")
        assert PermissionMapper.get_permission("temp.tool") == "temp:action"
        
        result = PermissionMapper.remove_mapping("temp.tool")
        
        assert result is True
        assert PermissionMapper.get_permission("temp.tool") is None
    
    def test_remove_nonexistent_returns_false(self):
        """Test removing non-existent mapping returns False."""
        result = PermissionMapper.remove_mapping("nonexistent.tool")
        
        assert result is False


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_tool_name(self):
        """Test handling of empty tool name."""
        assert PermissionMapper.get_permission("") is None
        assert PermissionMapper.is_tool_permitted("", []) is False
    
    def test_tool_name_with_multiple_dots(self):
        """Test tool name with multiple dots."""
        # Add a mapping with multiple dots
        PermissionMapper.add_mapping("backend.sub.tool", "backend:sub:tool")
        
        assert PermissionMapper.get_permission("backend.sub.tool") == "backend:sub:tool"
    
    def test_permission_with_special_characters(self):
        """Test handling permissions with special characters."""
        # Add mapping with special chars
        PermissionMapper.add_mapping("api_v2.get_data", "api_v2:data:get")
        
        assert PermissionMapper.get_permission("api_v2.get_data") == "api_v2:data:get"
    
    def test_case_sensitivity(self):
        """Test that tool names are case-sensitive."""
        assert PermissionMapper.get_permission("Notion.search_pages") is None
        assert PermissionMapper.get_permission("notion.Search_pages") is None


# =============================================================================
# WS-D5: Google Workspace Backend Mappings
# =============================================================================


class TestGooglePermissionMappings:
    """Tests for WS-D5 Google Workspace tool→permission mappings.

    Verifies that gdrive, gcalendar, and gmail tools are correctly mapped to
    the permission strings defined in the design doc and matching the control
    plane's ScopeMapper (WS-C1).
    """

    GDRIVE_MAPPINGS = {
        "gdrive.search_files": "gdrive:files:search",
        "gdrive.read_file": "gdrive:files:read",
        "gdrive.list_files": "gdrive:files:list",
        "gdrive.get_file_metadata": "gdrive:files:metadata",
    }

    GCALENDAR_MAPPINGS = {
        "gcalendar.list_calendars": "gcalendar:calendars:list",
        "gcalendar.list_events": "gcalendar:events:list",
        "gcalendar.read_event": "gcalendar:events:read",
        "gcalendar.search_events": "gcalendar:events:search",
    }

    GMAIL_MAPPINGS = {
        "gmail.list_messages": "gmail:messages:list",
        "gmail.read_message": "gmail:messages:read",
        "gmail.search_messages": "gmail:messages:search",
        "gmail.list_labels": "gmail:labels:list",
    }

    def test_gdrive_tools_resolve_correctly(self):
        for tool, expected in self.GDRIVE_MAPPINGS.items():
            assert PermissionMapper.get_permission(tool) == expected, tool

    def test_gcalendar_tools_resolve_correctly(self):
        for tool, expected in self.GCALENDAR_MAPPINGS.items():
            assert PermissionMapper.get_permission(tool) == expected, tool

    def test_gmail_tools_resolve_correctly(self):
        for tool, expected in self.GMAIL_MAPPINGS.items():
            assert PermissionMapper.get_permission(tool) == expected, tool

    def test_gdrive_backend_tool_count(self):
        tools = PermissionMapper.get_backend_tools("gdrive")
        assert len(tools) == 4, f"Expected 4 gdrive tools, got {tools}"

    def test_gcalendar_backend_tool_count(self):
        tools = PermissionMapper.get_backend_tools("gcalendar")
        assert len(tools) == 4, f"Expected 4 gcalendar tools, got {tools}"

    def test_gmail_backend_tool_count(self):
        tools = PermissionMapper.get_backend_tools("gmail")
        assert len(tools) == 4, f"Expected 4 gmail tools, got {tools}"

    def test_filter_gdrive_tools_includes_matched(self):
        tools = [{"name": t} for t in self.GDRIVE_MAPPINGS.keys()]
        filtered = PermissionMapper.filter_tools(
            tools, ["gdrive:files:search", "gdrive:files:read"]
        )
        names = {t["name"] for t in filtered}
        assert "gdrive.search_files" in names
        assert "gdrive.read_file" in names
        assert "gdrive.list_files" not in names
        assert "gdrive.get_file_metadata" not in names

    def test_unknown_gdrive_tool_denied_fail_closed(self):
        """Security: unknown gdrive tool must be denied even with valid gdrive permission."""
        assert not PermissionMapper.is_tool_permitted(
            "gdrive.unknown_tool", ["gdrive:files:search"]
        )

    def test_unknown_gcalendar_tool_denied_fail_closed(self):
        assert not PermissionMapper.is_tool_permitted(
            "gcalendar.delete_event", ["gcalendar:events:read"]
        )

    def test_unknown_gmail_tool_denied_fail_closed(self):
        assert not PermissionMapper.is_tool_permitted(
            "gmail.send_message", ["gmail:messages:read"]
        )

    def test_cross_backend_permission_does_not_grant_google_tools(self):
        """A notion permission must never grant a gdrive tool."""
        assert not PermissionMapper.is_tool_permitted(
            "gdrive.search_files", ["notion:pages:search"]
        )
        assert not PermissionMapper.is_tool_permitted(
            "gmail.read_message", ["slack:messages:read"]
        )

    def test_existing_backend_mappings_unchanged(self):
        """Regression: notion/slack/hubspot mappings must remain intact."""
        assert PermissionMapper.get_permission("notion.search_pages") == "notion:pages:search"
        assert PermissionMapper.get_permission("slack.send_message") == "slack:messages:send"
        assert PermissionMapper.get_permission("hubspot.get_contact") == "hubspot:contacts:read"

    def test_total_google_tools_in_registry(self):
        """All 12 Google tool entries must be present."""
        all_tools = PermissionMapper.get_all_tools()
        google_tools = [t for t in all_tools if t.startswith(("gdrive.", "gcalendar.", "gmail."))]
        assert len(google_tools) == 12, f"Expected 12 Google tools, got {len(google_tools)}: {google_tools}"
