"""Tests for the Dynamic Backend Loader (WS-C1)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.backends.dynamic_registry import DynamicBackendLoader, ServiceConfig


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.registered_backends = ["notion", "slack", "hubspot", "gdrive", "gcalendar", "gmail"]
    return adapter


@pytest.fixture
def mock_connection_manager():
    mgr = MagicMock()
    mgr.register_backend = MagicMock()
    mgr.unregister_backend = MagicMock()
    mgr.check_backend_health = AsyncMock()
    return mgr


@pytest.fixture
def mock_tool_cache():
    cache = MagicMock()
    cache.set_tools = MagicMock()
    cache.invalidate = MagicMock()
    return cache


@pytest.fixture
def loader(mock_adapter, mock_connection_manager, mock_tool_cache):
    return DynamicBackendLoader(
        adapter=mock_adapter,
        connection_manager=mock_connection_manager,
        tool_cache=mock_tool_cache,
        control_plane_url="http://localhost:8000",
        internal_api_token="test-token",
        refresh_interval_seconds=5,
    )


def _registry_response(services):
    """Build a mock httpx.Response for the registry endpoint."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"services": services}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestServiceConfig:
    def test_from_dict_minimal(self):
        cfg = ServiceConfig.from_dict({
            "service_id": "jira-mcp",
            "display_name": "Jira MCP",
            "backend_type": "mcp",
            "endpoint_url": "https://jira.example.com/mcp",
        })
        assert cfg.service_id == "jira-mcp"
        assert cfg.backend_type == "mcp"
        assert cfg.status == "active"
        assert cfg.transport == "rest"

    def test_from_dict_with_tools(self):
        cfg = ServiceConfig.from_dict({
            "service_id": "jira-mcp",
            "display_name": "Jira MCP",
            "backend_type": "mcp",
            "endpoint_url": "https://jira.example.com/mcp",
            "discovered_tools": [
                {"name": "search_issues", "description": "Search", "inputSchema": {}},
            ],
            "permission_map": {"jira-mcp.search_issues": "jira-mcp:issues:search"},
        })
        assert len(cfg.discovered_tools) == 1
        assert cfg.permission_map["jira-mcp.search_issues"] == "jira-mcp:issues:search"


class TestDynamicBackendLoader:
    @pytest.mark.asyncio
    async def test_initial_load_success(self, loader):
        services = [
            {
                "service_id": "jira-mcp",
                "display_name": "Jira",
                "backend_type": "mcp",
                "endpoint_url": "https://jira.example.com/mcp",
            },
        ]
        with patch("app.backends.dynamic_registry.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_registry_response(services))
            mock_client_cls.return_value = mock_client

            count = await loader.initial_load()

        assert count == 1
        assert "jira-mcp" in loader.known_service_ids

    @pytest.mark.asyncio
    async def test_initial_load_skips_existing_rest(self, loader, mock_adapter):
        """REST backends already registered by hardcoded adapter are skipped."""
        services = [
            {
                "service_id": "notion",
                "display_name": "Notion",
                "backend_type": "rest",
                "endpoint_url": "https://api.notion.com/v1",
            },
        ]
        with patch("app.backends.dynamic_registry.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_registry_response(services))
            mock_client_cls.return_value = mock_client

            count = await loader.initial_load()

        # Notion was already in the adapter so _register_service returns False
        # but the service is still tracked
        assert count == 1
        assert "notion" in loader.known_service_ids

    @pytest.mark.asyncio
    async def test_initial_load_handles_error(self, loader):
        """Registry fetch failure does not crash — returns 0 and relies on hardcoded backends."""
        with patch("app.backends.dynamic_registry.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
            mock_client_cls.return_value = mock_client

            count = await loader.initial_load()

        assert count == 0
        assert len(loader.known_service_ids) == 0

    @pytest.mark.asyncio
    async def test_periodic_refresh_adds_new(self, loader, mock_connection_manager):
        """New services appearing in the registry are added."""
        services = [
            {
                "service_id": "linear-mcp",
                "display_name": "Linear",
                "backend_type": "mcp",
                "endpoint_url": "https://linear.example.com/mcp",
            },
        ]
        with patch("app.backends.dynamic_registry.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_registry_response(services))
            mock_client_cls.return_value = mock_client

            await loader.periodic_refresh()

        assert "linear-mcp" in loader.known_service_ids
        mock_connection_manager.register_backend.assert_called_once()

    @pytest.mark.asyncio
    async def test_periodic_refresh_removes_deactivated(self, loader, mock_connection_manager, mock_tool_cache):
        """Services no longer in the registry are unregistered."""
        loader._known_services["old-service"] = "mcp"

        with patch("app.backends.dynamic_registry.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_registry_response([]))
            mock_client_cls.return_value = mock_client

            await loader.periodic_refresh()

        assert "old-service" not in loader.known_service_ids
        mock_connection_manager.unregister_backend.assert_called_once_with("old-service")
        mock_tool_cache.invalidate.assert_called_once_with("old-service")

    @pytest.mark.asyncio
    async def test_mcp_backend_sets_tools_in_cache(self, loader, mock_tool_cache):
        """MCP backends with discovered_tools populate the tool cache."""
        services = [
            {
                "service_id": "jira-mcp",
                "display_name": "Jira",
                "backend_type": "mcp",
                "endpoint_url": "https://jira.example.com/mcp",
                "discovered_tools": [
                    {"name": "search_issues", "description": "Search issues", "inputSchema": {}},
                ],
            },
        ]
        with patch("app.backends.dynamic_registry.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=_registry_response(services))
            mock_client_cls.return_value = mock_client

            await loader.initial_load()

        mock_tool_cache.set_tools.assert_called_once()
        call_args = mock_tool_cache.set_tools.call_args
        assert call_args[0][0] == "jira-mcp"
        assert len(call_args[0][1]) == 1

    @pytest.mark.asyncio
    async def test_report_health(self, loader, mock_connection_manager):
        """Health reporting probes backends and posts to Control Plane."""
        loader._known_services = {"jira-mcp": "mcp", "notion": "rest"}

        with patch("app.backends.dynamic_registry.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock()
            mock_client_cls.return_value = mock_client

            await loader.report_health()

        mock_connection_manager.check_backend_health.assert_called_once_with("jira-mcp")

    def test_stop(self, loader):
        loader._running = True
        loader.stop()
        assert loader._running is False

    def test_known_service_ids(self, loader):
        loader._known_services = {"a": "rest", "b": "mcp"}
        assert set(loader.known_service_ids) == {"a", "b"}
