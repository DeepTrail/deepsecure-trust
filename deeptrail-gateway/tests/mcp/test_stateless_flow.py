"""
Comprehensive stateless MCP flow tests (B10).

Validates that the gateway works correctly without initialize — the core
requirement of MCP 2026-07-28.  All tests derive tool access and permissions
from JWT context (delegated_permissions) rather than session state.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.mcp.handlers.tools_list import (
    handle_tools_list_standalone,
    configure_tools_list_handler,
)
from app.mcp.handlers.tools_call import (
    handle_tools_call_standalone,
    configure_tools_call_handler,
)
from app.mcp.handlers.discover import handle_discover
from app.mcp.session_manager import MCPSessionManager
from app.mcp.tool_cache import ToolCache, CachedTool
from app.mcp.protocol import MCPError


@pytest.fixture
def empty_session_manager():
    """Session manager with NO sessions — simulates stateless gateway."""
    return MCPSessionManager()


@pytest.fixture
def tool_cache():
    cache = ToolCache(ttl_seconds=300)
    cache.set_tools("notion", [
        CachedTool(name="search_pages", description="Search pages", input_schema={"type": "object"}),
        CachedTool(name="read_page", description="Read a page", input_schema={"type": "object"}),
    ])
    cache.set_tools("slack", [
        CachedTool(name="send_message", description="Send message", input_schema={"type": "object"}),
    ])
    return cache


@pytest.fixture(autouse=True)
def mock_fail_closed():
    with patch(
        "app.mcp.handlers.tools_call.enforce_fail_closed",
        new_callable=AsyncMock,
    ), patch(
        "app.mcp.handlers.tools_list.enforce_fail_closed",
        new_callable=AsyncMock,
    ):
        yield


class TestStatelessToolsList:
    """tools/list without initialize — derives tools from JWT permissions."""

    @pytest.mark.asyncio
    async def test_tools_list_without_session(self, empty_session_manager, tool_cache):
        """tools/list returns tools based on permissions even with no session."""
        params = {
            "_context": {
                "delegated_permissions": ["notion:pages:search"],
                "agent_id": "stateless-agent",
            },
        }

        result = await handle_tools_list_standalone(
            params, empty_session_manager, tool_cache
        )
        tools = result["tools"]
        tool_names = [t["name"] for t in tools]
        assert any("notion" in n for n in tool_names)

    @pytest.mark.asyncio
    async def test_tools_list_empty_permissions(self, empty_session_manager, tool_cache):
        """tools/list with empty permissions returns empty list."""
        params = {
            "_context": {
                "delegated_permissions": [],
                "agent_id": "stateless-agent",
            },
        }

        result = await handle_tools_list_standalone(
            params, empty_session_manager, tool_cache
        )
        assert result["tools"] == []

    @pytest.mark.asyncio
    async def test_tools_list_multiple_backends(self, empty_session_manager, tool_cache):
        """tools/list filters across multiple backends."""
        params = {
            "_context": {
                "delegated_permissions": [
                    "notion:pages:search",
                    "slack:messages:send",
                ],
                "agent_id": "stateless-agent",
            },
        }

        result = await handle_tools_list_standalone(
            params, empty_session_manager, tool_cache
        )
        tool_names = [t["name"] for t in result["tools"]]
        has_notion = any("notion" in n for n in tool_names)
        has_slack = any("slack" in n for n in tool_names)
        assert has_notion
        assert has_slack

    @pytest.mark.asyncio
    async def test_tools_list_includes_meta(self, empty_session_manager, tool_cache):
        """tools/list response includes _meta with ttlMs and cacheScope (B9)."""
        params = {
            "_context": {
                "delegated_permissions": ["notion:pages:search"],
                "agent_id": "stateless-agent",
            },
        }

        result = await handle_tools_list_standalone(
            params, empty_session_manager, tool_cache
        )
        assert "_meta" in result
        assert "ttlMs" in result["_meta"]
        assert "cacheScope" in result["_meta"]


class TestStatelessToolsCall:
    """tools/call without initialize — uses JWT context for auth and routing."""

    @pytest.mark.asyncio
    async def test_tools_call_without_session(self, empty_session_manager):
        """tools/call works with permissions from JWT (no session)."""
        configure_tools_call_handler(empty_session_manager)

        mock_injection = MagicMock()
        mock_injection.success = True
        mock_injection.headers = {"Authorization": "Bearer mock"}
        mock_injection.error = None
        mock_injection.error_message = None

        params = {
            "name": "notion.search_pages",
            "arguments": {"query": "test"},
            "_context": {
                "delegated_permissions": ["notion:pages:search"],
                "agent_id": "stateless-agent",
                "delegator": "user@example.com",
            },
        }

        with patch(
            "app.mcp.handlers.tools_call.get_credential_injector",
        ) as mock_ci:
            mock_ci.return_value.inject_credentials = AsyncMock(return_value=mock_injection)
            result = await handle_tools_call_standalone(params, empty_session_manager)
        assert "content" in result

    @pytest.mark.asyncio
    async def test_tools_call_no_permissions_rejected(self, empty_session_manager):
        """tools/call with no permissions raises auth error."""
        configure_tools_call_handler(empty_session_manager)

        params = {
            "name": "notion.search_pages",
            "arguments": {},
            "_context": {
                "delegated_permissions": [],
                "agent_id": "stateless-agent",
            },
        }

        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call_standalone(params, empty_session_manager)
        assert "Authentication required" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_tools_call_permission_denied(self, empty_session_manager):
        """tools/call denied when permission doesn't match tool."""
        configure_tools_call_handler(empty_session_manager)

        params = {
            "name": "notion.create_page",
            "arguments": {"title": "new"},
            "_context": {
                "delegated_permissions": ["slack:messages:write"],
                "agent_id": "stateless-agent",
                "delegator": "user@example.com",
            },
        }

        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call_standalone(params, empty_session_manager)
        # Permission denied code
        assert exc_info.value.code == -32001

    @pytest.mark.asyncio
    async def test_tools_call_no_context_rejected(self, empty_session_manager):
        """tools/call with no context at all raises auth error."""
        configure_tools_call_handler(empty_session_manager)

        params = {
            "name": "notion.search_pages",
            "arguments": {},
        }

        with pytest.raises(MCPError) as exc_info:
            await handle_tools_call_standalone(params, empty_session_manager)
        assert "Authentication required" in exc_info.value.message


