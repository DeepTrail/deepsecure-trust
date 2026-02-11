# Task: A1 Define Persona Dataclass and 5 Personas

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [Interactive Demo Plan](../../../../.cursor/plans/interactive_demo_plan_7ee6283a.plan.md) |
| **Specification** | [A1-spec.md](../specs/A1-spec.md) |
| **Workstream** | Interactive Demo |
| **Code Dependencies** | None |
| **Runtime Dependencies** | None |
| **Blocked By** | None |
| **Assigned** | - |
| **Created** | February 2026 |
| **Estimated Complexity** | `S` (< 1hr) |
| **Batch** | 1 |
| **Target Worktree** | `deepsecure-mvp` (main repo) |

---

## Dependencies

### Code Dependencies (must complete before starting)

None - this is a foundation task with no dependencies.

### Runtime Dependencies (must be deployed for integration testing)

None - this is a pure Python dataclass with no external service requirements.

### Development Mode

- [x] **Fallback behavior**: N/A - no runtime dependencies
- [x] **Local testing**: Unit tests can run standalone
- [x] **Integration testing**: N/A

---

## Pre-Conditions

Before starting this task, ensure:

- [x] No code dependencies - can start immediately
- [x] `demos/` directory exists in repository

---

## Task Description

Create the `Persona` dataclass and `PERSONAS` dictionary that define the 5 stakeholder personas for the interactive demo. Each persona represents a different perspective on the DeepSecure Virtual MCP Server journey.

### Context

The interactive demo allows users to experience "Sarah's Journey" from multiple stakeholder perspectives:
- **IT Admin**: Enterprise configuration (step 1)
- **Sarah**: User authentication, OAuth, delegation (steps 2-4, 10)
- **AI Agent Vendor**: Receives delegation, registers agent (steps 4-6, 9-10)
- **SDR-Assistant Agent**: Authenticates, discovers tools, executes (steps 5-9)
- **Security Officer**: Reviews denials and audits (steps 9-10)

### Technical Notes

- Use Python `dataclass` for clean, typed structure
- Colors should be valid `rich` library color names
- Step assignments determine when each persona is active
- Helper functions enable step-based persona lookups

---

## Specification (IMMUTABLE)

> **Source:** [A1-spec.md](../specs/A1-spec.md)

### Interface Contract

```python
from dataclasses import dataclass


@dataclass
class Persona:
    id: str           # Unique identifier (e.g., "it_admin")
    name: str         # Display name (e.g., "IT Admin")
    title: str        # Role title (e.g., "Enterprise Administrator")
    color: str        # Rich library color (e.g., "blue")
    emoji: str        # Visual identification
    steps: list[int]  # Journey steps this persona participates in
```

### PERSONAS Dictionary (5 entries)

| ID | Name | Title | Color | Steps |
|----|------|-------|-------|-------|
| `it_admin` | IT Admin | Enterprise Administrator | blue | [1] |
| `sarah` | Sarah | Sales Development Representative | green | [2, 3, 4, 10] |
| `vendor` | AI Agent Vendor | Third-Party AI Platform Provider | yellow | [4, 5, 6, 9, 10] |
| `agent` | SDR-Assistant | AI Agent (running on vendor infrastructure) | cyan | [5, 6, 7, 8, 9] |
| `security` | Security Officer | Enterprise Security & Compliance | red | [9, 10] |

### Helper Functions

| Function | Signature | Purpose |
|----------|-----------|---------|
| `get_persona` | `(persona_id: str) -> Persona` | Get persona by ID |
| `get_personas_for_step` | `(step: int) -> list[Persona]` | Get all personas for a step |
| `get_primary_persona_for_step` | `(step: int) -> Persona` | Get primary persona for a step |

### File Location

| Artifact | Path |
|----------|------|
| Implementation | `demos/interactive/personas.py` |
| Unit tests | `tests/demos/test_personas.py` (optional) |

---

## Acceptance Criteria

### Functional Criteria
- [ ] `Persona` dataclass has all 6 fields: id, name, title, color, emoji, steps
- [ ] `PERSONAS` dictionary contains exactly 5 personas
- [ ] All persona IDs match their dictionary keys
- [ ] Each persona has correct step assignments per mapping table
- [ ] `get_persona("sarah")` returns Sarah persona
- [ ] `get_personas_for_step(4)` returns [Sarah, Vendor]
- [ ] `get_primary_persona_for_step(5)` returns Agent

### Contract Verification (REQUIRED)
- [ ] Implementation matches [A1-spec.md](../specs/A1-spec.md) exactly
- [ ] All persona fields match spec values
- [ ] Step assignments match spec mapping table

### Technical Criteria
- [ ] Type hints on all public functions
- [ ] Docstrings on class and functions
- [ ] No external dependencies (only `dataclasses` from stdlib)
- [ ] No linting errors: `ruff check demos/interactive/personas.py`

---

## Files to Modify/Create

### Files to Create
- `demos/interactive/__init__.py` - Empty package init (if not exists)
- `demos/interactive/personas.py` - Persona dataclass and PERSONAS dict

### Tests to Add (Optional)
- `tests/demos/test_personas.py` - Unit tests for helper functions

---

## Post-Conditions

### Code Complete

- [ ] All acceptance criteria met
- [ ] File created at correct path: `demos/interactive/personas.py`
- [ ] Linting passes: `ruff check demos/interactive/`
- [ ] Contract verified against spec

### Verification Command

```bash
# Verify implementation exists
ls demos/interactive/personas.py

# Quick import test
python -c "from demos.interactive.personas import PERSONAS, get_persona; print(get_persona('sarah'))"
```

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| A2 | Code dependency satisfied | Can implement DemoContext with persona references |
| A3 | Code dependency satisfied | Can create package __init__.py |
| B1 | Code dependency satisfied | Can implement PromptUI with persona colors |
| B2 | Code dependency satisfied | Can implement RoleSwitcher |
| D1 | Code dependency satisfied | Can implement step handlers |

---

## References

- Design Doc: [Interactive Demo Plan](../../../../.cursor/plans/interactive_demo_plan_7ee6283a.plan.md)
- Specification: [A1-spec.md](../specs/A1-spec.md)
- Related Specs: [A2-spec.md](../specs/A2-spec.md) (uses Persona)
- Reference: `demos/demo_sarah_journey_e2e.py` (existing non-interactive demo)

---

## Notes

- This is a foundation task - keep it simple and focused
- Rich library colors: blue, green, yellow, cyan, red, magenta, white
- Emojis should render correctly in most terminals

---

## Execution Log

<!-- Updated during task execution -->

### Progress Updates

| Date | Update |
|------|--------|
| - | Task ticket created |

### Blockers Encountered

| Date | Blocker | Resolution |
|------|---------|------------|
| - | - | - |
