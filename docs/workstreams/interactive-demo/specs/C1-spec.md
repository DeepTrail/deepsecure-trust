# Task Specification: C1 Create APIClient with Display Formatting

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** Interactive Demo Plan - API Visualization

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | C1 |
| **Task Name** | Create APIClient with display formatting |
| **Type** | Component (Async HTTP Client) |
| **Location** | `demos/interactive/api_client.py` |
| **Validates** | API Visualization feature, Steps 2-10 |

---

## Component Specification

### Module: `demos.interactive.api_client`

| Field | Value |
|-------|-------|
| **Module** | `demos.interactive.api_client` |
| **Type** | Async HTTP Client Class |
| **Purpose** | Make HTTP requests with rich terminal display for demo visualization |

### Interface Contract

```python
from typing import Any

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax


class APIClient:
    """HTTP client with rich display capabilities for interactive demo.
    
    Wraps httpx.AsyncClient to provide formatted request/response display
    in the terminal, making API interactions visible and educational.
    
    Features:
    - Formatted request display (method, URL, headers, body)
    - Formatted response display (status, headers, JSON body)
    - Optional field highlighting in responses
    - Configurable display (can hide request/response)
    
    Attributes:
        control_plane_url: Base URL for control plane API
        gateway_url: Base URL for gateway API
        console: Rich Console for formatted output
    """
    
    def __init__(
        self,
        control_plane_url: str = "http://localhost:8000",
        gateway_url: str = "http://localhost:8002",
        console: Console | None = None,
    ) -> None:
        """Initialize the API client.
        
        Args:
            control_plane_url: Base URL for control plane (default: localhost:8000)
            gateway_url: Base URL for gateway (default: localhost:8002)
            console: Rich Console instance (creates new if None)
        """
        ...
    
    async def request(
        self,
        method: str,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        show_request: bool = True,
        show_response: bool = True,
    ) -> httpx.Response:
        """Make an HTTP request with optional display.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Full URL or path (if path, uses control_plane_url)
            json: Optional JSON body
            headers: Optional additional headers
            show_request: Whether to display the request (default: True)
            show_response: Whether to display the response (default: True)
            
        Returns:
            httpx.Response object
        """
        ...
    
    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        show_request: bool = True,
        show_response: bool = True,
    ) -> httpx.Response:
        """Convenience method for GET requests."""
        ...
    
    async def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        show_request: bool = True,
        show_response: bool = True,
    ) -> httpx.Response:
        """Convenience method for POST requests."""
        ...
    
    def show_request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Display a formatted HTTP request panel.
        
        Shows:
        - Method and URL in header
        - Headers (if provided)
        - JSON body (if provided, syntax-highlighted)
        
        Args:
            method: HTTP method
            url: Request URL
            body: Optional JSON body
            headers: Optional headers to display
        """
        ...
    
    def show_response(
        self,
        response: httpx.Response,
        highlight_fields: list[str] | None = None,
    ) -> None:
        """Display a formatted HTTP response panel.
        
        Shows:
        - Status code (color-coded: green=2xx, yellow=4xx, red=5xx)
        - Response time
        - JSON body (syntax-highlighted)
        - Optional field highlighting
        
        Args:
            response: httpx Response object
            highlight_fields: List of JSON field names to highlight
        """
        ...
    
    def show_json(
        self,
        data: dict[str, Any],
        title: str | None = None,
    ) -> None:
        """Display a formatted JSON panel.
        
        Used for displaying arbitrary JSON data (not tied to request/response).
        
        Args:
            data: Dictionary to display as JSON
            title: Optional panel title
        """
        ...
    
    def show_info(
        self,
        message: str,
        title: str | None = None,
    ) -> None:
        """Display an informational message panel.
        
        Used for status updates, explanations, etc.
        
        Args:
            message: Message text
            title: Optional panel title
        """
        ...
    
    def show_error(
        self,
        message: str,
        title: str = "Error",
    ) -> None:
        """Display an error message panel.
        
        Args:
            message: Error message
            title: Panel title (default: "Error")
        """
        ...
    
    async def close(self) -> None:
        """Close the underlying HTTP client.
        
        Should be called when done with the client.
        """
        ...
    
    async def __aenter__(self) -> "APIClient":
        """Async context manager entry."""
        ...
    
    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit - closes client."""
        ...
```

---

## Display Format Examples

### Request Panel

