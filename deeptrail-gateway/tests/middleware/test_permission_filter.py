"""
Tests for WS-C5: Permission Filter.

Tests the PermissionFilter class which filters tools/list responses
to only include tools the agent has delegated permission to use.

Key test areas:
- Filter tools by permissions (fail-closed behavior)
- Get permitted backends from permissions
- Reduction calculation for Demo 2 metric
- Integration with AgentContext
- Edge cases and error handling
"""

import logging
import pytest

from app.middleware.permission_filter import (
    PermissionFilter,
    filter_tools_for_agent,
    get_permitted_backends_for_agent,
)
from app.middleware.jwt_validation import AgentContext


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_tools() -> list[dict]:
    """
    Sample tool list for testing.
    
    Uses tools from PermissionMapper.TOOL_TO_PERMISSION to ensure
    they are recognized during filtering.
    """
    return [
        {"name": "notion.search_pages", "description": "Search Notion pages"},
        {"name": "notion.create_page", "description": "Create Notion page"},
        {"name": "notion.update_page", "description": "Update Notion page"},
        {"name": "slack.send_message", "description": "Send Slack message"},
        {"name": "slack.list_channels", "description": "List Slack channels"},
        {"name": "slack.list_users", "description": "List Slack users"},
    ]


@pytest.fixture
def agent_with_limited_perms() -> AgentContext:
    """Agent context with limited permissions (2 out of 10 tools)."""
    return AgentContext(
        agent_id="agent-123",
        owner="sarah@example.com",
        delegation_id="del-456",
        session_id="sess-789",
        delegated_permissions=[
            "notion:pages:search",
            "slack:messages:send",
        ],
    )


@pytest.fixture
def agent_with_backend_wide_perms() -> AgentContext:
    """Agent context with backend-wide permissions (all Notion and Slack tools)."""
    return AgentContext(
        agent_id="agent-456",
        owner="bob@example.com",
        delegation_id="del-789",
        session_id="sess-012",
        delegated_permissions=[
            # All Notion permissions for sample tools
            "notion:pages:search",
            "notion:pages:create",
            "notion:pages:update",
            # All Slack permissions for sample tools
            "slack:messages:send",
            "slack:channels:list",
            "slack:users:list",
        ],
    )


@pytest.fixture
def agent_with_no_perms() -> AgentContext:
    """Agent context with no permissions."""
    return AgentContext(
        agent_id="agent-empty",
        owner="nobody@example.com",
        delegation_id="del-empty",
        session_id="sess-empty",
        delegated_permissions=[],
    )


@pytest.fixture
def agent_with_all_perms() -> AgentContext:
    """
    Agent context with permissions for all sample tools.
    
    Maps to the sample_tools fixture:
    - notion.search_pages -> notion:pages:search
    - notion.create_page -> notion:pages:create
    - notion.update_page -> notion:pages:update
    - slack.send_message -> slack:messages:send
    - slack.list_channels -> slack:channels:list
    - slack.list_users -> slack:users:list
    """
    return AgentContext(
        agent_id="agent-admin",
        owner="admin@example.com",
        delegation_id="del-admin",
        session_id="sess-admin",
        delegated_permissions=[
            "notion:pages:search",
            "notion:pages:create",
            "notion:pages:update",
            "slack:messages:send",
            "slack:channels:list",
            "slack:users:list",
        ],
    )


# =============================================================================
# Test: filter_tools - Basic Functionality
# =============================================================================


