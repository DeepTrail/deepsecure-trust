# Task: WS-D1 Implement Backend Connection Manager

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-D: Backend Connectors |
| **Dependencies** | B8 (Tool Aggregator) |
| **Blocked By** | None (B8 ticket created) |
| **Assigned** | - |
| **Created** | February 4, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 4 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 1: Unified Connection, Demo 3: Delegation Execution |
| **Validates User Journey Step** | Step 6: Agent Connects, Step 8: Tool Execution |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] B8 (Tool Aggregator) ticket created
- [x] B3 (MCP Session tracking) is complete
- [x] B5 (Tool schema cache) is complete
- [ ] `deeptrail-gateway/app/mcp/` structure exists
- [ ] MCPSessionManager can be imported from `app.mcp.session_manager`
- [ ] ToolCache can be imported from `app.mcp.tool_cache`

---

## Task Description

Implement the BackendConnectionManager that manages connections to backend MCP servers (Notion, Slack, HubSpot, etc.). This component pools connections, performs health checks, and provides the interface for executing MCP requests against backends.

### Context

From the MVP design (Section 2.9 - Step 8: Agent Executes Task):

```
Gateway Processing for tools/call:

1. PARSE namespace: "notion.search_pages" → server: "notion", tool: "search_pages"

2. VALIDATE permission (handled by C5, C6)

3. GET CREDENTIALS for Notion (handled by C7)

4. FORWARD to backend Notion MCP Server:
   POST https://mcp.notion.com/tools/call
   Authorization: Bearer {sarah's-notion-oauth-token}
   {
     "method": "tools/call",
     "params": {
       "name": "search_pages",   // Stripped namespace
       "arguments": {"query": "competitor analysis", "limit": 5}
     }
   }

5. RECEIVE response from backend and return to agent
```

The connection manager is responsible for Step 4: maintaining connections to backends and forwarding requests.

### Responsibilities

1. **Backend Registration**: Register available backend MCP servers with their endpoints
2. **Connection Pooling**: Reuse connections to backends for efficiency
3. **Health Checks**: Monitor backend availability and mark unhealthy backends
4. **Request Forwarding**: Send MCP requests to the appropriate backend
5. **Error Handling**: Handle connection failures, timeouts, retries
6. **Lazy Initialization**: Connect to backends on first request

### Technical Notes

- Use `httpx.AsyncClient` for HTTP connections (async-friendly)
- Connection pool size configurable per backend
- Health check interval configurable (default: 30 seconds)
- Timeout configurable per backend (default: 30 seconds)
- Exponential backoff for retries on transient failures
- Thread-safe operations for concurrent access

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/backends/__init__.py` | **CREATE** | Package init |
| `deeptrail-gateway/app/backends/connection_manager.py` | **CREATE** | BackendConnectionManager |
| `deeptrail-gateway/tests/backends/__init__.py` | **CREATE** | Test package init |
| `deeptrail-gateway/tests/backends/test_connection_manager.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. Data Classes and Enums (`app/backends/connection_manager.py`)

