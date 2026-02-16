# Workstream Breakdown for: Interactive Sarah's Journey Demo

> **Generated from:** `.cursor/plans/interactive_demo_plan_7ee6283a.plan.md`
>
> **Generated on:** February 2026
>
> **Command:** `/breakdown-design`

---

## Summary

- **Total Workstreams:** 1 (single feature in `demos/`)
- **Total Tasks:** 9
- **Total Batches:** 4
- **Critical Path:** A1 → B1 → B2 → D1 → E1 → F1
- **Merge Points:** 0 (single worktree, no cross-service)
- **Estimated Total Effort:** 4 S, 4 M, 1 L

---

## Parallelization Decision

**Recommended Setup:** 1 worktree (main repo only)

| Worktree | Service | Workstreams | Branch Pattern |
|----------|---------|-------------|----------------|
| `deepsecure-mvp` | demos/ (root level) | A (all tasks) | `feature/interactive-demo` |

**Rationale:**
- All files are in `demos/` at repo root
- No changes to `deeptrail-control/` or `deeptrail-gateway/`
- No cross-service dependencies
- Single worktree is sufficient

**Tradeoff:**

| Option | Decision | Why |
|--------|----------|-----|
| Single Worktree | ✅ Chosen | All files in one location, no parallelization needed |
| Git Worktrees | ❌ | Overkill - no service boundaries to parallelize |
| Multiple Clones | ❌ | Unnecessary complexity |

**Setup Commands:**
```bash
# From main repo - create feature branch
git checkout -b feature/interactive-demo dev
```

---

## Workstream A: Interactive Demo Module (Single Workstream)

**Location:** `demos/` (repo root)  
**Batches:** 1, 2, 3, 4  
**Depends On:** Existing `demos/demo_sarah_journey_e2e.py`

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| **A1** | Define Persona dataclass and 5 personas | None | S | `demos/interactive/personas.py` (create) | Persona dataclass with id, name, title, color, steps; PERSONAS dict with 5 entries |
| **A2** | Implement DemoContext state manager | None | S | `demos/interactive/context.py` (create) | DemoContext dataclass with all step state fields; get_summary_for_persona() method |
| **A3** | Create package __init__.py | A1, A2 | S | `demos/interactive/__init__.py` (create) | Exports Persona, PERSONAS, DemoContext, PromptUI, RoleSwitcher, STEP_HANDLERS |
| **B1** | Implement PromptUI class | A1, A2 | M | `demos/interactive/prompts.py` (create) | PromptUI with role_banner, multi_select, confirm, select, show_json, show_insight methods using rich/questionary |
| **B2** | Implement RoleSwitcher | A1, B1 | M | `demos/interactive/role_switcher.py` (create) | switch_to_persona(), show_context_summary(), wait_for_user() with animated transitions |
| **C1** | Implement API display client | None | M | `demos/interactive/api_client.py` (create) | APIClient wrapping httpx with show_request/show_response display methods |
| **D1** | Implement all 10 step handlers | A1, A2, B1, B2, C1 | L | `demos/interactive/step_handlers.py` (create) | STEP_HANDLERS dict with async handlers for all 10 steps; multi-persona support for steps 4, 5-6, 9, 10 |
| **E1** | Create main interactive entry point | D1 | M | `demos/demo_sarah_journey_interactive.py` (create) | CLI with --persona, --auto, --start-step args; orchestrates all step handlers |
| **F1** | Update README with interactive demo docs | E1 | S | `demos/README.md` (modify) | Document interactive demo usage, persona descriptions, CLI options |

---

## Batch Execution Model

| Batch | Tasks (Parallel) | Depends On | Blocking For |
|-------|------------------|------------|--------------|
| **1** | A1, A2, C1 | None | Batch 2 |
| **2** | A3, B1 | Batch 1 | Batch 3 |
| **3** | B2, D1 | Batch 2 | Batch 4 |
| **4** | E1, F1 | Batch 3 | Done |

---

## Critical Path Analysis

```
Primary:   A1 → B1 → B2 → D1 → E1 → F1
           (personas → prompts → switcher → handlers → main → docs)

Parallel Track 1: A2 → (joins at D1)
Parallel Track 2: C1 → (joins at D1)
```

The critical path runs through the UI components (prompts, role_switcher) because the step handlers depend on all of them.

---

## Dependency Graph

