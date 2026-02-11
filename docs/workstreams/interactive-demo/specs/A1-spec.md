# Task Specification: A1 Define Persona Dataclass and 5 Personas

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** Interactive Demo Plan - Persona Definitions

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | A1 |
| **Task Name** | Define Persona dataclass and 5 personas |
| **Type** | Component (Dataclass) |
| **Location** | `demos/interactive/personas.py` |
| **Validates** | Persona Switching feature, All journey steps |

---

## Component Specification

### Module: `demos.interactive.personas`

| Field | Value |
|-------|-------|
| **Module** | `demos.interactive.personas` |
| **Type** | Dataclass + Dictionary |
| **Purpose** | Define the 5 personas who participate in Sarah's Journey demo |

### Interface Contract

```python
from dataclasses import dataclass


@dataclass
class Persona:
    """Represents a stakeholder persona in the interactive demo.
    
    Each persona has a unique perspective on the DeepSecure Virtual MCP Server
    and participates in specific steps of Sarah's Journey.
    
    Attributes:
        id: Unique identifier used as dictionary key (e.g., "it_admin")
        name: Display name shown in UI (e.g., "IT Admin")
        title: Full role title (e.g., "Enterprise Administrator")
        color: Rich library color for terminal display (e.g., "blue")
        emoji: Emoji for visual identification in banners
        steps: List of journey step numbers this persona participates in
    """
    
    id: str
    name: str
    title: str
    color: str
    emoji: str
    steps: list[int]
```

### PERSONAS Dictionary

```python
PERSONAS: dict[str, Persona] = {
    "it_admin": Persona(
        id="it_admin",
        name="IT Admin",
        title="Enterprise Administrator",
        color="blue",
        emoji="🔧",
        steps=[1],
    ),
    "sarah": Persona(
        id="sarah",
        name="Sarah",
        title="Sales Development Representative",
        color="green",
        emoji="👩‍💼",
        steps=[2, 3, 4, 10],
    ),
    "vendor": Persona(
        id="vendor",
        name="AI Agent Vendor",
        title="Third-Party AI Platform Provider",
        color="yellow",
        emoji="🏭",
        steps=[4, 5, 6, 9, 10],
    ),
    "agent": Persona(
        id="agent",
        name="SDR-Assistant",
        title="AI Agent (running on vendor infrastructure)",
        color="cyan",
        emoji="🤖",
        steps=[5, 6, 7, 8, 9],
    ),
    "security": Persona(
        id="security",
        name="Security Officer",
        title="Enterprise Security & Compliance",
        color="red",
        emoji="🛡️",
        steps=[9, 10],
    ),
}
```

### Helper Functions

```python
def get_persona(persona_id: str) -> Persona:
    """Get persona by ID, raising KeyError if not found."""
    return PERSONAS[persona_id]


def get_personas_for_step(step: int) -> list[Persona]:
    """Get all personas that participate in a given step."""
    return [p for p in PERSONAS.values() if step in p.steps]


def get_primary_persona_for_step(step: int) -> Persona:
    """Get the primary (first) persona for a step."""
    personas = get_personas_for_step(step)
    if not personas:
        raise ValueError(f"No persona defined for step {step}")
    return personas[0]
```

---

## Step-to-Persona Mapping

| Step | Primary Persona | Secondary Personas | Description |
|------|-----------------|-------------------|-------------|
| 1 | IT Admin | - | Enterprise configuration |
| 2 | Sarah | - | User authentication |
| 3 | Sarah | - | Connect OAuth services |
| 4 | Sarah | Vendor | Delegate permissions (split view) |
| 5 | Agent | Vendor | Agent authentication (vendor observes) |
| 6 | Agent | Vendor | MCP connection (vendor observes) |
| 7 | Agent | - | Tool discovery |
| 8 | Agent | - | Tool execution |
| 9 | Agent | Security | Permission denial (security reviews) |
| 10 | Sarah | Vendor, Security | Audit review (round-robin) |

---

## Public Interface

| Function/Class | Arguments | Returns | Description |
|----------------|-----------|---------|-------------|
| `Persona` | dataclass fields | `Persona` | Persona data structure |
| `PERSONAS` | - | `dict[str, Persona]` | All 5 personas by ID |
| `get_persona` | `persona_id: str` | `Persona` | Get persona by ID |
| `get_personas_for_step` | `step: int` | `list[Persona]` | Get all personas for step |
| `get_primary_persona_for_step` | `step: int` | `Persona` | Get primary persona for step |

---

## Usage Example

```python
from demos.interactive.personas import PERSONAS, get_personas_for_step, Persona

# Access a specific persona
sarah = PERSONAS["sarah"]
print(f"{sarah.emoji} {sarah.name}: {sarah.title}")
# Output: 👩‍💼 Sarah: Sales Development Representative

# Get personas for step 4 (delegation)
step_4_personas = get_personas_for_step(4)
for persona in step_4_personas:
    print(f"  {persona.name} participates in step 4")
# Output:
#   Sarah participates in step 4
#   AI Agent Vendor participates in step 4

# Use persona color for rich formatting
from rich.console import Console
console = Console()
console.print(f"[{sarah.color}]{sarah.name} is acting...[/{sarah.color}]")
```

---

## Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| `dataclasses` | Standard Library | Dataclass decorator |
| None | External | No external dependencies |

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Implementation | `demos/interactive/personas.py` |
| Unit tests | `tests/demos/test_personas.py` (optional) |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `Persona` dataclass has all 6 fields: id, name, title, color, emoji, steps
- [ ] `PERSONAS` dictionary contains exactly 5 personas
- [ ] All persona IDs match their dictionary keys
- [ ] Each persona has correct step assignments per mapping table
- [ ] Helper functions work correctly
- [ ] Type hints present on all public functions
- [ ] Docstrings present on class and functions

---

## References

- **Design Doc:** Interactive Demo Plan
- **Related Specs:** [A2-spec.md](./A2-spec.md) (uses Persona for summaries)
- **Upstream Dependencies:** None
- **Downstream Dependents:** A2, A3, B1, B2, D1
