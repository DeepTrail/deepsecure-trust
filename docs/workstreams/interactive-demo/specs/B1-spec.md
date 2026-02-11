# Task Specification: B1 Create PromptUI Class

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** Interactive Demo Plan - UI Components

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | B1 |
| **Task Name** | Create PromptUI class |
| **Type** | Component (UI Class) |
| **Location** | `demos/interactive/prompts.py` |
| **Validates** | Interactive prompts, formatted display |

---

## Component Specification

### Class: `PromptUI`

| Field | Value |
|-------|-------|
| **Module** | `demos.interactive.prompts` |
| **Class** | `PromptUI` |
| **Purpose** | Interactive prompt UI using rich and questionary |
| **Pattern** | Stateless utility class |

---

## Class Definition

```python
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
import questionary

from demos.interactive.personas import Persona


class PromptUI:
    """Interactive prompt UI using rich and questionary.
    
    Provides formatted prompts, banners, and display methods
    for the interactive demo experience.
    
    Attributes:
        console: Rich Console for formatted output
    """
    
    def __init__(
        self,
        console: Console | None = None,
    ) -> None:
        """Initialize the prompt UI.
        
        Args:
            console: Optional Rich Console. Creates new if not provided.
        """
        self.console = console or Console()
    
    def role_banner(
        self,
        persona: Persona,
        step: int,
        title: str,
    ) -> None:
        """Display a role-specific banner for a step.
        
        Shows persona emoji, name, and step title in persona's color.
        Creates a visually distinct marker for role switches.
        
        Args:
            persona: The Persona for styling
            step: Current step number (1-7)
            title: Step title text
        """
        ...
    
    def multi_select(
        self,
        prompt: str,
        choices: list[str],
        default: list[str] | None = None,
    ) -> list[str]:
        """Present multi-select prompt using questionary.
        
        Uses checkbox style for multiple selections.
        
        Args:
            prompt: Question text to display
            choices: List of available choices
            default: Pre-selected choices (optional)
            
        Returns:
            List of selected choices (may be empty)
        """
        ...
    
    def confirm(
        self,
        prompt: str,
        default: bool = True,
    ) -> bool:
        """Present yes/no confirmation prompt.
        
        Args:
            prompt: Question text to display
            default: Default answer (True = yes)
            
        Returns:
            True if confirmed, False otherwise
        """
        ...
    
    def select(
        self,
        prompt: str,
        choices: list[str],
        default: str | None = None,
    ) -> str:
        """Present single-select prompt.
        
        Args:
            prompt: Question text to display
            choices: List of available choices
            default: Pre-selected choice (optional)
            
        Returns:
            Selected choice string
        """
        ...
    
    def show_json(
        self,
        data: dict,
        title: str | None = None,
    ) -> None:
        """Display formatted JSON panel.
        
        Uses rich.syntax for syntax highlighting.
        
        Args:
            data: Dictionary to display as JSON
            title: Optional panel title
        """
        ...
    
    def show_insight(
        self,
        message: str,
        persona: Persona,
    ) -> None:
        """Display persona-specific insight or commentary.
        
        Shows a styled panel with persona's emoji and color.
        
        Args:
            message: Insight message text
            persona: Persona for styling
        """
        ...
    
    def wait_for_continue(
        self,
        message: str = "Press Enter to continue...",
    ) -> None:
        """Wait for user to press Enter.
        
        Displays message and blocks until Enter is pressed.
        
        Args:
            message: Prompt message to display
        """
        ...
```

---

## Public Methods

| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `__init__` | `console: Console \| None` | `None` | Initialize with optional Console |
| `role_banner` | `persona: Persona, step: int, title: str` | `None` | Display step banner with persona styling |
| `multi_select` | `prompt: str, choices: list[str], default: list[str] \| None` | `list[str]` | Multi-choice checkbox prompt |
| `confirm` | `prompt: str, default: bool` | `bool` | Yes/no confirmation prompt |
| `select` | `prompt: str, choices: list[str], default: str \| None` | `str` | Single-choice selection prompt |
| `show_json` | `data: dict, title: str \| None` | `None` | Display JSON with syntax highlighting |
| `show_insight` | `message: str, persona: Persona` | `None` | Display persona-styled insight panel |
| `wait_for_continue` | `message: str` | `None` | Pause until Enter pressed |

---

## Dependencies

| Dependency | Type | Purpose | Version |
|------------|------|---------|---------|
| `rich` | External | Console, Panel, Text, Syntax | >=13.0.0 |
| `questionary` | External | Interactive prompts | >=2.0.0 |
| `personas` | Internal | Persona dataclass for styling | A1 |

---

## Implementation Requirements

### Display Styling

1. **Role Banner Format:**
   ```
   ╭─────────────────────────────────────────╮
   │ 👩‍💻 Sarah Chen - Step 3: Connect Tools  │
   ╰─────────────────────────────────────────╯
   ```
   - Use persona's color for border
   - Show emoji, name, step number, title

2. **Insight Panel Format:**
   ```
   💡 Sarah's Insight:
   This shows how the SDK handles credential rotation...
   ```
   - Use persona's color
   - Prefix with persona's emoji

3. **JSON Display:**
   - Use `rich.syntax.Syntax` with `json` language
   - Wrap in Panel with optional title

### Prompt Behavior

1. **multi_select:** Use `questionary.checkbox()`
2. **confirm:** Use `questionary.confirm()`
3. **select:** Use `questionary.select()`
4. **wait_for_continue:** Use `input()` or `questionary.press_any_key_to_continue()`

---

## Usage Example

```python
from demos.interactive.prompts import PromptUI
from demos.interactive.personas import get_persona

ui = PromptUI()
sarah = get_persona("sarah")

# Show role banner
ui.role_banner(sarah, step=3, title="Connect External Tools")

# Ask for tool selection
tools = ui.multi_select(
    prompt="Select tools to connect:",
    choices=["OpenAI", "GitHub", "Slack", "Salesforce"],
    default=["OpenAI", "GitHub"],
)

# Show JSON response
ui.show_json(
    {"agent_id": "sdr-assistant", "tools": tools},
    title="Configuration",
)

# Persona insight
ui.show_insight(
    "The agent now has access to these tools through the gateway.",
    sarah,
)

# Wait before next step
ui.wait_for_continue()
```

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Implementation | `demos/interactive/prompts.py` |
| Unit tests | `tests/demos/test_prompts.py` |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] Class can be instantiated with default console
- [ ] Class can be instantiated with custom console
- [ ] `role_banner()` displays formatted banner
- [ ] `multi_select()` returns list of selections
- [ ] `confirm()` returns boolean
- [ ] `select()` returns single string
- [ ] `show_json()` displays formatted JSON
- [ ] `show_insight()` shows persona-styled panel
- [ ] `wait_for_continue()` blocks until Enter
- [ ] All methods handle edge cases (empty lists, etc.)

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Empty choices list | Raise `ValueError` for select/multi_select |
| Invalid persona | Accept any Persona (duck typing) |
| Keyboard interrupt | Let exception propagate |

---

## Technical Requirements

| Requirement | Value |
|-------------|-------|
| Python version | 3.10+ |
| External deps | `rich>=13.0.0`, `questionary>=2.0.0` |
| Internal deps | A1 (Persona dataclass) |
| Type hints | Required on all public methods |
| Docstrings | Required on all public methods |

---

## References

- **Design Doc:** Interactive Demo Plan
- **Related Specs:** [A1-spec.md](./A1-spec.md) (Persona)
- **Upstream Dependencies:** A1 (personas.py)
- **Downstream Dependents:** B2 (RoleSwitcher), D1 (step handlers)
