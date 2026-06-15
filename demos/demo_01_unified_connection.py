#!/usr/bin/env python3
"""
Demo 1: Unified MCP Connection

Demonstrates that an agent connects to ONE gateway endpoint and 
sees tools from MULTIPLE backend MCP servers.

Value Proposition:
- Agent connects to single endpoint (gateway)
- Agent sees tools from Notion, Slack, Google Drive, etc.
- Agent code has NO awareness of backend URLs
- Simplified connection management for AI agents

This is the foundational demo showing why the Virtual MCP Server
pattern provides significant value for multi-service AI agents.

Usage:
    # With real services
    python demo_01_unified_connection.py
    
    # With mock mode (no services required)
    python demo_01_unified_connection.py --mock
    
    # With custom gateway URL
    python demo_01_unified_connection.py --gateway http://localhost:8002/mcp

Reference:
    Design Doc Section 5.1 - Demo 1: Unified MCP Connection
"""

import argparse
import asyncio
import time
from dataclasses import dataclass
from typing import Any


# =============================================================================
# Configuration
# =============================================================================


DEFAULT_GATEWAY_URL = "http://localhost:8002/mcp"
DEFAULT_CONTROL_PLANE_URL = "http://localhost:8000"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ConnectionTimings:
    """Timing measurements for the connection."""
    init_time_ms: float
    list_time_ms: float
    total_time_ms: float


@dataclass
class DemoResult:
    """Result of running the demo."""
    success: bool
    tools: list[dict[str, Any]]
    backends: set[str]
    timings: ConnectionTimings
    error: str | None = None


# =============================================================================
# MCP Demo Client
# =============================================================================


class MCPDemoClient:
    """
    Simplified MCP client for demos.
    
    This is a minimal client that demonstrates the unified connection
    pattern. It connects to a single gateway and discovers tools from
    multiple backends.
    """
    
    def __init__(
        self,
        gateway_url: str,
        session_token: str | None = None,
    ):
        self.gateway_url = gateway_url
        self.session_token = session_token
        self.tools: list[dict[str, Any]] = []
        self.backends: set[str] = set()
        self._request_id = 0
    
    def _next_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id
    
    async def connect(self) -> ConnectionTimings:
        """
        Connect to the gateway and fetch tools.
        
        Returns:
            ConnectionTimings with performance measurements
        """
        import httpx
        
        headers: dict[str, str] = {}
        if self.session_token:
            headers["Authorization"] = f"Bearer {self.session_token}"
        
        total_start = time.perf_counter()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Initialize MCP connection
            init_start = time.perf_counter()
            init_response = await client.post(
                self.gateway_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "demo-client",
                            "version": "0.1.0",
                        },
                    },
                    "id": self._next_id(),
                },
                headers=headers,
            )
            init_time = (time.perf_counter() - init_start) * 1000
            
            if init_response.status_code != 200:
                raise RuntimeError(
                    f"Initialize failed ({init_response.status_code}): "
                    f"{init_response.text}"
                )
            
            init_result = init_response.json()
            if "error" in init_result:
                raise RuntimeError(
                    f"Initialize error: {init_result['error'].get('message', 'Unknown')}"
                )
            
            # Step 2: List available tools
            list_start = time.perf_counter()
            list_response = await client.post(
                self.gateway_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "params": {},
                    "id": self._next_id(),
                },
                headers=headers,
            )
            list_time = (time.perf_counter() - list_start) * 1000
            
            if list_response.status_code != 200:
                raise RuntimeError(
                    f"tools/list failed ({list_response.status_code}): "
                    f"{list_response.text}"
                )
            
            list_result = list_response.json()
            if "error" in list_result:
                raise RuntimeError(
                    f"tools/list error: {list_result['error'].get('message', 'Unknown')}"
                )
            
            # Extract tools and backends
            self.tools = list_result.get("result", {}).get("tools", [])
            self._extract_backends()
            
            total_time = (time.perf_counter() - total_start) * 1000
            
            return ConnectionTimings(
                init_time_ms=init_time,
                list_time_ms=list_time,
                total_time_ms=total_time,
            )
    
    def _extract_backends(self) -> None:
        """Extract backend namespaces from tool names."""
        for tool in self.tools:
            name = tool.get("name", "")
            if "." in name:
                namespace = name.split(".")[0]
                self.backends.add(namespace)


# =============================================================================
# Mock MCP Demo Client
# =============================================================================


class MockMCPDemoClient:
    """
    Mock client for demo without services.
    
    Provides realistic mock data to demonstrate the demo output
    when running without live backend services.
    """
    
    # Mock tools representing what Sarah would see after delegation
    MOCK_TOOLS = [
        {
            "name": "notion.search_pages",
            "description": "[Notion] Search pages in your workspace",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "notion.read_page",
            "description": "[Notion] Read page content by ID",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID"},
                },
                "required": ["page_id"],
            },
        },
        {
            "name": "slack.search_messages",
            "description": "[Slack] Search messages in channels",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "channel": {"type": "string", "description": "Channel name"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "slack.list_channels",
            "description": "[Slack] List accessible channels",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "gmail.search_messages",
            "description": "[Gmail] Search messages by query",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "gmail.list_messages",
            "description": "[Gmail] List messages from inbox",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results"},
                },
            },
        },
    ]
    
    def __init__(
        self,
        gateway_url: str,
        session_token: str | None = None,
    ):
        self.gateway_url = gateway_url
        self.session_token = session_token
        self.tools: list[dict[str, Any]] = []
        self.backends: set[str] = set()
    
    async def connect(self) -> ConnectionTimings:
        """Simulate connection with realistic timings."""
        # Simulate network latency
        await asyncio.sleep(0.02)
        
        self.tools = self.MOCK_TOOLS.copy()
        self.backends = {"notion", "slack", "gmail"}
        
        # Return realistic mock timings
        return ConnectionTimings(
            init_time_ms=23.5,
            list_time_ms=45.2,
            total_time_ms=68.7,
        )


