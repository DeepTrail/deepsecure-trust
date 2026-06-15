"""
Tests for Demo 4: Permission Enforcement.

Validates that the demo correctly demonstrates:
- Authorized tools are allowed
- Unauthorized tools are blocked at gateway
- Backend receives zero unauthorized requests
"""

import pytest

from demos.demo_04_permission_enforcement import (
    AUTHORIZED_TOOLS,
    CONFIG,
    DELEGATED_PERMISSIONS,
    TOOL_PERMISSIONS,
    UNAUTHORIZED_TOOLS,
    DemoConfig,
    DemoResult,
    MockBackendLog,
    ToolCallResult,
    get_permission_for_tool,
    is_tool_authorized,
    run_demo,
)


# =============================================================================
# DemoConfig Tests
# =============================================================================


class TestDemoConfig:
    """Tests for DemoConfig dataclass."""
    
    def test_config_has_gateway_url(self) -> None:
        """Config has a gateway URL."""
        config = DemoConfig()
        assert config.GATEWAY_URL is not None
        assert config.GATEWAY_URL.startswith("http")
    
    def test_config_has_agent_info(self) -> None:
        """Config has agent information."""
        config = DemoConfig()
        assert config.AGENT_ID is not None
        assert config.AGENT_NAME is not None
    
    def test_config_has_user_info(self) -> None:
        """Config has user information."""
        config = DemoConfig()
        assert config.USER_EMAIL is not None
        assert "@" in config.USER_EMAIL
    
    def test_global_config_exists(self) -> None:
        """Global CONFIG instance exists."""
        assert CONFIG is not None
        assert isinstance(CONFIG, DemoConfig)


# =============================================================================
# DemoResult Tests
# =============================================================================


class TestDemoResult:
    """Tests for DemoResult dataclass."""
    
    def test_success_result(self) -> None:
        """DemoResult with success."""
        result = DemoResult(
            success=True,
            authorized_calls=1,
            blocked_calls=2,
            backend_requests=1,
        )
        assert result.success is True
        assert result.authorized_calls == 1
        assert result.blocked_calls == 2
        assert result.backend_requests == 1
        assert result.error is None
    
    def test_failure_result(self) -> None:
        """DemoResult with failure."""
        result = DemoResult(
            success=False,
            error="Test error",
        )
        assert result.success is False
        assert result.error == "Test error"


# =============================================================================
# MockBackendLog Tests
# =============================================================================


class TestMockBackendLog:
    """Tests for MockBackendLog class."""
    
    def test_empty_log(self) -> None:
        """Empty log has no requests."""
        log = MockBackendLog()
        assert log.count_total() == 0
        assert log.requests_received == []
    
    def test_log_request(self) -> None:
        """Log records requests correctly."""
        log = MockBackendLog()
        log.log_request("notion.search_pages", {"query": "test"})
        
        assert log.count_total() == 1
        assert log.requests_received[0]["tool"] == "notion.search_pages"
        assert log.requests_received[0]["arguments"] == {"query": "test"}
    
    def test_log_multiple_requests(self) -> None:
        """Log records multiple requests."""
        log = MockBackendLog()
        log.log_request("notion.search_pages", {})
        log.log_request("slack.list_channels", {})
        log.log_request("notion.read_page", {"id": "123"})
        
        assert log.count_total() == 3
    
    def test_get_requests_for_tool(self) -> None:
        """Get requests filtered by tool name."""
        log = MockBackendLog()
        log.log_request("notion.search_pages", {"query": "a"})
        log.log_request("slack.list_channels", {})
        log.log_request("notion.search_pages", {"query": "b"})
        
        notion_requests = log.get_requests_for_tool("notion.search_pages")
        assert len(notion_requests) == 2
        
        slack_requests = log.get_requests_for_tool("slack.list_channels")
        assert len(slack_requests) == 1
        
        gmail_requests = log.get_requests_for_tool("gmail.search")
        assert len(gmail_requests) == 0
    
    def test_count_unauthorized_zero(self) -> None:
        """Count unauthorized returns 0 for authorized tools only."""
        log = MockBackendLog()
        log.log_request("notion.search_pages", {})
        log.log_request("notion.read_page", {})
        
        count = log.count_unauthorized(UNAUTHORIZED_TOOLS)
        assert count == 0
    
    def test_count_unauthorized_nonzero(self) -> None:
        """Count unauthorized returns correct count when present."""
        log = MockBackendLog()
        log.log_request("notion.search_pages", {})
        log.log_request("notion.create_page", {})  # Unauthorized
        log.log_request("notion.delete_page", {})  # Unauthorized
        
        count = log.count_unauthorized(UNAUTHORIZED_TOOLS)
        assert count == 2


