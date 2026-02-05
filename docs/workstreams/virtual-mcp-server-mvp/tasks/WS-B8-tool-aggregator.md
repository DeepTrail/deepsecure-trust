# Task: WS-B8 Implement Tool Aggregator

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-B: Gateway MCP Core |
| **Dependencies** | B5 (Tool schema cache), B6 (tools/list handler) |
| **Blocked By** | None (B5, B6 are complete ✅) |
| **Assigned** | - |
| **Created** | February 4, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 4 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 1: Unified Connection |
| **Validates User Journey Step** | Step 7: Agent Discovers Tools |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] B5 (Tool schema cache) is complete
- [x] B6 (tools/list handler) is complete
- [x] B4 (Namespace prefixer) is complete
- [ ] `deeptrail-gateway/` service structure exists
- [ ] ToolCache can be imported from `app.mcp.tool_cache`
- [ ] namespace utilities can be imported from `app.mcp.namespace`
- [ ] PermissionMapper can be imported from `app.mcp.permission_mapper`

---

## Task Description

Implement the ToolAggregator that combines tools from multiple backend MCP servers into a unified, namespaced view. This is the component that enables the "Unified Connection" value proposition: agent connects to ONE gateway and sees tools from 2-3 backends.

### Context

From the MVP design (Section 2.8 - Step 7: Agent Discovers Tools):

```
Gateway Processing for tools/list:

1. AGGREGATE from backends (what backends offer):
   ┌─────────────────────────────────────────────────────────────────┐
   │ Notion MCP Server offers:                                        │
   │   • search_pages    • read_page    • create_page    • ...       │
   │                                                                  │
   │ Slack MCP Server offers:                                         │
   │   • search_messages • send_message • list_channels  • ...       │
   └─────────────────────────────────────────────────────────────────┘

2. NAMESPACE PREFIX (avoid collisions):
   • search_pages     → notion.search_pages
   • read_page        → notion.read_page
   • search_messages  → slack.search_messages
   • list_channels    → slack.list_channels

3. FILTER by agent's delegated permissions:
   Agent sees only tools matching their delegated permissions
```

The aggregator must:
- **Aggregate Tools**: Collect tools from multiple backends via ToolCache
- **Apply Namespacing**: Prefix all tools with `{backend}.{tool}` pattern
- **Enhance Descriptions**: Add `[{Backend}]` prefix to descriptions
- **Support Filtering**: Filter tools by backend, permissions, or custom predicates
- **Handle Failures Gracefully**: Log warnings but continue if one backend fails

### Technical Notes

- Use ToolCache (B5) to fetch tools - avoid direct backend calls
- Use namespace utilities (B4) for prefixing
- Use PermissionMapper (B6) for permission-based filtering
- Thread-safe operations (supports concurrent access)
- Stateless design - no session state in aggregator itself

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/mcp/aggregator.py` | **CREATE** | ToolAggregator implementation |
| `deeptrail-gateway/app/mcp/__init__.py` | **MODIFY** | Export ToolAggregator |
| `deeptrail-gateway/tests/mcp/test_aggregator.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. ToolAggregator (`deeptrail-gateway/app/mcp/aggregator.py`)

