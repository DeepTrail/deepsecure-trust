# Task: WS-B5 Implement Tool Schema Cache

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-B: Gateway MCP Core |
| **Dependencies** | B4 (Namespace prefixer) |
| **Blocked By** | None (B4 is complete ✅) |
| **Assigned** | - |
| **Created** | January 30, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 3 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo:** | Demo 1: Unified Connection, Demo 2: Filtered Visibility |
| **Validates User Journey Step** | Step 7: Agent Discovers Tools |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] B4 (Namespace prefixer) is complete
- [ ] `deeptrail-gateway/` service structure exists
- [ ] Namespace utilities can be imported from `deeptrail-gateway.gateway.mcp.namespace`

---

## Task Description

Implement a tool schema cache that stores the tools available from each backend MCP server. This cache reduces latency by avoiding repeated `tools/list` calls to backends and supports TTL-based refresh.

### Context

From the MVP design (Section 4.1):

```
| Tool Aggregator | ✅ Required | Combine tools from 2-3 backends |
| Bloom Filter Optimization | ⏳ Post-MVP | Linear search acceptable for <20 tools |
```

When an agent calls `tools/list`:
1. Gateway checks cache for each backend's tools
2. If cache miss or expired, fetches from backend
3. Namespaces tools (via B4)
4. Filters by permissions
5. Returns aggregated list

### Technical Notes

- **TTL-based expiration**: Tools don't change often; cache for 5-15 minutes
- **Per-backend caching**: Each backend has its own cache entry
- **Schema storage**: Store full tool schema (name, description, inputSchema)
- **Thread-safe**: Multiple requests may access cache concurrently
- **Lazy refresh**: Refresh on next request after expiry, not proactively

---

## Acceptance Criteria

### Protocol
- [ ] Caches MCP tool schemas as returned by backends
- [ ] Supports standard MCP tool format (name, description, inputSchema)

### Security
- [ ] Cache is shared across agents (tools are backend-level, not user-level)
- [ ] No credential data in cache

### Integration
- [ ] ToolCache can be imported from `deeptrail-gateway.gateway.mcp`
- [ ] Works with namespace prefixer (B4) for namespacing cached tools
- [ ] Used by tools/list handler (B6) and tool aggregator (B8)

### Functional
- [ ] `get_tools(backend_id)` → List[Tool] (from cache or fetch)
- [ ] `set_tools(backend_id, tools)` → stores with TTL
- [ ] `invalidate(backend_id)` → removes cache entry
- [ ] `invalidate_all()` → clears entire cache
- [ ] `is_cached(backend_id)` → bool
- [ ] `get_cache_stats()` → hits, misses, entries count
- [ ] Configurable TTL (default 5 minutes)
- [ ] Thread-safe access

### General
- [ ] Unit tests for cache operations
- [ ] Tests for TTL expiration
- [ ] Tests for concurrent access
- [ ] No new linting errors introduced

---

## Files to Create

| File | Purpose |
|------|---------|
| `deeptrail-gateway/gateway/mcp/tool_cache.py` | Tool schema cache with TTL |
| `deeptrail-gateway/tests/gateway/mcp/test_tool_cache.py` | Unit tests |

---

## Files to Modify

| File | Changes |
|------|---------|
| `deeptrail-gateway/gateway/mcp/__init__.py` | Export ToolCache |

---

## Implementation Hints