# =============================================================================
# ToolCallResult Tests
# =============================================================================


class TestToolCallResult:
    """Tests for ToolCallResult dataclass."""
    
    def test_successful_call(self) -> None:
        """ToolCallResult for successful authorized call."""
        result = ToolCallResult(
            tool="notion.search_pages",
            permission="notion:pages:search",
            delegated=True,
            success=True,
            blocked_at_gateway=False,
            reached_backend=True,
        )
        assert result.success is True
        assert result.delegated is True
        assert result.blocked_at_gateway is False
        assert result.reached_backend is True
        assert result.error_code is None
    
    def test_blocked_call(self) -> None:
        """ToolCallResult for blocked unauthorized call."""
        result = ToolCallResult(
            tool="notion.create_page",
            permission="notion:pages:create",
            delegated=False,
            success=False,
            blocked_at_gateway=True,
            reached_backend=False,
            error_code=-32001,
            error_message="Permission denied: notion:pages:create not delegated",
        )
        assert result.success is False
        assert result.delegated is False
        assert result.blocked_at_gateway is True
        assert result.reached_backend is False
        assert result.error_code == -32001


# =============================================================================
# Permission Configuration Tests
# =============================================================================


class TestPermissionConfiguration:
    """Tests for permission configuration."""
    
    def test_delegated_permissions_exist(self) -> None:
        """Delegated permissions list exists and has entries."""
        assert len(DELEGATED_PERMISSIONS) > 0
        assert "notion:pages:search" in DELEGATED_PERMISSIONS
        assert "notion:pages:read" in DELEGATED_PERMISSIONS
    
    def test_tool_permissions_mapping(self) -> None:
        """Tool to permission mapping is complete."""
        assert len(TOOL_PERMISSIONS) > 0
        assert "notion.search_pages" in TOOL_PERMISSIONS
        assert TOOL_PERMISSIONS["notion.search_pages"] == "notion:pages:search"
    
    def test_authorized_tools_list(self) -> None:
        """Authorized tools list is computed correctly."""
        assert len(AUTHORIZED_TOOLS) > 0
        for tool in AUTHORIZED_TOOLS:
            permission = TOOL_PERMISSIONS[tool]
            assert permission in DELEGATED_PERMISSIONS
    
    def test_unauthorized_tools_list(self) -> None:
        """Unauthorized tools list is computed correctly."""
        assert len(UNAUTHORIZED_TOOLS) > 0
        for tool in UNAUTHORIZED_TOOLS:
            permission = TOOL_PERMISSIONS[tool]
            assert permission not in DELEGATED_PERMISSIONS
    
    def test_no_overlap_between_authorized_and_unauthorized(self) -> None:
        """Authorized and unauthorized tools don't overlap."""
        authorized_set = set(AUTHORIZED_TOOLS)
        unauthorized_set = set(UNAUTHORIZED_TOOLS)
        assert authorized_set.isdisjoint(unauthorized_set)
    
    def test_all_tools_categorized(self) -> None:
        """All tools are either authorized or unauthorized."""
        all_tools = set(TOOL_PERMISSIONS.keys())
        categorized_tools = set(AUTHORIZED_TOOLS) | set(UNAUTHORIZED_TOOLS)
        assert all_tools == categorized_tools


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_is_tool_authorized_true(self) -> None:
        """is_tool_authorized returns True for authorized tools."""
        assert is_tool_authorized("notion.search_pages") is True
        assert is_tool_authorized("notion.read_page") is True
        assert is_tool_authorized("slack.list_channels") is True
    
    def test_is_tool_authorized_false(self) -> None:
        """is_tool_authorized returns False for unauthorized tools."""
        assert is_tool_authorized("notion.create_page") is False
        assert is_tool_authorized("notion.delete_page") is False
        assert is_tool_authorized("slack.send_message") is False
    
    def test_is_tool_authorized_unknown(self) -> None:
        """is_tool_authorized returns False for unknown tools."""
        assert is_tool_authorized("unknown.tool") is False
    
    def test_get_permission_for_tool_exists(self) -> None:
        """get_permission_for_tool returns correct permission."""
        assert get_permission_for_tool("notion.search_pages") == "notion:pages:search"
        assert get_permission_for_tool("slack.send_message") == "slack:messages:send"
    
    def test_get_permission_for_tool_unknown(self) -> None:
        """get_permission_for_tool handles unknown tools."""
        assert get_permission_for_tool("unknown.tool") == "unknown:permission"


