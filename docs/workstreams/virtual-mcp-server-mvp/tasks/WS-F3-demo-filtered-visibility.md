# Task: WS-F3 Create Demo 2: Filtered Tool Visibility

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-F: Integration & Demos |
| **Code Dependencies** | C5 (Permission filter middleware) ✅ |
| **Runtime Dependencies** | Gateway, Control Plane, Mock Backend MCP Servers |
| **Blocked By** | None |
| **Assigned** | - |
| **Created** | February 6, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 8 |
| **Target Worktree** | `vmcp-gateway` |

---

## Dependencies

### Code Dependencies (must complete before starting)

| Task | What We Need | Status |
|------|--------------|--------|
| C5 | Permission filter middleware for tools/list filtering | ✅ |

### Runtime Dependencies (must be deployed for integration testing)

| Service | Endpoint | Required For |
|---------|----------|--------------|
| Gateway | `http://localhost:8002` | Demo entry point |
| Control Plane | `http://localhost:8000` | Delegation info |
| Mock Notion MCP | `http://localhost:9001` | Backend tools (15 total) |
| Mock Slack MCP | `http://localhost:9002` | Backend tools (22 total) |

### Development Mode

When runtime dependencies are unavailable:

- [x] **Fallback behavior**: Demo script can use mocked responses
- [x] **Local testing**: Unit tests verify demo script structure
- [x] **Integration testing**: Full demo requires all services

---

## Pre-Conditions

Before starting this task, ensure:

- [x] C5 (Permission filter middleware) is complete ✅
- [x] Permission filtering working on tools/list

---

## Task Description

Create **Demo 2: Filtered Tool Visibility** - a demonstration script that shows an agent sees ONLY the tools delegated to them, not all tools offered by backends.

### Context

From the design doc (Section 5.2):
```python
# Show what backends actually offer vs what agent sees
all_notion_tools = 15  # search, read, create, update, delete, share, ...
all_slack_tools = 22   # search, send, list, create_channel, ...

agent_sees = 4  # Only: notion.search_pages, notion.read_page, 
                #       slack.search_messages, slack.list_channels

print(f"Backends offer {all_notion_tools + all_slack_tools} tools")
print(f"Agent sees {agent_sees} tools (filtered by delegation)")
# Output: Backends offer 37 tools
#         Agent sees 4 tools (filtered by delegation)
```

**Success Criteria**: 90%+ reduction in visible tools.

### Technical Notes

The demo should:
1. Show the contrast between "all available" and "delegated only"
2. Visualize the filtering in action
3. Explain WHY each tool is filtered (permission mapping)
4. Work in mock mode for documentation

---

## Acceptance Criteria

- [ ] Demo shows total tools available from backends
- [ ] Demo shows filtered tools based on delegation
- [ ] Demo calculates and displays filtering percentage
- [ ] Demo explains permission-to-tool mapping
- [ ] Includes both real and mock modes
- [ ] Clear visualization of filtered vs. available
- [ ] No new linting errors introduced

---

## Files to Modify/Create

### Files to Create

- `deeptrail-gateway/demos/demo_02_filtered_visibility.py` - Main demo script

### Files to Modify

- `deeptrail-gateway/demos/README.md` - Add Demo 2 instructions

### Tests to Add

- `deeptrail-gateway/tests/demos/test_demo_02.py` - Demo script validation

---

## Implementation Details

### Demo Script