```python
"""
Backend Connection Manager

Manages connections to backend MCP servers. Provides connection pooling,
health checks, and request forwarding for the Virtual MCP Server gateway.

Architecture:
- Gateway maintains pool of connections to each backend
- Connections are reused across agent sessions
- Health checks run periodically in background
- Unhealthy backends are marked and excluded from routing

Usage:
    from app.backends.connection_manager import BackendConnectionManager
    
    manager = BackendConnectionManager()
    
    # Register backends
    manager.register_backend(BackendConfig(
        backend_id="notion",
        base_url="https://api.notion.com/mcp",
        health_endpoint="/health",
    ))
    
    # Send request
    response = await manager.send_request(
        backend_id="notion",
        method="tools/call",
        params={"name": "search_pages", "arguments": {...}},
        auth_header="Bearer token123"
    )
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class BackendStatus(Enum):
    """
    Backend connection status.
    
    Lifecycle: UNKNOWN → HEALTHY or UNHEALTHY
    """
    UNKNOWN = "unknown"       # Not yet checked
    HEALTHY = "healthy"       # Passing health checks
    UNHEALTHY = "unhealthy"   # Failing health checks
    DISABLED = "disabled"     # Manually disabled


class RequestMethod(str, Enum):
    """MCP request methods."""
    INITIALIZE = "initialize"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"


# =============================================================================
# Configuration Data Classes
# =============================================================================


@dataclass
class BackendConfig:
    """
    Configuration for a backend MCP server.
    
    Attributes:
        backend_id: Unique identifier (e.g., "notion", "slack")
        base_url: Base URL for MCP requests
        health_endpoint: Path for health check (None to disable)
        timeout_seconds: Request timeout
        max_connections: Maximum pool connections
        retry_attempts: Number of retries on failure
        retry_delay_seconds: Base delay between retries (exponential backoff)
    """
    backend_id: str
    base_url: str
    health_endpoint: str | None = "/health"
    timeout_seconds: float = 30.0
    max_connections: int = 10
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.backend_id:
            raise ValueError("backend_id is required")
        if not self.base_url:
            raise ValueError("base_url is required")
        # Remove trailing slash from base_url
        self.base_url = self.base_url.rstrip("/")


@dataclass
class BackendState:
    """
    Runtime state for a backend connection.
    
    Attributes:
        config: Backend configuration
        status: Current health status
        client: HTTP client for this backend
        last_health_check: Timestamp of last health check
        last_error: Last error message (if unhealthy)
        consecutive_failures: Number of consecutive failed requests
    """
    config: BackendConfig
    status: BackendStatus = BackendStatus.UNKNOWN
    client: httpx.AsyncClient | None = None
    last_health_check: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    
    def mark_healthy(self) -> None:
        """Mark backend as healthy."""
        self.status = BackendStatus.HEALTHY
        self.last_health_check = datetime.now(timezone.utc)
        self.last_error = None
        self.consecutive_failures = 0
    
    def mark_unhealthy(self, error: str) -> None:
        """Mark backend as unhealthy with error."""
        self.status = BackendStatus.UNHEALTHY
        self.last_health_check = datetime.now(timezone.utc)
        self.last_error = error
        self.consecutive_failures += 1
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for logging/debugging."""
        return {
            "backend_id": self.config.backend_id,
            "base_url": self.config.base_url,
            "status": self.status.value,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
        }


@dataclass
class MCPRequest:
    """
    MCP JSON-RPC request to send to backend.
    
    Attributes:
        method: MCP method (e.g., "tools/call")
        params: Request parameters
        request_id: JSON-RPC request ID
    """
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    request_id: str | int = field(default_factory=lambda: 1)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-RPC 2.0 format."""
        return {
            "jsonrpc": "2.0",
            "method": self.method,
            "params": self.params,
            "id": self.request_id,
        }


@dataclass
class MCPResponse:
    """
    MCP JSON-RPC response from backend.
    
    Attributes:
        result: Successful result (if no error)
        error: Error object (if failed)
        request_id: JSON-RPC request ID
        raw: Raw response dict
    """
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    request_id: str | int | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_success(self) -> bool:
        """Check if response is successful."""
        return self.error is None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPResponse":
        """Parse from JSON-RPC response dict."""
        return cls(
            result=data.get("result"),
            error=data.get("error"),
            request_id=data.get("id"),
            raw=data,
        )
    
    @classmethod
    def from_error(cls, code: int, message: str, request_id: Any = None) -> "MCPResponse":
        """Create error response."""
        return cls(
            error={"code": code, "message": message},
            request_id=request_id,
        )


# =============================================================================
# Exceptions
# =============================================================================


class BackendError(Exception):
    """Base exception for backend errors."""
    pass


class BackendNotFoundError(BackendError):
    """Raised when backend is not registered."""
    pass


class BackendUnavailableError(BackendError):
    """Raised when backend is unhealthy or unreachable."""
    pass


class BackendTimeoutError(BackendError):
    """Raised when request times out."""
    pass


class BackendRequestError(BackendError):
    """Raised when request fails."""
    pass


# =============================================================================
# Connection Manager
# =============================================================================


class BackendConnectionManager:
    """
    Manages connections to backend MCP servers.
    
    Features:
    - Connection pooling per backend
    - Periodic health checks
    - Automatic retries with exponential backoff
    - Graceful handling of backend failures
    
    Thread Safety:
        This implementation uses asyncio locks for thread-safety.
        Safe for concurrent access from multiple async tasks.
    
    Usage:
        manager = BackendConnectionManager()
        
        # Register backends
        manager.register_backend(BackendConfig(
            backend_id="notion",
            base_url="https://api.notion.com/mcp"
        ))
        
        # Start health checks (optional)
        await manager.start_health_checks(interval_seconds=30)
        
        # Send request
        response = await manager.send_request(
            backend_id="notion",
            request=MCPRequest(method="tools/list"),
            auth_header="Bearer token123"
        )
        
        # Cleanup
        await manager.close_all()
    """
    
    # Default settings
    DEFAULT_HEALTH_CHECK_INTERVAL = 30.0  # seconds
    
    def __init__(self) -> None:
        """Initialize empty connection manager."""
        self._backends: dict[str, BackendState] = {}
        self._lock = asyncio.Lock()
        self._health_check_task: asyncio.Task | None = None
        self._shutdown = False
    
    # ─────────────────────────────────────────────────────────────────
    # Backend Registration
    # ─────────────────────────────────────────────────────────────────
    
    def register_backend(self, config: BackendConfig) -> None:
        """
        Register a backend MCP server.
        
        Args:
            config: Backend configuration
            
        Note:
            Does not create the HTTP client yet - that happens lazily
            on first request or health check.
        """
        if config.backend_id in self._backends:
            logger.warning(f"Backend {config.backend_id} already registered, replacing")
        
        self._backends[config.backend_id] = BackendState(config=config)
        logger.info(f"Registered backend: {config.backend_id} at {config.base_url}")
    
    def unregister_backend(self, backend_id: str) -> bool:
        """
        Unregister a backend and close its connections.
        
        Args:
            backend_id: Backend to unregister
            
        Returns:
            True if backend was registered and removed
        """
        if backend_id not in self._backends:
            return False
        
        state = self._backends.pop(backend_id)
        if state.client:
            # Schedule client close (don't await in sync method)
            asyncio.create_task(state.client.aclose())
        
        logger.info(f"Unregistered backend: {backend_id}")
        return True
    
    def get_backend_ids(self) -> list[str]:
        """Get list of registered backend IDs."""
        return list(self._backends.keys())
    
    def get_backend_status(self, backend_id: str) -> BackendStatus | None:
        """
        Get health status of a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            BackendStatus or None if not registered
        """
        state = self._backends.get(backend_id)
        return state.status if state else None
    
    def get_healthy_backends(self) -> list[str]:
        """Get list of healthy backend IDs."""
        return [
            bid for bid, state in self._backends.items()
            if state.status == BackendStatus.HEALTHY
        ]
    
    def get_all_backend_states(self) -> dict[str, dict[str, Any]]:
        """Get status info for all backends (for debugging/monitoring)."""
        return {
            bid: state.to_dict()
            for bid, state in self._backends.items()
        }
    
    # ─────────────────────────────────────────────────────────────────
    # Connection Management
    # ─────────────────────────────────────────────────────────────────
    
    async def _get_or_create_client(self, backend_id: str) -> httpx.AsyncClient:
        """
        Get or create HTTP client for backend (lazy initialization).
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Configured httpx.AsyncClient
            
        Raises:
            BackendNotFoundError: If backend not registered
        """
        async with self._lock:
            state = self._backends.get(backend_id)
            if not state:
                raise BackendNotFoundError(f"Backend '{backend_id}' not registered")
            
            if state.client is None:
                config = state.config
                state.client = httpx.AsyncClient(
                    base_url=config.base_url,
                    timeout=httpx.Timeout(config.timeout_seconds),
                    limits=httpx.Limits(max_connections=config.max_connections),
                )
                logger.debug(f"Created HTTP client for backend: {backend_id}")
            
            return state.client
    
    async def close_backend(self, backend_id: str) -> bool:
        """
        Close connections for a specific backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            True if backend existed and was closed
        """
        async with self._lock:
            state = self._backends.get(backend_id)
            if not state:
                return False
            
            if state.client:
                await state.client.aclose()
                state.client = None
                logger.debug(f"Closed HTTP client for backend: {backend_id}")
            
            return True
    
    async def close_all(self) -> None:
        """Close all backend connections and stop health checks."""
        self._shutdown = True
        
        # Stop health checks
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
        
        # Close all clients
        async with self._lock:
            for state in self._backends.values():
                if state.client:
                    await state.client.aclose()
                    state.client = None
        
        logger.info("Closed all backend connections")
    
    # ─────────────────────────────────────────────────────────────────
    # Health Checks
    # ─────────────────────────────────────────────────────────────────
    
    async def check_backend_health(self, backend_id: str) -> bool:
        """
        Check health of a specific backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            True if healthy, False otherwise
        """
        state = self._backends.get(backend_id)
        if not state:
            return False
        
        config = state.config
        
        # Skip if no health endpoint configured
        if not config.health_endpoint:
            state.mark_healthy()
            return True
        
        try:
            client = await self._get_or_create_client(backend_id)
            response = await client.get(config.health_endpoint)
            
            if response.status_code == 200:
                state.mark_healthy()
                logger.debug(f"Backend {backend_id} is healthy")
                return True
            else:
                state.mark_unhealthy(f"Health check returned {response.status_code}")
                logger.warning(f"Backend {backend_id} unhealthy: status {response.status_code}")
                return False
                
        except httpx.TimeoutException:
            state.mark_unhealthy("Health check timed out")
            logger.warning(f"Backend {backend_id} health check timed out")
            return False
            
        except Exception as e:
            state.mark_unhealthy(str(e))
            logger.warning(f"Backend {backend_id} health check failed: {e}")
            return False
    
    async def check_all_backends_health(self) -> dict[str, bool]:
        """
        Check health of all registered backends.
        
        Returns:
            Dict mapping backend_id to health status
        """
        results = {}
        for backend_id in self._backends:
            results[backend_id] = await self.check_backend_health(backend_id)
        return results
    
    async def start_health_checks(
        self,
        interval_seconds: float = DEFAULT_HEALTH_CHECK_INTERVAL
    ) -> None:
        """
        Start periodic health checks in background.
        
        Args:
            interval_seconds: Interval between health checks
        """
        if self._health_check_task:
            logger.warning("Health checks already running")
            return
        
        async def health_check_loop():
            while not self._shutdown:
                try:
                    await self.check_all_backends_health()
                    await asyncio.sleep(interval_seconds)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Health check error: {e}")
                    await asyncio.sleep(interval_seconds)
        
        self._health_check_task = asyncio.create_task(health_check_loop())
        logger.info(f"Started health checks with {interval_seconds}s interval")
    
    def stop_health_checks(self) -> None:
        """Stop periodic health checks."""
        if self._health_check_task:
            self._health_check_task.cancel()
            self._health_check_task = None
            logger.info("Stopped health checks")
    
    # ─────────────────────────────────────────────────────────────────
    # Request Handling
    # ─────────────────────────────────────────────────────────────────
    
    async def send_request(
        self,
        backend_id: str,
        request: MCPRequest,
        auth_header: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> MCPResponse:
        """
        Send MCP request to a backend.
        
        Args:
            backend_id: Target backend identifier
            request: MCP request to send
            auth_header: Authorization header value (e.g., "Bearer token")
            extra_headers: Additional headers to include
            
        Returns:
            MCPResponse from backend
            
        Raises:
            BackendNotFoundError: If backend not registered
            BackendUnavailableError: If backend is unhealthy
            BackendTimeoutError: If request times out
            BackendRequestError: If request fails
        """
        state = self._backends.get(backend_id)
        if not state:
            raise BackendNotFoundError(f"Backend '{backend_id}' not registered")
        
        # Check if backend is healthy (unless status is unknown)
        if state.status == BackendStatus.UNHEALTHY:
            raise BackendUnavailableError(
                f"Backend '{backend_id}' is unhealthy: {state.last_error}"
            )
        
        if state.status == BackendStatus.DISABLED:
            raise BackendUnavailableError(
                f"Backend '{backend_id}' is disabled"
            )
        
        config = state.config
        client = await self._get_or_create_client(backend_id)
        
        # Build headers
        headers = {"Content-Type": "application/json"}
        if auth_header:
            headers["Authorization"] = auth_header
        if extra_headers:
            headers.update(extra_headers)
        
        # Retry loop
        last_error: Exception | None = None
        for attempt in range(config.retry_attempts):
            try:
                response = await client.post(
                    "/",  # MCP endpoint is typically at root
                    json=request.to_dict(),
                    headers=headers,
                )
                
                # Parse response
                if response.status_code == 200:
                    data = response.json()
                    state.mark_healthy()  # Successful request = healthy
                    return MCPResponse.from_dict(data)
                else:
                    error_text = response.text[:200]  # Truncate for logging
                    logger.warning(
                        f"Backend {backend_id} returned {response.status_code}: {error_text}"
                    )
                    return MCPResponse.from_error(
                        code=-32000,
                        message=f"Backend returned {response.status_code}",
                        request_id=request.request_id,
                    )
                    
            except httpx.TimeoutException as e:
                last_error = BackendTimeoutError(f"Request to {backend_id} timed out")
                logger.warning(f"Timeout on attempt {attempt + 1} for {backend_id}")
                
            except httpx.RequestError as e:
                last_error = BackendRequestError(f"Request to {backend_id} failed: {e}")
                logger.warning(f"Request error on attempt {attempt + 1} for {backend_id}: {e}")
            
            # Exponential backoff before retry
            if attempt < config.retry_attempts - 1:
                delay = config.retry_delay_seconds * (2 ** attempt)
                await asyncio.sleep(delay)
        
        # All retries failed
        state.mark_unhealthy(str(last_error))
        raise last_error or BackendRequestError(f"Request to {backend_id} failed")
    
    async def send_tools_list(
        self,
        backend_id: str,
        auth_header: str | None = None,
    ) -> MCPResponse:
        """
        Send tools/list request to a backend.
        
        Convenience method for fetching available tools.
        
        Args:
            backend_id: Target backend
            auth_header: Authorization header
            
        Returns:
            MCPResponse containing tools list
        """
        return await self.send_request(
            backend_id=backend_id,
            request=MCPRequest(method=RequestMethod.TOOLS_LIST),
            auth_header=auth_header,
        )
    
    async def send_tools_call(
        self,
        backend_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        auth_header: str | None = None,
    ) -> MCPResponse:
        """
        Send tools/call request to a backend.
        
        Convenience method for executing a tool.
        
        Args:
            backend_id: Target backend
            tool_name: Tool name (without namespace prefix)
            arguments: Tool arguments
            auth_header: Authorization header
            
        Returns:
            MCPResponse containing tool result
        """
        return await self.send_request(
            backend_id=backend_id,
            request=MCPRequest(
                method=RequestMethod.TOOLS_CALL,
                params={"name": tool_name, "arguments": arguments},
            ),
            auth_header=auth_header,
        )
    
    async def send_initialize(
        self,
        backend_id: str,
        client_info: dict[str, Any] | None = None,
        auth_header: str | None = None,
    ) -> MCPResponse:
        """
        Send initialize request to a backend.
        
        Convenience method for MCP initialization handshake.
        
        Args:
            backend_id: Target backend
            client_info: Client information for handshake
            auth_header: Authorization header
            
        Returns:
            MCPResponse containing server info
        """
        params = {}
        if client_info:
            params["clientInfo"] = client_info
        
        return await self.send_request(
            backend_id=backend_id,
            request=MCPRequest(
                method=RequestMethod.INITIALIZE,
                params=params,
            ),
            auth_header=auth_header,
        )


# =============================================================================
# Factory Functions
# =============================================================================


def create_default_manager() -> BackendConnectionManager:
    """
    Create a connection manager with default MVP backends.
    
    For MVP, we configure mock/test backends. In production,
    these would be loaded from configuration or database.
    
    Returns:
        Configured BackendConnectionManager
    """
    manager = BackendConnectionManager()
    
    # MVP: Register placeholder backends
    # Production: Load from config/database
    default_backends = [
        BackendConfig(
            backend_id="notion",
            base_url="https://mcp.notion.so",
            health_endpoint="/health",
        ),
        BackendConfig(
            backend_id="slack",
            base_url="https://mcp.slack.com",
            health_endpoint="/health",
        ),
        BackendConfig(
            backend_id="hubspot",
            base_url="https://mcp.hubspot.com",
            health_endpoint="/health",
        ),
    ]
    
    for config in default_backends:
        manager.register_backend(config)
    
    return manager
```

