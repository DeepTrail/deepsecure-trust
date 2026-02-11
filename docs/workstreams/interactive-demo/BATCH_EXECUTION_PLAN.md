# Batch Execution Plan: Interactive Demo

> **Generated from:** [interactive-demo-breakdown.md](../../interactive-demo-breakdown.md)
>
> **Design Doc:** [interactive_demo_plan_7ee6283a.plan.md](../../../.cursor/plans/interactive_demo_plan_7ee6283a.plan.md)
>
> **Last Updated:** February 2026

---

## Quick Reference

| Batch | Total Tasks | Waves | Fully Parallel? | Worktree |
|-------|-------------|-------|-----------------|----------|
| 1 | 3 | 1 | ✅ Yes | deepsecure-mvp |
| 2 | 2 | 1 | ✅ Yes | deepsecure-mvp |
| 3 | 2 | 2 | ❌ No (B2→D1) | deepsecure-mvp |
| 4 | 2 | 2 | ❌ No (E1→F1) | deepsecure-mvp |

---

## Worktree Reference

| Worktree | Path | Branch | Workstreams |
|----------|------|--------|-------------|
| **deepsecure-mvp** | `/Users/imaxxs/repositories/deepsecure-mvp` | `feature/interactive-demo` | A (all tasks) |

**Note:** Single worktree - all tasks run in the main repo since all files are in `demos/`.

---

## Batch 1: Foundation (3 tasks)

### Dependencies

| Task | Description | Dependencies | Files |
|------|-------------|--------------|-------|
| A1 | Define Persona dataclass and 5 personas | None | `demos/interactive/personas.py` |
| A2 | Implement DemoContext state manager | None | `demos/interactive/context.py` |
| C1 | Implement API display client | None | `demos/interactive/api_client.py` |

### Wave Analysis

**Wave 1: All 3 tasks parallel** (no internal dependencies)

| Wave | Tasks |
|------|-------|
| **1** | A1, A2, C1 |

### Visual Dependency Graph

```
                    deepsecure-mvp (main repo)
─────────────────────────────────────────────────────────
                                                         
Wave 1:        A1         A2         C1                  
           (personas)  (context)  (api_client)           
               │          │          │                   
               └────┬─────┴──────────┘                   
                    │                                    
            [Batch 1 Complete]                           
                    │                                    
                    ▼                                    
                Batch 2                                  
```

### Execution Strategy

All 3 tasks can run in sequence (single terminal) or parallel (multiple Claude windows). Since they're independent foundation modules, order doesn't matter.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH 1 - WAVE 1 (All Parallel - Foundation)
# ═══════════════════════════════════════════════════════════════

# --- Setup (one-time) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout -b feature/interactive-demo dev  # if not already created
mkdir -p demos/interactive

# --- Create Task Specs (in Plan mode) ---
/create-task-spec 1 interactive-demo

# --- Create Task Tickets (after specs approved) ---
/create-task-ticket A1 interactive-demo
/create-task-ticket A2 interactive-demo
/create-task-ticket C1 interactive-demo

# --- Execute Tasks (can run sequentially or parallel) ---
# Note: /complete-task runs automatically after /execute-task
/execute-task A1 interactive-demo
/execute-task A2 interactive-demo
/execute-task C1 interactive-demo
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 100% (all 3 tasks parallel) |
| **Waves** | 1 |
| **Bottleneck** | None |
| **Merge Point** | None |
| **Unblocks** | Batch 2 (A3, B1) |

---

## Batch 2: UI Components (2 tasks)

### Dependencies

| Task | Description | Dependencies | Files |
|------|-------------|--------------|-------|
| A3 | Create package __init__.py | A1 ✅, A2 ✅ | `demos/interactive/__init__.py` |
| B1 | Implement PromptUI class | A1 ✅, A2 ✅ | `demos/interactive/prompts.py` |

### Wave Analysis

**Wave 1: Both tasks parallel** (all dependencies from Batch 1 are complete)

| Wave | Tasks |
|------|-------|
| **1** | A3, B1 |

### Visual Dependency Graph

```
                    deepsecure-mvp (main repo)
─────────────────────────────────────────────────────────
                                                         
Wave 1:            A3              B1                    
              (__init__)       (prompts)                 
                   │               │                     
                   └───────┬───────┘                     
                           │                             
                   [Batch 2 Complete]                    
                           │                             
                           ▼                             
                       Batch 3                           
```

### Execution Strategy

Both tasks can run in parallel. A3 is small (exports only), B1 is medium (rich/questionary UI).

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH 2 - WAVE 1 (All Parallel - UI Components)
# ═══════════════════════════════════════════════════════════════

cd /Users/imaxxs/repositories/deepsecure-mvp

# --- Create Task Specs (in Plan mode) ---
/create-task-spec 2 interactive-demo

# --- Create Task Tickets (after specs approved) ---
/create-task-ticket A3 interactive-demo
/create-task-ticket B1 interactive-demo

