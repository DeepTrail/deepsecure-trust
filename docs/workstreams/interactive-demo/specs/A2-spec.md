# Task Specification: A2 Implement DemoContext State Manager

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** Interactive Demo Plan - State Management

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | A2 |
| **Task Name** | Implement DemoContext class |
| **Type** | Component (Dataclass + State Manager) |
| **Location** | `demos/interactive/context.py` |
| **Validates** | State Management feature, All journey steps |

---

## Component Specification

### Module: `demos.interactive.context`

| Field | Value |
|-------|-------|
| **Module** | `demos.interactive.context` |
| **Type** | Dataclass with methods |
| **Purpose** | Manage state across all 10 journey steps, track progress, and provide persona-specific context views |

### Interface Contract

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DemoContext:
    """Central state manager for the interactive demo.
    
    Tracks all state generated during Sarah's Journey, including:
    - Authentication tokens and session IDs
    - Connected services and permissions
    - Tool discovery and execution results
    - Audit events
    
    The context is accumulated across steps and provides
    persona-specific views of relevant state.
    
    Attributes:
        current_step: Current step number (0 = not started, 1-10 = active)
        current_persona: ID of currently active persona
        org_id: Organization ID from Step 1
        org_name: Organization display name from Step 1
        user_token: Sarah's user JWT from Step 2
        user_email: Sarah's email from Step 2
        connected_services: List of OAuth service names from Step 3
        delegation_id: Delegation session ID from Step 4
        delegated_permissions: List of permission strings from Step 4
        agent_id: Agent's unique identifier from Step 5
        agent_jwt: Agent's JWT token from Step 5
        mcp_session_id: MCP session ID from Step 6
        discovered_tools: List of tool metadata dicts from Step 7
        tool_call_results: List of tool execution results from Step 8
        denied_tool: Tool name that was denied in Step 9
        denial_reason: Reason for denial in Step 9
        audit_events: List of audit event dicts from Step 10
    """
    
    # Current state
    current_step: int = 0
    current_persona: str = "sarah"
    
    # Step 1: Enterprise Configuration (IT Admin)
    org_id: str | None = None
    org_name: str | None = None
    
    # Step 2: User Authentication (Sarah)
    user_token: str | None = None
    user_email: str | None = None
    
    # Step 3: OAuth Connection (Sarah)
    connected_services: list[str] = field(default_factory=list)
    
    # Step 4: Permission Delegation (Sarah -> Vendor)
    delegation_id: str | None = None
    delegated_permissions: list[str] = field(default_factory=list)
    
    # Step 5-6: Agent Authentication & MCP Connection (Agent)
    agent_id: str | None = None
    agent_jwt: str | None = None
    mcp_session_id: str | None = None
    
    # Step 7-8: Tool Discovery & Execution (Agent)
    discovered_tools: list[dict[str, Any]] = field(default_factory=list)
    tool_call_results: list[dict[str, Any]] = field(default_factory=list)
    
    # Step 9: Permission Denial (Agent attempts, Security reviews)
    denied_tool: str | None = None
    denial_reason: str | None = None
    
    # Step 10: Audit Review (All personas)
    audit_events: list[dict[str, Any]] = field(default_factory=list)
    
    def get_summary_for_persona(self, persona_id: str) -> dict[str, Any]:
        """Return context summary relevant to a specific persona.
        
        Each persona sees different aspects of the state:
        - IT Admin: org configuration
        - Sarah: her tokens, services, delegations
        - Vendor: delegation details, agent registration
        - Agent: agent credentials, MCP session, tools
        - Security: all events, denials, audit trail
        
        Args:
            persona_id: The persona ID ("it_admin", "sarah", etc.)
            
        Returns:
            Dictionary with persona-relevant state fields
        """
        ...
    
    def advance_step(self) -> None:
        """Move to the next step.
        
        Increments current_step by 1.
        Updates current_persona based on step-to-persona mapping.
        
        Raises:
            ValueError: If already at step 10
        """
        ...
    
    def go_to_step(self, step: int) -> None:
        """Jump to a specific step.
        
        Used for navigation (e.g., going back to review).
        Updates current_persona based on step-to-persona mapping.
        
        Args:
            step: Target step number (1-10)
            
        Raises:
            ValueError: If step is out of range
        """
        ...
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize entire context for display or persistence.
        
        Returns:
            Dictionary with all context fields
        """
        ...
    
    def reset(self) -> None:
        """Reset context to initial state.
        
        Clears all accumulated state and returns to step 0.
        Used when restarting the demo.
        """
        ...
```

---

## Persona-Specific Summaries

The `get_summary_for_persona` method returns different views based on persona:

### IT Admin Summary

```python
{
    "role": "Enterprise Administrator",
    "org_id": "<org_id>",
    "org_name": "<org_name>",
    "message": "Organization configured successfully"
}
```

### Sarah Summary

```python
{
    "role": "Sales Development Representative",
    "email": "<user_email>",
    "connected_services": ["gmail", "salesforce"],
    "delegated_to": "SDR-Assistant",
    "permissions": ["email:read", "email:send", "calendar:read"]
}
```

### Vendor Summary

```python
{
    "role": "AI Platform Provider",
    "delegation_id": "<delegation_id>",
    "agent_id": "<agent_id>",
    "agent_registered": True,
    "permissions_received": ["email:read", "email:send"]
}
```

### Agent Summary

```python
{
    "role": "SDR-Assistant Agent",
    "agent_id": "<agent_id>",
    "mcp_session": "<mcp_session_id>",
    "tools_discovered": 3,
    "tool_calls_made": 2,
    "status": "active"
}
```

### Security Summary

```python
{
    "role": "Security & Compliance",
    "total_events": 15,
    "denied_operations": 1,
    "last_denial": {
        "tool": "<denied_tool>",
        "reason": "<denial_reason>"
    },
    "audit_status": "clean"
}
```

---

## Public Interface

| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `__init__` | dataclass defaults | `DemoContext` | Create context with defaults |
| `get_summary_for_persona` | `persona_id: str` | `dict[str, Any]` | Persona-specific view |
| `advance_step` | - | `None` | Move to next step |
| `go_to_step` | `step: int` | `None` | Jump to specific step |
| `to_dict` | - | `dict[str, Any]` | Full serialization |
| `reset` | - | `None` | Clear all state |

---

## Usage Example

```python
from demos.interactive.context import DemoContext

# Create context
ctx = DemoContext()

# Step 1: IT Admin sets up org
ctx.current_step = 1
ctx.current_persona = "it_admin"
ctx.org_id = "org_abc123"
ctx.org_name = "Acme Corp"

# Step 2: Sarah authenticates
ctx.advance_step()  # Now step 2, persona = "sarah"
ctx.user_token = "eyJ..."
ctx.user_email = "sarah@acme.com"

# Get persona-specific summary
sarah_view = ctx.get_summary_for_persona("sarah")
print(sarah_view)
# Output: {"role": "Sales Development Representative", "email": "sarah@acme.com", ...}

# Serialize full context
full_state = ctx.to_dict()

# Reset for new demo run
ctx.reset()
assert ctx.current_step == 0
```

---

## Step-to-Persona Mapping (used by advance_step/go_to_step)

```python
STEP_PRIMARY_PERSONA: dict[int, str] = {
    1: "it_admin",
    2: "sarah",
    3: "sarah",
    4: "sarah",
    5: "agent",
    6: "agent",
    7: "agent",
    8: "agent",
    9: "agent",
    10: "sarah",  # Final audit review starts with Sarah
}
```

---

## Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| `dataclasses` | Standard Library | Dataclass and field decorators |
| `typing` | Standard Library | Type hints (Any) |
| `personas` | Internal | Imports `PERSONAS` for validation (optional) |

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Implementation | `demos/interactive/context.py` |
| Unit tests | `tests/demos/test_context.py` (optional) |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `DemoContext` dataclass has all fields per specification
- [ ] All fields have correct default values (None, 0, or empty list)
- [ ] `get_summary_for_persona` returns appropriate dict for each persona
- [ ] `advance_step` increments step and updates persona correctly
- [ ] `go_to_step` validates range and updates persona
- [ ] `to_dict` returns complete serialization
- [ ] `reset` clears all fields to defaults
- [ ] Type hints present on all methods
- [ ] Docstrings present on class and all public methods

---

## References

- **Design Doc:** Interactive Demo Plan
- **Related Specs:** [A1-spec.md](./A1-spec.md) (provides Persona definitions)
- **Upstream Dependencies:** A1 (personas.py)
- **Downstream Dependents:** A3, B1, B2, D1, E1
