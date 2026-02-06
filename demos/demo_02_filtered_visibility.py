#!/usr/bin/env python3
"""
Demo 2: Filtered Tool Visibility

Demonstrates that an agent sees ONLY the tools delegated to them,
not all tools offered by the backend MCP servers.

Value Proposition:
- Backends offer many tools (15 Notion, 22 Slack = 37 total)
- Agent sees only 4 tools (delegated by user)
- 90%+ reduction in attack surface
- Agent cannot even discover hidden tools

This demo shows the security value of permission-based filtering.
The agent's view is strictly limited to what was explicitly delegated.

Usage:
    # With real services
    python demo_02_filtered_visibility.py
    
    # With mock mode (no services required)
    python demo_02_filtered_visibility.py --mock

Reference:
    Design Doc Section 5.2 - Demo 2: Filtered Tool Visibility
"""

import argparse
import asyncio
from dataclasses import dataclass


# =============================================================================
# Configuration
# =============================================================================


DEFAULT_GATEWAY_URL = "http://localhost:8002/mcp"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Tool:
    """Represents a tool with its permission mapping."""
    name: str
    permission: str
    description: str


@dataclass
class FilteringResult:
    """Result of the filtering demonstration."""
    total_tools: int
    visible_tools: int
    hidden_tools: int
    reduction_percentage: float
    visible_tool_list: list[tuple[str, Tool]]
    hidden_tool_list: list[tuple[str, Tool]]


# =============================================================================
# Mock Backend Tool Catalogs
# =============================================================================


# All tools offered by Notion MCP Server (15 tools)
ALL_NOTION_TOOLS: list[Tool] = [
    Tool("search_pages", "notion:pages:search", "Search pages in workspace"),
    Tool("read_page", "notion:pages:read", "Read page content"),
    Tool("create_page", "notion:pages:create", "Create new page"),
    Tool("update_page", "notion:pages:update", "Update existing page"),
    Tool("delete_page", "notion:pages:delete", "Delete page permanently"),
    Tool("archive_page", "notion:pages:archive", "Archive page"),
    Tool("share_page", "notion:pages:share", "Share page with users"),
    Tool("search_databases", "notion:databases:search", "Search databases"),
    Tool("query_database", "notion:databases:query", "Query database entries"),
    Tool("create_database", "notion:databases:create", "Create new database"),
    Tool("update_database", "notion:databases:update", "Update database schema"),
    Tool("list_users", "notion:users:list", "List workspace users"),
    Tool("get_user", "notion:users:read", "Get user details"),
    Tool("list_blocks", "notion:blocks:list", "List page blocks"),
    Tool("get_block", "notion:blocks:read", "Get block content"),
]

# All tools offered by Slack MCP Server (22 tools)
ALL_SLACK_TOOLS: list[Tool] = [
    Tool("search_messages", "slack:messages:search", "Search messages"),
    Tool("send_message", "slack:messages:send", "Send message to channel"),
    Tool("delete_message", "slack:messages:delete", "Delete a message"),
    Tool("edit_message", "slack:messages:edit", "Edit a message"),
    Tool("list_channels", "slack:channels:list", "List accessible channels"),
    Tool("create_channel", "slack:channels:create", "Create new channel"),
    Tool("archive_channel", "slack:channels:archive", "Archive channel"),
    Tool("invite_to_channel", "slack:channels:invite", "Invite user to channel"),
    Tool("kick_from_channel", "slack:channels:kick", "Remove user from channel"),
    Tool("set_topic", "slack:channels:topic", "Set channel topic"),
    Tool("list_users", "slack:users:list", "List workspace users"),
    Tool("get_user_profile", "slack:users:profile", "Get user profile"),
    Tool("set_user_status", "slack:users:status", "Set user status"),
    Tool("upload_file", "slack:files:upload", "Upload file"),
    Tool("delete_file", "slack:files:delete", "Delete file"),
    Tool("share_file", "slack:files:share", "Share file in channel"),
    Tool("create_reminder", "slack:reminders:create", "Create reminder"),
    Tool("list_reminders", "slack:reminders:list", "List reminders"),
    Tool("add_reaction", "slack:reactions:add", "Add emoji reaction"),
    Tool("remove_reaction", "slack:reactions:remove", "Remove emoji reaction"),
    Tool("start_call", "slack:calls:start", "Start a call"),
    Tool("schedule_message", "slack:messages:schedule", "Schedule message"),
]