### 2. Package Init (`app/backends/__init__.py`)

```python
"""
Backend Connectors Package

Provides connection management for backend MCP servers.

Main Components:
- BackendConnectionManager: Manages connections, pooling, health checks
- BackendConfig: Configuration for a backend server
- MCPRequest/MCPResponse: Request/response wrappers

Usage:
    from app.backends import (
        BackendConnectionManager,
        BackendConfig,
        MCPRequest,
        MCPResponse,
    )
"""

from .connection_manager import (
    # Enums
    BackendStatus,
    RequestMethod,
    # Data Classes
    BackendConfig,
    BackendState,
    MCPRequest,
    MCPResponse,
    # Exceptions
    BackendError,
    BackendNotFoundError,
    BackendUnavailableError,
    BackendTimeoutError,
    BackendRequestError,
    # Manager
    BackendConnectionManager,
    # Factory
    create_default_manager,
)

__all__ = [
    # Enums
    "BackendStatus",
    "RequestMethod",
    # Data Classes
    "BackendConfig",
    "BackendState",
    "MCPRequest",
    "MCPResponse",
    # Exceptions
    "BackendError",
    "BackendNotFoundError",
    "BackendUnavailableError",
    "BackendTimeoutError",
    "BackendRequestError",
    # Manager
    "BackendConnectionManager",
    # Factory
    "create_default_manager",
]
```