```
╭─────────────────────── POST /api/v1/auth/token ───────────────────────╮
│ Headers:                                                               │
│   Authorization: Bearer eyJ...                                         │
│   Content-Type: application/json                                       │
│                                                                        │
│ Body:                                                                  │
│ {                                                                      │
│   "email": "sarah@acme.com",                                          │
│   "password": "********"                                               │
│ }                                                                      │
╰────────────────────────────────────────────────────────────────────────╯
```

### Response Panel (Success)

```
╭───────────────────── 200 OK (45ms) ──────────────────────╮
│ {                                                         │
│   "access_token": "eyJ...",  ← highlighted                │
│   "token_type": "bearer",                                 │
│   "expires_in": 3600                                      │
│ }                                                         │
╰───────────────────────────────────────────────────────────╯
```

### Response Panel (Error)

```
╭───────────────────── 403 Forbidden (12ms) ─────────────────────╮
│ {                                                               │
│   "detail": "Permission denied: calendar:write not delegated", │
│   "code": "PERMISSION_DENIED"                                  │
│ }                                                               │
╰─────────────────────────────────────────────────────────────────╯
```

---

## Public Interface

| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `__init__` | `control_plane_url`, `gateway_url`, `console` | `None` | Initialize client |
| `request` | `method`, `url`, `json`, `headers`, `show_*` | `httpx.Response` | Make request with display |
| `get` | `url`, `headers`, `show_*` | `httpx.Response` | GET request |
| `post` | `url`, `json`, `headers`, `show_*` | `httpx.Response` | POST request |
| `show_request` | `method`, `url`, `body`, `headers` | `None` | Display request panel |
| `show_response` | `response`, `highlight_fields` | `None` | Display response panel |
| `show_json` | `data`, `title` | `None` | Display JSON panel |
| `show_info` | `message`, `title` | `None` | Display info panel |
| `show_error` | `message`, `title` | `None` | Display error panel |
| `close` | - | `None` | Close HTTP client |
| `__aenter__` | - | `APIClient` | Context manager entry |
| `__aexit__` | `*args` | `None` | Context manager exit |

---

## URL Resolution

The client resolves URLs as follows:

```python
def _resolve_url(self, url: str) -> str:
    """Resolve URL to full URL.
    
    - If URL starts with http:// or https://, use as-is
    - If URL contains "gateway" or "mcp", prepend gateway_url
    - Otherwise, prepend control_plane_url
    """
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if "gateway" in url or "mcp" in url:
        return f"{self.gateway_url}{url}"
    return f"{self.control_plane_url}{url}"
```

---

## Usage Example

```python
import asyncio
from demos.interactive.api_client import APIClient


async def demo():
    async with APIClient() as client:
        # Make a request with display
        response = await client.post(
            "/api/v1/auth/token",
            json={"email": "sarah@acme.com", "password": "secret"},
        )
        
        # Show the token (highlight specific field)
        token_data = response.json()
        client.show_json(
            {"access_token": token_data["access_token"][:20] + "..."},
            title="Extracted Token"
        )
        
        # Make request without display
        response = await client.get(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
            show_request=False,
        )
        
        # Display info message
        client.show_info("Agent authentication complete!", title="Status")


asyncio.run(demo())
```

---

## Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| `httpx` | External | Async HTTP client |
| `rich` | External | Terminal formatting (Console, Panel, Syntax) |
| `typing` | Standard Library | Type hints |

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Implementation | `demos/interactive/api_client.py` |
| Unit tests | `tests/demos/test_api_client.py` (optional) |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `APIClient` class has all specified methods
- [ ] Constructor accepts `control_plane_url`, `gateway_url`, `console`
- [ ] `request` method makes HTTP calls and displays correctly
- [ ] `get` and `post` convenience methods work
- [ ] `show_request` displays formatted request panel
- [ ] `show_response` displays formatted response with status coloring
- [ ] `show_json`, `show_info`, `show_error` display correct panel types
- [ ] URL resolution logic works for both control plane and gateway
- [ ] Async context manager (`async with`) works correctly
- [ ] Type hints present on all methods
- [ ] Docstrings present on class and all public methods

---

## References

- **Design Doc:** Interactive Demo Plan
- **Related Specs:** None (standalone utility)
- **Reference Implementation:** `demos/demo_sarah_journey_e2e.py` (simpler HTTP calls)
- **Upstream Dependencies:** None
- **Downstream Dependents:** A3, D1, E1