# =============================================================================
# Sarah's Delegation (from design doc)
# =============================================================================


# Sarah delegated only these 4 permissions to her agent
SARAH_DELEGATED_PERMISSIONS: list[str] = [
    "notion:pages:search",
    "notion:pages:read",
    "slack:messages:search",
    "slack:channels:list",
]


# =============================================================================
# Filtering Logic
# =============================================================================


def filter_tools(
    all_tools: list[tuple[str, Tool]],
    delegated_permissions: list[str],
) -> FilteringResult:
    """
    Filter tools based on delegated permissions.
    
    This simulates what the gateway's permission filter does.
    
    Args:
        all_tools: List of (backend_name, Tool) tuples
        delegated_permissions: List of permission strings
        
    Returns:
        FilteringResult with visible/hidden breakdown
    """
    visible: list[tuple[str, Tool]] = []
    hidden: list[tuple[str, Tool]] = []
    
    for backend, tool in all_tools:
        if tool.permission in delegated_permissions:
            visible.append((backend, tool))
        else:
            hidden.append((backend, tool))
    
    total = len(all_tools)
    visible_count = len(visible)
    hidden_count = len(hidden)
    reduction = (hidden_count / total * 100) if total > 0 else 0.0
    
    return FilteringResult(
        total_tools=total,
        visible_tools=visible_count,
        hidden_tools=hidden_count,
        reduction_percentage=reduction,
        visible_tool_list=visible,
        hidden_tool_list=hidden,
    )


def get_all_tools() -> list[tuple[str, Tool]]:
    """Get all tools from all backends."""
    all_tools: list[tuple[str, Tool]] = []
    
    for tool in ALL_NOTION_TOOLS:
        all_tools.append(("notion", tool))
    
    for tool in ALL_SLACK_TOOLS:
        all_tools.append(("slack", tool))
    
    return all_tools


# =============================================================================
# Display Functions
# =============================================================================


def print_banner() -> None:
    """Print demo banner."""
    print()
    print("=" * 70)
    print("  DEMO 2: FILTERED TOOL VISIBILITY")
    print("=" * 70)
    print()
    print("  Value Proposition:")
    print("  • Backends offer MANY tools (dangerous capabilities)")
    print("  • Agent sees ONLY delegated tools (safe subset)")
    print("  • Massive reduction in attack surface")
    print()
    print("-" * 70)


def print_all_backend_tools() -> None:
    """Print all tools offered by backends."""
    print()
    print("📦 ALL TOOLS OFFERED BY BACKENDS")
    print("-" * 50)
    
    print(f"\n   Notion MCP Server ({len(ALL_NOTION_TOOLS)} tools):")
    for tool in ALL_NOTION_TOOLS:
        print(f"   • notion.{tool.name:<25} → {tool.permission}")
    
    print(f"\n   Slack MCP Server ({len(ALL_SLACK_TOOLS)} tools):")
    for tool in ALL_SLACK_TOOLS:
        print(f"   • slack.{tool.name:<25} → {tool.permission}")
    
    total = len(ALL_NOTION_TOOLS) + len(ALL_SLACK_TOOLS)
    print()
    print(f"   TOTAL: {total} tools available across all backends")


def print_delegated_permissions() -> None:
    """Print Sarah's delegated permissions."""
    print()
    print("🔐 SARAH'S DELEGATED PERMISSIONS")
    print("-" * 50)
    print("   Sarah delegated these permissions to her agent:")
    print()
    for perm in SARAH_DELEGATED_PERMISSIONS:
        print(f"   ✓ {perm}")
    print()
    print(f"   Total delegated: {len(SARAH_DELEGATED_PERMISSIONS)} permissions")


def print_visible_tools(result: FilteringResult) -> None:
    """Print tools visible to the agent after filtering."""
    print()
    print("👁️  TOOLS VISIBLE TO AGENT (after filtering)")
    print("-" * 50)
    print()
    print("   Agent's tools/list response:")
    
    for backend, tool in result.visible_tool_list:
        print(f"   ✓ {backend}.{tool.name:<25} (allowed: {tool.permission})")
    
    print()
    print(f"   VISIBLE: {result.visible_tools} tools")


