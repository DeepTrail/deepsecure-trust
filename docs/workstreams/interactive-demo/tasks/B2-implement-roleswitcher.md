# Task: B2 Implement RoleSwitcher

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | B2 |
| **Status** | `pending` |
| **Dependencies** | A1 ✅ (Persona), B1 (PromptUI) |
| **Complexity** | M (Medium) |
| **Batch** | 3 |
| **Wave** | 1 (first in batch) |
| **Worktree** | deepsecure-mvp (main repo) |

---

## Specification

> See full specification: [B2-spec.md](../specs/B2-spec.md)

### Key Contracts

| Contract | Value |
|----------|-------|
| **Module** | `demos.interactive.role_switcher` |
| **Class** | `RoleSwitcher` |
| **File** | `demos/interactive/role_switcher.py` |
| **Pattern** | Stateful controller class |

### Class Interface

```python
class RoleSwitcher:
    def __init__(self, ui: PromptUI | None = None, console: Console | None = None) -> None: ...
    def switch_to(self, persona_id: str, step: int, title: str, show_banner: bool = True) -> Persona: ...
    def get_current(self) -> Persona: ...
    def show_vendor_perspective(self, step: int, title: str) -> None: ...
    def show_all_perspectives(self, step: int, title: str, personas: list[str] | None = None) -> None: ...
    def prompt_role_switch(self, available_personas: list[str] | None = None) -> str: ...
```

---

## Pre-Conditions

- [x] A1 complete: `demos/interactive/personas.py` exists with Persona, PERSONAS, get_persona
- [ ] B1 complete: `demos/interactive/prompts.py` exists with PromptUI

---

## Task Description

Create the `RoleSwitcher` class that manages role switching between personas during the interactive demo:

### 1. Create the Module

Create `demos/interactive/role_switcher.py` with the `RoleSwitcher` class.

### 2. Implement State Management

- Track current persona as `self.current_persona`
- Default starting persona is `sarah` (primary demo protagonist)

### 3. Implement Core Methods

| Method | Implementation |
|--------|----------------|
| `__init__()` | Store ui (or create PromptUI), console, set default persona to sarah |
| `switch_to()` | Update current_persona, call `ui.role_banner()` if show_banner=True |
| `get_current()` | Return current_persona |

### 4. Implement Split-View Methods

| Method | Implementation |
|--------|----------------|
| `show_vendor_perspective()` | Call `switch_to("vendor", step, title)` |
| `show_all_perspectives()` | Loop through personas, switch to each, display |

### 5. Implement User Selection

| Method | Implementation |
|--------|----------------|
| `prompt_role_switch()` | Use `ui.select()` with persona names, return selected ID |

---

## Persona IDs Reference

| Persona ID | Name | Steps |
|------------|------|-------|
| `it_admin` | Alex Martinez (IT Admin) | 1, 10 |
| `sarah` | Sarah Chen (Developer) | 2, 3, 4, 5, 6, 7, 10 |
| `vendor` | Jordan Lee (AI Agent Vendor) | 4, 5-6, 9, 10 |
| `agent` | SDR-Assistant Agent | 8, 10 |
| `security` | Morgan Taylor (Security Officer) | 10 |

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `demos/interactive/role_switcher.py` | Create | RoleSwitcher class implementation |

---

## Acceptance Criteria

### Class Structure
- [ ] Class named `RoleSwitcher` in `demos/interactive/role_switcher.py`
- [ ] Constructor accepts optional `PromptUI` and `Console` parameters
- [ ] Creates default PromptUI if not provided
- [ ] All 6 methods implemented per spec

### State Management
- [ ] Default starting persona is "sarah"
- [ ] `current_persona` attribute tracks active persona
- [ ] `switch_to()` updates `current_persona`

### Core Methods
- [ ] `switch_to()` calls `ui.role_banner()` when `show_banner=True`
- [ ] `switch_to()` skips banner when `show_banner=False`
- [ ] `switch_to()` returns the Persona object
- [ ] `switch_to()` raises `ValueError` for invalid persona_id
- [ ] `get_current()` returns current persona

### Split-View Methods
- [ ] `show_vendor_perspective()` switches to "vendor" persona
- [ ] `show_all_perspectives()` cycles through all 5 personas (or specified list)

### User Selection
- [ ] `prompt_role_switch()` uses `ui.select()` for persona selection
- [ ] `prompt_role_switch()` returns selected persona ID string

### Code Quality
- [ ] Type hints on all public methods
- [ ] Docstrings on all public methods
- [ ] Imports from `demos.interactive.personas` and `demos.interactive.prompts`

### Integration
- [ ] Import works: `from demos.interactive.role_switcher import RoleSwitcher`
- [ ] Works with PromptUI: `switcher = RoleSwitcher(ui=PromptUI())`

---

## Post-Conditions

After this task:
- `RoleSwitcher` class available for D1 (step handlers)
- Role switching functionality ready for the demo experience

---

## Validation Mapping

| Validates | Description |
|-----------|-------------|
| **Demo** | All steps with role changes, split views, audit review |
| **User Journey** | Steps 4, 5-6, 9 (split view), Step 10 (round-robin) |

---

## Test Commands

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp

# Verify import works
python -c "from demos.interactive.role_switcher import RoleSwitcher; print('✅ Import works')"

# Quick instantiation test
python -c "
from demos.interactive.role_switcher import RoleSwitcher
from demos.interactive.prompts import PromptUI

switcher = RoleSwitcher()
current = switcher.get_current()
print(f'Default persona: {current.name}')

sarah = switcher.switch_to('sarah', step=1, title='Test')
print(f'Switched to: {sarah.name}')
print('✅ RoleSwitcher works')
"
```

---

## Execution Command

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/execute-task B2 interactive-demo
```

---

## References

- **Design Doc:** Interactive Demo Plan
- **Specification:** [B2-spec.md](../specs/B2-spec.md)
- **Related Tasks:** A1 (Persona - dependency), B1 (PromptUI - dependency)
- **Downstream:** D1 (step handlers use RoleSwitcher)
