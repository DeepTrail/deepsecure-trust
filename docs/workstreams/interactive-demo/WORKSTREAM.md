# Workstream: Interactive Sarah's Journey Demo

> **Execution Status:** [STATUS.md](./STATUS.md) ← Live tracking of all phases, batches, and tasks
>
> **Batch Execution Plan:** [BATCH_EXECUTION_PLAN.md](./BATCH_EXECUTION_PLAN.md) ← Wave analysis and commands
>
> **Breakdown Doc:** [interactive-demo-breakdown.md](../../interactive-demo-breakdown.md)

---

## Overview

| Field | Value |
|-------|-------|
| **Design Doc** | [Interactive Demo Plan](../../../.cursor/plans/interactive_demo_plan_7ee6283a.plan.md) |
| **Breakdown Doc** | [interactive-demo-breakdown.md](../../interactive-demo-breakdown.md) |
| **Status** | `in_progress` |
| **Owner** | - |
| **Created** | February 2026 |
| **Target Completion** | TBD |

---

## Description

Transform the existing `demos/demo_sarah_journey_e2e.py` into an interactive CLI experience with role-switching between five personas (IT Admin, Sarah, AI Agent Vendor, SDR-Assistant Agent, Security Officer). Users make choices at each step and see the journey from different stakeholder perspectives.

Key features:
- **Persona switching**: Switch between 5 roles during the demo
- **Interactive prompts**: Multi-select permissions, confirm actions, choose tools
- **Split view**: Show vendor perspective after Sarah acts (steps 4, 5-6, 9)
- **Round-robin audit**: All personas review from their perspective (step 10)
- **CLI options**: --persona, --auto, --start-step

---

## Parallelization Strategy

### Worktree Assignment

| Worktree | Branch | Services | Workstreams | This Workstream? |
|----------|--------|----------|-------------|------------------|
| `deepsecure-mvp` | `feature/interactive-demo` | demos/ (root) | A (all tasks) | ✅ |

### Decision Rationale

**Setup:** 1 worktree (main repo only)

**Why this decision:**
- All files are in `demos/` at repo root
- No changes to `deeptrail-control/` or `deeptrail-gateway/`
- No cross-service dependencies
- Single worktree is sufficient

**Alternatives Considered:**
- Multiple worktrees - Rejected: no service boundaries to parallelize
- Multiple clones - Rejected: unnecessary complexity

---

## Workstream Dependencies

### Can Run In Parallel With
- N/A (single workstream)

### Blocked By
- None (existing `demo_sarah_journey_e2e.py` already working)

### Blocks
- N/A (self-contained feature)

---

## Batch Execution Model

| Batch | Tasks | Status | Depends On | Blocking For |
|-------|-------|--------|------------|--------------|
| **1** | A1, A2, C1 | ✅ Complete | None | Batch 2 |
| **2** | A3, B1 | ✅ Complete | Batch 1 ✅ | Batch 3 |
| **3** | B2, D1 | ⏳ Ready | Batch 2 ✅ | Batch 4 |
| **4** | E1, F1 | ⏸️ Pending | Batch 3 | Done |

---

## All Tasks

| Task ID | Task Name | Status | Dependencies | Batch | Complexity |
|---------|-----------|--------|--------------|-------|------------|
| A1 | Define Persona dataclass and 5 personas | ✅ `complete` | None | 1 | S |
| A2 | Implement DemoContext state manager | ✅ `complete` | None | 1 | S |
| C1 | Implement API display client | ✅ `complete` | None | 1 | M |
| A3 | Create package __init__.py | ✅ `complete` | A1 ✅, A2 ✅ | 2 | S |
| B1 | Implement PromptUI class | ✅ `complete` | A1 ✅, A2 ✅ | 2 | M |
| B2 | Implement RoleSwitcher | `ready` | A1 ✅, B1 ✅ | 3 | M |
| D1 | Implement all 10 step handlers | `pending` | A1, A2, B1, B2, C1 | 3 | L |
| E1 | Create main interactive entry point | `pending` | D1 | 4 | M |
| F1 | Update README with interactive demo docs | `pending` | E1 | 4 | S |

### Task Dependency Graph

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

## Task Links

### Task Specifications

_Created with `/create-task-spec`_

**Batch 1 Specs:**
- [x] [A1-spec.md](./specs/A1-spec.md) - Persona dataclass and PERSONAS dictionary
- [x] [A2-spec.md](./specs/A2-spec.md) - DemoContext state manager
- [x] [C1-spec.md](./specs/C1-spec.md) - APIClient with display formatting

**Batch 2 Specs:**
- [x] [A3-spec.md](./specs/A3-spec.md) - Package __init__.py exports
- [x] [B1-spec.md](./specs/B1-spec.md) - PromptUI class interface

**Batch 3 Specs:**
- [x] [B2-spec.md](./specs/B2-spec.md) - RoleSwitcher class interface
- [x] [D1-spec.md](./specs/D1-spec.md) - Step handlers registry and functions