def print_hidden_tools(result: FilteringResult) -> None:
    """Print tools hidden from the agent."""
    print()
    print("🚫 TOOLS HIDDEN FROM AGENT")
    print("-" * 50)
    
    # Group by backend
    notion_hidden = [(b, t) for b, t in result.hidden_tool_list if b == "notion"]
    slack_hidden = [(b, t) for b, t in result.hidden_tool_list if b == "slack"]
    
    print(f"\n   Hidden Notion tools ({len(notion_hidden)}):")
    for backend, tool in notion_hidden:
        print(f"   ✗ {backend}.{tool.name:<25} (denied: {tool.permission})")
    
    print(f"\n   Hidden Slack tools ({len(slack_hidden)}):")
    for backend, tool in slack_hidden:
        print(f"   ✗ {backend}.{tool.name:<25} (denied: {tool.permission})")
    
    print()
    print(f"   HIDDEN: {result.hidden_tools} tools")


def print_summary(result: FilteringResult) -> None:
    """Print the filtering summary."""
    print()
    print("=" * 70)
    print("  ✅ FILTERING SUMMARY")
    print("=" * 70)
    print()
    print(f"   Backends offer:    {result.total_tools:3} tools")
    print(f"   Agent sees:        {result.visible_tools:3} tools")
    print(f"   Hidden from agent: {result.hidden_tools:3} tools")
    print()
    print(f"   📉 Attack surface reduction: {result.reduction_percentage:.1f}%")
    print()
    
    # Visual comparison bar
    visible_bar = "█" * result.visible_tools
    # Scale hidden bar to fit display (max 40 chars)
    hidden_scale = min(result.hidden_tools, 40)
    hidden_bar = "░" * hidden_scale
    overflow = "..." if result.hidden_tools > 40 else ""
    
    print(f"   Visible: {visible_bar} ({result.visible_tools})")
    print(f"   Hidden:  {hidden_bar}{overflow} ({result.hidden_tools})")
    print()
    
    # Key insight box
    print("   ┌─────────────────────────────────────────────────────────────┐")
    print("   │  KEY INSIGHT                                                │")
    print("   │                                                             │")
    print("   │  The agent CANNOT discover or call hidden tools.            │")
    print("   │  They simply don't exist from the agent's perspective.      │")
    print("   │                                                             │")
    print("   │  Even if the agent tries to call notion.delete_page,        │")
    print("   │  the gateway will reject it with 'tool not found'.          │")
    print("   └─────────────────────────────────────────────────────────────┘")
    print()
    print("=" * 70)
    print()


# =============================================================================
# Demo Result
# =============================================================================


@dataclass
class DemoResult:
    """Result of running the demo."""
    success: bool
    filtering_result: FilteringResult
    error: str | None = None


# =============================================================================
# Main Demo Function
# =============================================================================


async def run_demo(
    mock_mode: bool = False,
) -> DemoResult:
    """
    Run the filtered visibility demo.
    
    Args:
        mock_mode: If True, use mock data (always used currently)
        
    Returns:
        DemoResult with filtering statistics
    """
    print_banner()
    
    if mock_mode:
        print("🎭 Running in MOCK MODE (no services required)")
    else:
        print("🔌 Running with LIVE SERVICES (mock data for demo)")
    print("-" * 70)
    
    try:
        # Show all available tools from backends
        print_all_backend_tools()
        
        # Show what Sarah delegated
        print_delegated_permissions()
        
        # Perform filtering
        all_tools = get_all_tools()
        result = filter_tools(all_tools, SARAH_DELEGATED_PERMISSIONS)
        
        # Show filtered results
        print_visible_tools(result)
        print_hidden_tools(result)
        print_summary(result)
        
        return DemoResult(
            success=True,
            filtering_result=result,
        )
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ Error: {error_msg}")
        
        return DemoResult(
            success=False,
            filtering_result=FilteringResult(0, 0, 0, 0.0, [], []),
            error=error_msg,
        )


# =============================================================================
# CLI Entry Point
# =============================================================================


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Demo 2: Filtered Tool Visibility - "
                    "Agents see only delegated tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with mock data (always used for this demo)
    python demo_02_filtered_visibility.py --mock
    
    # Run demo
    python demo_02_filtered_visibility.py
        """,
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode (default behavior for this demo)",
    )
    args = parser.parse_args()
    
    result = asyncio.run(run_demo(mock_mode=args.mock))
    
    return 0 if result.success else 1


if __name__ == "__main__":
    exit(main())