class TestFilterTools:
    """Tests for PermissionFilter.filter_tools()"""

    def test_filter_returns_only_permitted_tools(
        self, sample_tools, agent_with_limited_perms
    ):
        """C5: Should filter to only permitted tools"""
        filtered = PermissionFilter.filter_tools(
            tools=sample_tools,
            agent_context=agent_with_limited_perms,
        )

        names = [t["name"] for t in filtered]
        assert "notion.search_pages" in names
        assert "slack.send_message" in names
        assert "notion.create_page" not in names
        assert "notion.update_page" not in names
        assert "slack.list_channels" not in names
        assert len(filtered) == 2

    def test_filter_with_backend_wide_permissions(
        self, sample_tools, agent_with_backend_wide_perms
    ):
        """C5: Should filter correctly with multiple backend permissions"""
        filtered = PermissionFilter.filter_tools(
            tools=sample_tools,
            agent_context=agent_with_backend_wide_perms,
        )

        names = [t["name"] for t in filtered]
        # All notion tools should be present
        assert "notion.search_pages" in names
        assert "notion.create_page" in names
        assert "notion.update_page" in names
        # All slack tools should be present
        assert "slack.send_message" in names
        assert "slack.list_channels" in names
        assert "slack.list_users" in names
        assert len(filtered) == 6

    def test_filter_with_all_permissions(
        self, sample_tools, agent_with_all_perms
    ):
        """C5: Should return all tools when all permissions are present"""
        filtered = PermissionFilter.filter_tools(
            tools=sample_tools,
            agent_context=agent_with_all_perms,
        )

        assert len(filtered) == len(sample_tools)
        names = [t["name"] for t in filtered]
        for tool in sample_tools:
            assert tool["name"] in names

    def test_filter_preserves_tool_schema(
        self, sample_tools, agent_with_limited_perms
    ):
        """C5: Filtered tools should preserve full schema"""
        filtered = PermissionFilter.filter_tools(
            tools=sample_tools,
            agent_context=agent_with_limited_perms,
        )

        for tool in filtered:
            assert "name" in tool
            assert "description" in tool

    def test_filter_with_empty_tools_list(self, agent_with_limited_perms):
        """C5: Should handle empty tools list"""
        filtered = PermissionFilter.filter_tools(
            tools=[],
            agent_context=agent_with_limited_perms,
        )

        assert filtered == []

    def test_filter_with_tools_containing_extra_fields(
        self, agent_with_limited_perms
    ):
        """C5: Should preserve extra fields in tool schema"""
        tools = [
            {
                "name": "notion.search_pages",
                "description": "Search pages",
                "inputSchema": {"type": "object"},
                "custom_field": "custom_value",
            },
            {
                "name": "slack.send_message",
                "description": "Send message",
                "inputSchema": {"type": "object"},
            },
        ]

        filtered = PermissionFilter.filter_tools(
            tools=tools,
            agent_context=agent_with_limited_perms,
        )

        assert len(filtered) == 2
        notion_tool = next(t for t in filtered if t["name"] == "notion.search_pages")
        assert notion_tool["custom_field"] == "custom_value"


# =============================================================================
# Test: filter_tools - Fail-Closed Behavior (Security)
# =============================================================================


class TestFilterToolsFailClosed:
    """Tests for C5 fail-closed security behavior"""

    def test_filter_with_none_context_returns_empty(self, sample_tools):
        """C5 Fail-closed: None context should return empty list"""
        filtered = PermissionFilter.filter_tools(
            tools=sample_tools,
            agent_context=None,
        )

        assert filtered == []

    def test_filter_with_no_permissions_returns_empty(
        self, sample_tools, agent_with_no_perms
    ):
        """C5: Empty permissions should return empty list"""
        filtered = PermissionFilter.filter_tools(
            tools=sample_tools,
            agent_context=agent_with_no_perms,
        )

        assert filtered == []

    def test_filter_with_unknown_tool_excluded(self, agent_with_limited_perms):
        """C5 Fail-closed: Unknown tools should be excluded"""
        tools = [
            {"name": "notion.search_pages", "description": "Search"},
            {"name": "unknown.some_tool", "description": "Unknown"},
            {"name": "another.mystery_tool", "description": "Mystery"},
        ]

        filtered = PermissionFilter.filter_tools(
            tools=tools,
            agent_context=agent_with_limited_perms,
        )

        names = [t["name"] for t in filtered]
        assert "notion.search_pages" in names
        assert "unknown.some_tool" not in names
        assert "another.mystery_tool" not in names
        assert len(filtered) == 1

    def test_filter_with_malformed_tool_names(self, agent_with_limited_perms):
        """C5: Should handle malformed tool names gracefully"""
        tools = [
            {"name": "notion.search_pages", "description": "Valid"},
            {"name": "no_namespace", "description": "No namespace"},
            {"name": "", "description": "Empty name"},
            {"name": "slack.send_message", "description": "Valid Slack"},
        ]

        filtered = PermissionFilter.filter_tools(
            tools=tools,
            agent_context=agent_with_limited_perms,
        )

        names = [t["name"] for t in filtered]
        assert "notion.search_pages" in names
        assert "slack.send_message" in names
        assert "no_namespace" not in names
        assert len(filtered) == 2


