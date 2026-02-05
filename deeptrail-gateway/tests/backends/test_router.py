"""Tests for backend router (WS-D6)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.backends.router import (
    BackendRouter,
    RouterError,
    BackendNotFoundError,
    InvalidToolNameError,
    create_router,
    create_router_with_backends,
)
from app.backends.base_mcp_client import (
    BaseMCPClient,
    ToolResult,
    ToolSchema,
    ToolCallStatus,
    MCPClientError,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_connection_manager():
    """Create mock connection manager."""
    manager = MagicMock()
    manager.is_backend_registered = MagicMock(return_value=False)
    return manager


@pytest.fixture
def mock_notion_client():
    """Create mock Notion client."""
    client = MagicMock(spec=BaseMCPClient)
    client.backend_id = "notion"
    client.call_tool = AsyncMock()
    client.list_tools = AsyncMock()
    client.check_health = AsyncMock(return_value=True)
    client.initialize = AsyncMock()
    return client


@pytest.fixture
def mock_slack_client():
    """Create mock Slack client."""
    client = MagicMock(spec=BaseMCPClient)
    client.backend_id = "slack"
    client.call_tool = AsyncMock()
    client.list_tools = AsyncMock()
    client.check_health = AsyncMock(return_value=True)
    client.initialize = AsyncMock()
    return client


@pytest.fixture
def mock_hubspot_client():
    """Create mock HubSpot client."""
    client = MagicMock(spec=BaseMCPClient)
    client.backend_id = "hubspot"
    client.call_tool = AsyncMock()
    client.list_tools = AsyncMock()
    client.check_health = AsyncMock(return_value=True)
    client.initialize = AsyncMock()
    return client


@pytest.fixture
def router(mock_connection_manager):
    """Create router with mock connection manager."""
    return BackendRouter(mock_connection_manager, auto_register_generic=False)


# =============================================================================
# Backend Registration Tests
# =============================================================================


class TestBackendRegistration:
    """Tests for backend registration."""
    
    def test_register_backend(self, router, mock_notion_client):
        """Test registering a backend."""
        router.register_backend("notion", mock_notion_client)
        
        assert "notion" in router.registered_backends
        assert router.backend_count == 1
    
    def test_register_multiple_backends(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test registering multiple backends."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        
        assert router.backend_count == 2
        assert set(router.registered_backends) == {"notion", "slack"}
    
    def test_register_three_backends(
        self, router, mock_notion_client, mock_slack_client, mock_hubspot_client
    ):
        """Test registering three backends."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        router.register_backend("hubspot", mock_hubspot_client)
        
        assert router.backend_count == 3
        assert set(router.registered_backends) == {"notion", "slack", "hubspot"}
    
    def test_unregister_backend(self, router, mock_notion_client):
        """Test unregistering a backend."""
        router.register_backend("notion", mock_notion_client)
        
        result = router.unregister_backend("notion")
        
        assert result is True
        assert "notion" not in router.registered_backends
    
    def test_unregister_nonexistent(self, router):
        """Test unregistering non-existent backend."""
        result = router.unregister_backend("nonexistent")
        
        assert result is False
    
    def test_get_backend(self, router, mock_notion_client):
        """Test getting a registered backend."""
        router.register_backend("notion", mock_notion_client)
        
        client = router.get_backend("notion")
        
        assert client is mock_notion_client
    
    def test_get_nonexistent_backend(self, router):
        """Test getting non-existent backend returns None."""
        client = router.get_backend("nonexistent")
        
        assert client is None
    
    def test_register_empty_backend_id(self, router, mock_notion_client):
        """Test registering with empty backend_id raises."""
        with pytest.raises(ValueError) as exc:
            router.register_backend("", mock_notion_client)
        assert "empty" in str(exc.value)
    
    def test_register_none_client(self, router):
        """Test registering None client raises."""
        with pytest.raises(ValueError) as exc:
            router.register_backend("notion", None)
        assert "None" in str(exc.value)
    
    def test_replace_existing_backend(self, router, mock_notion_client, mock_slack_client):
        """Test replacing an existing backend."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("notion", mock_slack_client)  # Replace
        
        assert router.backend_count == 1
        assert router.get_backend("notion") is mock_slack_client
    
    def test_registered_backends_property(self, router, mock_notion_client):
        """Test registered_backends returns a list."""
        router.register_backend("notion", mock_notion_client)
        
        backends = router.registered_backends
        
        assert isinstance(backends, list)
        assert backends == ["notion"]
    
    def test_backend_count_property(self, router, mock_notion_client, mock_slack_client):
        """Test backend_count property."""
        assert router.backend_count == 0
        
        router.register_backend("notion", mock_notion_client)
        assert router.backend_count == 1
        
        router.register_backend("slack", mock_slack_client)
        assert router.backend_count == 2


# =============================================================================
# Auto-Registration Tests
# =============================================================================


class TestAutoRegistration:
    """Tests for auto-registration of generic clients."""
    
    def test_auto_register_when_enabled(self, mock_connection_manager):
        """Test auto-registration creates generic client when backend exists."""
        mock_connection_manager.is_backend_registered.return_value = True
        router = BackendRouter(mock_connection_manager, auto_register_generic=True)
        
        client = router.get_backend("notion")
        
        assert client is not None
        assert "notion" in router.registered_backends
    
    def test_no_auto_register_when_disabled(self, mock_connection_manager):
        """Test no auto-registration when disabled."""
        mock_connection_manager.is_backend_registered.return_value = True
        router = BackendRouter(mock_connection_manager, auto_register_generic=False)
        
        client = router.get_backend("notion")
        
        assert client is None
    
    def test_no_auto_register_unknown_backend(self, mock_connection_manager):
        """Test no auto-registration for unknown backend."""
        mock_connection_manager.is_backend_registered.return_value = False
        router = BackendRouter(mock_connection_manager, auto_register_generic=True)
        
        client = router.get_backend("unknown")
        
        assert client is None


# =============================================================================
# Tool Name Parsing Tests
# =============================================================================


class TestToolNameParsing:
    """Tests for tool name parsing."""
    
    def test_parse_simple_tool(self, router):
        """Test parsing simple namespaced tool."""
        backend_id, tool_name = router.parse_tool_name("notion.search_pages")
        
        assert backend_id == "notion"
        assert tool_name == "search_pages"
    
    def test_parse_tool_with_dots(self, router):
        """Test parsing tool name containing dots."""
        backend_id, tool_name = router.parse_tool_name("github.repos.create")
        
        assert backend_id == "github"
        assert tool_name == "repos.create"
    
    def test_parse_slack_tool(self, router):
        """Test parsing Slack tool name."""
        backend_id, tool_name = router.parse_tool_name("slack.send_message")
        
        assert backend_id == "slack"
        assert tool_name == "send_message"
    
    def test_parse_hubspot_tool(self, router):
        """Test parsing HubSpot tool name."""
        backend_id, tool_name = router.parse_tool_name("hubspot.get_contact")
        
        assert backend_id == "hubspot"
        assert tool_name == "get_contact"
    
    def test_parse_empty_raises(self, router):
        """Test parsing empty string raises."""
        with pytest.raises(InvalidToolNameError) as exc:
            router.parse_tool_name("")
        assert "empty" in str(exc.value).lower()
    
    def test_parse_no_namespace_raises(self, router):
        """Test parsing tool without namespace raises."""
        with pytest.raises(InvalidToolNameError) as exc:
            router.parse_tool_name("search_pages")
        assert "namespace" in str(exc.value).lower()
    
    def test_parse_empty_backend_raises(self, router):
        """Test parsing with empty backend raises."""
        with pytest.raises(InvalidToolNameError) as exc:
            router.parse_tool_name(".search_pages")
        assert "empty" in str(exc.value).lower()
    
    def test_parse_empty_tool_raises(self, router):
        """Test parsing with empty tool name raises."""
        with pytest.raises(InvalidToolNameError) as exc:
            router.parse_tool_name("notion.")
        assert "empty" in str(exc.value).lower()


# =============================================================================
# Get Backend for Tool Tests
# =============================================================================


class TestGetBackendForTool:
    """Tests for get_backend_for_tool method."""
    
    def test_get_backend_for_tool(self, router, mock_notion_client):
        """Test getting backend for a namespaced tool."""
        router.register_backend("notion", mock_notion_client)
        
        client = router.get_backend_for_tool("notion.search_pages")
        
        assert client is mock_notion_client
    
    def test_get_backend_for_unknown_raises(self, router):
        """Test getting backend for unknown namespace raises."""
        with pytest.raises(BackendNotFoundError):
            router.get_backend_for_tool("unknown.tool")
    
    def test_get_backend_for_invalid_tool_raises(self, router):
        """Test getting backend for invalid tool name raises."""
        with pytest.raises(InvalidToolNameError):
            router.get_backend_for_tool("no_namespace")


# =============================================================================
# Tool Routing Tests
# =============================================================================


class TestToolRouting:
    """Tests for tool routing."""
    
    @pytest.mark.asyncio
    async def test_route_to_notion(self, router, mock_notion_client):
        """Test routing to Notion backend."""
        router.register_backend("notion", mock_notion_client)
        mock_notion_client.call_tool.return_value = ToolResult(
            status=ToolCallStatus.SUCCESS,
            content=[{"type": "text", "text": "results"}],
        )
        
        result = await router.route_tool_call(
            "notion.search_pages",
            {"query": "test"},
            auth_token="Bearer xyz"
        )
        
        assert not result.is_error
        mock_notion_client.call_tool.assert_called_once_with(
            tool_name="search_pages",
            arguments={"query": "test"},
            auth_token="Bearer xyz",
        )
    
    @pytest.mark.asyncio
    async def test_route_to_slack(self, router, mock_slack_client):
        """Test routing to Slack backend."""
        router.register_backend("slack", mock_slack_client)
        mock_slack_client.call_tool.return_value = ToolResult(
            status=ToolCallStatus.SUCCESS,
            content=[{"type": "text", "text": "sent"}],
        )
        
        result = await router.route_tool_call(
            "slack.send_message",
            {"channel": "C123", "text": "Hello"},
        )
        
        assert not result.is_error
        mock_slack_client.call_tool.assert_called_once_with(
            tool_name="send_message",
            arguments={"channel": "C123", "text": "Hello"},
            auth_token=None,
        )
    
    @pytest.mark.asyncio
    async def test_route_to_hubspot(self, router, mock_hubspot_client):
        """Test routing to HubSpot backend."""
        router.register_backend("hubspot", mock_hubspot_client)
        mock_hubspot_client.call_tool.return_value = ToolResult(
            status=ToolCallStatus.SUCCESS,
            content=[{"type": "text", "text": "contact"}],
        )
        
        result = await router.route_tool_call(
            "hubspot.get_contact",
            {"contact_id": "12345"},
            auth_token="Bearer abc"
        )
        
        assert not result.is_error
        mock_hubspot_client.call_tool.assert_called_once_with(
            tool_name="get_contact",
            arguments={"contact_id": "12345"},
            auth_token="Bearer abc",
        )
    
    @pytest.mark.asyncio
    async def test_route_unknown_backend(self, router):
        """Test routing to unknown backend returns error."""
        result = await router.route_tool_call(
            "unknown.tool",
            {},
        )
        
        assert result.is_error
        assert "unknown" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_route_invalid_tool_name(self, router):
        """Test routing invalid tool name returns error."""
        result = await router.route_tool_call(
            "no_namespace",
            {},
        )
        
        assert result.is_error
        assert "namespace" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_route_empty_tool_name(self, router):
        """Test routing empty tool name returns error."""
        result = await router.route_tool_call(
            "",
            {},
        )
        
        assert result.is_error
        assert "empty" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_route_mcp_client_error(self, router, mock_notion_client):
        """Test routing handles MCPClientError."""
        router.register_backend("notion", mock_notion_client)
        mock_notion_client.call_tool.side_effect = MCPClientError("Connection failed")
        
        result = await router.route_tool_call(
            "notion.search_pages",
            {},
        )
        
        assert result.is_error
        assert "backend error" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_route_generic_exception(self, router, mock_notion_client):
        """Test routing handles generic exceptions."""
        router.register_backend("notion", mock_notion_client)
        mock_notion_client.call_tool.side_effect = RuntimeError("Unexpected")
        
        result = await router.route_tool_call(
            "notion.search_pages",
            {},
        )
        
        assert result.is_error
        assert "internal error" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_route_preserves_arguments(self, router, mock_notion_client):
        """Test routing preserves all arguments."""
        router.register_backend("notion", mock_notion_client)
        mock_notion_client.call_tool.return_value = ToolResult(
            status=ToolCallStatus.SUCCESS,
            content=[],
        )
        
        complex_args = {
            "query": "test",
            "limit": 50,
            "nested": {"key": "value"},
            "list_arg": [1, 2, 3],
        }
        
        await router.route_tool_call(
            "notion.search_pages",
            complex_args,
        )
        
        mock_notion_client.call_tool.assert_called_once()
        call_args = mock_notion_client.call_tool.call_args
        assert call_args.kwargs["arguments"] == complex_args


# =============================================================================
# Tool Aggregation Tests
# =============================================================================


class TestToolAggregation:
    """Tests for tool aggregation."""
    
    @pytest.mark.asyncio
    async def test_list_all_tools(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test listing tools from all backends."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        
        mock_notion_client.list_tools.return_value = [
            ToolSchema(name="search_pages", description="Search"),
        ]
        mock_slack_client.list_tools.return_value = [
            ToolSchema(name="send_message", description="Send"),
        ]
        
        tools = await router.list_all_tools()
        
        assert len(tools) == 2
        tool_names = [t.name for t in tools]
        assert "notion.search_pages" in tool_names
        assert "slack.send_message" in tool_names
    
    @pytest.mark.asyncio
    async def test_list_tools_adds_namespace_to_description(
        self, router, mock_notion_client
    ):
        """Test listing tools adds namespace to description."""
        router.register_backend("notion", mock_notion_client)
        mock_notion_client.list_tools.return_value = [
            ToolSchema(name="search", description="Search pages"),
        ]
        
        tools = await router.list_all_tools()
        
        assert len(tools) == 1
        assert "[Notion]" in tools[0].description
        assert "Search pages" in tools[0].description
    
    @pytest.mark.asyncio
    async def test_list_tools_handles_empty_description(
        self, router, mock_notion_client
    ):
        """Test listing tools handles empty description."""
        router.register_backend("notion", mock_notion_client)
        mock_notion_client.list_tools.return_value = [
            ToolSchema(name="search", description=None),
        ]
        
        tools = await router.list_all_tools()
        
        assert len(tools) == 1
        assert "[Notion]" in tools[0].description
    
    @pytest.mark.asyncio
    async def test_list_tools_with_include_filter(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test listing tools with namespace include filter."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        
        mock_notion_client.list_tools.return_value = [
            ToolSchema(name="search", description="Search"),
        ]
        
        tools = await router.list_all_tools(include_namespaces=["notion"])
        
        assert len(tools) == 1
        assert tools[0].name == "notion.search"
        mock_slack_client.list_tools.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_list_tools_with_exclude_filter(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test listing tools with namespace exclude filter."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        
        mock_slack_client.list_tools.return_value = [
            ToolSchema(name="send", description="Send"),
        ]
        
        tools = await router.list_all_tools(exclude_namespaces=["notion"])
        
        assert len(tools) == 1
        assert tools[0].name == "slack.send"
        mock_notion_client.list_tools.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_list_tools_handles_error(self, router, mock_notion_client):
        """Test listing tools handles backend errors gracefully."""
        router.register_backend("notion", mock_notion_client)
        mock_notion_client.list_tools.side_effect = Exception("Failed")
        
        tools = await router.list_all_tools()
        
        assert tools == []  # Empty, not exception
    
    @pytest.mark.asyncio
    async def test_list_tools_partial_failure(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test listing tools continues on partial failure."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        
        mock_notion_client.list_tools.side_effect = Exception("Failed")
        mock_slack_client.list_tools.return_value = [
            ToolSchema(name="send", description="Send"),
        ]
        
        tools = await router.list_all_tools()
        
        # Should still get Slack tools
        assert len(tools) == 1
        assert tools[0].name == "slack.send"
    
    @pytest.mark.asyncio
    async def test_list_tools_preserves_schema(
        self, router, mock_notion_client
    ):
        """Test listing tools preserves input schema."""
        router.register_backend("notion", mock_notion_client)
        input_schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
        }
        mock_notion_client.list_tools.return_value = [
            ToolSchema(
                name="search",
                description="Search",
                input_schema=input_schema,
            ),
        ]
        
        tools = await router.list_all_tools()
        
        assert tools[0].input_schema == input_schema
    
    @pytest.mark.asyncio
    async def test_list_empty_backends(self, router):
        """Test listing tools with no backends."""
        tools = await router.list_all_tools()
        
        assert tools == []


# =============================================================================
# Health Checking Tests
# =============================================================================


class TestHealthChecking:
    """Tests for health checking."""
    
    @pytest.mark.asyncio
    async def test_check_backend_health(self, router, mock_notion_client):
        """Test checking single backend health."""
        router.register_backend("notion", mock_notion_client)
        mock_notion_client.check_health.return_value = True
        
        healthy = await router.check_backend_health("notion")
        
        assert healthy is True
        mock_notion_client.check_health.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_backend_health_unhealthy(self, router, mock_notion_client):
        """Test checking unhealthy backend."""
        router.register_backend("notion", mock_notion_client)
        mock_notion_client.check_health.return_value = False
        
        healthy = await router.check_backend_health("notion")
        
        assert healthy is False
    
    @pytest.mark.asyncio
    async def test_check_backend_health_nonexistent(self, router):
        """Test checking non-existent backend returns False."""
        healthy = await router.check_backend_health("nonexistent")
        
        assert healthy is False
    
    @pytest.mark.asyncio
    async def test_check_all_backends_health(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test checking all backends health."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        mock_notion_client.check_health.return_value = True
        mock_slack_client.check_health.return_value = False
        
        health = await router.check_all_backends_health()
        
        assert health == {"notion": True, "slack": False}
    
    @pytest.mark.asyncio
    async def test_check_all_backends_empty(self, router):
        """Test checking health with no backends."""
        health = await router.check_all_backends_health()
        
        assert health == {}
    
    @pytest.mark.asyncio
    async def test_get_healthy_backends(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test getting list of healthy backends."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        mock_notion_client.check_health.return_value = True
        mock_slack_client.check_health.return_value = False
        
        healthy = await router.get_healthy_backends()
        
        assert healthy == ["notion"]
    
    @pytest.mark.asyncio
    async def test_get_healthy_backends_all_healthy(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test getting healthy backends when all healthy."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        mock_notion_client.check_health.return_value = True
        mock_slack_client.check_health.return_value = True
        
        healthy = await router.get_healthy_backends()
        
        assert set(healthy) == {"notion", "slack"}
    
    @pytest.mark.asyncio
    async def test_get_healthy_backends_none_healthy(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test getting healthy backends when none healthy."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        mock_notion_client.check_health.return_value = False
        mock_slack_client.check_health.return_value = False
        
        healthy = await router.get_healthy_backends()
        
        assert healthy == []


# =============================================================================
# Initialization Tests
# =============================================================================


class TestInitialization:
    """Tests for backend initialization."""
    
    @pytest.mark.asyncio
    async def test_initialize_all_backends(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test initializing all backends."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        
        results = await router.initialize_all_backends(auth_token="Bearer xyz")
        
        assert results == {"notion": True, "slack": True}
        mock_notion_client.initialize.assert_called_once_with(auth_token="Bearer xyz")
        mock_slack_client.initialize.assert_called_once_with(auth_token="Bearer xyz")
    
    @pytest.mark.asyncio
    async def test_initialize_partial_failure(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test initialization with partial failure."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        mock_notion_client.initialize.side_effect = Exception("Failed")
        
        results = await router.initialize_all_backends()
        
        assert results["notion"] is False
        assert results["slack"] is True
    
    @pytest.mark.asyncio
    async def test_initialize_empty_backends(self, router):
        """Test initializing with no backends."""
        results = await router.initialize_all_backends()
        
        assert results == {}


# =============================================================================
# Factory Functions Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""
    
    def test_create_router(self, mock_connection_manager):
        """Test create_router factory."""
        router = create_router(mock_connection_manager)
        
        assert isinstance(router, BackendRouter)
        assert router.backend_count == 0
    
    def test_create_router_with_options(self, mock_connection_manager):
        """Test create_router with options."""
        router = create_router(
            mock_connection_manager,
            auto_register_generic=False
        )
        
        assert isinstance(router, BackendRouter)
    
    def test_create_router_with_backends(self, mock_connection_manager):
        """Test create_router_with_backends factory."""
        router = create_router_with_backends(
            mock_connection_manager,
            backend_ids=["notion", "slack"],
        )
        
        assert isinstance(router, BackendRouter)
        assert router.backend_count == 2
        assert "notion" in router.registered_backends
        assert "slack" in router.registered_backends
    
    def test_create_router_with_empty_backends(self, mock_connection_manager):
        """Test create_router_with_backends with empty list."""
        router = create_router_with_backends(
            mock_connection_manager,
            backend_ids=[],
        )
        
        assert router.backend_count == 0


# =============================================================================
# Exception Tests
# =============================================================================


class TestExceptions:
    """Tests for exception classes."""
    
    def test_router_error_base(self):
        """Test RouterError is base exception."""
        error = RouterError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_backend_not_found_error(self):
        """Test BackendNotFoundError inheritance."""
        error = BackendNotFoundError("Backend not found")
        assert isinstance(error, RouterError)
        assert str(error) == "Backend not found"
    
    def test_invalid_tool_name_error(self):
        """Test InvalidToolNameError inheritance."""
        error = InvalidToolNameError("Invalid tool name")
        assert isinstance(error, RouterError)
        assert str(error) == "Invalid tool name"


# =============================================================================
# Integration-Like Tests
# =============================================================================


class TestIntegrationScenarios:
    """Tests for integration-like scenarios."""
    
    @pytest.mark.asyncio
    async def test_multi_backend_routing(
        self, router, mock_notion_client, mock_slack_client, mock_hubspot_client
    ):
        """Test routing to multiple backends."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        router.register_backend("hubspot", mock_hubspot_client)
        
        # Set up responses
        mock_notion_client.call_tool.return_value = ToolResult(
            status=ToolCallStatus.SUCCESS,
            content=[{"type": "text", "text": "notion result"}],
        )
        mock_slack_client.call_tool.return_value = ToolResult(
            status=ToolCallStatus.SUCCESS,
            content=[{"type": "text", "text": "slack result"}],
        )
        mock_hubspot_client.call_tool.return_value = ToolResult(
            status=ToolCallStatus.SUCCESS,
            content=[{"type": "text", "text": "hubspot result"}],
        )
        
        # Route to each backend
        notion_result = await router.route_tool_call("notion.search", {})
        slack_result = await router.route_tool_call("slack.send", {})
        hubspot_result = await router.route_tool_call("hubspot.get", {})
        
        # Verify each routed correctly
        assert not notion_result.is_error
        assert not slack_result.is_error
        assert not hubspot_result.is_error
        
        mock_notion_client.call_tool.assert_called_once()
        mock_slack_client.call_tool.assert_called_once()
        mock_hubspot_client.call_tool.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_full_workflow(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test full registration, listing, and routing workflow."""
        # Register backends
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        
        # Set up tool lists
        mock_notion_client.list_tools.return_value = [
            ToolSchema(name="search_pages", description="Search"),
            ToolSchema(name="create_page", description="Create"),
        ]
        mock_slack_client.list_tools.return_value = [
            ToolSchema(name="send_message", description="Send"),
        ]
        
        # List all tools
        tools = await router.list_all_tools()
        assert len(tools) == 3
        
        # Set up tool call response
        mock_notion_client.call_tool.return_value = ToolResult(
            status=ToolCallStatus.SUCCESS,
            content=[],
        )
        
        # Route a call
        result = await router.route_tool_call(
            "notion.search_pages",
            {"query": "test"},
        )
        
        assert not result.is_error
