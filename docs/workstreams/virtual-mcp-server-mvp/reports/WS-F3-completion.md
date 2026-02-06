# WS-F3 Completion Report: Create Demo 2: Filtered Visibility

## Task Summary

| Field | Value |
|-------|-------|
| **Task ID** | WS-F3 |
| **Task Name** | Create Demo 2: Filtered Tool Visibility |
| **Status** | ✅ Completed |
| **Completed** | February 6, 2026 |
| **Workstream** | WS-F: Integration & Demos |
| **Batch** | 8 |

---

## Deliverables

### Files Created

| File | Description |
|------|-------------|
| `deeptrail-gateway/demos/demo_02_filtered_visibility.py` | Main demo script (340 lines) |
| `deeptrail-gateway/tests/demos/test_demo_02.py` | Demo unit tests (32 tests) |

### Files Modified

| File | Changes |
|------|---------|
| `deeptrail-gateway/demos/README.md` | Added Demo 2 documentation |

---

## Implementation Details

### Key Components

#### Tool Dataclass

```python
@dataclass
class Tool:
    """Represents a tool with its permission mapping."""
    name: str
    permission: str
    description: str
```

#### Tool Catalogs

- **ALL_NOTION_TOOLS**: 15 tools representing Notion MCP server
- **ALL_SLACK_TOOLS**: 22 tools representing Slack MCP server
- **Total**: 37 tools across backends

#### Sarah's Delegation

```python
SARAH_DELEGATED_PERMISSIONS = [
    "notion:pages:search",
    "notion:pages:read",
    "slack:messages:search",
    "slack:channels:list",
]
```

Only 4 permissions delegated = 4 tools visible = 89.2% reduction.

### Filtering Logic

```python
def filter_tools(
    all_tools: list[tuple[str, Tool]],
    delegated_permissions: list[str],
) -> FilteringResult:
    """Filter tools based on delegated permissions."""
    # Simple permission check
    for backend, tool in all_tools:
        if tool.permission in delegated_permissions:
            visible.append((backend, tool))
        else:
            hidden.append((backend, tool))
```

### Demo Output Sections

1. **Banner**: Explains value proposition
2. **All Backend Tools**: Lists all 37 tools with permissions
3. **Delegated Permissions**: Shows Sarah's 4 delegated permissions
4. **Visible Tools**: Shows the 4 tools the agent can see
5. **Hidden Tools**: Shows the 33 tools hidden from agent
6. **Summary**: Attack surface reduction visualization

---

## Test Coverage

### Test Results

```
32 passed in 0.08s
```

### Test Categories

| Category | Tests | Coverage |
|----------|-------|----------|
| ToolDataClass | 1 | Dataclass creation |
| FilteringResult | 1 | Result dataclass |
| ToolCatalogs | 7 | Tool counts, permissions, format |
| DelegatedPermissions | 4 | Permission validation |
| FilteringLogic | 10 | Core filtering behavior |
| GetAllTools | 4 | Tool aggregation |
| RunDemo | 3 | Demo execution |
| ValueProposition | 3 | Security validation |

### Key Test Cases

1. **test_massive_attack_surface_reduction**: Verifies 89%+ reduction
2. **test_dangerous_tools_are_hidden**: Confirms delete/archive/kick are hidden
3. **test_only_read_operations_visible**: Validates only safe operations exposed

---

## Acceptance Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Demo shows total tools from backends | ✅ Met | Displays 37 tools |
| Demo shows filtered tools from delegation | ✅ Met | Displays 4 visible tools |
| Demo calculates filtering percentage | ✅ Met | Shows 89.2% reduction |
| Demo explains permission-to-tool mapping | ✅ Met | Shows permission → tool |
| Includes real and mock modes | ✅ Met | `--mock` flag supported |
| Clear visualization | ✅ Met | Bar charts, icons |
| No new linting errors | ✅ Met | `ruff check` passes |

---

## Quality Checks

| Check | Status |
|-------|--------|
| Lint (ruff) | ✅ Pass |
| Unit Tests | ✅ 32 passed |
| Demo Mock Mode | ✅ Works |
| All Demo Tests | ✅ 51 passed (Demo 1 + Demo 2) |

---

## Security Value Demonstrated

### Attack Surface Reduction

| Metric | Value |
|--------|-------|
| Total backend tools | 37 |
| Visible to agent | 4 |
| Hidden from agent | 33 |
| **Reduction** | **89.2%** |

### Dangerous Operations Hidden

The following dangerous tools are hidden from the agent:

| Operation | Tool | Why Dangerous |
|-----------|------|---------------|
| Delete page | `notion.delete_page` | Data loss |
| Delete message | `slack.delete_message` | Data loss |
| Delete file | `slack.delete_file` | Data loss |
| Archive channel | `slack.archive_channel` | Disruption |
| Kick user | `slack.kick_from_channel` | Disruption |
| Create channel | `slack.create_channel` | Proliferation |

### Key Insight

The agent cannot even **discover** hidden tools. When it calls `tools/list`, only the 4 delegated tools appear. The other 33 tools simply don't exist from the agent's perspective.

---

## Demo Sample Output

```
======================================================================
  DEMO 2: FILTERED TOOL VISIBILITY
======================================================================

  Value Proposition:
  • Backends offer MANY tools (dangerous capabilities)
  • Agent sees ONLY delegated tools (safe subset)
  • Massive reduction in attack surface

----------------------------------------------------------------------

📦 ALL TOOLS OFFERED BY BACKENDS
--------------------------------------------------
   TOTAL: 37 tools available across all backends

👁️  TOOLS VISIBLE TO AGENT (after filtering)
--------------------------------------------------
   ✓ notion.search_pages     (allowed: notion:pages:search)
   ✓ notion.read_page        (allowed: notion:pages:read)
   ✓ slack.search_messages   (allowed: slack:messages:search)
   ✓ slack.list_channels     (allowed: slack:channels:list)

   VISIBLE: 4 tools

======================================================================
  ✅ FILTERING SUMMARY
======================================================================

   Backends offer:     37 tools
   Agent sees:          4 tools
   Hidden from agent:  33 tools

   📉 Attack surface reduction: 89.2%

   ┌─────────────────────────────────────────────────────────────┐
   │  KEY INSIGHT                                                │
   │  The agent CANNOT discover or call hidden tools.            │
   │  They simply don't exist from the agent's perspective.      │
   └─────────────────────────────────────────────────────────────┘

======================================================================
```

---

## Progress Update

| Metric | Before | After |
|--------|--------|-------|
| Batch 8 Progress | 60% (3/5) | 80% (4/5) |
| WS-F Progress | 25% (2/8) | 37.5% (3/8) |
| Overall Progress | 81.8% (36/44) | 84.1% (37/44) |

---

## Next Steps

The following tasks are ready:
- **F4**: Create Demo 3: Delegation Execution (last task in Batch 8)
- **E6**: Implement audit query API (from Batch 9)

---

## References

- Task Ticket: [WS-F3-demo-filtered-visibility.md](../tasks/WS-F3-demo-filtered-visibility.md)
- Design Doc: Section 5.2 - Demo 2: Filtered Tool Visibility
- Related: C5 (Permission filter middleware)