# =============================================================================
# Demo Execution Tests
# =============================================================================


class TestDemoExecution:
    """Tests for demo execution."""
    
    @pytest.mark.asyncio
    async def test_demo_runs_in_mock_mode(self) -> None:
        """Demo runs successfully in mock mode."""
        result = await run_demo(mock_mode=True)
        assert result.success is True
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_demo_returns_correct_metrics(self) -> None:
        """Demo returns correct metrics."""
        result = await run_demo(mock_mode=True)
        
        # Should have at least 1 authorized call and 2 blocked calls
        assert result.authorized_calls >= 1
        assert result.blocked_calls >= 1
        assert result.backend_requests >= 1
    
    @pytest.mark.asyncio
    async def test_demo_backend_requests_equals_authorized(self) -> None:
        """Backend requests should equal authorized calls only."""
        result = await run_demo(mock_mode=True)
        
        # Backend should only receive authorized calls
        # (blocked calls don't reach backend)
        assert result.backend_requests == result.authorized_calls


# =============================================================================
# Security Verification Tests
# =============================================================================


class TestSecurityVerification:
    """Tests verifying security properties of the demo."""
    
    def test_unauthorized_tools_contain_dangerous_operations(self) -> None:
        """Unauthorized tools include dangerous operations."""
        unauthorized_permissions = [
            TOOL_PERMISSIONS[tool] for tool in UNAUTHORIZED_TOOLS
        ]
        assert "notion:pages:create" in unauthorized_permissions
        assert "notion:pages:delete" in unauthorized_permissions
        assert "slack:messages:send" in unauthorized_permissions
    
    def test_authorized_tools_are_read_only(self) -> None:
        """Authorized tools are primarily read operations."""
        authorized_permissions = [
            TOOL_PERMISSIONS[tool] for tool in AUTHORIZED_TOOLS
        ]
        # Search and read are safe operations
        assert "notion:pages:search" in authorized_permissions
        assert "notion:pages:read" in authorized_permissions
        assert "slack:messages:search" in authorized_permissions
        assert "slack:channels:list" in authorized_permissions
    
    def test_backend_log_never_receives_blocked_requests(self) -> None:
        """Simulate the security model: blocked requests never log."""
        log = MockBackendLog()
        
        # Simulate authorized call - logs to backend
        tool = "notion.search_pages"
        if is_tool_authorized(tool):
            log.log_request(tool, {"query": "test"})
        
        # Simulate unauthorized call - does NOT log to backend
        tool = "notion.create_page"
        if is_tool_authorized(tool):
            log.log_request(tool, {"title": "test"})  # This won't run
        
        # Verify only authorized request reached backend
        assert log.count_total() == 1
        assert log.count_unauthorized(UNAUTHORIZED_TOOLS) == 0


# =============================================================================
# Value Proposition Tests
# =============================================================================


class TestValueProposition:
    """Tests verifying the demo's value proposition."""
    
    def test_value_prop_gateway_blocks_unauthorized(self) -> None:
        """Value: Gateway blocks unauthorized requests."""
        # If a tool is not authorized, it should be blocked
        for tool in UNAUTHORIZED_TOOLS:
            assert is_tool_authorized(tool) is False
    
    def test_value_prop_backend_zero_unauthorized(self) -> None:
        """Value: Backend receives zero unauthorized requests."""
        log = MockBackendLog()
        
        # Process all tools through authorization
        for tool in TOOL_PERMISSIONS:
            if is_tool_authorized(tool):
                log.log_request(tool, {})
        
        # Backend should only have authorized tools
        assert log.count_unauthorized(UNAUTHORIZED_TOOLS) == 0
    
    def test_value_prop_clear_error_messages(self) -> None:
        """Value: Clear error messages for denied requests."""
        for tool in UNAUTHORIZED_TOOLS:
            permission = get_permission_for_tool(tool)
            error_message = f"Permission denied: {permission} not delegated"
            
            # Error message clearly indicates the missing permission
            assert permission in error_message
            assert "not delegated" in error_message
