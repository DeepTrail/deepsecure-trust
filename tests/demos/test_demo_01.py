"""
Tests for Demo 1: Unified MCP Connection.

Tests verify that the demo script works correctly in mock mode
and produces the expected output structure.
"""

import pytest

from demos.demo_01_unified_connection import (
    ConnectionTimings,
    DemoResult,
    MCPDemoClient,
    MockMCPDemoClient,
    run_demo,
)


# =============================================================================
# ConnectionTimings Tests
# =============================================================================


class TestConnectionTimings:
    """Tests for ConnectionTimings dataclass."""
    
    def test_timings_creation(self):
        """Test creating connection timings."""
        timings = ConnectionTimings(
            init_time_ms=25.0,
            list_time_ms=50.0,
            total_time_ms=75.0,
        )
        
        assert timings.init_time_ms == 25.0
        assert timings.list_time_ms == 50.0
        assert timings.total_time_ms == 75.0


class TestDemoResult:
    """Tests for DemoResult dataclass."""
    
    def test_success_result(self):
        """Test creating a success result."""
        result = DemoResult(
            success=True,
            tools=[{"name": "test.tool"}],
            backends={"test"},
            timings=ConnectionTimings(10, 20, 30),
        )
        
        assert result.success is True
        assert len(result.tools) == 1
        assert "test" in result.backends
        assert result.error is None
    
    def test_error_result(self):
        """Test creating an error result."""
        result = DemoResult(
            success=False,
            tools=[],
            backends=set(),
            timings=ConnectionTimings(0, 0, 0),
            error="Connection failed",
        )
        
        assert result.success is False
        assert result.error == "Connection failed"


# =============================================================================
# MockMCPDemoClient Tests
# =============================================================================


class TestMockMCPDemoClient:
    """Tests for MockMCPDemoClient."""
    
    @pytest.mark.asyncio
    async def test_mock_client_returns_tools(self):
        """Mock client returns expected tools."""
        client = MockMCPDemoClient("http://test:8002/mcp")
        await client.connect()
        
        assert len(client.tools) == 6
        assert len(client.backends) == 3
        assert "notion" in client.backends
        assert "slack" in client.backends
        assert "gmail" in client.backends
    
    @pytest.mark.asyncio
    async def test_mock_client_returns_timings(self):
        """Mock client returns timing info."""
        client = MockMCPDemoClient("http://test:8002/mcp")
        timings = await client.connect()
        
        assert timings.init_time_ms > 0
        assert timings.list_time_ms > 0
        assert timings.total_time_ms > 0
    
    @pytest.mark.asyncio
    async def test_mock_client_accepts_token(self):
        """Mock client accepts session token."""
        client = MockMCPDemoClient(
            "http://test:8002/mcp",
            session_token="test-token",
        )
        await client.connect()
        
        assert client.session_token == "test-token"
        assert len(client.tools) > 0
    
    def test_tools_have_correct_namespace_format(self):
        """Tools follow namespace.action format."""
        client = MockMCPDemoClient("http://test:8002/mcp")
        
        for tool in client.MOCK_TOOLS:
            name = tool["name"]
            assert "." in name, f"Tool {name} should have namespace prefix"
            namespace, action = name.split(".", 1)
            assert namespace in ["notion", "slack", "gmail"]
            assert len(action) > 0
    
    def test_tools_have_descriptions(self):
        """All tools have descriptions."""
        client = MockMCPDemoClient("http://test:8002/mcp")
        
        for tool in client.MOCK_TOOLS:
            assert "description" in tool
            assert len(tool["description"]) > 0
    
    def test_tools_have_input_schemas(self):
        """All tools have input schemas."""
        client = MockMCPDemoClient("http://test:8002/mcp")
        
        for tool in client.MOCK_TOOLS:
            assert "inputSchema" in tool
            schema = tool["inputSchema"]
            assert schema.get("type") == "object"
            assert "properties" in schema


# =============================================================================
# MCPDemoClient Tests
# =============================================================================


