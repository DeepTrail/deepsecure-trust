"""
Unit tests for MCP Tool Definitions.

WS-J2: Tests to verify tool definitions align with Permission Mapper.

Tests cover:
- All Permission Mapper tools have definitions
- Tool definitions have required fields
- Backend tool counts match expectations
"""

import pytest

from app.mcp.tool_definitions import (
    NOTION_TOOLS,
    SLACK_TOOLS,
    populate_tool_cache,
    get_all_tool_definitions,
)
from app.mcp.permission_mapper import PermissionMapper
from app.mcp.tool_cache import ToolCache


# =============================================================================
# WS-J2: Alignment with Permission Mapper
# =============================================================================


class TestPermissionMapperAlignment:
    """Test that tool definitions align with Permission Mapper."""
    
    def test_all_notion_permission_mapper_tools_have_definitions(self):
        """Verify every Notion tool in Permission Mapper has a definition."""
        permission_mapper_tools = PermissionMapper.get_backend_tools("notion")
        defined_tools = [tool.name for tool in NOTION_TOOLS]
        
        for pm_tool in permission_mapper_tools:
            # Extract tool name without namespace (notion.search_pages -> search_pages)
            tool_name = pm_tool.split(".", 1)[1] if "." in pm_tool else pm_tool
            assert tool_name in defined_tools, \
                f"Permission Mapper tool '{pm_tool}' missing from NOTION_TOOLS"
    
    def test_all_slack_permission_mapper_tools_have_definitions(self):
        """Verify every Slack tool in Permission Mapper has a definition."""
        permission_mapper_tools = PermissionMapper.get_backend_tools("slack")
        defined_tools = [tool.name for tool in SLACK_TOOLS]
        
        for pm_tool in permission_mapper_tools:
            tool_name = pm_tool.split(".", 1)[1] if "." in pm_tool else pm_tool
            assert tool_name in defined_tools, \
                f"Permission Mapper tool '{pm_tool}' missing from SLACK_TOOLS"
    
class TestNotionToolDefinitions:
    """Tests for Notion tool definitions."""
    
    def test_notion_tool_count(self):
        """Test expected number of Notion tools."""
        assert len(NOTION_TOOLS) == 8, \
            f"Expected 8 Notion tools, got {len(NOTION_TOOLS)}"
    
    def test_notion_tools_have_required_fields(self):
        """Test all Notion tools have required fields."""
        for tool in NOTION_TOOLS:
            assert tool.name, f"Tool missing name"
            assert tool.description, f"Tool {tool.name} missing description"
            assert tool.inputSchema, f"Tool {tool.name} missing inputSchema"
            assert tool.inputSchema.get("type") == "object", \
                f"Tool {tool.name} inputSchema should be object type"
    
    def test_read_page_exists_not_get_page(self):
        """WS-J2: Verify 'read_page' exists (not 'get_page') to match Permission Mapper."""
        tool_names = [tool.name for tool in NOTION_TOOLS]
        assert "read_page" in tool_names, "'read_page' should exist to match Permission Mapper"
    
    def test_database_tools_exist(self):
        """WS-J2: Verify database tools exist."""
        tool_names = [tool.name for tool in NOTION_TOOLS]
        assert "list_databases" in tool_names
        assert "query_database" in tool_names


class TestSlackToolDefinitions:
    """Tests for Slack tool definitions."""
    
    def test_slack_tool_count(self):
        """Test expected number of Slack tools."""
        assert len(SLACK_TOOLS) == 7, \
            f"Expected 7 Slack tools, got {len(SLACK_TOOLS)}"
    
    def test_slack_tools_have_required_fields(self):
        """Test all Slack tools have required fields."""
        for tool in SLACK_TOOLS:
            assert tool.name, f"Tool missing name"
            assert tool.description, f"Tool {tool.name} missing description"
            assert tool.inputSchema, f"Tool {tool.name} missing inputSchema"
    
    def test_send_message_exists_not_post_message(self):
        """WS-J2: Verify 'send_message' exists (not 'post_message') to match Permission Mapper."""
        tool_names = [tool.name for tool in SLACK_TOOLS]
        assert "send_message" in tool_names, "'send_message' should exist to match Permission Mapper"
    
    def test_additional_slack_tools_exist(self):
        """WS-J2: Verify additional Slack tools exist."""
        tool_names = [tool.name for tool in SLACK_TOOLS]
        assert "join_channel" in tool_names
        assert "post_reaction" in tool_names
        assert "list_users" in tool_names


# =============================================================================
# Cache Population Tests
# =============================================================================


class TestCachePopulation:
    """Tests for populate_tool_cache function."""
    
    def test_populate_tool_cache(self):
        """Test that populate_tool_cache adds all backend tools."""
        cache = ToolCache(ttl_seconds=300)
        populate_tool_cache(cache)
        
        assert cache.is_cached("notion")
        assert cache.is_cached("slack")
    
    def test_get_all_tool_definitions_structure(self):
        """Test get_all_tool_definitions returns correct structure."""
        defs = get_all_tool_definitions()
        
        assert "notion" in defs
        assert "slack" in defs
        
        assert defs["notion"] == NOTION_TOOLS
        assert defs["slack"] == SLACK_TOOLS
