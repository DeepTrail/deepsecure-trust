# Task Specification: B2 Implement RoleSwitcher

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** Interactive Demo Plan - Role Switching

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | B2 |
| **Task Name** | Implement RoleSwitcher |
| **Type** | Component (UI Class) |
| **Location** | `demos/interactive/role_switcher.py` |
| **Validates** | Role switching between personas during demo |

---

## Component Specification

### Class: `RoleSwitcher`

| Field | Value |
|-------|-------|
| **Module** | `demos.interactive.role_switcher` |
| **Class** | `RoleSwitcher` |
| **Purpose** | Manage role switching between personas during interactive demo |
| **Pattern** | Stateful controller class |

---

## Class Definition

```python
from rich.console import Console

from demos.interactive.personas import Persona, PERSONAS, get_persona
from demos.interactive.prompts import PromptUI


class RoleSwitcher:
    """Manages role switching between personas during the interactive demo.
    
    Handles transitions between different stakeholder perspectives,
    displaying appropriate banners and maintaining role state.
    
    Attributes:
        ui: PromptUI instance for display
        current_persona: Currently active Persona
        console: Rich Console for output
    """
    
    def __init__(
        self,
        ui: PromptUI | None = None,
        console: Console | None = None,
    ) -> None:
        """Initialize the role switcher.
        
        Args:
            ui: Optional PromptUI instance. Creates new if not provided.
            console: Optional Rich Console. Creates new if not provided.
        """
        ...
    
    def switch_to(
        self,
        persona_id: str,
        step: int,
        title: str,
        show_banner: bool = True,
    ) -> Persona:
        """Switch to a different persona role.
        
        Displays role banner and updates internal state.
        
        Args:
            persona_id: ID of persona to switch to (e.g., "sarah", "it_admin")
            step: Current step number (1-10)
            title: Step title for banner display
            show_banner: Whether to display the role banner (default: True)
            
        Returns:
            The Persona that was switched to
            
        Raises:
            ValueError: If persona_id is not valid
        """
        ...
    
    def get_current(self) -> Persona:
        """Get the currently active persona.
        
        Returns:
            Currently active Persona
        """
        ...
    
    def show_vendor_perspective(
        self,
        step: int,
        title: str,
    ) -> None:
        """Switch to vendor perspective for split-view steps.
        
        Used for steps 4, 5-6, 9 where vendor sees agent's actions.
        
        Args:
            step: Current step number
            title: Step title
        """
        ...
    
    def show_all_perspectives(
        self,
        step: int,
        title: str,
        personas: list[str] | None = None,
    ) -> None:
        """Show perspectives from multiple personas (round-robin).
        
        Used for step 10 (audit) where all personas review.
        
        Args:
            step: Current step number
            title: Step title
            personas: List of persona IDs to cycle through (default: all 5)
        """
        ...
    
    def prompt_role_switch(
        self,
        available_personas: list[str] | None = None,
    ) -> str:
        """Prompt user to select a persona to switch to.
        
        Uses PromptUI.select() to let user choose.
        
        Args:
            available_personas: List of persona IDs to offer (default: all 5)
            
        Returns:
            Selected persona ID
        """
        ...
```

---

## Public Methods

| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `__init__` | `ui: PromptUI \| None, console: Console \| None` | `None` | Initialize with optional UI/Console |
| `switch_to` | `persona_id: str, step: int, title: str, show_banner: bool` | `Persona` | Switch to specified persona |
| `get_current` | None | `Persona` | Get currently active persona |
| `show_vendor_perspective` | `step: int, title: str` | `None` | Switch to vendor view |
| `show_all_perspectives` | `step: int, title: str, personas: list[str] \| None` | `None` | Round-robin all personas |
| `prompt_role_switch` | `available_personas: list[str] \| None` | `str` | User selects persona |

---

## Persona IDs Reference

| Persona ID | Name | Used In Steps |
|------------|------|---------------|
| `it_admin` | Alex Martinez (IT Admin) | 1, 10 |
| `sarah` | Sarah Chen (Developer) | 2, 3, 4, 5, 6, 7, 10 |
| `vendor` | Jordan Lee (AI Agent Vendor) | 4, 5-6, 9, 10 |
| `agent` | SDR-Assistant Agent | 8, 10 |
| `security` | Morgan Taylor (Security Officer) | 10 |

---

## Dependencies

| Dependency | Type | Purpose | Version |
|------------|------|---------|---------|
| `rich` | External | Console output | >=13.0.0 |
| `personas` | Internal | Persona, PERSONAS, get_persona | A1 |
| `prompts` | Internal | PromptUI for banners and selection | B1 |

---

## Implementation Requirements

### State Management

1. **Track current persona**: Store as `self.current_persona`
2. **Default persona**: Start with `sarah` (primary demo protagonist)

### Banner Display

When switching roles, display banner via `PromptUI.role_banner()`:
```
╭─────────────────────────────────────────╮
│ 🔧 Alex Martinez - Step 1: Setup Org   │
╰─────────────────────────────────────────╯
```

### Split-View Steps

Steps 4, 5-6, 9 show both Sarah's actions and vendor's perspective:
1. First show Sarah acting
2. Then call `show_vendor_perspective()` to show vendor seeing the action

### Round-Robin Audit (Step 10)

All 5 personas review the audit log:
1. Cycle through each persona
2. Show their perspective/insights
3. Use `show_all_perspectives()` method

---

## Usage Example

```python
from demos.interactive.role_switcher import RoleSwitcher
from demos.interactive.prompts import PromptUI

ui = PromptUI()
switcher = RoleSwitcher(ui=ui)

# Switch to IT Admin for step 1
admin = switcher.switch_to("it_admin", step=1, title="Organization Setup")

# Switch to Sarah for step 2
sarah = switcher.switch_to("sarah", step=2, title="Install SDK")

# Split view for step 4
switcher.switch_to("sarah", step=4, title="Create Agent Identity")
# ... sarah's actions ...
switcher.show_vendor_perspective(step=4, title="Vendor Sees Agent")

# Round-robin for audit step
switcher.show_all_perspectives(step=10, title="Review Audit Log")

# Get current persona
current = switcher.get_current()
print(f"Current: {current.name}")
```

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Implementation | `demos/interactive/role_switcher.py` |
| Unit tests | `tests/demos/test_role_switcher.py` |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] Class can be instantiated with default PromptUI
- [ ] Class can be instantiated with custom PromptUI
- [ ] `switch_to()` updates current persona
- [ ] `switch_to()` displays role banner (when show_banner=True)
- [ ] `switch_to()` raises ValueError for invalid persona_id
- [ ] `get_current()` returns current persona
- [ ] `show_vendor_perspective()` switches to vendor persona
- [ ] `show_all_perspectives()` cycles through all 5 personas
- [ ] `prompt_role_switch()` uses PromptUI.select()
- [ ] Default starting persona is "sarah"

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid persona_id | Raise `ValueError` with message |
| No current persona | Default to "sarah" |
| Empty personas list | Use all 5 personas |

---

## Technical Requirements

| Requirement | Value |
|-------------|-------|
| Python version | 3.10+ |
| External deps | `rich>=13.0.0` |
| Internal deps | A1 (Persona), B1 (PromptUI) |
| Type hints | Required on all public methods |
| Docstrings | Required on all public methods |

---

## References

- **Design Doc:** Interactive Demo Plan
- **Related Specs:** [A1-spec.md](./A1-spec.md), [B1-spec.md](./B1-spec.md)
- **Upstream Dependencies:** A1 (personas.py), B1 (prompts.py)
- **Downstream Dependents:** D1 (step handlers)