# =============================================================================
# Test: Demo 2 Metric - Tool Reduction
# =============================================================================


class TestDemoMetricReduction:
    """Tests for Demo 2: 90%+ tool reduction"""

    def test_filter_reduction_calculation(
        self, sample_tools, agent_with_limited_perms
    ):
        """C5 Demo 2: Should achieve significant reduction with limited perms"""
        filtered = PermissionFilter.filter_tools(
            tools=sample_tools,
            agent_context=agent_with_limited_perms,
        )

        original = len(sample_tools)  # 10
        after = len(filtered)  # 2
        reduction = (original - after) / original * 100

        # 2/10 = 80% reduction
        assert reduction >= 50  # At least 50% reduction
        assert reduction == 80.0  # Exactly 80% for our fixtures

    def test_90_percent_reduction_achievable(self):
        """C5 Demo 2: 90%+ reduction should be achievable"""
        # 20 tools, agent has 2 permissions = 90% reduction
        tools = [
            {"name": f"backend{i}.tool{j}", "description": f"Tool {j}"}
            for i in range(4)
            for j in range(5)
        ]  # 20 tools

        agent = AgentContext(
            agent_id="limited-agent",
            owner="user@example.com",
            delegation_id="del",
            session_id="sess",
            delegated_permissions=[
                "backend0:tool:tool0",  # Matches backend0.tool0
                "backend1:tool:tool0",  # Matches backend1.tool0
            ],
        )

        filtered = PermissionFilter.filter_tools(
            tools=tools,
            agent_context=agent,
        )

        original = len(tools)  # 20
        after = len(filtered)  # 2
        reduction = (original - after) / original * 100

        assert reduction >= 90.0

    def test_calculate_reduction_method(self):
        """C5: calculate_reduction should compute correctly"""
        # 90% reduction
        assert PermissionFilter.calculate_reduction(20, 2) == 90.0
        
        # 80% reduction
        assert PermissionFilter.calculate_reduction(10, 2) == 80.0
        
        # 0% reduction
        assert PermissionFilter.calculate_reduction(10, 10) == 0.0
        
        # 100% reduction
        assert PermissionFilter.calculate_reduction(10, 0) == 100.0
        
        # Edge case: 0 original
        assert PermissionFilter.calculate_reduction(0, 0) == 0.0


# =============================================================================
# Test: get_permitted_backends
# =============================================================================


