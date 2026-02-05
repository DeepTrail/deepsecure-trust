# Task: WS-B4 Implement Namespace Prefixer

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-B: Gateway MCP Core |
| **Dependencies** | B1 (MCP JSON-RPC 2.0 parser) |
| **Blocked By** | None (B1 is complete ✅) |
| **Assigned** | - |
| **Created** | January 30, 2026 |
| **Estimated Complexity** | `S` (< 2 hours) |
| **Batch** | 2 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 1: Unified Connection (tool discovery) |
| **Validates User Journey Step** | Step 7: Agent Discovers Tools (Filtered tools/list) |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] B1 (MCP JSON-RPC 2.0 parser) is complete
- [ ] `deeptrail-gateway/` service structure exists
- [ ] Tool schema structures are available from B1

---

## Task Description

Implement the namespace prefixer that transforms tool names from backend MCP servers into globally unique namespaced names. This prevents collisions when aggregating tools from multiple backends (e.g., both Notion and Slack might have a `search` tool).

### Context

From the MVP design (Section 2.8 - Step 7):

```
NAMESPACE PREFIX (avoid collisions):
  • search_pages     → notion.search_pages
  • read_page        → notion.read_page
  • search_messages  → slack.search_messages
  • list_channels    → slack.list_channels
```

The pattern is: `{backend_id}.{original_tool_name}`

This enables:
- **Collision avoidance**: Multiple backends can have same tool names
- **Clear attribution**: Agent knows which backend a tool comes from
- **Routing**: Gateway can parse namespace to route `tools/call` to correct backend

### Technical Notes

- Namespace format: `{backend_id}.{tool_name}` (e.g., `notion.search_pages`)
- Backend ID should be lowercase, alphanumeric with underscores
- Tool descriptions should be prefixed with `[Backend]` for clarity
- Must support both prefixing (on tools/list) and unprefixing (on tools/call)
- Consider edge cases: tool names with dots, empty backend IDs

---

## Acceptance Criteria

### Protocol
- [ ] N/A (utility module)

### Security
- [ ] No injection vulnerabilities in namespace parsing
- [ ] Validates backend_id format (no special characters that could cause issues)

### Integration
- [ ] Module can be imported from `deeptrail-gateway.gateway.mcp`
- [ ] Works with Tool schema structures from B1
- [ ] Follows utility patterns in the codebase

### Functional
- [ ] `prefix_tool_name(backend_id, tool_name)` returns `{backend}.{tool}`
- [ ] `unprefix_tool_name(namespaced_name)` returns `(backend_id, tool_name)`
- [ ] `prefix_tool(backend_id, tool)` returns tool with prefixed name and description
- [ ] `prefix_tools(backend_id, tools)` prefixes a list of tools
- [ ] Handles edge cases: dots in tool names, empty strings, special characters
- [ ] Description prefixing: adds `[Backend]` prefix (e.g., `[Notion] Search pages`)

### General
- [ ] Unit tests covering normal cases and edge cases
- [ ] No new linting errors introduced

---

## Files to Create

| File | Purpose |
|------|---------|
| `deeptrail-gateway/gateway/mcp/namespace.py` | Namespace prefixing utilities |
| `deeptrail-gateway/tests/gateway/mcp/test_namespace.py` | Unit tests |

---

## Files to Modify

| File | Changes |
|------|---------|
| `deeptrail-gateway/gateway/mcp/__init__.py` | Export namespace utilities |

---

## Implementation Hints

