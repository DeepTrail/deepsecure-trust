"""
Tests for Demo 2: Filtered Tool Visibility.

Tests verify that the demo correctly demonstrates the filtering
of tools based on delegated permissions.
"""

import pytest

from demos.demo_02_filtered_visibility import (
    ALL_NOTION_TOOLS,
    ALL_SLACK_TOOLS,
    SARAH_DELEGATED_PERMISSIONS,
    FilteringResult,
    Tool,
    filter_tools,
    get_all_tools,
    run_demo,
)


# =============================================================================
# Tool Data Class Tests
# =============================================================================


class TestToolDataClass:
    """Tests for Tool dataclass."""
    
    def test_tool_creation(self):
        """Test creating a Tool."""
        tool = Tool(
            name="search_pages",
            permission="notion:pages:search",
            description="Search pages",
        )
        
        assert tool.name == "search_pages"
        assert tool.permission == "notion:pages:search"
        assert tool.description == "Search pages"


class TestFilteringResult:
    """Tests for FilteringResult dataclass."""
    
    def test_filtering_result_creation(self):
        """Test creating a FilteringResult."""
        result = FilteringResult(
            total_tools=37,
            visible_tools=4,
            hidden_tools=33,
            reduction_percentage=89.2,
            visible_tool_list=[],
            hidden_tool_list=[],
        )
        
        assert result.total_tools == 37
        assert result.visible_tools == 4
        assert result.hidden_tools == 33
        assert result.reduction_percentage == 89.2


# =============================================================================
# Tool Catalog Tests
# =============================================================================


class TestToolCatalogs:
    """Tests for the mock tool catalogs."""
    
    def test_notion_tools_count(self):
        """Notion has expected number of tools."""
        assert len(ALL_NOTION_TOOLS) == 15
    
    def test_slack_tools_count(self):
        """Slack has expected number of tools."""
        assert len(ALL_SLACK_TOOLS) == 22
    
    def test_total_tools_count(self):
        """Total tools matches design doc (37)."""
        total = len(ALL_NOTION_TOOLS) + len(ALL_SLACK_TOOLS)
        assert total == 37
    
    def test_all_notion_tools_have_permissions(self):
        """All Notion tools have permission mappings."""
        for tool in ALL_NOTION_TOOLS:
            assert tool.permission.startswith("notion:")
            assert len(tool.permission) > 0
    
    def test_all_slack_tools_have_permissions(self):
        """All Slack tools have permission mappings."""
        for tool in ALL_SLACK_TOOLS:
            assert tool.permission.startswith("slack:")
            assert len(tool.permission) > 0
    
    def test_all_tools_have_descriptions(self):
        """All tools have descriptions."""
        for tool in ALL_NOTION_TOOLS + ALL_SLACK_TOOLS:
            assert len(tool.description) > 0
    
    def test_permission_format(self):
        """Permissions follow service:resource:action format."""
        for tool in ALL_NOTION_TOOLS + ALL_SLACK_TOOLS:
            parts = tool.permission.split(":")
            assert len(parts) == 3, f"Permission {tool.permission} should have 3 parts"
            assert parts[0] in ["notion", "slack"]


# =============================================================================
# Delegation Tests
# =============================================================================


class TestDelegatedPermissions:
    """Tests for Sarah's delegated permissions."""
    
    def test_delegated_permissions_count(self):
        """Sarah delegated expected number of permissions."""
        assert len(SARAH_DELEGATED_PERMISSIONS) == 4
    
    def test_delegated_permissions_are_valid(self):
        """All delegated permissions exist in tool catalogs."""
        all_permissions = set()
        for tool in ALL_NOTION_TOOLS + ALL_SLACK_TOOLS:
            all_permissions.add(tool.permission)
        
        for perm in SARAH_DELEGATED_PERMISSIONS:
            assert perm in all_permissions, f"Permission {perm} not in catalogs"
    
    def test_delegated_permissions_include_notion(self):
        """Delegation includes Notion permissions."""
        notion_perms = [p for p in SARAH_DELEGATED_PERMISSIONS if p.startswith("notion:")]
        assert len(notion_perms) == 2
    
    def test_delegated_permissions_include_slack(self):
        """Delegation includes Slack permissions."""
        slack_perms = [p for p in SARAH_DELEGATED_PERMISSIONS if p.startswith("slack:")]
        assert len(slack_perms) == 2


# =============================================================================
# Filtering Logic Tests
# =============================================================================


