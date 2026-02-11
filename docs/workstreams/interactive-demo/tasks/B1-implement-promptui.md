# Task: B1 Implement PromptUI Class

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | B1 |
| **Status** | `completed` |
| **Dependencies** | A1 ✅ (Persona dataclass) |
| **Complexity** | M (Medium) |
| **Batch** | 2 |
| **Worktree** | deepsecure-mvp (main repo) |

---

## Specification

> See full specification: [B1-spec.md](../specs/B1-spec.md)

### Key Contracts

| Contract | Value |
|----------|-------|
| **Module** | `demos.interactive.prompts` |
| **Class** | `PromptUI` |
| **File** | `demos/interactive/prompts.py` |
| **Pattern** | Stateless utility class |

### Class Interface

```python
class PromptUI:
    def __init__(self, console: Console | None = None) -> None: ...
    def role_banner(self, persona: Persona, step: int, title: str) -> None: ...
    def multi_select(self, prompt: str, choices: list[str], default: list[str] | None = None) -> list[str]: ...
    def confirm(self, prompt: str, default: bool = True) -> bool: ...
    def select(self, prompt: str, choices: list[str], default: str | None = None) -> str: ...
    def show_json(self, data: dict, title: str | None = None) -> None: ...
    def show_insight(self, message: str, persona: Persona) -> None: ...
    def wait_for_continue(self, message: str = "Press Enter to continue...") -> None: ...
```

---

## Pre-Conditions

- [x] A1 complete: `demos/interactive/personas.py` exists with Persona dataclass
- [x] `rich` package available (already in project deps)
- [x] `questionary` package available (already in project deps)

---

## Task Description

Create the `PromptUI` class that provides interactive prompt functionality for the demo:

### 1. Create the Module

Create `demos/interactive/prompts.py` with the `PromptUI` class.

### 2. Implement Display Methods

| Method | Implementation |
|--------|----------------|
| `role_banner()` | Use `rich.panel.Panel` with persona's color, show emoji + name + step + title |
| `show_json()` | Use `rich.syntax.Syntax` with `json` language, wrap in Panel |
| `show_insight()` | Use `rich.panel.Panel` with persona's color, prefix with emoji |

### 3. Implement Prompt Methods

| Method | Implementation |
|--------|----------------|
| `multi_select()` | Use `questionary.checkbox()` |
| `confirm()` | Use `questionary.confirm()` |
| `select()` | Use `questionary.select()` |
| `wait_for_continue()` | Use `input()` or `questionary.press_any_key_to_continue()` |

### 4. Display Styling Requirements

**Role Banner Format:**
```
╭─────────────────────────────────────────╮
│ 👩‍💻 Sarah Chen - Step 3: Connect Tools  │
╰─────────────────────────────────────────╯
```

**Insight Panel Format:**
```
💡 Sarah's Insight:
This shows how the SDK handles credential rotation...
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `demos/interactive/prompts.py` | Create | PromptUI class implementation |

---

## Acceptance Criteria

### Class Structure
- [ ] Class named `PromptUI` in `demos/interactive/prompts.py`
- [ ] Constructor accepts optional `Console` parameter
- [ ] Creates default Console if not provided
- [ ] All 8 methods implemented per spec

### Display Methods
- [ ] `role_banner()` shows formatted panel with persona styling
- [ ] `role_banner()` uses persona's color for border
- [ ] `role_banner()` displays: emoji, name, step number, title
- [ ] `show_json()` uses `rich.syntax.Syntax` for highlighting
- [ ] `show_json()` wraps in Panel with optional title
- [ ] `show_insight()` shows panel with persona's emoji and color

### Prompt Methods
- [ ] `multi_select()` uses `questionary.checkbox()`
- [ ] `multi_select()` returns list of selected strings
- [ ] `multi_select()` handles empty choices (raises ValueError)
- [ ] `confirm()` uses `questionary.confirm()`
- [ ] `confirm()` returns boolean
- [ ] `select()` uses `questionary.select()`
- [ ] `select()` returns single string
- [ ] `select()` handles empty choices (raises ValueError)
- [ ] `wait_for_continue()` blocks until Enter pressed

### Code Quality
- [ ] Type hints on all public methods
- [ ] Docstrings on all public methods
- [ ] Imports from `demos.interactive.personas` for Persona type

### Integration
- [ ] Import works: `from demos.interactive.prompts import PromptUI`
- [ ] Works with Persona from A1: `ui.role_banner(get_persona("sarah"), 1, "Test")`

---

## Post-Conditions

After this task:
- `PromptUI` class available for B2 (RoleSwitcher) and D1 (step handlers)
- Interactive prompts ready for the demo experience

---

## Validation Mapping

| Validates | Description |
|-----------|-------------|
| **Demo** | All interactive demo steps with user prompts |
| **User Journey** | Steps 2-7 where user makes choices |

---

## Test Commands

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp

# Verify import works
python -c "from demos.interactive.prompts import PromptUI; print('✅ Import works')"

# Quick instantiation test
python -c "
from demos.interactive.prompts import PromptUI
from demos.interactive.personas import get_persona

ui = PromptUI()
sarah = get_persona('sarah')
ui.role_banner(sarah, step=1, title='Test Step')
print('✅ PromptUI works')
"
```

---

## Execution Command

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/execute-task B1 interactive-demo
```

---

## References

- **Design Doc:** [Interactive Demo Plan](../../../.cursor/plans/interactive_demo_plan_7ee6283a.plan.md)
- **Specification:** [B1-spec.md](../specs/B1-spec.md)
- **Related Tasks:** A1 (Persona - dependency)
- **Downstream:** B2 (RoleSwitcher), D1 (step handlers)
- **External Deps:** `rich>=13.0.0`, `questionary>=2.0.0`