```python
# deeptrail-gateway/gateway/mcp/tool_cache.py

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Callable
from threading import RLock
import logging

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """MCP Tool schema."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Tool":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            input_schema=data.get("inputSchema", {})
        )


@dataclass
class CacheEntry:
    """Cache entry with TTL."""
    tools: List[Tool]
    cached_at: datetime
    expires_at: datetime
    
    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    entries: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class ToolCache:
    """
    Cache for backend MCP tool schemas.
    
    Reduces latency by caching tools/list responses from backends
    with configurable TTL-based expiration.
    """
    
    DEFAULT_TTL_SECONDS = 300  # 5 minutes
    
    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        fetcher: Optional[Callable[[str], List[Tool]]] = None
    ):
        """
        Initialize tool cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries
            fetcher: Optional function to fetch tools from backend
                     Signature: (backend_id: str) -> List[Tool]
        """
        self._ttl = timedelta(seconds=ttl_seconds)
        self._fetcher = fetcher
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = RLock()
        self._stats = CacheStats()
    
    def get_tools(
        self,
        backend_id: str,
        fetcher: Optional[Callable[[], List[Tool]]] = None
    ) -> List[Tool]:
        """
        Get tools for a backend, fetching if not cached or expired.
        
        Args:
            backend_id: Backend identifier (e.g., "notion")
            fetcher: Optional fetcher function for this specific call
        
        Returns:
            List of tools for the backend
        """
        with self._lock:
            entry = self._cache.get(backend_id)
            
            if entry and not entry.is_expired:
                self._stats.hits += 1
                logger.debug(f"Cache hit for backend: {backend_id}")
                return entry.tools
            
            self._stats.misses += 1
            logger.debug(f"Cache miss for backend: {backend_id}")
            
            # Try to fetch
            fetch_fn = fetcher or (lambda: self._fetcher(backend_id) if self._fetcher else [])
            try:
                tools = fetch_fn()
                self.set_tools(backend_id, tools)
                return tools
            except Exception as e:
                logger.error(f"Failed to fetch tools for {backend_id}: {e}")
                # Return stale data if available
                if entry:
                    logger.warning(f"Returning stale cache for {backend_id}")
                    return entry.tools
                return []
    
    def set_tools(self, backend_id: str, tools: List[Tool]) -> None:
        """
        Store tools in cache.
        
        Args:
            backend_id: Backend identifier
            tools: List of tools to cache
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            self._cache[backend_id] = CacheEntry(
                tools=tools,
                cached_at=now,
                expires_at=now + self._ttl
            )
            self._stats.entries = len(self._cache)
            logger.debug(f"Cached {len(tools)} tools for {backend_id}")
    
    def invalidate(self, backend_id: str) -> bool:
        """
        Remove backend from cache.
        
        Returns:
            True if entry existed and was removed
        """
        with self._lock:
            if backend_id in self._cache:
                del self._cache[backend_id]
                self._stats.entries = len(self._cache)
                logger.debug(f"Invalidated cache for {backend_id}")
                return True
            return False
    
    def invalidate_all(self) -> int:
        """
        Clear entire cache.
        
        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats.entries = 0
            logger.debug(f"Invalidated entire cache ({count} entries)")
            return count
    
    def is_cached(self, backend_id: str) -> bool:
        """Check if backend has valid (non-expired) cache entry."""
        with self._lock:
            entry = self._cache.get(backend_id)
            return entry is not None and not entry.is_expired
    
    def get_cache_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                entries=len(self._cache)
            )
    
    def get_all_cached_backends(self) -> List[str]:
        """Get list of all cached backend IDs."""
        with self._lock:
            return list(self._cache.keys())
    
    def get_ttl_remaining(self, backend_id: str) -> Optional[float]:
        """
        Get seconds until cache entry expires.
        
        Returns:
            Seconds remaining, or None if not cached
        """
        with self._lock:
            entry = self._cache.get(backend_id)
            if not entry:
                return None
            remaining = (entry.expires_at - datetime.now(timezone.utc)).total_seconds()
            return max(0, remaining)


# Convenience function for creating a shared cache instance
_global_cache: Optional[ToolCache] = None

def get_tool_cache() -> ToolCache:
    """Get or create global tool cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = ToolCache()
    return _global_cache
```

---

## Post-Conditions

After completing this task:

- [ ] All acceptance criteria met
- [ ] Tests pass locally: `pytest deeptrail-gateway/tests/gateway/mcp/test_tool_cache.py`
- [ ] Linting passes: `ruff check deeptrail-gateway/gateway/mcp/`
- [ ] Type checking passes: `mypy deeptrail-gateway/gateway/mcp/`
- [ ] Task B6 (tools/list handler) can use cache
- [ ] Task B8 (tool aggregator) can use cache