```
BATCH 1 (Parallel)           BATCH 2              BATCH 3              BATCH 4
─────────────────           ─────────            ─────────            ─────────

   ┌─────────┐               ┌─────────┐          ┌─────────┐          ┌─────────┐
   │   A1    │──────────────▶│   B1    │─────────▶│   B2    │          │   E1    │
   │personas │               │ prompts │          │switcher │          │  main   │
   └─────────┘               └─────────┘          └────┬────┘          └────┬────┘
        │                         │                    │                    │
        │                         │                    │                    ▼
        │                    ┌────▼────┐          ┌────▼────┐          ┌─────────┐
        │                    │   A3    │          │   D1    │─────────▶│   F1    │
        │                    │ __init__|          │handlers │          │ README  │
        │                    └─────────┘          └─────────┘          └─────────┘
        │                                              ▲
   ┌────▼────┐                                         │
   │   A2    │─────────────────────────────────────────┤
   │ context │                                         │
   └─────────┘                                         │
                                                       │
   ┌─────────┐                                         │
   │   C1    │─────────────────────────────────────────┘
   │api_client│
   └─────────┘
```

---

## File Organization Plan

| Type | Location | Files | Notes |
|------|----------|-------|-------|
| Interactive Demo Module | `demos/interactive/` | `*.py` | New package |
| Main Entry Point | `demos/` | `demo_sarah_journey_interactive.py` | New file |
| Documentation | `demos/` | `README.md` | Modify existing |

**Directory Structure:**
```
demos/
├── demo_sarah_journey_e2e.py          # Existing (keep as-is)
├── demo_sarah_journey_interactive.py  # NEW: Main entry point
├── README.md                          # MODIFY: Add interactive docs
└── interactive/                       # NEW: Package
    ├── __init__.py                    # Package exports
    ├── personas.py                    # Persona definitions
    ├── context.py                     # DemoContext state
    ├── prompts.py                     # PromptUI (rich/questionary)
    ├── role_switcher.py               # Role switching logic
    ├── step_handlers.py               # All 10 step handlers
    └── api_client.py                  # HTTP client with display
```

---

## Technical Requirements Checklist

| Requirement | Pattern | Applies To |
|-------------|---------|------------|
| External dependencies | `pip install rich questionary` | All interactive UI |
| Async support | `async def` handlers | step_handlers.py, api_client.py |
| CLI args | `argparse` | demo_sarah_journey_interactive.py |
| HTTP client | `httpx.AsyncClient` | api_client.py |

---

## Demo/Milestone → Task Matrix

| Demo Feature | Description | Validating Tasks |
|--------------|-------------|------------------|
| Persona Switching | Switch between 5 roles during demo | A1, B2, D1 |
| Interactive Prompts | Multi-select, confirm, input | B1, D1 |
| Split View | Show vendor perspective after Sarah acts | D1 (step 4, 5-6, 9) |
| Round Robin | All 3 personas review audit | D1 (step 10) |
| API Visualization | Show request/response JSON | C1, D1 |
| CLI Options | --persona, --auto, --start-step | E1 |

---

## User Journey → Task Matrix

| Step | Action | Implementing Tasks |
|------|--------|-------------------|
| 1 | IT Admin configures enterprise | A1, D1 |
| 2-3 | Sarah authenticates, connects services | A1, D1 |
| 4 | Sarah delegates + Vendor receives | A1, B2, D1 |
| 5-6 | Agent authenticates + Vendor observes | A1, B2, D1 |
| 7-8 | Agent discovers and uses tools | A1, D1 |
| 9 | Agent denied + Security reviews | A1, B2, D1 |
| 10 | All personas review audit | A1, B2, D1 |

---

## Execution Commands

### Batch 1 (Parallel - No Dependencies)
```bash
# All can run in parallel
/create-task-ticket A1 interactive-demo
/create-task-ticket A2 interactive-demo
/create-task-ticket C1 interactive-demo

# Execute
/execute-task A1 interactive-demo
/execute-task A2 interactive-demo
/execute-task C1 interactive-demo

# Complete
/complete-task A1 interactive-demo
/complete-task A2 interactive-demo
/complete-task C1 interactive-demo
```

### Batch 2 (Depends on Batch 1)
```bash
/create-task-ticket A3 interactive-demo
/create-task-ticket B1 interactive-demo

/execute-task A3 interactive-demo
/execute-task B1 interactive-demo

/complete-task A3 interactive-demo
/complete-task B1 interactive-demo
```

### Batch 3 (Depends on Batch 2)
```bash
/create-task-ticket B2 interactive-demo
/create-task-ticket D1 interactive-demo

/execute-task B2 interactive-demo
/execute-task D1 interactive-demo

/complete-task B2 interactive-demo
/complete-task D1 interactive-demo
```

### Batch 4 (Depends on Batch 3)
```bash
/create-task-ticket E1 interactive-demo
/create-task-ticket F1 interactive-demo

/execute-task E1 interactive-demo
/execute-task F1 interactive-demo

/complete-task E1 interactive-demo
/complete-task F1 interactive-demo
```

---

## Next Steps

1. **Create workstream structure:** `/create-workstream interactive-demo`
2. **Create task tickets for Batch 1:** `/create-task-ticket A1 interactive-demo`
3. **Begin execution**
