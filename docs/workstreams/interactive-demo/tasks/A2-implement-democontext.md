# Task: A2 Implement DemoContext State Manager

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [Interactive Demo Plan](../../../../.cursor/plans/interactive_demo_plan_7ee6283a.plan.md) |
| **Specification** | [A2-spec.md](../specs/A2-spec.md) |
| **Workstream** | Interactive Demo |
| **Code Dependencies** | None (can use A1's Persona optionally) |
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

| Task | What We Need | Status |
|------|--------------|--------|
| A1 | `Persona` dataclass (optional, for validation) | ⬜ Parallel |

> **Note:** A2 can start in parallel with A1. The `Persona` import is optional for validation in `get_summary_for_persona`.

### Runtime Dependencies (must be deployed for integration testing)

None - this is a pure Python dataclass with no external service requirements.

### Development Mode

- [x] **Fallback behavior**: N/A - no runtime dependencies
- [x] **Local testing**: Unit tests can run standalone
- [x] **Integration testing**: N/A

---

## Pre-Conditions

Before starting this task, ensure:

- [x] No blocking code dependencies - can start immediately
- [x] `demos/interactive/` directory exists (created by A1 or created here)

---

## Task Description

Implement the `DemoContext` dataclass that manages all state across the 10 journey steps. This is the central state container that tracks authentication tokens, connected services, delegated permissions, tool discovery results, and audit events.

### Context

The interactive demo accumulates state as users progress through Sarah's Journey:
- **Step 1**: Organization configuration (IT Admin)
- **Steps 2-4**: User auth, OAuth, delegation (Sarah)
- **Steps 5-6**: Agent auth, MCP connection (Agent)
- **Steps 7-8**: Tool discovery and execution (Agent)
- **Step 9**: Permission denial demonstration (Agent/Security)
- **Step 10**: Audit review (All personas)

Each persona sees a different "view" of the context via `get_summary_for_persona()`.

### Technical Notes

- Use `dataclass` with `field(default_factory=list)` for mutable defaults
- Include step-to-persona mapping for automatic persona switching
- All fields should be typed with `| None` for optional fields
- Methods should update `current_persona` when step changes

---

## Specification (IMMUTABLE)

> **Source:** [A2-spec.md](../specs/A2-spec.md)

### Interface Contract

```python
@dataclass
class DemoContext:
    # Current state
    current_step: int = 0
    current_persona: str = "sarah"
    
    # Step 1-10 fields (16 total)
    org_id: str | None = None
    org_name: str | None = None
    user_token: str | None = None
    user_email: str | None = None
    connected_services: list[str] = field(default_factory=list)
    delegation_id: str | None = None
    delegated_permissions: list[str] = field(default_factory=list)
    agent_id: str | None = None
    agent_jwt: str | None = None
    mcp_session_id: str | None = None
    discovered_tools: list[dict[str, Any]] = field(default_factory=list)
    tool_call_results: list[dict[str, Any]] = field(default_factory=list)
    denied_tool: str | None = None
    denial_reason: str | None = None
    audit_events: list[dict[str, Any]] = field(default_factory=list)
    
    # Methods
    def get_summary_for_persona(self, persona_id: str) -> dict[str, Any]: ...
    def advance_step(self) -> None: ...
    def go_to_step(self, step: int) -> None: ...
    def to_dict(self) -> dict[str, Any]: ...
    def reset(self) -> None: ...
```

### Step-to-Persona Mapping

| Step | Primary Persona |
|------|-----------------|
| 1 | it_admin |
| 2-4 | sarah |
| 5-9 | agent |
| 10 | sarah |

### File Location

| Artifact | Path |
|----------|------|
| Implementation | `demos/interactive/context.py` |
| Unit tests | `tests/demos/test_context.py` (optional) |

---

## Acceptance Criteria

### Functional Criteria
- [ ] `DemoContext` dataclass has all 16 state fields
- [ ] All fields have correct default values (None, 0, or empty list)
- [ ] `get_summary_for_persona("sarah")` returns Sarah-relevant fields
- [ ] `get_summary_for_persona("it_admin")` returns IT Admin-relevant fields
- [ ] `get_summary_for_persona("vendor")` returns Vendor-relevant fields
- [ ] `get_summary_for_persona("agent")` returns Agent-relevant fields
- [ ] `get_summary_for_persona("security")` returns Security-relevant fields
- [ ] `advance_step()` increments step and updates persona correctly
- [ ] `go_to_step(5)` jumps to step 5 and sets persona to "agent"
- [ ] `to_dict()` returns complete serialization of all fields
- [ ] `reset()` clears all fields to initial defaults

### Contract Verification (REQUIRED)
- [ ] Implementation matches [A2-spec.md](../specs/A2-spec.md) exactly
- [ ] All field names and types match spec
- [ ] Method signatures match spec

### Technical Criteria
- [ ] Type hints on all methods
- [ ] Docstrings on class and all public methods
- [ ] No external dependencies (only stdlib)
- [ ] No linting errors: `ruff check demos/interactive/context.py`

---

## Files to Modify/Create

### Files to Create
- `demos/interactive/context.py` - DemoContext dataclass

### Tests to Add (Optional)
- `tests/demos/test_context.py` - Unit tests for methods

---

## Post-Conditions

### Code Complete

- [ ] All acceptance criteria met
- [ ] File created at correct path: `demos/interactive/context.py`
- [ ] Linting passes: `ruff check demos/interactive/`
- [ ] Contract verified against spec

### Verification Command

```bash
# Verify implementation exists
ls demos/interactive/context.py

# Quick import test
python -c "from demos.interactive.context import DemoContext; ctx = DemoContext(); ctx.advance_step(); print(f'Step: {ctx.current_step}, Persona: {ctx.current_persona}')"
```

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| A3 | Code dependency satisfied | Can create package __init__.py |
| B1 | Code dependency satisfied | Can implement PromptUI with context access |
| B2 | Code dependency satisfied | Can implement RoleSwitcher |
| D1 | Code dependency satisfied | Can implement step handlers |
| E1 | Code dependency satisfied | Can create main entry point |

---

## References

- Design Doc: [Interactive Demo Plan](../../../../.cursor/plans/interactive_demo_plan_7ee6283a.plan.md)
- Specification: [A2-spec.md](../specs/A2-spec.md)
- Related Specs: [A1-spec.md](../specs/A1-spec.md) (Persona dataclass)
- Reference: `demos/demo_sarah_journey_e2e.py` (existing demo state handling)

---

## Notes

- The `get_summary_for_persona` method is key for the split-view feature
- Consider using `dataclasses.asdict()` for `to_dict()` implementation
- The `STEP_PRIMARY_PERSONA` mapping can be a module-level constant

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