```python
"""
MCP Tool Aggregator for Virtual MCP Server.

Combines tools from multiple backend MCP servers into a unified, namespaced
view. This is the core component enabling the "Unified Connection" value
proposition.

How it works:
1. Collect tools from ToolCache for specified backends
2. Apply namespace prefix to each tool (notion.search_pages)
3. Enhance descriptions with backend prefix ([Notion] Search pages)
4. Optionally filter by permissions or custom predicates
5. Return aggregated, namespaced tools

Usage:
    from app.mcp.aggregator import ToolAggregator
    from app.mcp.tool_cache import ToolCache
    
    cache = ToolCache()
    aggregator = ToolAggregator(cache)
    
    # Aggregate from all registered backends
    tools = aggregator.aggregate_all()
    
    # Aggregate from specific backends
    tools = aggregator.aggregate(backends=["notion", "slack"])
    
    # Aggregate with permission filtering
    tools = aggregator.aggregate_with_permissions(
        backends=["notion", "slack"],
        permissions=["notion:pages:search", "slack:messages:search"]
    )
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .namespace import Tool, prefix_tool
from .permission_mapper import PermissionMapper
from .tool_cache import CachedTool, ToolCache

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AggregatedTool:
    """
    A tool that has been aggregated from a backend with namespace applied.
    
    Attributes:
        name: Namespaced tool name (e.g., "notion.search_pages")
        description: Enhanced description with backend prefix
        inputSchema: JSON Schema for parameters
        backend: Original backend ID (e.g., "notion")
        original_name: Original tool name without namespace (e.g., "search_pages")
    """
    name: str
    description: str
    inputSchema: dict[str, Any]
    backend: str
    original_name: str
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to MCP tool format for JSON-RPC response."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
        }
    
    def to_tool(self) -> Tool:
        """Convert to namespace.Tool for compatibility."""
        return Tool(
            name=self.name,
            description=self.description,
            inputSchema=self.inputSchema,
        )


@dataclass
class AggregationResult:
    """
    Result of a tool aggregation operation.
    
    Attributes:
        tools: List of aggregated tools
        backends_succeeded: Backends that provided tools
        backends_failed: Backends that failed to provide tools
        total_tools: Total number of tools aggregated
    """
    tools: list[AggregatedTool] = field(default_factory=list)
    backends_succeeded: list[str] = field(default_factory=list)
    backends_failed: list[str] = field(default_factory=list)
    
    @property
    def total_tools(self) -> int:
        """Total number of aggregated tools."""
        return len(self.tools)
    
    @property
    def all_succeeded(self) -> bool:
        """Whether all backends succeeded."""
        return len(self.backends_failed) == 0
    
    def to_tool_list(self) -> list[dict[str, Any]]:
        """Convert to list of MCP tool dictionaries."""
        return [tool.to_dict() for tool in self.tools]


# =============================================================================
# Aggregator
# =============================================================================


class ToolAggregator:
    """
    Aggregates tools from multiple backend MCP servers.
    
    The aggregator collects tools from the ToolCache, applies namespace
    prefixes, and optionally filters by permissions. It provides a unified
    view of all available tools across backends.
    
    Thread-safety: This class is thread-safe. Multiple threads can call
    aggregation methods concurrently.
    
    Example:
        aggregator = ToolAggregator(tool_cache)
        
        # Get all tools from all backends
        result = aggregator.aggregate_all()
        print(f"Found {result.total_tools} tools from {len(result.backends_succeeded)} backends")
        
        # Get tools filtered by permissions
        result = aggregator.aggregate_with_permissions(
            backends=["notion", "slack"],
            permissions=["notion:pages:search", "slack:messages:search"]
        )
    """
    
    def __init__(
        self,
        tool_cache: ToolCache,
        registered_backends: list[str] | None = None,
    ):
        """
        Initialize the aggregator.
        
        Args:
            tool_cache: ToolCache instance for fetching backend tools
            registered_backends: List of known backend IDs (optional, for aggregate_all)
        """
        self._tool_cache = tool_cache
        self._registered_backends = registered_backends or []
    
    def register_backend(self, backend_id: str) -> None:
        """
        Register a backend for aggregate_all() calls.
        
        Args:
            backend_id: Backend identifier (e.g., "notion")
        """
        if backend_id not in self._registered_backends:
            self._registered_backends.append(backend_id)
            logger.debug("Registered backend for aggregation: %s", backend_id)
    
    def unregister_backend(self, backend_id: str) -> bool:
        """
        Unregister a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            True if backend was removed, False if not found
        """
        if backend_id in self._registered_backends:
            self._registered_backends.remove(backend_id)
            logger.debug("Unregistered backend: %s", backend_id)
            return True
        return False
    
    def get_registered_backends(self) -> list[str]:
        """Get list of registered backend IDs."""
        return list(self._registered_backends)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Core Aggregation Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def aggregate(
        self,
        backends: Iterable[str],
        filter_func: Callable[[AggregatedTool], bool] | None = None,
    ) -> AggregationResult:
        """
        Aggregate tools from specified backends.
        
        Args:
            backends: Backend IDs to aggregate from
            filter_func: Optional function to filter tools (returns True to include)
            
        Returns:
            AggregationResult with aggregated tools and status
        """
        result = AggregationResult()
        
        for backend_id in backends:
            try:
                # Get tools from cache
                cached_tools = self._tool_cache.get_tools(backend_id)
                
                if cached_tools is None:
                    logger.warning(
                        "No cached tools for backend: %s (cache miss or not registered)",
                        backend_id
                    )
                    result.backends_failed.append(backend_id)
                    continue
                
                # Convert and namespace each tool
                for cached_tool in cached_tools:
                    aggregated = self._create_aggregated_tool(cached_tool, backend_id)
                    
                    # Apply filter if provided
                    if filter_func is not None and not filter_func(aggregated):
                        continue
                    
                    result.tools.append(aggregated)
                
                result.backends_succeeded.append(backend_id)
                logger.debug(
                    "Aggregated %d tools from backend: %s",
                    len([t for t in result.tools if t.backend == backend_id]),
                    backend_id
                )
                
            except Exception as e:
                logger.error(
                    "Failed to aggregate tools from backend %s: %s",
                    backend_id,
                    str(e)
                )
                result.backends_failed.append(backend_id)
        
        logger.info(
            "Aggregation complete: %d tools from %d backends (%d failed)",
            result.total_tools,
            len(result.backends_succeeded),
            len(result.backends_failed)
        )
        
        return result
    
    def aggregate_all(
        self,
        filter_func: Callable[[AggregatedTool], bool] | None = None,
    ) -> AggregationResult:
        """
        Aggregate tools from all registered backends.
        
        Args:
            filter_func: Optional function to filter tools
            
        Returns:
            AggregationResult with aggregated tools from all backends
        """
        return self.aggregate(self._registered_backends, filter_func)
    
    def aggregate_with_permissions(
        self,
        backends: Iterable[str],
        permissions: list[str],
    ) -> AggregationResult:
        """
        Aggregate tools filtered by delegated permissions.
        
        Uses PermissionMapper to check if each tool's required permission
        is in the provided permission list.
        
        Args:
            backends: Backend IDs to aggregate from
            permissions: List of delegated permission strings
            
        Returns:
            AggregationResult with only permitted tools
        """
        def permission_filter(tool: AggregatedTool) -> bool:
            return PermissionMapper.is_tool_permitted(tool.name, permissions)
        
        return self.aggregate(backends, permission_filter)
    
    def aggregate_for_backend(
        self,
        backend_id: str,
        filter_func: Callable[[AggregatedTool], bool] | None = None,
    ) -> AggregationResult:
        """
        Aggregate tools from a single backend.
        
        Convenience method for single-backend aggregation.
        
        Args:
            backend_id: Backend to aggregate from
            filter_func: Optional filter function
            
        Returns:
            AggregationResult from the specified backend
        """
        return self.aggregate([backend_id], filter_func)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Helper Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def _create_aggregated_tool(
        self,
        cached_tool: CachedTool,
        backend_id: str,
    ) -> AggregatedTool:
        """
        Create an AggregatedTool from a cached tool.
        
        Applies namespace prefix and enhances description.
        
        Args:
            cached_tool: Tool from cache
            backend_id: Backend identifier for prefixing
            
        Returns:
            AggregatedTool with namespace applied
        """
        # Use namespace.prefix_tool for consistent prefixing
        prefixed = prefix_tool(cached_tool.to_dict(), backend_id)
        
        return AggregatedTool(
            name=prefixed["name"],
            description=prefixed["description"],
            inputSchema=prefixed.get("inputSchema", {}),
            backend=backend_id,
            original_name=cached_tool.name,
        )
    
    def get_backend_for_tool(self, namespaced_tool: str) -> str | None:
        """
        Extract backend ID from a namespaced tool name.
        
        Args:
            namespaced_tool: Tool name like "notion.search_pages"
            
        Returns:
            Backend ID or None if invalid format
        """
        if "." not in namespaced_tool:
            return None
        return namespaced_tool.split(".", 1)[0]
    
    def get_original_name(self, namespaced_tool: str) -> str | None:
        """
        Extract original tool name from namespaced tool.
        
        Args:
            namespaced_tool: Tool name like "notion.search_pages"
            
        Returns:
            Original name (e.g., "search_pages") or None if invalid
        """
        if "." not in namespaced_tool:
            return None
        return namespaced_tool.split(".", 1)[1]
    
    def find_tool(
        self,
        namespaced_tool: str,
        backends: Iterable[str] | None = None,
    ) -> AggregatedTool | None:
        """
        Find a specific tool by namespaced name.
        
        Args:
            namespaced_tool: Tool name like "notion.search_pages"
            backends: Backends to search (defaults to registered)
            
        Returns:
            AggregatedTool or None if not found
        """
        backend_id = self.get_backend_for_tool(namespaced_tool)
        if not backend_id:
            return None
        
        original_name = self.get_original_name(namespaced_tool)
        if not original_name:
            return None
        
        # Check if backend is in search scope
        search_backends = list(backends) if backends else self._registered_backends
        if backend_id not in search_backends:
            return None
        
        # Get tools from cache
        cached_tools = self._tool_cache.get_tools(backend_id)
        if not cached_tools:
            return None
        
        # Find matching tool
        for cached_tool in cached_tools:
            if cached_tool.name == original_name:
                return self._create_aggregated_tool(cached_tool, backend_id)
        
        return None


# =============================================================================
# Global Instance
# =============================================================================


_aggregator: ToolAggregator | None = None


def get_tool_aggregator() -> ToolAggregator:
    """
    Get the global ToolAggregator instance.
    
    Raises:
        RuntimeError: If aggregator not initialized
    """
    if _aggregator is None:
        raise RuntimeError(
            "ToolAggregator not initialized. Call configure_tool_aggregator() first."
        )
    return _aggregator


def configure_tool_aggregator(
    tool_cache: ToolCache,
    registered_backends: list[str] | None = None,
) -> ToolAggregator:
    """
    Initialize the global ToolAggregator.
    
    Args:
        tool_cache: ToolCache instance
        registered_backends: Initial list of backends
        
    Returns:
        Configured ToolAggregator instance
    """
    global _aggregator
    _aggregator = ToolAggregator(tool_cache, registered_backends)
    logger.info(
        "ToolAggregator configured with %d backends",
        len(registered_backends or [])
    )
    return _aggregator
```