---

## Acceptance Criteria

### Backend Registration Criteria

- [ ] `register_backend()` accepts `BackendConfig` and stores backend
- [ ] `unregister_backend()` removes backend and closes connections
- [ ] `get_backend_ids()` returns list of registered backends
- [ ] `get_backend_status()` returns current health status
- [ ] Duplicate registrations log warning and replace

### Connection Pooling Criteria

- [ ] HTTP clients created lazily on first request
- [ ] Connections reused across requests
- [ ] Pool size configurable per backend
- [ ] `close_backend()` closes specific backend connections
- [ ] `close_all()` closes all connections and stops health checks

### Health Check Criteria

- [ ] `check_backend_health()` sends GET to health endpoint
- [ ] Healthy backends marked as `HEALTHY`
- [ ] Failed health checks mark backend as `UNHEALTHY`
- [ ] `start_health_checks()` runs periodic checks in background
- [ ] Health check interval configurable
- [ ] Backends without health endpoint always marked healthy

### Request Handling Criteria

- [ ] `send_request()` sends JSON-RPC 2.0 formatted request
- [ ] Authorization header included when provided
- [ ] Requests to unhealthy backends raise `BackendUnavailableError`
- [ ] Timeouts raise `BackendTimeoutError`
- [ ] Retries with exponential backoff on transient failures
- [ ] Successful requests update backend to healthy status

