"""HTTP client with rich display capabilities for interactive demo.

This module provides an async HTTP client wrapper that displays formatted
requests and responses in the terminal using the rich library, making
API interactions visible and educational during the interactive demo.
"""

import json
import re
from typing import Any

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


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
        self.control_plane_url = control_plane_url.rstrip("/")
        self.gateway_url = gateway_url.rstrip("/")
        self.console = console or Console()
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

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

    def _mask_sensitive_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        """Mask sensitive fields in data for display.

        Args:
            data: Dictionary to mask

        Returns:
            Dictionary with sensitive fields masked
        """
        if not isinstance(data, dict):
            return data

        masked = {}
        sensitive_keys = {"password", "secret", "token", "api_key", "apikey"}

        for key, value in data.items():
            lower_key = key.lower()
            if any(s in lower_key for s in sensitive_keys):
                if isinstance(value, str) and len(value) > 0:
                    masked[key] = "********"
                else:
                    masked[key] = value
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive_fields(value)
            elif isinstance(value, list):
                masked[key] = [
                    self._mask_sensitive_fields(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked[key] = value

        return masked

    def _truncate_token(self, value: str, max_length: int = 40) -> str:
        """Truncate long tokens for readability."""
        if len(value) > max_length:
            return f"{value[:max_length]}..."
        return value

    def _format_headers(self, headers: dict[str, str] | None) -> str:
        """Format headers for display, truncating long values."""
        if not headers:
            return ""

        lines = []
        for key, value in headers.items():
            if key.lower() == "authorization":
                # Truncate auth tokens
                if value.startswith("Bearer "):
                    token = value[7:]
                    value = f"Bearer {self._truncate_token(token)}"
            lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    def _get_status_color(self, status_code: int) -> str:
        """Get color for status code."""
        if 200 <= status_code < 300:
            return "green"
        elif 400 <= status_code < 500:
            return "yellow"
        else:
            return "red"

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
        full_url = self._resolve_url(url)
        client = self._get_client()

        if show_request:
            self.show_request(method, full_url, body=json, headers=headers)

        response = await client.request(
            method=method,
            url=full_url,
            json=json,
            headers=headers,
        )

        if show_response:
            self.show_response(response)

        return response

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        show_request: bool = True,
        show_response: bool = True,
    ) -> httpx.Response:
        """Convenience method for GET requests."""
        return await self.request(
            "GET",
            url,
            headers=headers,
            show_request=show_request,
            show_response=show_response,
        )

    async def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        show_request: bool = True,
        show_response: bool = True,
    ) -> httpx.Response:
        """Convenience method for POST requests."""
        return await self.request(
            "POST",
            url,
            json=json,
            headers=headers,
            show_request=show_request,
            show_response=show_response,
        )

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
        content_parts = []

        if headers:
            formatted_headers = self._format_headers(headers)
            if formatted_headers:
                content_parts.append(f"[dim]Headers:[/dim]\n{formatted_headers}")

        if body:
            masked_body = self._mask_sensitive_fields(body)
            json_str = json.dumps(masked_body, indent=2)
            syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
            if content_parts:
                content_parts.append("")
            content_parts.append("[dim]Body:[/dim]")

        # Build panel content
        if content_parts and not body:
            panel_content = "\n".join(content_parts)
        elif content_parts and body:
            # Add syntax separately for body
            text_content = "\n".join(content_parts)
            self.console.print(
                Panel(
                    text_content,
                    title=f"[bold cyan]{method} {url}[/bold cyan]",
                    border_style="cyan",
                    padding=(0, 1),
                )
            )
            masked_body = self._mask_sensitive_fields(body)
            json_str = json.dumps(masked_body, indent=2)
            syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
            self.console.print(syntax)
            return
        else:
            panel_content = "[dim]No body[/dim]"

        if body and not headers:
            masked_body = self._mask_sensitive_fields(body)
            json_str = json.dumps(masked_body, indent=2)
            syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
            self.console.print(
                Panel(
                    syntax,
                    title=f"[bold cyan]{method} {url}[/bold cyan]",
                    border_style="cyan",
                    padding=(0, 1),
                )
            )
        else:
            self.console.print(
                Panel(
                    panel_content,
                    title=f"[bold cyan]{method} {url}[/bold cyan]",
                    border_style="cyan",
                    padding=(0, 1),
                )
            )

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
        status_code = response.status_code
        status_color = self._get_status_color(status_code)
        status_text = httpx.codes.get_reason_phrase(status_code)

        # Get response time in ms
        elapsed_ms = response.elapsed.total_seconds() * 1000

        # Build title with status and time
        title = f"[bold {status_color}]{status_code} {status_text}[/bold {status_color}] [dim]({elapsed_ms:.0f}ms)[/dim]"

        # Try to parse JSON body
        try:
            body = response.json()
            json_str = json.dumps(body, indent=2)

            # Highlight specific fields if requested
            if highlight_fields:
                for field in highlight_fields:
                    # Add arrow marker to highlighted fields
                    pattern = rf'"{re.escape(field)}": '
                    json_str = re.sub(pattern, f'"{field}": ', json_str)

            syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
            panel_content = syntax
        except (json.JSONDecodeError, ValueError):
            # Non-JSON response
            panel_content = response.text[:500] if response.text else "[dim]No body[/dim]"

        self.console.print(
            Panel(
                panel_content,
                title=title,
                border_style=status_color,
                padding=(0, 1),
            )
        )

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
        json_str = json.dumps(data, indent=2)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)

        panel_title = f"[bold blue]{title}[/bold blue]" if title else None

        self.console.print(
            Panel(
                syntax,
                title=panel_title,
                border_style="blue",
                padding=(0, 1),
            )
        )

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
        panel_title = f"[bold green]{title}[/bold green]" if title else None

        self.console.print(
            Panel(
                Text(message),
                title=panel_title,
                border_style="green",
                padding=(0, 1),
            )
        )

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
        self.console.print(
            Panel(
                Text(message, style="red"),
                title=f"[bold red]{title}[/bold red]",
                border_style="red",
                padding=(0, 1),
            )
        )

    async def close(self) -> None:
        """Close the underlying HTTP client.

        Should be called when done with the client.
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "APIClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit - closes client."""
        await self.close()