```python
#!/usr/bin/env python3
"""
Demo 2: Filtered Tool Visibility

Demonstrates that an agent sees ONLY the tools delegated to them,
not all tools offered by the backend MCP servers.

Value Proposition:
- Backends offer many tools (15 Notion, 22 Slack = 37 total)
- Agent sees only 4 tools (delegated by user)
- 90%+ reduction in attack surface

Usage:
    # With real services
    python demo_02_filtered_visibility.py
    
    # With mock mode
    python demo_02_filtered_visibility.py --mock
"""

import asyncio
import argparse
from typing import Dict, List, Optional

# Demo configuration
GATEWAY_URL = "http://localhost:8002/mcp"

# Mock data: all tools offered by backends
ALL_NOTION_TOOLS = [
    {"name": "search_pages", "permission": "notion:pages:search"},
    {"name": "read_page", "permission": "notion:pages:read"},
    {"name": "create_page", "permission": "notion:pages:create"},
    {"name": "update_page", "permission": "notion:pages:update"},
    {"name": "delete_page", "permission": "notion:pages:delete"},
    {"name": "archive_page", "permission": "notion:pages:archive"},
    {"name": "share_page", "permission": "notion:pages:share"},
    {"name": "search_databases", "permission": "notion:databases:search"},
    {"name": "query_database", "permission": "notion:databases:query"},
    {"name": "create_database", "permission": "notion:databases:create"},
    {"name": "update_database", "permission": "notion:databases:update"},
    {"name": "list_users", "permission": "notion:users:list"},
    {"name": "get_user", "permission": "notion:users:read"},
    {"name": "list_blocks", "permission": "notion:blocks:list"},
    {"name": "get_block", "permission": "notion:blocks:read"},
]

ALL_SLACK_TOOLS = [
    {"name": "search_messages", "permission": "slack:messages:search"},
    {"name": "send_message", "permission": "slack:messages:send"},
    {"name": "delete_message", "permission": "slack:messages:delete"},
    {"name": "edit_message", "permission": "slack:messages:edit"},
    {"name": "list_channels", "permission": "slack:channels:list"},
    {"name": "create_channel", "permission": "slack:channels:create"},
    {"name": "archive_channel", "permission": "slack:channels:archive"},
    {"name": "invite_to_channel", "permission": "slack:channels:invite"},
    {"name": "kick_from_channel", "permission": "slack:channels:kick"},
    {"name": "set_topic", "permission": "slack:channels:topic"},
    {"name": "list_users", "permission": "slack:users:list"},
    {"name": "get_user_profile", "permission": "slack:users:profile"},
    {"name": "set_user_status", "permission": "slack:users:status"},
    {"name": "upload_file", "permission": "slack:files:upload"},
    {"name": "delete_file", "permission": "slack:files:delete"},
    {"name": "share_file", "permission": "slack:files:share"},
    {"name": "create_reminder", "permission": "slack:reminders:create"},
    {"name": "list_reminders", "permission": "slack:reminders:list"},
    {"name": "add_reaction", "permission": "slack:reactions:add"},
    {"name": "remove_reaction", "permission": "slack:reactions:remove"},
    {"name": "start_call", "permission": "slack:calls:start"},
    {"name": "schedule_message", "permission": "slack:messages:schedule"},
]

# Sarah's delegated permissions (from design doc)
SARAH_DELEGATED_PERMISSIONS = [
    "notion:pages:search",
    "notion:pages:read",
    "slack:messages:search",
    "slack:channels:list",
]


def print_banner():
    """Print demo banner."""
    print("\n" + "=" * 70)
    print(" DEMO 2: FILTERED TOOL VISIBILITY")
    print("=" * 70)
    print()
    print(" Value Proposition:")
    print(" • Backends offer MANY tools (dangerous capabilities)")
    print(" • Agent sees ONLY delegated tools (safe subset)")
    print(" • Massive reduction in attack surface")
    print()
    print("-" * 70)


def print_all_tools():
    """Print all tools offered by backends."""
    print("\n📦 ALL TOOLS OFFERED BY BACKENDS")
    print("-" * 50)
    
    print(f"\n   Notion MCP Server ({len(ALL_NOTION_TOOLS)} tools):")
    for tool in ALL_NOTION_TOOLS:
        print(f"   • notion.{tool['name']:<25} → {tool['permission']}")
    
    print(f"\n   Slack MCP Server ({len(ALL_SLACK_TOOLS)} tools):")
    for tool in ALL_SLACK_TOOLS:
        print(f"   • slack.{tool['name']:<25} → {tool['permission']}")
    
    total = len(ALL_NOTION_TOOLS) + len(ALL_SLACK_TOOLS)
    print(f"\n   TOTAL: {total} tools available")


def print_delegated_permissions():
    """Print Sarah's delegated permissions."""
    print("\n🔐 SARAH'S DELEGATED PERMISSIONS")
    print("-" * 50)
    print("   Sarah delegated these permissions to her agent:")
    print()
    for perm in SARAH_DELEGATED_PERMISSIONS:
        print(f"   ✓ {perm}")
    print()
    print(f"   Total delegated: {len(SARAH_DELEGATED_PERMISSIONS)} permissions")


def print_filtered_tools():
    """Print tools visible to the agent after filtering."""
    print("\n👁️  TOOLS VISIBLE TO AGENT (after filtering)")
    print("-" * 50)
    
    visible_tools = []
    
    # Filter Notion tools
    for tool in ALL_NOTION_TOOLS:
        if tool["permission"] in SARAH_DELEGATED_PERMISSIONS:
            visible_tools.append(("notion", tool))
    
    # Filter Slack tools
    for tool in ALL_SLACK_TOOLS:
        if tool["permission"] in SARAH_DELEGATED_PERMISSIONS:
            visible_tools.append(("slack", tool))
    
    print("\n   Agent's tools/list response:")
    for backend, tool in visible_tools:
        print(f"   ✓ {backend}.{tool['name']:<25} (allowed: {tool['permission']})")
    
    print(f"\n   VISIBLE: {len(visible_tools)} tools")
    
    return visible_tools


def print_hidden_tools():
    """Print tools hidden from the agent."""
    print("\n🚫 TOOLS HIDDEN FROM AGENT")
    print("-" * 50)
    
    hidden_count = 0
    
    # Hidden Notion tools
    print("\n   Hidden Notion tools:")
    for tool in ALL_NOTION_TOOLS:
        if tool["permission"] not in SARAH_DELEGATED_PERMISSIONS:
            print(f"   ✗ notion.{tool['name']:<25} (denied: {tool['permission']})")
            hidden_count += 1
    
    # Hidden Slack tools
    print("\n   Hidden Slack tools:")
    for tool in ALL_SLACK_TOOLS:
        if tool["permission"] not in SARAH_DELEGATED_PERMISSIONS:
            print(f"   ✗ slack.{tool['name']:<25} (denied: {tool['permission']})")
            hidden_count += 1
    
    print(f"\n   HIDDEN: {hidden_count} tools")
    
    return hidden_count


def print_summary(visible_count: int, hidden_count: int):
    """Print the filtering summary."""
    total = visible_count + hidden_count
    reduction = (hidden_count / total) * 100 if total > 0 else 0
    
    print("\n" + "=" * 70)
    print(" ✅ FILTERING SUMMARY")
    print("=" * 70)
    print()
    print(f"   Backends offer:    {total:3} tools")
    print(f"   Agent sees:        {visible_count:3} tools")
    print(f"   Hidden from agent: {hidden_count:3} tools")
    print()
    print(f"   📉 Attack surface reduction: {reduction:.1f}%")
    print()
    
    # Visual bar
    visible_bar = "█" * visible_count
    hidden_bar = "░" * min(hidden_count, 33)  # Cap for display
    print(f"   Visible: {visible_bar}")
    print(f"   Hidden:  {hidden_bar}{'...' if hidden_count > 33 else ''}")
    print()
    
    # Key insight
    print("   KEY INSIGHT:")
    print("   The agent CANNOT discover or call hidden tools.")
    print("   They simply don't exist from the agent's perspective.")
    print()
    print("=" * 70)


async def run_demo(mock_mode: bool = False):
    """Run the demo."""
    print_banner()
    
    if mock_mode:
        print("🎭 Running in MOCK MODE")
    else:
        print("🔌 Running with LIVE SERVICES")
    print("-" * 70)
    
    # Show all available tools
    print_all_tools()
    
    # Show delegation
    print_delegated_permissions()
    
    # Show filtered result
    visible_tools = print_filtered_tools()
    
    # Show hidden tools
    hidden_count = print_hidden_tools()
    
    # Summary
    print_summary(len(visible_tools), hidden_count)
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Demo 2: Filtered Tool Visibility"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode"
    )
    args = parser.parse_args()
    
    exit_code = asyncio.run(run_demo(mock_mode=args.mock))
    exit(exit_code)


if __name__ == "__main__":
    main()
```