### Convenience Methods Criteria

- [ ] `send_tools_list()` sends `tools/list` request
- [ ] `send_tools_call()` sends `tools/call` with name and arguments
- [ ] `send_initialize()` sends `initialize` with client info

### Test Criteria

- [ ] Test backend registration and unregistration
- [ ] Test lazy connection creation
- [ ] Test health check success and failure
- [ ] Test request success with mocked httpx
- [ ] Test request timeout handling
- [ ] Test retry behavior
- [ ] Test concurrent access safety
- [ ] All tests pass with `pytest tests/backends/test_connection_manager.py`

---

## Test Cases

Create `deeptrail-gateway/tests/backends/__init__.py` (empty) and `test_connection_manager.py`:

```python
"""Tests for Backend Connection Manager."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.backends.connection_manager import (
    BackendConnectionManager,
    BackendConfig,
    BackendStatus,
    MCPRequest,
    MCPResponse,
    BackendNotFoundError,
    BackendUnavailableError,
    BackendTimeoutError,
)


@pytest.fixture
def manager():
    """Create a fresh connection manager."""
    return BackendConnectionManager()


@pytest.fixture
def notion_config():
    """Create Notion backend config."""
    return BackendConfig(
        backend_id="notion",
        base_url="https://mcp.notion.so",
        health_endpoint="/health",
        timeout_seconds=10.0,
    )


class TestBackendRegistration:
    """Tests for backend registration."""
    
    def test_register_backend(self, manager, notion_config):
        """Test registering a backend."""
        manager.register_backend(notion_config)
        
        assert "notion" in manager.get_backend_ids()
        assert manager.get_backend_status("notion") == BackendStatus.UNKNOWN
    
    def test_register_duplicate_backend(self, manager, notion_config):
        """Test registering same backend twice replaces it."""
        manager.register_backend(notion_config)
        
        new_config = BackendConfig(
            backend_id="notion",
            base_url="https://new-url.com",
        )
        manager.register_backend(new_config)
        
        assert len(manager.get_backend_ids()) == 1
    
    def test_unregister_backend(self, manager, notion_config):
        """Test unregistering a backend."""
        manager.register_backend(notion_config)
        
        result = manager.unregister_backend("notion")
        
        assert result is True
        assert "notion" not in manager.get_backend_ids()
    
    def test_unregister_nonexistent_backend(self, manager):
        """Test unregistering non-existent backend returns False."""
        result = manager.unregister_backend("nonexistent")
        assert result is False
    
    def test_get_healthy_backends(self, manager, notion_config):
        """Test getting healthy backends."""
        manager.register_backend(notion_config)
        manager._backends["notion"].mark_healthy()
        
        healthy = manager.get_healthy_backends()
        
        assert "notion" in healthy


class TestConnectionManagement:
    """Tests for connection lifecycle."""
    
    @pytest.mark.asyncio
    async def test_lazy_client_creation(self, manager, notion_config):
        """Test that HTTP client is created lazily."""
        manager.register_backend(notion_config)
        
        # Client should not exist yet
        assert manager._backends["notion"].client is None
        
        # Accessing client creates it
        with patch.object(httpx.AsyncClient, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"jsonrpc": "2.0", "result": {}, "id": 1}
            )
            
            # Force client creation by sending request
            await manager.send_request(
                "notion",
                MCPRequest(method="tools/list"),
            )
        
        # Now client should exist
        assert manager._backends["notion"].client is not None
    
    @pytest.mark.asyncio
    async def test_close_backend(self, manager, notion_config):
        """Test closing a specific backend."""
        manager.register_backend(notion_config)
        
        # Create client
        await manager._get_or_create_client("notion")
        assert manager._backends["notion"].client is not None
        
        # Close
        await manager.close_backend("notion")
        assert manager._backends["notion"].client is None
    
    @pytest.mark.asyncio
    async def test_close_all(self, manager, notion_config):
        """Test closing all backends."""
        manager.register_backend(notion_config)
        await manager._get_or_create_client("notion")
        
        await manager.close_all()
        
        assert manager._backends["notion"].client is None


class TestHealthChecks:
    """Tests for health check functionality."""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, manager, notion_config):
        """Test successful health check."""
        manager.register_backend(notion_config)
        
        with patch.object(httpx.AsyncClient, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            
            result = await manager.check_backend_health("notion")
        
        assert result is True
        assert manager.get_backend_status("notion") == BackendStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, manager, notion_config):
        """Test failed health check."""
        manager.register_backend(notion_config)
        
        with patch.object(httpx.AsyncClient, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(status_code=503)
            
            result = await manager.check_backend_health("notion")
        
        assert result is False
        assert manager.get_backend_status("notion") == BackendStatus.UNHEALTHY
    
    @pytest.mark.asyncio
    async def test_health_check_timeout(self, manager, notion_config):
        """Test health check timeout."""
        manager.register_backend(notion_config)
        
        with patch.object(httpx.AsyncClient, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Timeout")
            
            result = await manager.check_backend_health("notion")
        
        assert result is False
        assert manager.get_backend_status("notion") == BackendStatus.UNHEALTHY
    
    @pytest.mark.asyncio
    async def test_no_health_endpoint(self, manager):
        """Test backend without health endpoint is always healthy."""
        config = BackendConfig(
            backend_id="test",
            base_url="https://test.com",
            health_endpoint=None,  # No health endpoint
        )
        manager.register_backend(config)
        
        result = await manager.check_backend_health("test")
        
        assert result is True
        assert manager.get_backend_status("test") == BackendStatus.HEALTHY


class TestRequestHandling:
    """Tests for MCP request handling."""
    
    @pytest.mark.asyncio
    async def test_send_request_success(self, manager, notion_config):
        """Test successful request."""
        manager.register_backend(notion_config)
        
        with patch.object(httpx.AsyncClient, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {
                    "jsonrpc": "2.0",
                    "result": {"tools": []},
                    "id": 1
                }
            )
            
            response = await manager.send_request(
                "notion",
                MCPRequest(method="tools/list"),
                auth_header="Bearer token123"
            )
        
        assert response.is_success
        assert response.result == {"tools": []}
        
        # Verify auth header was included
        call_kwargs = mock_post.call_args.kwargs
        assert "Authorization" in call_kwargs["headers"]
        assert call_kwargs["headers"]["Authorization"] == "Bearer token123"
    
    @pytest.mark.asyncio
    async def test_send_request_to_unknown_backend(self, manager):
        """Test request to unregistered backend raises error."""
        with pytest.raises(BackendNotFoundError):
            await manager.send_request(
                "unknown",
                MCPRequest(method="tools/list")
            )
    
    @pytest.mark.asyncio
    async def test_send_request_to_unhealthy_backend(self, manager, notion_config):
        """Test request to unhealthy backend raises error."""
        manager.register_backend(notion_config)
        manager._backends["notion"].mark_unhealthy("Test failure")
        
        with pytest.raises(BackendUnavailableError):
            await manager.send_request(
                "notion",
                MCPRequest(method="tools/list")
            )
    
    @pytest.mark.asyncio
    async def test_send_request_timeout(self, manager, notion_config):
        """Test request timeout raises error after retries."""
        manager.register_backend(notion_config)
        manager._backends["notion"].config.retry_attempts = 2
        manager._backends["notion"].config.retry_delay_seconds = 0.01
        
        with patch.object(httpx.AsyncClient, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Timeout")
            
            with pytest.raises(BackendTimeoutError):
                await manager.send_request(
                    "notion",
                    MCPRequest(method="tools/list")
                )
        
        # Verify retries happened
        assert mock_post.call_count == 2


class TestConvenienceMethods:
    """Tests for convenience request methods."""
    
    @pytest.mark.asyncio
    async def test_send_tools_list(self, manager, notion_config):
        """Test tools/list convenience method."""
        manager.register_backend(notion_config)
        
        with patch.object(BackendConnectionManager, 'send_request', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = MCPResponse(result={"tools": []})
            
            await manager.send_tools_list("notion", auth_header="Bearer token")
        
        call_args = mock_send.call_args
        assert call_args.kwargs["request"].method == "tools/list"
    
    @pytest.mark.asyncio
    async def test_send_tools_call(self, manager, notion_config):
        """Test tools/call convenience method."""
        manager.register_backend(notion_config)
        
        with patch.object(BackendConnectionManager, 'send_request', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = MCPResponse(result={"content": []})
            
            await manager.send_tools_call(
                "notion",
                tool_name="search_pages",
                arguments={"query": "test"},
                auth_header="Bearer token"
            )
        
        call_args = mock_send.call_args
        assert call_args.kwargs["request"].method == "tools/call"
        assert call_args.kwargs["request"].params["name"] == "search_pages"


class TestMCPRequest:
    """Tests for MCPRequest data class."""
    
    def test_to_dict_format(self):
        """Test JSON-RPC 2.0 format."""
        request = MCPRequest(
            method="tools/call",
            params={"name": "search", "arguments": {}},
            request_id=42
        )
        
        result = request.to_dict()
        
        assert result["jsonrpc"] == "2.0"
        assert result["method"] == "tools/call"
        assert result["params"] == {"name": "search", "arguments": {}}
        assert result["id"] == 42


class TestMCPResponse:
    """Tests for MCPResponse data class."""
    
    def test_from_dict_success(self):
        """Test parsing successful response."""
        data = {
            "jsonrpc": "2.0",
            "result": {"tools": []},
            "id": 1
        }
        
        response = MCPResponse.from_dict(data)
        
        assert response.is_success
        assert response.result == {"tools": []}
        assert response.error is None
    
    def test_from_dict_error(self):
        """Test parsing error response."""
        data = {
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid request"},
            "id": 1
        }
        
        response = MCPResponse.from_dict(data)
        
        assert not response.is_success
        assert response.error["code"] == -32600
    
    def test_from_error_factory(self):
        """Test creating error response."""
        response = MCPResponse.from_error(-32000, "Backend error", request_id=5)
        
        assert not response.is_success
        assert response.error["code"] == -32000
        assert response.error["message"] == "Backend error"
        assert response.request_id == 5
```