# --- Execute Tasks ---
# Note: /complete-task runs automatically after /execute-task
/execute-task A3 interactive-demo
/execute-task B1 interactive-demo
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 100% (both tasks parallel) |
| **Waves** | 1 |
| **Bottleneck** | None |
| **Merge Point** | None |
| **Unblocks** | Batch 3 (B2, D1) |

---

## Batch 3: Role Switching & Handlers (2 tasks) ⚠️ SEQUENTIAL

### Dependencies

| Task | Description | Dependencies | Files |
|------|-------------|--------------|-------|
| B2 | Implement RoleSwitcher | A1 ✅, B1 ✅ | `demos/interactive/role_switcher.py` |
| D1 | Implement all 10 step handlers | A1 ✅, A2 ✅, B1 ✅, **B2**, C1 ✅ | `demos/interactive/step_handlers.py` |

### Wave Analysis

**D1 depends on B2 (within this batch)** → Creates sequential dependency

| Wave | Tasks |
|------|-------|
| **1** | B2 |
| **2** | D1 |

### Visual Dependency Graph

```
                    deepsecure-mvp (main repo)
─────────────────────────────────────────────────────────
                                                         
Wave 1:                 B2                               
                   (role_switcher)                       
                        │                                
                        ▼                                
Wave 2:                 D1                               
                  (step_handlers)                        
                        │                                
                [Batch 3 Complete]                       
                        │                                
                        ▼                                
                    Batch 4                              
```

### Execution Strategy

**Sequential execution required.** B2 must complete before D1 starts because step handlers need the RoleSwitcher for multi-persona steps.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH 3 - MULTI-WAVE EXECUTION (Sequential)
# ═══════════════════════════════════════════════════════════════

cd /Users/imaxxs/repositories/deepsecure-mvp

# --- Create Task Specs (in Plan mode) ---
/create-task-spec 3 interactive-demo

# --- Create Task Tickets (after specs approved) ---
/create-task-ticket B2 interactive-demo
/create-task-ticket D1 interactive-demo

# ───────────────────────────────────────────────────────────────
# WAVE 1: B2 (RoleSwitcher)
# ───────────────────────────────────────────────────────────────
# Note: /complete-task runs automatically after /execute-task

/execute-task B2 interactive-demo

# ⏸️ WAIT: B2 must complete before Wave 2

# ───────────────────────────────────────────────────────────────
# WAVE 2: D1 (Step Handlers - LARGEST TASK)
# ───────────────────────────────────────────────────────────────

/execute-task D1 interactive-demo
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 0% (strictly sequential) |
| **Waves** | 2 |
| **Bottleneck** | D1 (depends on B2, largest task in project - L complexity) |
| **Merge Point** | None |
| **Unblocks** | Batch 4 (E1, F1) |

---

## Batch 4: Integration & Docs (2 tasks) ⚠️ SEQUENTIAL

### Dependencies

| Task | Description | Dependencies | Files |
|------|-------------|--------------|-------|
| E1 | Create main interactive entry point | D1 ✅ | `demos/demo_sarah_journey_interactive.py` |
| F1 | Update README with interactive demo docs | **E1** | `demos/README.md` |

### Wave Analysis

**F1 depends on E1 (within this batch)** → Creates sequential dependency

| Wave | Tasks |
|------|-------|
| **1** | E1 |
| **2** | F1 |

### Visual Dependency Graph

```
                    deepsecure-mvp (main repo)
─────────────────────────────────────────────────────────
                                                         
Wave 1:                 E1                               
                    (main.py)                            
                        │                                
                        ▼                                
Wave 2:                 F1                               
                    (README)                             
                        │                                
                [Batch 4 Complete]                       
                        │                                
                        ▼                                
              ✅ INTERACTIVE DEMO COMPLETE!              
```

### Execution Strategy

**Sequential execution required.** README documentation should reference the completed entry point.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH 4 - FINAL BATCH (Sequential)
# ═══════════════════════════════════════════════════════════════

cd /Users/imaxxs/repositories/deepsecure-mvp

# --- Create Task Specs (in Plan mode) ---
# Note: F1 (README) may skip spec - documentation only
/create-task-spec 4 interactive-demo

# --- Create Task Tickets (after specs approved) ---
/create-task-ticket E1 interactive-demo
/create-task-ticket F1 interactive-demo

# ───────────────────────────────────────────────────────────────
# WAVE 1: E1 (Main Entry Point)
# ───────────────────────────────────────────────────────────────
# Note: /complete-task runs automatically after /execute-task

/execute-task E1 interactive-demo

# ⏸️ WAIT: E1 must complete before Wave 2

# ───────────────────────────────────────────────────────────────
# WAVE 2: F1 (Documentation)
# ───────────────────────────────────────────────────────────────

/execute-task F1 interactive-demo

# ───────────────────────────────────────────────────────────────
# FINAL: Verification
# ───────────────────────────────────────────────────────────────