class TestGetPermittedBackends:
    """Tests for PermissionFilter.get_permitted_backends()"""

    def test_get_permitted_backends_basic(self, agent_with_limited_perms):
        """C5: Should extract backend IDs from permissions"""
        backends = PermissionFilter.get_permitted_backends(agent_with_limited_perms)

        assert "notion" in backends
        assert "slack" in backends
        assert len(backends) == 2

    def test_get_permitted_backends_multiple(self, agent_with_all_perms):
        """C5: Should get all backends from permissions"""
        backends = PermissionFilter.get_permitted_backends(agent_with_all_perms)

        assert "notion" in backends
        assert "slack" in backends
        assert len(backends) == 2

    def test_get_permitted_backends_none_context(self):
        """C5 Fail-closed: None context should return empty set"""
        backends = PermissionFilter.get_permitted_backends(None)

        assert backends == set()

    def test_get_permitted_backends_no_perms(self, agent_with_no_perms):
        """C5: Empty permissions should return empty set"""
        backends = PermissionFilter.get_permitted_backends(agent_with_no_perms)

        assert backends == set()

    def test_get_permitted_backends_deduplicates(self):
        """C5: Should deduplicate backends with multiple permissions"""
        agent = AgentContext(
            agent_id="agent",
            owner="user@example.com",
            delegation_id="del",
            session_id="sess",
            delegated_permissions=[
                "notion:pages:search",
                "notion:pages:create",
                "notion:blocks:read",
                "notion:blocks:write",
            ],
        )

        backends = PermissionFilter.get_permitted_backends(agent)

        assert backends == {"notion"}

    def test_get_permitted_backends_from_permissions(self):
        """C5: Should extract backends from permissions list"""
        permissions = [
            "notion:pages:search",
            "slack:messages:send",
            "gdrive:files:search",
        ]

        backends = PermissionFilter.get_permitted_backends_from_permissions(permissions)

        assert backends == {"notion", "slack", "gdrive"}


# =============================================================================
# Test: filter_tools_by_permissions
# =============================================================================


class TestFilterToolsByPermissions:
    """Tests for PermissionFilter.filter_tools_by_permissions()"""

    def test_filter_by_permissions_list(self, sample_tools):
        """C5: Should filter using permissions list directly"""
        permissions = ["notion:pages:search", "slack:messages:send"]

        filtered = PermissionFilter.filter_tools_by_permissions(
            tools=sample_tools,
            delegated_permissions=permissions,
            agent_id="test-agent",
        )

        names = [t["name"] for t in filtered]
        assert "notion.search_pages" in names
        assert "slack.send_message" in names
        assert len(filtered) == 2

    def test_filter_by_permissions_empty_list(self, sample_tools):
        """C5: Empty permissions list should return empty"""
        filtered = PermissionFilter.filter_tools_by_permissions(
            tools=sample_tools,
            delegated_permissions=[],
            agent_id="test-agent",
        )

        assert filtered == []


# =============================================================================
# Test: is_tool_permitted
# =============================================================================


class TestIsToolPermitted:
    """Tests for PermissionFilter.is_tool_permitted()"""

    def test_is_tool_permitted_true(self, agent_with_limited_perms):
        """C5: Should return True for permitted tool"""
        assert PermissionFilter.is_tool_permitted(
            "notion.search_pages",
            agent_with_limited_perms,
        ) is True

    def test_is_tool_permitted_false(self, agent_with_limited_perms):
        """C5: Should return False for non-permitted tool"""
        assert PermissionFilter.is_tool_permitted(
            "notion.create_page",
            agent_with_limited_perms,
        ) is False

    def test_is_tool_permitted_none_context(self):
        """C5 Fail-closed: None context should return False"""
        assert PermissionFilter.is_tool_permitted(
            "notion.search_pages",
            None,
        ) is False

    def test_is_tool_permitted_no_perms(self, agent_with_no_perms):
        """C5: No permissions should return False"""
        assert PermissionFilter.is_tool_permitted(
            "notion.search_pages",
            agent_with_no_perms,
        ) is False


# =============================================================================
# Test: Convenience Functions
# =============================================================================


class TestConvenienceFunctions:
    """Tests for module-level convenience functions"""

    def test_filter_tools_for_agent(self, sample_tools, agent_with_limited_perms):
        """C5: Convenience function should work"""
        filtered = filter_tools_for_agent(
            tools=sample_tools,
            agent_context=agent_with_limited_perms,
        )

        assert len(filtered) == 2
        names = [t["name"] for t in filtered]
        assert "notion.search_pages" in names
        assert "slack.send_message" in names

    def test_get_permitted_backends_for_agent(self, agent_with_limited_perms):
        """C5: Convenience function should work"""
        backends = get_permitted_backends_for_agent(agent_with_limited_perms)

        assert backends == {"notion", "slack"}


# =============================================================================
# Test: Logging and Audit
# =============================================================================