class TestServerDiscover:
    """server/discover returns metadata without any session state."""

    @pytest.mark.asyncio
    async def test_discover_returns_protocol_versions(self):
        result = await handle_discover({"_context": {}})
        assert "protocolVersions" in result
        assert "2026-07-28" in result["protocolVersions"]

    @pytest.mark.asyncio
    async def test_discover_returns_server_info(self):
        result = await handle_discover({"_context": {}})
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "DeepTrail Virtual MCP Server"

    @pytest.mark.asyncio
    async def test_discover_returns_capabilities(self):
        result = await handle_discover({"_context": {}})
        assert "capabilities" in result
        assert "tools" in result["capabilities"]


class TestInitializeOptional:
    """B7: Verify the full MCP lifecycle works without calling initialize."""

    @pytest.mark.asyncio
    async def test_full_journey_without_initialize(self, empty_session_manager, tool_cache):
        """Complete MCP journey: discover -> tools/list -> tools/call, no initialize."""
        configure_tools_call_handler(empty_session_manager)

        # Step 1: server/discover
        discover_result = await handle_discover({"_context": {}})
        assert "2026-07-28" in discover_result["protocolVersions"]

        # Step 2: tools/list (stateless)
        list_params = {
            "_context": {
                "delegated_permissions": ["notion:pages:search"],
                "agent_id": "no-init-agent",
            },
        }
        list_result = await handle_tools_list_standalone(
            list_params, empty_session_manager, tool_cache
        )
        assert len(list_result["tools"]) > 0

        # Step 3: tools/call (stateless, with mocked creds)
        mock_injection = MagicMock()
        mock_injection.success = True
        mock_injection.headers = {"Authorization": "Bearer mock"}
        mock_injection.error = None
        mock_injection.error_message = None

        call_params = {
            "name": "notion.search_pages",
            "arguments": {"query": "quarterly"},
            "_context": {
                "delegated_permissions": ["notion:pages:search"],
                "agent_id": "no-init-agent",
                "delegator": "user@example.com",
            },
        }

        with patch(
            "app.mcp.handlers.tools_call.get_credential_injector",
        ) as mock_ci:
            mock_ci.return_value.inject_credentials = AsyncMock(return_value=mock_injection)
            call_result = await handle_tools_call_standalone(
                call_params, empty_session_manager
            )
        assert "content" in call_result

    @pytest.mark.asyncio
    async def test_session_manager_has_zero_sessions(self, empty_session_manager):
        """The session manager should have no sessions in stateless mode."""
        assert empty_session_manager.get_session_count() == 0


class TestDualProtocolVersioning:
    """Verify both 2025-11-25 (stateful) and 2026-07-28 (stateless) work."""

    @pytest.mark.asyncio
    async def test_legacy_version_with_session_works(self, tool_cache):
        """2025-11-25 client with an active session gets tools from session cache."""
        mgr = MCPSessionManager()
        mgr.create_agent_session(
            agent_session_id="legacy-agent",
            delegator="alice@example.com",
            delegated_permissions=["notion:pages:search"],
            connected_services=[
                {
                    "service_id": "notion",
                    "oauth_token_ref": "vault://ref",
                    "available_tools": ["search_pages"],
                }
            ],
        )

        params = {
            "_context": {
                "agent_session_id": "legacy-agent",
                "delegated_permissions": ["notion:pages:search"],
                "mcp_protocol_version": "2025-11-25",
            },
        }

        result = await handle_tools_list_standalone(params, mgr, tool_cache)
        tool_names = [t["name"] for t in result["tools"]]
        assert any("notion" in n for n in tool_names)

    @pytest.mark.asyncio
    async def test_modern_version_without_session_works(self, empty_session_manager, tool_cache):
        """2026-07-28 client with no session gets tools from JWT permissions."""
        params = {
            "_context": {
                "delegated_permissions": ["notion:pages:search"],
                "agent_id": "modern-agent",
                "mcp_protocol_version": "2026-07-28",
            },
        }

        result = await handle_tools_list_standalone(
            params, empty_session_manager, tool_cache
        )
        tool_names = [t["name"] for t in result["tools"]]
        assert any("notion" in n for n in tool_names)