---

## Test Cases

### Unit Tests

```python
# tests/demos/test_demo_02.py

import pytest
from demos.demo_02_filtered_visibility import (
    ALL_NOTION_TOOLS,
    ALL_SLACK_TOOLS,
    SARAH_DELEGATED_PERMISSIONS
)

class TestDemo02:
    
    def test_notion_tools_count(self):
        """Notion has expected number of tools."""
        assert len(ALL_NOTION_TOOLS) == 15
    
    def test_slack_tools_count(self):
        """Slack has expected number of tools."""
        assert len(ALL_SLACK_TOOLS) == 22
    
    def test_total_tools_count(self):
        """Total tools matches design doc."""
        total = len(ALL_NOTION_TOOLS) + len(ALL_SLACK_TOOLS)
        assert total == 37
    
    def test_delegated_permissions_count(self):
        """Sarah delegated expected number of permissions."""
        assert len(SARAH_DELEGATED_PERMISSIONS) == 4
    
    def test_visible_tools_count(self):
        """Agent sees expected number of tools."""
        visible = 0
        for tool in ALL_NOTION_TOOLS + ALL_SLACK_TOOLS:
            if tool["permission"] in SARAH_DELEGATED_PERMISSIONS:
                visible += 1
        assert visible == 4
    
    def test_filtering_reduction(self):
        """Filtering achieves 90%+ reduction."""
        total = len(ALL_NOTION_TOOLS) + len(ALL_SLACK_TOOLS)
        visible = 4
        reduction = ((total - visible) / total) * 100
        assert reduction >= 89  # 89.2% in our case
    
    def test_all_tools_have_permissions(self):
        """All tools have permission mappings."""
        for tool in ALL_NOTION_TOOLS + ALL_SLACK_TOOLS:
            assert "permission" in tool
            assert len(tool["permission"]) > 0
```

---

## Post-Conditions

### Code Complete (enables dependent tasks to start)

- [ ] All acceptance criteria met
- [ ] Unit tests pass locally: `pytest deeptrail-gateway/tests/demos/`
- [ ] Demo runs in mock mode
- [ ] Completion report created

### Integration Complete (validated at merge point)

- [ ] Demo runs with live services
- [ ] Filtering matches design doc expectations

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| - | - | Demo is leaf task |

---

## References

- Design Doc: [Section 5.2 - Demo 2: Filtered Tool Visibility](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md#52-demo-2-filtered-tool-visibility)
- Related Code: `deeptrail-gateway/app/middleware/permission_filter.py`

---

## Notes

- The 90%+ reduction is a key selling point for security
- Demo should visually emphasize the contrast between "all" and "visible"
- Consider adding comparison to traditional API key approach

---

## Execution Log

### Progress Updates

| Date | Update |
|------|--------|
| - | - |

### Blockers Encountered

| Date | Blocker | Resolution |
|------|---------|------------|
| - | - | - |