# =============================================================================
# Display Functions
# =============================================================================


def print_banner() -> None:
    """Print demo banner."""
    print()
    print("=" * 70)
    print("  DEMO 1: UNIFIED MCP CONNECTION")
    print("=" * 70)
    print()
    print("  Value Proposition:")
    print("  • Agent connects to ONE endpoint")
    print("  • Agent sees tools from MULTIPLE backends")
    print("  • Agent code has NO awareness of backend URLs")
    print()
    print("-" * 70)


def print_connection_info(
    gateway_url: str,
    timings: ConnectionTimings,
) -> None:
    """Print connection information."""
    print()
    print("📡 CONNECTION ESTABLISHED")
    print("-" * 40)
    print(f"   Gateway URL:    {gateway_url}")
    print(f"   Initialize:     {timings.init_time_ms:.1f}ms")
    print(f"   tools/list:     {timings.list_time_ms:.1f}ms")
    print(f"   Total time:     {timings.total_time_ms:.1f}ms")


def print_tools_summary(
    tools: list[dict[str, Any]],
    backends: set[str],
) -> None:
    """Print tools summary."""
    print()
    print("🔧 TOOLS DISCOVERED")
    print("-" * 40)
    print(f"   Total tools:      {len(tools)}")
    print(f"   Backend servers:  {len(backends)}")
    print(f"   Backends:         {', '.join(sorted(backends))}")
    
    print()
    print("   Tool list:")
    for tool in tools:
        name = tool.get("name", "unknown")
        desc = tool.get("description", "")
        # Truncate description if too long
        if len(desc) > 35:
            desc = desc[:32] + "..."
        print(f"   • {name:<30} {desc}")


def print_value_proposition(
    gateway_url: str,
    tools: list[dict[str, Any]],
    backends: set[str],
) -> None:
    """Print the key value proposition."""
    print()
    print("=" * 70)
    print("  ✅ KEY INSIGHT")
    print("=" * 70)
    print()
    print("   Connected to: 1 server (gateway)")
    print(f"   Can access:   {len(tools)} tools from {len(backends)} backends")
    print()
    print("   Agent code contains:")
    print(f"   ✓ Gateway URL:  {gateway_url}")
    
    # Show what's hidden
    for backend in sorted(backends):
        backend_display = backend.title()
        print(f"   ✗ {backend_display} URL:   (hidden from agent)")
    
    print()
    print("   The agent has NO awareness of individual backend URLs!")
    print()
    print("=" * 70)
    print()


def print_error(error: str) -> None:
    """Print error message."""
    print()
    print(f"❌ Error: {error}")
    print()
    print("   To run without services, use: --mock")
    print()


# =============================================================================
# Main Demo Function
# =============================================================================


async def run_demo(
    gateway_url: str,
    mock_mode: bool = False,
) -> DemoResult:
    """
    Run the unified connection demo.
    
    Args:
        gateway_url: URL of the gateway endpoint
        mock_mode: If True, use mock data instead of live services
        
    Returns:
        DemoResult with success status and data
    """
    print_banner()
    
    if mock_mode:
        print("🎭 Running in MOCK MODE (no services required)")
        print("-" * 70)
        client: MCPDemoClient | MockMCPDemoClient = MockMCPDemoClient(gateway_url)
    else:
        print("🔌 Connecting to live services...")
        print("-" * 70)
        client = MCPDemoClient(gateway_url)
    
    try:
        timings = await client.connect()
        
        print_connection_info(gateway_url, timings)
        print_tools_summary(client.tools, client.backends)
        print_value_proposition(gateway_url, client.tools, client.backends)
        
        return DemoResult(
            success=True,
            tools=client.tools,
            backends=client.backends,
            timings=timings,
        )
        
    except Exception as e:
        error_msg = str(e)
        print_error(error_msg)
        
        return DemoResult(
            success=False,
            tools=[],
            backends=set(),
            timings=ConnectionTimings(0, 0, 0),
            error=error_msg,
        )


# =============================================================================
# CLI Entry Point
# =============================================================================


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Demo 1: Unified MCP Connection - "
                    "One gateway, multiple backends",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with mock data (no services needed)
    python demo_01_unified_connection.py --mock
    
    # Run with live services
    python demo_01_unified_connection.py
    
    # Run with custom gateway URL
    python demo_01_unified_connection.py --gateway http://gateway.example.com/mcp
        """,
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode without live services",
    )
    parser.add_argument(
        "--gateway",
        default=DEFAULT_GATEWAY_URL,
        help=f"Gateway URL (default: {DEFAULT_GATEWAY_URL})",
    )
    args = parser.parse_args()
    
    result = asyncio.run(run_demo(
        gateway_url=args.gateway,
        mock_mode=args.mock,
    ))
    
    return 0 if result.success else 1


if __name__ == "__main__":
    exit(main())