```python
# deeptrail-gateway/gateway/mcp/namespace.py

from typing import Tuple, List, Dict, Any, Optional
from dataclasses import dataclass
import re

# Namespace separator
NAMESPACE_SEPARATOR = "."

# Valid backend ID pattern (lowercase alphanumeric + underscore)
BACKEND_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class NamespaceError(Exception):
    """Error in namespace operations."""
    pass


def validate_backend_id(backend_id: str) -> None:
    """Validate backend ID format."""
    if not backend_id:
        raise NamespaceError("Backend ID cannot be empty")
    if not BACKEND_ID_PATTERN.match(backend_id):
        raise NamespaceError(
            f"Invalid backend ID '{backend_id}'. "
            "Must be lowercase alphanumeric starting with letter."
        )


def prefix_tool_name(backend_id: str, tool_name: str) -> str:
    """
    Add namespace prefix to a tool name.
    
    Args:
        backend_id: Backend identifier (e.g., "notion", "slack")
        tool_name: Original tool name (e.g., "search_pages")
    
    Returns:
        Namespaced tool name (e.g., "notion.search_pages")
    """
    validate_backend_id(backend_id)
    if not tool_name:
        raise NamespaceError("Tool name cannot be empty")
    return f"{backend_id}{NAMESPACE_SEPARATOR}{tool_name}"


def unprefix_tool_name(namespaced_name: str) -> Tuple[str, str]:
    """
    Remove namespace prefix from a tool name.
    
    Args:
        namespaced_name: Namespaced tool name (e.g., "notion.search_pages")
    
    Returns:
        Tuple of (backend_id, tool_name)
    
    Raises:
        NamespaceError: If name doesn't contain valid namespace
    """
    if NAMESPACE_SEPARATOR not in namespaced_name:
        raise NamespaceError(
            f"Invalid namespaced tool name '{namespaced_name}'. "
            f"Missing namespace separator '{NAMESPACE_SEPARATOR}'."
        )
    
    # Split on first separator only (tool names might contain dots)
    backend_id, tool_name = namespaced_name.split(NAMESPACE_SEPARATOR, 1)
    
    validate_backend_id(backend_id)
    if not tool_name:
        raise NamespaceError("Tool name cannot be empty after namespace")
    
    return backend_id, tool_name


def prefix_description(backend_id: str, description: str) -> str:
    """
    Add backend prefix to tool description.
    
    Args:
        backend_id: Backend identifier (e.g., "notion")
        description: Original description
    
    Returns:
        Prefixed description (e.g., "[Notion] Search pages in workspace")
    """
    # Capitalize first letter for display
    display_name = backend_id.replace("_", " ").title()
    return f"[{display_name}] {description}"


@dataclass
class Tool:
    """MCP Tool representation."""
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


def prefix_tool(backend_id: str, tool: Tool) -> Tool:
    """
    Create a new tool with namespaced name and description.
    
    Args:
        backend_id: Backend identifier
        tool: Original tool
    
    Returns:
        New Tool with prefixed name and description
    """
    return Tool(
        name=prefix_tool_name(backend_id, tool.name),
        description=prefix_description(backend_id, tool.description),
        input_schema=tool.input_schema
    )


def prefix_tools(backend_id: str, tools: List[Tool]) -> List[Tool]:
    """
    Prefix a list of tools with backend namespace.
    
    Args:
        backend_id: Backend identifier
        tools: List of original tools
    
    Returns:
        List of tools with prefixed names and descriptions
    """
    return [prefix_tool(backend_id, tool) for tool in tools]


def get_backend_from_tool_name(namespaced_name: str) -> str:
    """
    Extract just the backend ID from a namespaced tool name.
    
    Args:
        namespaced_name: Namespaced tool name (e.g., "notion.search_pages")
    
    Returns:
        Backend ID (e.g., "notion")
    """
    backend_id, _ = unprefix_tool_name(namespaced_name)
    return backend_id
```

---

## Post-Conditions

After completing this task:

- [ ] All acceptance criteria met
- [ ] Tests pass locally: `pytest deeptrail-gateway/tests/gateway/mcp/test_namespace.py`
- [ ] Linting passes: `ruff check deeptrail-gateway/gateway/mcp/`
- [ ] Type checking passes: `mypy deeptrail-gateway/gateway/mcp/`
- [ ] Task B5 (tool schema cache) can proceed
- [ ] Task B6 (tools/list handler) can use namespace utilities
- [ ] Task B7 (tools/call handler) can use unprefix for routing

---

## References

- Design Doc Section 2.8: Step 7 - Agent Discovers Tools (Filtered tools/list)
- Design Doc Section 2.9: Step 8 - Agent Executes Tool (namespace routing)
- B1 Task: MCP JSON-RPC 2.0 parser for Tool structures

---

## Notes

- Keep the separator as `.` for readability and common convention
- Backend IDs should match service registration (e.g., `notion`, `slack`, `hubspot`)
- The `unprefix_tool_name` function is critical for routing in B7
- Consider caching the parsed namespace for performance in hot path
- C4 (tool→permission mapper) will map namespaced tools to permission strings

---

## Test Cases to Cover

```python
# test_namespace.py

def test_prefix_tool_name_basic():
    assert prefix_tool_name("notion", "search_pages") == "notion.search_pages"

def test_prefix_tool_name_with_underscore_backend():
    assert prefix_tool_name("hub_spot", "get_contact") == "hub_spot.get_contact"

def test_unprefix_tool_name_basic():
    assert unprefix_tool_name("slack.send_message") == ("slack", "send_message")

def test_unprefix_tool_name_with_dots_in_tool():
    # Tool name contains dots (edge case)
    assert unprefix_tool_name("github.repos.create") == ("github", "repos.create")

def test_invalid_backend_id():
    with pytest.raises(NamespaceError):
        prefix_tool_name("Notion", "search")  # Uppercase not allowed

def test_empty_tool_name():
    with pytest.raises(NamespaceError):
        prefix_tool_name("notion", "")

def test_prefix_description():
    result = prefix_description("notion", "Search pages in workspace")
    assert result == "[Notion] Search pages in workspace"

def test_prefix_description_with_underscore():
    result = prefix_description("hub_spot", "Get contact details")
    assert result == "[Hub Spot] Get contact details"
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