---

## References

- Design Doc Section 4.1: Component Implementation Status
- Design Doc Section 2.8: Step 7 - Agent Discovers Tools
- B4 Task: Namespace prefixer (tools are namespaced after retrieval)
- B6 Task: tools/list handler (consumes cached tools)

---

## Notes

- **Shared cache**: Cache is backend-level, not agent-level (all agents see same backend tools)
- **TTL tuning**: Start with 5 minutes; adjust based on how often backends change tools
- **Stale-while-revalidate**: Return stale data on fetch failure for resilience
- **Thread safety**: Use RLock for reentrant locking
- **Consider**: Adding refresh callback for proactive refresh before expiry

---

## Test Cases to Cover

```python
# test_tool_cache.py

import time
from unittest.mock import MagicMock

def test_cache_stores_and_retrieves_tools():
    cache = ToolCache(ttl_seconds=60)
    tools = [Tool("search", "Search", {})]
    
    cache.set_tools("notion", tools)
    retrieved = cache.get_tools("notion")
    
    assert len(retrieved) == 1
    assert retrieved[0].name == "search"

def test_cache_hit_increments_stats():
    cache = ToolCache()
    cache.set_tools("notion", [Tool("t1", "d1", {})])
    
    cache.get_tools("notion")
    cache.get_tools("notion")
    
    stats = cache.get_cache_stats()
    assert stats.hits == 2
    assert stats.misses == 0

def test_cache_miss_calls_fetcher():
    fetcher = MagicMock(return_value=[Tool("fetched", "Fetched tool", {})])
    cache = ToolCache(fetcher=fetcher)
    
    tools = cache.get_tools("notion")
    
    fetcher.assert_called_once_with("notion")
    assert tools[0].name == "fetched"

def test_cache_expires_after_ttl():
    cache = ToolCache(ttl_seconds=1)  # 1 second TTL
    cache.set_tools("notion", [Tool("t1", "", {})])
    
    assert cache.is_cached("notion") is True
    time.sleep(1.1)
    assert cache.is_cached("notion") is False

def test_invalidate_removes_entry():
    cache = ToolCache()
    cache.set_tools("notion", [])
    
    assert cache.is_cached("notion") is True
    cache.invalidate("notion")
    assert cache.is_cached("notion") is False

def test_invalidate_all_clears_cache():
    cache = ToolCache()
    cache.set_tools("notion", [])
    cache.set_tools("slack", [])
    
    count = cache.invalidate_all()
    
    assert count == 2
    assert cache.get_cache_stats().entries == 0

def test_stale_data_returned_on_fetch_failure():
    fetcher = MagicMock(side_effect=Exception("Network error"))
    cache = ToolCache(ttl_seconds=0, fetcher=fetcher)  # Immediate expiry
    
    # Pre-populate with stale data
    cache._cache["notion"] = CacheEntry(
        tools=[Tool("stale", "", {})],
        cached_at=datetime.now(timezone.utc) - timedelta(hours=1),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    
    tools = cache.get_tools("notion")
    
    assert len(tools) == 1
    assert tools[0].name == "stale"

def test_thread_safety():
    import threading
    
    cache = ToolCache()
    errors = []
    
    def writer():
        try:
            for i in range(100):
                cache.set_tools(f"backend-{i}", [Tool(f"t{i}", "", {})])
        except Exception as e:
            errors.append(e)
    
    def reader():
        try:
            for i in range(100):
                cache.get_tools(f"backend-{i % 50}")
        except Exception as e:
            errors.append(e)
    
    threads = [threading.Thread(target=writer) for _ in range(5)]
    threads += [threading.Thread(target=reader) for _ in range(5)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(errors) == 0
```

---

## Execution Log

### Progress Updates

| Date | Update |
|------|--------|
| - | Task created, ready to start |

### Blockers Encountered

| Date | Blocker | Resolution |
|------|---------|------------|
| - | - | - |