# Test the interactive demo
cd demos
python demo_sarah_journey_interactive.py --help
python demo_sarah_journey_interactive.py --auto  # Quick run

# 🎉 INTERACTIVE DEMO COMPLETE!
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 0% (strictly sequential) |
| **Waves** | 2 |
| **Bottleneck** | E1 (orchestrates all components) |
| **Completion** | ✅ Interactive Demo Complete! |

---

## Overall Execution Summary

### Batch Parallelism Overview

| Batch | Tasks | Waves | Parallel % | Description |
|-------|-------|-------|------------|-------------|
| 1 | 3 | 1 | 100% | Foundation (personas, context, api_client) |
| 2 | 2 | 1 | 100% | UI Components (__init__, prompts) |
| 3 | 2 | 2 | 0% | Core Logic (role_switcher → step_handlers) |
| 4 | 2 | 2 | 0% | Integration (main → README) |

### Merge Points Summary

| Point | After Batch | Converging | Actions Required |
|-------|-------------|------------|------------------|
| _None_ | - | - | Single worktree, no merge points needed |

### Total Commands Needed

| Command Type | Count |
|--------------|-------|
| `/create-task-spec` | 4 (one per batch) |
| `/create-task-ticket` | 9 (one per task) |
| `/execute-task` | 9 (one per task) |
| `/complete-task` | 9 (auto after execute) |
| **Total** | 31 commands |

### Critical Path

```
A1 → B1 → B2 → D1 → E1 → F1
│                          │
└────── 6 tasks on path ───┘
```

**Note:** A2 and C1 are off the critical path (can complete any time before D1).

### Task Distribution by File

| File | Tasks | Complexity |
|------|-------|------------|
| `demos/interactive/personas.py` | A1 | S |
| `demos/interactive/context.py` | A2 | S |
| `demos/interactive/__init__.py` | A3 | S |
| `demos/interactive/prompts.py` | B1 | M |
| `demos/interactive/role_switcher.py` | B2 | M |
| `demos/interactive/api_client.py` | C1 | M |
| `demos/interactive/step_handlers.py` | D1 | **L** (largest) |
| `demos/demo_sarah_journey_interactive.py` | E1 | M |
| `demos/README.md` | F1 | S |

### Complexity Distribution

```
Small (S):  4 tasks (A1, A2, A3, F1)
Medium (M): 4 tasks (B1, B2, C1, E1)
Large (L):  1 task  (D1 - step handlers)
```

---

## Quick Command Reference

### Full Execution Script (Copy-Paste Ready)

```bash
# ═══════════════════════════════════════════════════════════════
# INTERACTIVE DEMO - FULL EXECUTION
# ═══════════════════════════════════════════════════════════════

cd /Users/imaxxs/repositories/deepsecure-mvp

# Setup
git checkout -b feature/interactive-demo dev
mkdir -p demos/interactive

# ─── BATCH 1: Foundation ───────────────────────────────────────
/create-task-spec 1 interactive-demo  # Create specs first
/create-task-ticket A1 interactive-demo
/create-task-ticket A2 interactive-demo
/create-task-ticket C1 interactive-demo

# Note: /complete-task runs automatically after /execute-task
/execute-task A1 interactive-demo
/execute-task A2 interactive-demo
/execute-task C1 interactive-demo

# ─── BATCH 2: UI Components ────────────────────────────────────
/create-task-spec 2 interactive-demo  # Create specs first
/create-task-ticket A3 interactive-demo
/create-task-ticket B1 interactive-demo

/execute-task A3 interactive-demo
/execute-task B1 interactive-demo

# ─── BATCH 3: Core Logic (SEQUENTIAL) ──────────────────────────
/create-task-spec 3 interactive-demo  # Create specs first
/create-task-ticket B2 interactive-demo
/create-task-ticket D1 interactive-demo

/execute-task B2 interactive-demo
# ⏸️ B2 must complete before D1
/execute-task D1 interactive-demo

# ─── BATCH 4: Integration (SEQUENTIAL) ─────────────────────────
/create-task-spec 4 interactive-demo  # Create specs first (F1 may skip)
/create-task-ticket E1 interactive-demo
/create-task-ticket F1 interactive-demo

/execute-task E1 interactive-demo
# ⏸️ E1 must complete before F1
/execute-task F1 interactive-demo

# ─── VERIFICATION ──────────────────────────────────────────────
cd demos
python demo_sarah_journey_interactive.py --help
python demo_sarah_journey_interactive.py --auto

# 🎉 DONE!
```

### One-Liner to Create All Tickets for a Batch

```bash
# Batch 1
for t in A1 A2 C1; do echo "/create-task-ticket $t interactive-demo"; done

# Batch 2
for t in A3 B1; do echo "/create-task-ticket $t interactive-demo"; done

# Batch 3
for t in B2 D1; do echo "/create-task-ticket $t interactive-demo"; done

# Batch 4
for t in E1 F1; do echo "/create-task-ticket $t interactive-demo"; done
```

---

*Generated by `/create-batch-execution-plan` command*