---

## Post-Conditions

After completing this task:

- [ ] BackendConnectionManager can register and manage backends
- [ ] Connection pooling works for efficient resource usage
- [ ] Health checks monitor backend availability
- [ ] MCP requests can be forwarded to backends
- [ ] D2 (Base MCP Client) can use connection manager
- [ ] B7 (tools/call handler) can route calls to backends
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.9 Step 8: Agent Executes Task
- **Related Components**: 
  - [WS-B3: MCP Session Manager](./WS-B3-mcp-session-tracking.md) - Session tracking
  - [WS-B8: Tool Aggregator](./WS-B8-tool-aggregator.md) - Tool discovery
- **Downstream Tasks**:
  - [WS-D2: Base MCP Client](./WS-D2-base-mcp-client.md) - Uses connection manager
  - [WS-D3-D5: Backend Clients](./WS-D3-notion-client.md) - Specific backend implementations
  - [WS-D6: Backend Router](./WS-D6-backend-router.md) - Routes by namespace

---

## Notes

- Uses `httpx.AsyncClient` for async HTTP requests (FastAPI-friendly)
- Connection pooling reduces overhead for repeated backend calls
- Health checks run in background task, won't block request handling
- Exponential backoff prevents thundering herd on transient failures
- MVP uses placeholder backend URLs; production would configure real endpoints
- Thread-safe using asyncio locks for concurrent access
- For production, consider adding:
  - Circuit breaker pattern
  - Metrics/tracing integration
  - Connection warming on startup
  - Backend configuration from database/config service