class TestLogging:
    """Tests for logging and audit trail"""

    def test_filter_logs_warning_on_none_context(self, sample_tools, caplog):
        """C5: Should log warning when context is None"""
        with caplog.at_level(logging.WARNING):
            PermissionFilter.filter_tools(
                tools=sample_tools,
                agent_context=None,
            )

        assert "No agent context" in caplog.text
        assert "fail-closed" in caplog.text

    def test_filter_logs_info_on_empty_permissions(
        self, sample_tools, agent_with_no_perms, caplog
    ):
        """C5: Should log info when permissions are empty"""
        with caplog.at_level(logging.INFO):
            PermissionFilter.filter_tools(
                tools=sample_tools,
                agent_context=agent_with_no_perms,
            )

        assert "no delegated permissions" in caplog.text

    def test_filter_logs_reduction_stats(
        self, sample_tools, agent_with_limited_perms, caplog
    ):
        """C5: Should log reduction statistics"""
        with caplog.at_level(logging.INFO):
            PermissionFilter.filter_tools(
                tools=sample_tools,
                agent_context=agent_with_limited_perms,
            )

        # Should log something like "2/10 tools (80.0% reduction)"
        assert "reduction" in caplog.text
        assert "agent-123" in caplog.text


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_filter_single_tool_permitted(self):
        """C5: Should handle single permitted tool"""
        tools = [{"name": "notion.search_pages", "description": "Search"}]
        agent = AgentContext(
            agent_id="agent",
            owner="user@example.com",
            delegation_id="del",
            session_id="sess",
            delegated_permissions=["notion:pages:search"],
        )

        filtered = PermissionFilter.filter_tools(tools, agent)

        assert len(filtered) == 1

    def test_filter_single_tool_not_permitted(self):
        """C5: Should handle single non-permitted tool"""
        tools = [{"name": "notion.search_pages", "description": "Search"}]
        agent = AgentContext(
            agent_id="agent",
            owner="user@example.com",
            delegation_id="del",
            session_id="sess",
            delegated_permissions=["slack:messages:send"],
        )

        filtered = PermissionFilter.filter_tools(tools, agent)

        assert len(filtered) == 0

    def test_filter_with_missing_name_field(self, agent_with_limited_perms):
        """C5: Should handle tools without name field"""
        tools = [
            {"name": "notion.search_pages", "description": "Valid"},
            {"description": "Missing name"},
            {"name": "slack.send_message", "description": "Valid Slack"},
        ]

        filtered = PermissionFilter.filter_tools(tools, agent_with_limited_perms)

        # Only valid tools with names should be included
        names = [t.get("name") for t in filtered]
        assert "notion.search_pages" in names
        assert "slack.send_message" in names
        assert None not in names or len(filtered) == 2

    def test_backends_with_malformed_permissions(self):
        """C5: Should handle malformed permission strings"""
        agent = AgentContext(
            agent_id="agent",
            owner="user@example.com",
            delegation_id="del",
            session_id="sess",
            delegated_permissions=[
                "notion:pages:search",  # Valid
                "singlepart",  # Only backend
                "",  # Empty
                "::",  # Only colons
                "slack:messages:send",  # Valid
            ],
        )

        backends = PermissionFilter.get_permitted_backends(agent)

        assert "notion" in backends
        assert "slack" in backends
        # "singlepart" is technically valid as backend
        assert "singlepart" in backends
        # Empty string should not be included
        assert "" not in backends

    def test_filter_preserves_order(self, agent_with_limited_perms):
        """C5: Should preserve tool order from input"""
        tools = [
            {"name": "slack.send_message", "description": "1"},
            {"name": "notion.search_pages", "description": "2"},
            {"name": "gdrive.search_files", "description": "3"},
        ]

        filtered = PermissionFilter.filter_tools(tools, agent_with_limited_perms)

        # Slack comes before Notion in input, should be same in output
        names = [t["name"] for t in filtered]
        assert names.index("slack.send_message") < names.index("notion.search_pages")