### 2. Update `__init__.py`

```python
# Add to deeptrail-gateway/app/mcp/__init__.py
from .aggregator import (
    AggregatedTool,
    AggregationResult,
    ToolAggregator,
    configure_tool_aggregator,
    get_tool_aggregator,
)

__all__ = [
    # ... existing exports ...
    "AggregatedTool",
    "AggregationResult",
    "ToolAggregator",
    "configure_tool_aggregator",
    "get_tool_aggregator",
]
```

---

## Acceptance Criteria

### Aggregation Criteria

- [ ] `aggregate()` collects tools from specified backends via ToolCache
- [ ] `aggregate_all()` collects from all registered backends
- [ ] Tools from multiple backends combined into single list
- [ ] Failed backend doesn't stop aggregation of others (graceful failure)
- [ ] `AggregationResult` tracks succeeded and failed backends

### Namespacing Criteria

- [ ] All tool names prefixed with `{backend}.{tool}` pattern
- [ ] Descriptions enhanced with `[{Backend}]` prefix
- [ ] `inputSchema` preserved unchanged
- [ ] Original name and backend tracked in `AggregatedTool`

### Filtering Criteria

- [ ] `filter_func` parameter allows custom filtering
- [ ] `aggregate_with_permissions()` filters by delegated permissions
- [ ] Uses `PermissionMapper.is_tool_permitted()` for permission checks
- [ ] Unpermitted tools excluded from result