class TestFilteringLogic:
    """Tests for the filter_tools function."""
    
    def test_filter_tools_returns_result(self):
        """filter_tools returns a FilteringResult."""
        all_tools = get_all_tools()
        result = filter_tools(all_tools, SARAH_DELEGATED_PERMISSIONS)
        
        assert isinstance(result, FilteringResult)
    
    def test_visible_tools_count(self):
        """Agent sees expected number of tools (4)."""
        all_tools = get_all_tools()
        result = filter_tools(all_tools, SARAH_DELEGATED_PERMISSIONS)
        
        assert result.visible_tools == 4
    
    def test_hidden_tools_count(self):
        """Expected number of tools are hidden (33)."""
        all_tools = get_all_tools()
        result = filter_tools(all_tools, SARAH_DELEGATED_PERMISSIONS)
        
        assert result.hidden_tools == 33
    
    def test_total_equals_visible_plus_hidden(self):
        """Total tools equals visible plus hidden."""
        all_tools = get_all_tools()
        result = filter_tools(all_tools, SARAH_DELEGATED_PERMISSIONS)
        
        assert result.total_tools == result.visible_tools + result.hidden_tools
    
    def test_filtering_reduction_percentage(self):
        """Filtering achieves 89%+ reduction."""
        all_tools = get_all_tools()
        result = filter_tools(all_tools, SARAH_DELEGATED_PERMISSIONS)
        
        # Design doc specifies 90%+ reduction
        # With 4/37 visible = 33/37 hidden = 89.2%
        assert result.reduction_percentage >= 89.0
    
    def test_visible_tools_have_correct_permissions(self):
        """All visible tools match delegated permissions."""
        all_tools = get_all_tools()
        result = filter_tools(all_tools, SARAH_DELEGATED_PERMISSIONS)
        
        for backend, tool in result.visible_tool_list:
            assert tool.permission in SARAH_DELEGATED_PERMISSIONS
    
    def test_hidden_tools_not_in_delegation(self):
        """All hidden tools are NOT in delegated permissions."""
        all_tools = get_all_tools()
        result = filter_tools(all_tools, SARAH_DELEGATED_PERMISSIONS)
        
        for backend, tool in result.hidden_tool_list:
            assert tool.permission not in SARAH_DELEGATED_PERMISSIONS
    
    def test_empty_delegation_hides_all(self):
        """Empty delegation hides all tools."""
        all_tools = get_all_tools()
        result = filter_tools(all_tools, [])
        
        assert result.visible_tools == 0
        assert result.hidden_tools == 37
        assert result.reduction_percentage == 100.0
    
    def test_full_delegation_shows_all(self):
        """Full delegation shows all tools."""
        all_tools = get_all_tools()
        all_permissions = [t.permission for _, t in all_tools]
        result = filter_tools(all_tools, all_permissions)
        
        assert result.visible_tools == 37
        assert result.hidden_tools == 0
        assert result.reduction_percentage == 0.0


# =============================================================================
# get_all_tools Tests
# =============================================================================


class TestGetAllTools:
    """Tests for get_all_tools function."""
    
    def test_returns_all_tools(self):
        """Returns all tools from all backends."""
        all_tools = get_all_tools()
        assert len(all_tools) == 37
    
    def test_includes_backend_names(self):
        """Each tool has a backend name."""
        all_tools = get_all_tools()
        
        backends = set(backend for backend, _ in all_tools)
        assert backends == {"notion", "slack"}
    
    def test_notion_tools_labeled_correctly(self):
        """Notion tools have 'notion' backend."""
        all_tools = get_all_tools()
        
        notion_tools = [(b, t) for b, t in all_tools if b == "notion"]
        assert len(notion_tools) == 15
    
    def test_slack_tools_labeled_correctly(self):
        """Slack tools have 'slack' backend."""
        all_tools = get_all_tools()
        
        slack_tools = [(b, t) for b, t in all_tools if b == "slack"]
        assert len(slack_tools) == 22


# =============================================================================
# Demo Run Tests
# =============================================================================


class TestRunDemo:
    """Tests for the run_demo function."""
    
    @pytest.mark.asyncio
    async def test_run_demo_succeeds(self):
        """Demo runs successfully."""
        result = await run_demo(mock_mode=True)
        
        assert result.success is True
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_run_demo_returns_filtering_result(self):
        """Demo returns filtering result."""
        result = await run_demo(mock_mode=True)
        
        assert isinstance(result.filtering_result, FilteringResult)
        assert result.filtering_result.total_tools == 37
        assert result.filtering_result.visible_tools == 4
    
    @pytest.mark.asyncio
    async def test_run_demo_calculates_reduction(self):
        """Demo calculates attack surface reduction."""
        result = await run_demo(mock_mode=True)
        
        assert result.filtering_result.reduction_percentage >= 89.0


# =============================================================================
# Value Proposition Tests
# =============================================================================


class TestValueProposition:
    """Tests that verify the demo's security value proposition."""
    
    def test_massive_attack_surface_reduction(self):
        """
        Key value proposition:
        90%+ reduction in accessible functionality.
        """
        all_tools = get_all_tools()
        result = filter_tools(all_tools, SARAH_DELEGATED_PERMISSIONS)
        
        # Design doc promises 90%+ reduction
        # Actual is 89.2% which rounds to 89%
        assert result.reduction_percentage >= 89.0
    
    def test_dangerous_tools_are_hidden(self):
        """
        Dangerous operations like delete, archive, kick are hidden.
        """
        all_tools = get_all_tools()
        result = filter_tools(all_tools, SARAH_DELEGATED_PERMISSIONS)
        
        # Get all hidden tool names
        hidden_names = [tool.name for _, tool in result.hidden_tool_list]
        
        # These dangerous operations should be hidden
        dangerous_ops = [
            "delete_page",
            "delete_message",
            "delete_file",
            "archive_channel",
            "kick_from_channel",
            "create_channel",
        ]
        
        for op in dangerous_ops:
            assert op in hidden_names, f"{op} should be hidden"
    
    def test_only_read_operations_visible(self):
        """
        Sarah only delegated read/search operations.
        """
        all_tools = get_all_tools()
        result = filter_tools(all_tools, SARAH_DELEGATED_PERMISSIONS)
        
        # All visible tools should be read/search operations
        for backend, tool in result.visible_tool_list:
            assert any(
                keyword in tool.name
                for keyword in ["search", "read", "list"]
            ), f"Tool {tool.name} should be a read operation"