**Batch 4 Specs:**
- [x] [E1-spec.md](./specs/E1-spec.md) - Main interactive entry point CLI
- [ ] F1 - N/A (documentation only, no spec needed)

### Task Tickets

- [x] [A1: Define Persona dataclass and 5 personas](./tasks/A1-define-persona-dataclass.md)
- [x] [A2: Implement DemoContext state manager](./tasks/A2-implement-democontext.md)
- [x] [C1: Create APIClient with display formatting](./tasks/C1-create-apiclient.md)
- [x] [A3: Create package __init__.py](./tasks/A3-create-package-init.md)
- [x] [B1: Implement PromptUI class](./tasks/B1-implement-promptui.md)
- [x] [B2: Implement RoleSwitcher](./tasks/B2-implement-roleswitcher.md)
- [ ] D1: Implement all 10 step handlers
- [x] [E1: Create main interactive entry point](./tasks/E1-create-main-entry-point.md)
- [x] [F1: Update README with interactive demo docs](./tasks/F1-update-readme.md)

### Completion Reports
- [x] A1 - Complete (implementation verified, no formal report)
- [x] A2 - Complete (implementation verified, no formal report)
- [x] [C1-completion.md](./reports/C1-completion.md) - APIClient with display formatting
- [x] [A3-completion.md](./reports/A3-completion.md) - Package __init__.py exports
- [x] [B1-completion.md](./reports/B1-completion.md) - PromptUI class

---

## Progress

### Overall Progress: **56%**

```
[███████████░░░░░░░░░] 56% complete (5/9 tasks)
```

| Metric | Value |
|--------|-------|
| **Total Tasks** | 9 |
| **Completed** | 5 (A1, A2, C1, A3, B1) |
| **In Progress** | 0 |
| **Ready** | 1 (B2) |
| **Pending** | 3 |

### Milestone Tracking

| Milestone | Target Date | Status | Notes |
|-----------|-------------|--------|-------|
| All task tickets created | TBD | ⏳ | Batch 1 done |
| Batch 1 complete (core dataclasses) | 2026-02-10 | ✅ | A1, A2, C1 complete |
| Batch 2 complete (UI components) | 2026-02-10 | ✅ | A3, B1 complete |
| Batch 3 complete (handlers) | TBD | ⏸️ | |
| Batch 4 complete (integration) | TBD | ⏸️ | |
| Interactive demo working | TBD | ⏸️ | |

---

## Files Affected

This workstream will create or modify:

### New Files
- `demos/interactive/__init__.py` - Package exports
- `demos/interactive/personas.py` - Persona definitions
- `demos/interactive/context.py` - DemoContext state
- `demos/interactive/prompts.py` - PromptUI (rich/questionary)
- `demos/interactive/role_switcher.py` - Role switching logic
- `demos/interactive/step_handlers.py` - All 10 step handlers
- `demos/interactive/api_client.py` - HTTP client with display
- `demos/demo_sarah_journey_interactive.py` - Main entry point

### Modified Files
- `demos/README.md` - Add interactive demo documentation

### Test Files
- N/A (demo script, not production code)

---

## Technical Requirements

| Requirement | Pattern | Applies To |
|-------------|---------|------------|
| External dependencies | `pip install rich questionary` | All interactive UI |
| Async support | `async def` handlers | step_handlers.py, api_client.py |
| CLI args | `argparse` | demo_sarah_journey_interactive.py |
| HTTP client | `httpx.AsyncClient` | api_client.py |

---

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Backend services not running | Medium | High | Add clear error message if services unavailable |
| Complex step handler logic | Medium | Medium | Use existing e2e test as reference |
| questionary compatibility | Low | Low | Falls back to simple input() if needed |

---

## Notes

- This feature builds on the existing `demos/demo_sarah_journey_e2e.py` which already has working API calls
- The interactive demo is for demonstration purposes, not production
- All API calls should work if backend services are running (`docker compose up`)

---

## History

| Date | Event |
|------|-------|
| Feb 2026 | Workstream created |
| Feb 2026 | Breakdown generated |
| Feb 2026 | Batch 1 specs created (A1, A2, C1) |
| Feb 2026 | Task ticket A1 created |
| Feb 2026 | Task ticket A2 created |
| Feb 2026 | Task ticket C1 created |
| 2026-02-10 | A1 completed - Persona dataclass |
| 2026-02-10 | A2 completed - DemoContext state manager |
| 2026-02-10 | C1 completed - APIClient with display formatting |
| 2026-02-10 | Batch 1 complete - all foundation tasks done |
| 2026-02-11 | Batch 2 specs created (A3, B1) |
| 2026-02-11 | Batch 3 specs created (B2, D1) |
| 2026-02-11 | Batch 4 specs created (E1; F1 skipped - docs only) |
| 2026-02-10 | A3 completed - Package __init__.py with APIClient export |
| 2026-02-10 | B1 completed - PromptUI class with questionary integration |
| 2026-02-10 | Batch 2 complete - all UI components done |