### Helper Methods Criteria

- [ ] `get_backend_for_tool()` extracts backend from namespaced name
- [ ] `get_original_name()` extracts original tool name
- [ ] `find_tool()` locates specific tool by namespaced name
- [ ] `register_backend()` / `unregister_backend()` manage backend list

### Integration Criteria

- [ ] Works with ToolCache (B5) for tool retrieval
- [ ] Uses namespace utilities (B4) for prefixing
- [ ] Compatible with PermissionMapper (B6) for filtering
- [ ] Exported from `app.mcp.__init__.py`
- [ ] All tests pass with `pytest tests/mcp/test_aggregator.py`

---

## Test Cases

Create `deeptrail-gateway/tests/mcp/test_aggregator.py`:

```python
"""Tests for ToolAggregator."""

import pytest
from unittest.mock import MagicMock, patch

from app.mcp.aggregator import (
    AggregatedTool,
    AggregationResult,
    ToolAggregator,
    configure_tool_aggregator,
    get_tool_aggregator,
)
from app.mcp.tool_cache import CachedTool, ToolCache


@pytest.fixture
def mock_tool_cache():
    """Create mock tool cache with test data."""
    cache = MagicMock(spec=ToolCache)
    
    notion_tools = [
        CachedTool(name="search_pages", description="Search pages", inputSchema={"type": "object"}),
        CachedTool(name="read_page", description="Read a page", inputSchema={"type": "object"}),
        CachedTool(name="create_page", description="Create a page", inputSchema={"type": "object"}),
    ]
    
    slack_tools = [
        CachedTool(name="search_messages", description="Search messages", inputSchema={"type": "object"}),
        CachedTool(name="send_message", description="Send a message", inputSchema={"type": "object"}),
        CachedTool(name="list_channels", description="List channels", inputSchema={"type": "object"}),
    ]
    
    def get_tools(backend_id):
        if backend_id == "notion":
            return notion_tools
        elif backend_id == "slack":
            return slack_tools
        return None
    
    cache.get_tools.side_effect = get_tools
    return cache


@pytest.fixture
def aggregator(mock_tool_cache):
    """Create aggregator with mock cache."""
    return ToolAggregator(
        tool_cache=mock_tool_cache,
        registered_backends=["notion", "slack"]
    )


class TestAggregatedTool:
    """Test AggregatedTool data class."""
    
    def test_to_dict(self):
        """Test conversion to MCP format."""
        tool = AggregatedTool(
            name="notion.search_pages",
            description="[Notion] Search pages",
            inputSchema={"type": "object"},
            backend="notion",
            original_name="search_pages"
        )
        
        result = tool.to_dict()
        
        assert result["name"] == "notion.search_pages"
        assert result["description"] == "[Notion] Search pages"
        assert "inputSchema" in result
        # backend and original_name not in MCP format
        assert "backend" not in result
        assert "original_name" not in result


class TestAggregationResult:
    """Test AggregationResult data class."""
    
    def test_total_tools(self):
        """Test total_tools property."""
        result = AggregationResult()
        assert result.total_tools == 0
        
        result.tools.append(MagicMock())
        result.tools.append(MagicMock())
        assert result.total_tools == 2
    
    def test_all_succeeded(self):
        """Test all_succeeded property."""
        result = AggregationResult()
        result.backends_succeeded = ["notion", "slack"]
        assert result.all_succeeded is True
        
        result.backends_failed = ["hubspot"]
        assert result.all_succeeded is False


class TestToolAggregator:
    """Test ToolAggregator class."""
    
    def test_aggregate_single_backend(self, aggregator):
        """Test aggregating from single backend."""
        result = aggregator.aggregate(["notion"])
        
        assert result.total_tools == 3
        assert "notion" in result.backends_succeeded
        assert len(result.backends_failed) == 0
        
        # Check namespacing
        tool_names = [t.name for t in result.tools]
        assert "notion.search_pages" in tool_names
        assert "notion.read_page" in tool_names
    
    def test_aggregate_multiple_backends(self, aggregator):
        """Test aggregating from multiple backends."""
        result = aggregator.aggregate(["notion", "slack"])
        
        assert result.total_tools == 6  # 3 + 3
        assert "notion" in result.backends_succeeded
        assert "slack" in result.backends_succeeded
        
        # Check both namespaces present
        tool_names = [t.name for t in result.tools]
        assert any(t.startswith("notion.") for t in tool_names)
        assert any(t.startswith("slack.") for t in tool_names)
    
    def test_aggregate_all(self, aggregator):
        """Test aggregate_all with registered backends."""
        result = aggregator.aggregate_all()
        
        assert result.total_tools == 6
        assert len(result.backends_succeeded) == 2
    
    def test_aggregate_with_filter(self, aggregator):
        """Test aggregation with custom filter."""
        # Only include search tools
        def search_only(tool: AggregatedTool) -> bool:
            return "search" in tool.name
        
        result = aggregator.aggregate(["notion", "slack"], filter_func=search_only)
        
        assert result.total_tools == 2
        assert "notion.search_pages" in [t.name for t in result.tools]
        assert "slack.search_messages" in [t.name for t in result.tools]
    
    def test_aggregate_with_permissions(self, aggregator):
        """Test aggregation filtered by permissions."""
        permissions = ["notion:pages:search", "slack:messages:search"]
        
        with patch("app.mcp.aggregator.PermissionMapper") as mock_mapper:
            mock_mapper.is_tool_permitted.side_effect = lambda tool, perms: (
                tool in ["notion.search_pages", "slack.search_messages"]
            )
            
            result = aggregator.aggregate_with_permissions(
                ["notion", "slack"],
                permissions
            )
        
        # Only permitted tools included
        tool_names = [t.name for t in result.tools]
        assert "notion.search_pages" in tool_names
        assert "slack.search_messages" in tool_names
    
    def test_aggregate_failed_backend(self, aggregator, mock_tool_cache):
        """Test graceful handling of failed backend."""
        mock_tool_cache.get_tools.side_effect = lambda b: None if b == "hubspot" else (
            [CachedTool(name="search_pages", description="Search", inputSchema={})] if b == "notion" else None
        )
        
        result = aggregator.aggregate(["notion", "hubspot"])
        
        assert "notion" in result.backends_succeeded
        assert "hubspot" in result.backends_failed
        assert result.total_tools == 1  # Only notion tools
    
    def test_namespacing_applied(self, aggregator):
        """Test namespace prefixing is applied."""
        result = aggregator.aggregate_for_backend("notion")
        
        for tool in result.tools:
            assert tool.name.startswith("notion.")
            assert tool.backend == "notion"
            assert not tool.original_name.startswith("notion.")
    
    def test_description_enhancement(self, aggregator):
        """Test description is enhanced with backend prefix."""
        result = aggregator.aggregate_for_backend("notion")
        
        for tool in result.tools:
            assert tool.description.startswith("[Notion]")


class TestHelperMethods:
    """Test helper methods."""
    
    def test_get_backend_for_tool(self, aggregator):
        """Test extracting backend from namespaced tool."""
        assert aggregator.get_backend_for_tool("notion.search_pages") == "notion"
        assert aggregator.get_backend_for_tool("slack.send_message") == "slack"
        assert aggregator.get_backend_for_tool("invalid") is None
    
    def test_get_original_name(self, aggregator):
        """Test extracting original name from namespaced tool."""
        assert aggregator.get_original_name("notion.search_pages") == "search_pages"
        assert aggregator.get_original_name("slack.send_message") == "send_message"
        assert aggregator.get_original_name("invalid") is None
    
    def test_find_tool(self, aggregator):
        """Test finding specific tool by name."""
        tool = aggregator.find_tool("notion.search_pages")
        
        assert tool is not None
        assert tool.name == "notion.search_pages"
        assert tool.backend == "notion"
        assert tool.original_name == "search_pages"
    
    def test_find_tool_not_found(self, aggregator):
        """Test finding non-existent tool."""
        assert aggregator.find_tool("notion.nonexistent") is None
        assert aggregator.find_tool("unknown.tool") is None


class TestBackendRegistration:
    """Test backend registration."""
    
    def test_register_backend(self, mock_tool_cache):
        """Test registering new backend."""
        aggregator = ToolAggregator(mock_tool_cache)
        assert len(aggregator.get_registered_backends()) == 0
        
        aggregator.register_backend("notion")
        assert "notion" in aggregator.get_registered_backends()
    
    def test_unregister_backend(self, aggregator):
        """Test unregistering backend."""
        assert aggregator.unregister_backend("notion") is True
        assert "notion" not in aggregator.get_registered_backends()
        
        # Already removed
        assert aggregator.unregister_backend("notion") is False


class TestGlobalInstance:
    """Test global instance management."""
    
    def test_configure_and_get(self, mock_tool_cache):
        """Test configuring and getting global instance."""
        configure_tool_aggregator(mock_tool_cache, ["notion"])
        
        agg = get_tool_aggregator()
        assert agg is not None
        assert "notion" in agg.get_registered_backends()
```

---

## Post-Conditions

After completing this task:

- [ ] ToolAggregator is available for import from `app.mcp`
- [ ] Tools from multiple backends can be aggregated into unified view
- [ ] tools/list handler (B6) can use aggregator for tool collection
- [ ] D1 (backend connection manager) has component to aggregate from
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.8 Step 7: Agent Discovers Tools
- **Key Value Proposition**: Demo 1 (Unified Connection)
- **Related Components**: 
  - [WS-B5: Tool Schema Cache](./WS-B5-tool-schema-cache.md) - Provides cached tools
  - [WS-B6: tools/list Handler](./WS-B6-tools-list-handler.md) - Uses aggregator
  - [WS-B4: Namespace Prefixer](./WS-B4-namespace-prefixer.md) - Prefixing logic
- **Downstream Tasks**:
  - [WS-D1: Backend Connection Manager](./WS-D1-backend-connection-manager.md)

---

## Notes

- The aggregator is stateless - it doesn't store any session information
- Thread-safe by design (no mutable shared state except registered_backends)
- Failed backends are logged but don't stop aggregation of others
- MVP implementation uses in-memory registered_backends; production would use config