class TestMCPDemoClient:
    """Tests for MCPDemoClient."""
    
    def test_client_initialization(self):
        """Test client initialization."""
        client = MCPDemoClient("http://gateway:8002/mcp")
        
        assert client.gateway_url == "http://gateway:8002/mcp"
        assert client.session_token is None
        assert len(client.tools) == 0
        assert len(client.backends) == 0
    
    def test_client_with_token(self):
        """Test client with session token."""
        client = MCPDemoClient(
            "http://gateway:8002/mcp",
            session_token="test-jwt",
        )
        
        assert client.session_token == "test-jwt"
    
    def test_next_id_increments(self):
        """Test request ID incrementing."""
        client = MCPDemoClient("http://gateway:8002/mcp")
        
        id1 = client._next_id()
        id2 = client._next_id()
        id3 = client._next_id()
        
        assert id1 == 1
        assert id2 == 2
        assert id3 == 3
    
    def test_extract_backends(self):
        """Test backend extraction from tools."""
        client = MCPDemoClient("http://gateway:8002/mcp")
        client.tools = [
            {"name": "notion.search"},
            {"name": "slack.send"},
            {"name": "notion.read"},
        ]
        
        client._extract_backends()
        
        assert len(client.backends) == 2
        assert "notion" in client.backends
        assert "slack" in client.backends


# =============================================================================
# Demo Run Tests
# =============================================================================


class TestRunDemo:
    """Tests for the run_demo function."""
    
    @pytest.mark.asyncio
    async def test_run_demo_mock_mode_succeeds(self):
        """Demo succeeds in mock mode."""
        result = await run_demo(
            gateway_url="http://test:8002/mcp",
            mock_mode=True,
        )
        
        assert result.success is True
        assert len(result.tools) == 6
        assert len(result.backends) == 3
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_run_demo_returns_timings(self):
        """Demo returns timing information."""
        result = await run_demo(
            gateway_url="http://test:8002/mcp",
            mock_mode=True,
        )
        
        assert result.timings.init_time_ms > 0
        assert result.timings.list_time_ms > 0
        assert result.timings.total_time_ms > 0
    
    @pytest.mark.asyncio
    async def test_run_demo_has_multiple_backends(self):
        """Demo shows tools from multiple backends."""
        result = await run_demo(
            gateway_url="http://test:8002/mcp",
            mock_mode=True,
        )
        
        # Key value prop: multiple backends from one connection
        assert len(result.backends) >= 2
        
        # Verify specific backends
        assert "notion" in result.backends
        assert "slack" in result.backends


# =============================================================================
# Value Proposition Tests
# =============================================================================


class TestValueProposition:
    """Tests that verify the demo's value proposition."""
    
    @pytest.mark.asyncio
    async def test_single_gateway_multiple_backends(self):
        """
        The key value proposition:
        ONE gateway connection provides access to MULTIPLE backends.
        """
        result = await run_demo(
            gateway_url="http://test:8002/mcp",  # ONE URL
            mock_mode=True,
        )
        
        # ONE connection (gateway URL)
        # MULTIPLE backends
        assert len(result.backends) >= 2, "Should have multiple backends"
        
        # Tools from each backend
        tool_backends = set()
        for tool in result.tools:
            name = tool.get("name", "")
            if "." in name:
                tool_backends.add(name.split(".")[0])
        
        assert tool_backends == result.backends
    
    @pytest.mark.asyncio
    async def test_no_backend_urls_in_client(self):
        """Agent code should have no awareness of backend URLs."""
        client = MockMCPDemoClient("http://gateway:8002/mcp")
        await client.connect()
        
        # Client only knows gateway URL
        assert "gateway" in client.gateway_url
        
        # Client doesn't have any backend URLs
        client_attributes = vars(client)
        for attr_name, attr_value in client_attributes.items():
            if isinstance(attr_value, str) and "://" in attr_value:
                # Should only be the gateway URL
                assert "gateway" in attr_value, (
                    f"Found non-gateway URL in {attr_name}: {attr_value}"
                )
    
    @pytest.mark.asyncio
    async def test_tools_are_namespaced(self):
        """All tools should be namespaced with backend prefix."""
        result = await run_demo(
            gateway_url="http://test:8002/mcp",
            mock_mode=True,
        )
        
        for tool in result.tools:
            name = tool.get("name", "")
            assert "." in name, f"Tool {name} should be namespaced"
            
            namespace, _ = name.split(".", 1)
            assert namespace in result.backends, (
                f"Tool namespace {namespace} should be in backends"
            )
