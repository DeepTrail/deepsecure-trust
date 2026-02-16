# Task Specification: A3 Create Package __init__.py

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** Interactive Demo Plan - Package Structure
>
> **Status:** Already implemented - spec for documentation

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | A3 |
| **Task Name** | Create package __init__.py |
| **Type** | Component (Package Exports) |
| **Location** | `demos/interactive/__init__.py` |
| **Validates** | Package structure, clean imports |

---

## Component Specification

### Module: `demos.interactive`

| Field | Value |
|-------|-------|
| **Module** | `demos.interactive` |
| **Type** | Package __init__.py |
| **Purpose** | Export public API for the interactive demo package |

### Current Exports (Batch 1)

```python
"""Interactive demo for Sarah's Journey - DeepSecure Virtual MCP Server."""

from demos.interactive.context import DemoContext, STEP_PRIMARY_PERSONA
from demos.interactive.personas import (
    PERSONAS,
    Persona,
    get_persona,
    get_personas_for_step,
    get_primary_persona_for_step,
)

__all__ = [
    # Context (A2)
    "DemoContext",
    "STEP_PRIMARY_PERSONA",
    # Personas (A1)
    "Persona",
    "PERSONAS",
    "get_persona",
    "get_personas_for_step",
    "get_primary_persona_for_step",
]
```

### Future Exports (After Batch 2, 3)

```python
# After B1 complete:
from demos.interactive.prompts import PromptUI

# After B2 complete:
from demos.interactive.role_switcher import RoleSwitcher

# After C1 complete (already available):
from demos.interactive.api_client import APIClient

# After D1 complete:
from demos.interactive.step_handlers import STEP_HANDLERS

# Updated __all__:
__all__ = [
    # Context
    "DemoContext",
    "STEP_PRIMARY_PERSONA",
    # Personas
    "Persona",
    "PERSONAS",
    "get_persona",
    "get_personas_for_step",
    "get_primary_persona_for_step",
    # UI (Batch 2)
    "PromptUI",
    # Role Switching (Batch 3)
    "RoleSwitcher",
    # API Client (Batch 1)
    "APIClient",
    # Step Handlers (Batch 3)
    "STEP_HANDLERS",
]
```

---

## Public Interface

### Exported Symbols

| Symbol | Source Module | Description |
|--------|---------------|-------------|
| `DemoContext` | `context` | State manager dataclass |
| `STEP_PRIMARY_PERSONA` | `context` | Step-to-persona mapping dict |
| `Persona` | `personas` | Persona dataclass |
| `PERSONAS` | `personas` | Dict of 5 personas |
| `get_persona` | `personas` | Get persona by ID |
| `get_personas_for_step` | `personas` | Get all personas for step |
| `get_primary_persona_for_step` | `personas` | Get primary persona for step |

---

## Usage Example

```python
# Import from package (clean API)
from demos.interactive import (
    DemoContext,
    PERSONAS,
    Persona,
    get_persona,
)

# Create context
ctx = DemoContext()

# Get a persona
sarah = get_persona("sarah")
print(f"{sarah.emoji} {sarah.name}")
```

---

## Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| `context` | Internal | DemoContext, STEP_PRIMARY_PERSONA |
| `personas` | Internal | Persona, PERSONAS, helpers |

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Implementation | `demos/interactive/__init__.py` |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [x] Package docstring present
- [x] All Batch 1 symbols exported (DemoContext, Persona, etc.)
- [x] `__all__` list matches exported symbols
- [x] Imports work: `from demos.interactive import DemoContext`
- [ ] Future: Add PromptUI after B1 complete
- [ ] Future: Add RoleSwitcher after B2 complete
- [ ] Future: Add APIClient export
- [ ] Future: Add STEP_HANDLERS after D1 complete

---

## References

- **Design Doc:** Interactive Demo Plan
- **Related Specs:** [A1-spec.md](./A1-spec.md), [A2-spec.md](./A2-spec.md)
- **Upstream Dependencies:** A1 (personas.py), A2 (context.py)
- **Downstream Dependents:** All tasks that import from package
