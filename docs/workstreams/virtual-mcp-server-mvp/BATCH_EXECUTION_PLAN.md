# Batch Execution Plan: Virtual MCP Server MVP

> **Generated from:** [deepsecure-virtual-mcp-server-mvp-breakdown.md](../../deepsecure-virtual-mcp-server-mvp-breakdown.md)
>
> **Design Doc:** [deepsecure-virtual-mcp-server-mvp.md](../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md)
>
> **Last Updated:** February 4, 2026

---

## Quick Reference

| Batch | Total Tasks | Complete | Waves | Status | Worktrees |
|-------|-------------|----------|-------|--------|-----------|
| 1 | 3 | 3 ✅ | 1 | ✅ Complete | control, gateway |
| 2 | 5 | 5 ✅ | 1 | ✅ Complete | control, gateway |
| 3 | 4 | 4 ✅ | 1 | ✅ Complete | control, gateway |
| 4 | 9 | 9 ✅ | 4 | ✅ Complete (MP1!) | control, gateway |
| 5 | 6 | 0 | 2 | ⏳ Ready ← CURRENT | control, gateway |
| 6 | 3 | 0 | 2 | ⏸️ Pending | control, gateway |
| 7 | 3 | 0 | 2 | ⏸️ Pending | control, gateway |
| 8 | 5 | 0 | 2 | ⏸️ Pending | control, gateway |
| 9 | 5 | 0 | 2 | ⏸️ Pending | control, gateway |

---

## Worktree Reference

| Worktree | Path | Branch | Workstreams |
|----------|------|--------|-------------|
| **vmcp-control** | `/Users/imaxxs/repositories/vmcp-control` | `feature/vmcp-control` | A, C (control), E (control) |
| **vmcp-gateway** | `/Users/imaxxs/repositories/vmcp-gateway` | `feature/vmcp-gateway` | B, C (gateway), D, E (gateway) |

---

## Batch 1: Foundation (3 tasks)

### Dependencies

| Task | Description | Dependencies | Worktree |
|------|-------------|--------------|----------|
| A1 | Define User Session data model | None | vmcp-control |
| B1 | Implement MCP JSON-RPC 2.0 parser | None | vmcp-gateway |
| E1 | Define audit event model | None | vmcp-control |

### Wave Analysis

**Wave 1: All 3 tasks parallel** (no internal dependencies)

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | A1, E1 | B1 |

### Visual Dependency Graph

```
CONTROL (vmcp-control)          GATEWAY (vmcp-gateway)
─────────────────────           ─────────────────────
    A1        E1                       B1
    │         │                        │
    └────┬────┘                        │
         │                             │
         └───────────┬─────────────────┘
                     │
              [Batch 1 Complete]
                     │
                     ▼
                 Batch 2
```

### Execution Strategy

All tasks can run in parallel across both worktrees.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH 1 - WAVE 1 (All Parallel)
# ═══════════════════════════════════════════════════════════════

# --- Create Task Tickets (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-ticket WS-A1 virtual-mcp-server-mvp
/create-task-ticket WS-B1 virtual-mcp-server-mvp
/create-task-ticket WS-E1 virtual-mcp-server-mvp

# --- Execute Tasks (parallel in separate terminals) ---

# Terminal 1: vmcp-control
cd /Users/imaxxs/repositories/vmcp-control
/execute-task WS-A1 virtual-mcp-server-mvp
/complete-task WS-A1 virtual-mcp-server-mvp
/execute-task WS-E1 virtual-mcp-server-mvp
/complete-task WS-E1 virtual-mcp-server-mvp

# Terminal 2: vmcp-gateway
cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-B1 virtual-mcp-server-mvp
/complete-task WS-B1 virtual-mcp-server-mvp

# --- Sync Status (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 100% (all 3 tasks parallel) |
| **Waves** | 1 |
| **Bottleneck** | None |
| **Unblocks** | Batch 2 (A2, A3, A5, B2, B4) |

---

## Batch 2: Services & Handlers (5 tasks)

### Dependencies

| Task | Description | Dependencies | Worktree |
|------|-------------|--------------|----------|
| A2 | Implement UserSessionService | A1 ✅ | vmcp-control |
| A3 | Define Connected Services model | A1 ✅ | vmcp-control |
| A5 | Define Delegation Token model | A1 ✅ | vmcp-control |
| B2 | Implement initialize handler | B1 ✅ | vmcp-gateway |
| B4 | Implement namespace prefixer | B1 ✅ | vmcp-gateway |

### Wave Analysis

**Wave 1: All 5 tasks parallel** (all dependencies from Batch 1 are complete)

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | A2, A3, A5 | B2, B4 |

### Visual Dependency Graph

```
CONTROL (vmcp-control)          GATEWAY (vmcp-gateway)
─────────────────────           ─────────────────────
   A2    A3    A5                   B2    B4
   │     │     │                    │     │
   └──┬──┴──┬──┘                    └──┬──┘
      │     │                          │
      └─────┼──────────────────────────┘
            │
     [Batch 2 Complete]
            │
            ▼
        Batch 3
```

### Execution Strategy

All tasks can run in parallel across both worktrees.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH 2 - WAVE 1 (All Parallel)
# ═══════════════════════════════════════════════════════════════

# --- Create Task Tickets (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-ticket WS-A2 virtual-mcp-server-mvp
/create-task-ticket WS-A3 virtual-mcp-server-mvp
/create-task-ticket WS-A5 virtual-mcp-server-mvp
/create-task-ticket WS-B2 virtual-mcp-server-mvp
/create-task-ticket WS-B4 virtual-mcp-server-mvp

# --- Execute Tasks (parallel in separate terminals) ---

# Terminal 1: vmcp-control
cd /Users/imaxxs/repositories/vmcp-control
/execute-task WS-A2 virtual-mcp-server-mvp
/complete-task WS-A2 virtual-mcp-server-mvp
/execute-task WS-A3 virtual-mcp-server-mvp
/complete-task WS-A3 virtual-mcp-server-mvp
/execute-task WS-A5 virtual-mcp-server-mvp
/complete-task WS-A5 virtual-mcp-server-mvp

# Terminal 2: vmcp-gateway
cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-B2 virtual-mcp-server-mvp
/complete-task WS-B2 virtual-mcp-server-mvp
/execute-task WS-B4 virtual-mcp-server-mvp
/complete-task WS-B4 virtual-mcp-server-mvp

# --- Sync Status (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 100% (all 5 tasks parallel) |
| **Waves** | 1 |
| **Bottleneck** | None |
| **Unblocks** | Batch 3 (A4, A6, B3, B5) |

---

## Batch 3: Storage & Session (4 tasks)

### Dependencies

| Task | Description | Dependencies | Worktree |
|------|-------------|--------------|----------|
| A4 | Implement OAuth token vault storage | A3 ✅ | vmcp-control |
| A6 | Implement DelegationService | A5 ✅ | vmcp-control |
| B3 | Implement MCP Session tracking | B2 ✅ | vmcp-gateway |
| B5 | Implement tool schema cache | B4 ✅ | vmcp-gateway |

### Wave Analysis

**Wave 1: All 4 tasks parallel** (all dependencies from Batch 2 are complete)

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | A4, A6 | B3, B5 |

### Visual Dependency Graph

```
CONTROL (vmcp-control)          GATEWAY (vmcp-gateway)
─────────────────────           ─────────────────────
      A4    A6                       B3    B5
      │     │                        │     │
      └──┬──┘                        └──┬──┘
         │                              │
         └──────────────┬───────────────┘
                        │
                [Batch 3 Complete]
                        │
                        ▼
                    Batch 4
```

### Execution Strategy

All tasks can run in parallel across both worktrees.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH 3 - WAVE 1 (All Parallel)
# ═══════════════════════════════════════════════════════════════

# --- Create Task Tickets (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-ticket WS-A4 virtual-mcp-server-mvp
/create-task-ticket WS-A6 virtual-mcp-server-mvp
/create-task-ticket WS-B3 virtual-mcp-server-mvp
/create-task-ticket WS-B5 virtual-mcp-server-mvp

# --- Execute Tasks (parallel in separate terminals) ---

# Terminal 1: vmcp-control
cd /Users/imaxxs/repositories/vmcp-control
/execute-task WS-A4 virtual-mcp-server-mvp
/complete-task WS-A4 virtual-mcp-server-mvp
/execute-task WS-A6 virtual-mcp-server-mvp
/complete-task WS-A6 virtual-mcp-server-mvp

# Terminal 2: vmcp-gateway
cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-B3 virtual-mcp-server-mvp
/complete-task WS-B3 virtual-mcp-server-mvp
/execute-task WS-B5 virtual-mcp-server-mvp
/complete-task WS-B5 virtual-mcp-server-mvp

# --- Sync Status (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 100% (all 4 tasks parallel) |
| **Waves** | 1 |
| **Bottleneck** | None |
| **Unblocks** | Batch 4 (A7, A8, B6, B7, B8, C1, C2, D1, D2) |

---

## Batch 4: Agent Auth & Handlers (9 tasks) ⚠️ COMPLEX

### Dependencies

| Task | Description | Dependencies | Worktree |
|------|-------------|--------------|----------|
| A7 | Define Agent Session model | A5 ✅ | vmcp-control |
| A8 | Implement AgentSessionService | A6 ✅, **A7** | vmcp-control |
| B6 | Implement tools/list handler | B3 ✅, B5 ✅ | vmcp-gateway |
| B7 | Implement tools/call handler | B3 ✅, B4 ✅ | vmcp-gateway |
| B8 | Implement tool aggregator | B5 ✅, **B6** | vmcp-gateway |
| C1 | Implement agent challenge endpoint | **A8** | vmcp-control |
| C2 | Implement agent verify endpoint | **C1** | vmcp-control |
| D1 | Implement backend connection manager | **B8** | vmcp-gateway |
| D2 | Implement base MCP client | **D1** | vmcp-gateway |

### Wave Analysis

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | A7 | B6, B7 |
| **2** | A8 | B8 |
| **3** | C1 | D1 |
| **4** | C2 | D2 |

### Visual Dependency Graph

```
CONTROL (vmcp-control)          GATEWAY (vmcp-gateway)
─────────────────────           ─────────────────────

Wave 1:    A7 ───────┐               B6 ──────┐
                     │         B7    │        │
                     │        (||)   │        │
Wave 2:              ▼               ▼        │
           A8 ───────┤               B8 ──────┤
                     │                        │
Wave 3:              ▼                        ▼
           C1 ───────┤               D1 ──────┤
                     │                        │
Wave 4:              ▼                        ▼
           C2        │               D2       │
                     │                        │
                     └────────┬───────────────┘
                              │
                      [Batch 4 Complete]
                              │
                      ════════╪════════
                             MP1
                      (A8 + B3 converge)
                      ════════╪════════
                              │
                              ▼
                          Batch 5
```

### Execution Strategy

**4 waves required** due to internal dependencies.
- Control and Gateway can run in parallel within each wave
- Must wait for each wave to complete before starting next

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH 4 - MULTI-WAVE EXECUTION
# ═══════════════════════════════════════════════════════════════

# --- Create ALL Task Tickets First (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-ticket WS-A7 virtual-mcp-server-mvp
/create-task-ticket WS-A8 virtual-mcp-server-mvp
/create-task-ticket WS-B6 virtual-mcp-server-mvp
/create-task-ticket WS-B7 virtual-mcp-server-mvp
/create-task-ticket WS-B8 virtual-mcp-server-mvp
/create-task-ticket WS-C1 virtual-mcp-server-mvp
/create-task-ticket WS-C2 virtual-mcp-server-mvp
/create-task-ticket WS-D1 virtual-mcp-server-mvp
/create-task-ticket WS-D2 virtual-mcp-server-mvp

# ───────────────────────────────────────────────────────────────
# WAVE 1: A7 || B6, B7
# ───────────────────────────────────────────────────────────────

# Terminal 1: vmcp-control
cd /Users/imaxxs/repositories/vmcp-control
/execute-task WS-A7 virtual-mcp-server-mvp
/complete-task WS-A7 virtual-mcp-server-mvp

# Terminal 2: vmcp-gateway (B6 and B7 can run in parallel or sequence)
cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-B6 virtual-mcp-server-mvp
/complete-task WS-B6 virtual-mcp-server-mvp
/execute-task WS-B7 virtual-mcp-server-mvp
/complete-task WS-B7 virtual-mcp-server-mvp

# ⏸️ WAIT: Ensure A7 and B6 are complete before Wave 2

# ───────────────────────────────────────────────────────────────
# WAVE 2: A8 || B8
# ───────────────────────────────────────────────────────────────

# Terminal 1: vmcp-control
cd /Users/imaxxs/repositories/vmcp-control
/execute-task WS-A8 virtual-mcp-server-mvp
/complete-task WS-A8 virtual-mcp-server-mvp

# Terminal 2: vmcp-gateway
cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-B8 virtual-mcp-server-mvp
/complete-task WS-B8 virtual-mcp-server-mvp

# ⏸️ WAIT: Ensure A8 and B8 are complete before Wave 3

# ───────────────────────────────────────────────────────────────
# WAVE 3: C1 || D1
# ───────────────────────────────────────────────────────────────

# Terminal 1: vmcp-control
cd /Users/imaxxs/repositories/vmcp-control
/execute-task WS-C1 virtual-mcp-server-mvp
/complete-task WS-C1 virtual-mcp-server-mvp

# Terminal 2: vmcp-gateway
cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-D1 virtual-mcp-server-mvp
/complete-task WS-D1 virtual-mcp-server-mvp

# ⏸️ WAIT: Ensure C1 and D1 are complete before Wave 4

# ───────────────────────────────────────────────────────────────
# WAVE 4: C2 || D2
# ───────────────────────────────────────────────────────────────

# Terminal 1: vmcp-control
cd /Users/imaxxs/repositories/vmcp-control
/execute-task WS-C2 virtual-mcp-server-mvp
/complete-task WS-C2 virtual-mcp-server-mvp

# Terminal 2: vmcp-gateway
cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-D2 virtual-mcp-server-mvp
/complete-task WS-D2 virtual-mcp-server-mvp

# ───────────────────────────────────────────────────────────────
# POST-BATCH 4: Sync and Merge Point MP1
# ───────────────────────────────────────────────────────────────

# Sync Status (from main repo)
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp

# See MERGE_POINTS.md for MP1 actions before Batch 5
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 44% (4 parallel pairs across 4 waves) |
| **Waves** | 4 |
| **Bottleneck** | A7→A8→C1→C2 chain (control), B6→B8→D1→D2 chain (gateway) |
| **Merge Point** | **MP1** (A8 + B3 converge) after this batch |
| **Unblocks** | Batch 5 (C3, C4, D3, D4, D5, D6) |

---

## Batch 5: JWT & Backend Clients (6 tasks)

### Dependencies

| Task | Description | Dependencies | Worktree |
|------|-------------|--------------|----------|
| C3 | Implement JWT validation middleware | C2 ✅ | vmcp-gateway |
| C4 | Implement tool→permission mapper | B4 ✅ | vmcp-gateway |
| D3 | Implement Notion MCP client | D2 ✅ | vmcp-gateway |
| D4 | Implement Slack MCP client | D2 ✅ | vmcp-gateway |
| D5 | Implement HubSpot MCP client | D2 ✅ | vmcp-gateway |
| D6 | Implement backend router | D1 ✅, B7 ✅ | vmcp-gateway |

### Wave Analysis

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | - | C3, C4, D3, D4, D5 |
| **2** | - | D6 (needs D3-D5 outputs for routing) |

**Note:** D6 technically depends only on D1 and B7, but logically should wait for D3-D5 to have backends to route to.

### Visual Dependency Graph

```
CONTROL (vmcp-control)          GATEWAY (vmcp-gateway)
─────────────────────           ─────────────────────

Wave 1:    (none)                C3    C4    D3    D4    D5
                                 │     │     │     │     │
                                 └──┬──┴─────┴──┬──┴─────┘
                                    │           │
Wave 2:                             │           ▼
                                    │          D6
                                    │           │
                                    └─────┬─────┘
                                          │
                                  [Batch 5 Complete]
                                          │
                                  ════════╪════════
                                         MP2
                                  (B8 + C3 converge)
                                  ════════╪════════
                                          │
                                          ▼
                                      Batch 6
```

### Execution Strategy

Mostly Gateway work. Wave 1 is highly parallel (5 tasks), Wave 2 is single task.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH 5 - MULTI-WAVE EXECUTION (Gateway Only)
# ═══════════════════════════════════════════════════════════════

# --- Create Task Tickets (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-ticket WS-C3 virtual-mcp-server-mvp
/create-task-ticket WS-C4 virtual-mcp-server-mvp
/create-task-ticket WS-D3 virtual-mcp-server-mvp
/create-task-ticket WS-D4 virtual-mcp-server-mvp
/create-task-ticket WS-D5 virtual-mcp-server-mvp
/create-task-ticket WS-D6 virtual-mcp-server-mvp

# ───────────────────────────────────────────────────────────────
# WAVE 1: C3, C4, D3, D4, D5 (All Parallel)
# ───────────────────────────────────────────────────────────────

# Terminal: vmcp-gateway (run sequentially or parallel in multiple windows)
cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-C3 virtual-mcp-server-mvp
/complete-task WS-C3 virtual-mcp-server-mvp
/execute-task WS-C4 virtual-mcp-server-mvp
/complete-task WS-C4 virtual-mcp-server-mvp
/execute-task WS-D3 virtual-mcp-server-mvp
/complete-task WS-D3 virtual-mcp-server-mvp
/execute-task WS-D4 virtual-mcp-server-mvp
/complete-task WS-D4 virtual-mcp-server-mvp
/execute-task WS-D5 virtual-mcp-server-mvp
/complete-task WS-D5 virtual-mcp-server-mvp

# ⏸️ WAIT: Ensure D3, D4, D5 are complete before Wave 2

# ───────────────────────────────────────────────────────────────
# WAVE 2: D6
# ───────────────────────────────────────────────────────────────

# Terminal: vmcp-gateway
cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-D6 virtual-mcp-server-mvp
/complete-task WS-D6 virtual-mcp-server-mvp

# ───────────────────────────────────────────────────────────────
# POST-BATCH 5: Sync and Merge Point MP2
# ───────────────────────────────────────────────────────────────

cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp

# See MERGE_POINTS.md for MP2 actions before Batch 6
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 83% (5 parallel in Wave 1, 1 in Wave 2) |
| **Waves** | 2 |
| **Bottleneck** | D6 (must wait for backend clients) |
| **Merge Point** | **MP2** (B8 + C3 converge) after this batch |
| **Unblocks** | Batch 6 (C5, C6, C7) |

---

## Batch 6: Permission Middleware (3 tasks)

### Dependencies

| Task | Description | Dependencies | Worktree |
|------|-------------|--------------|----------|
| C5 | Implement permission filter | C3 ✅, C4 ✅ | vmcp-gateway |
| C6 | Implement delegation validator | C3 ✅, A6 ✅ | vmcp-gateway |
| C7 | Implement credential injection | **C6**, A4 ✅ | vmcp-gateway |

### Wave Analysis

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | - | C5, C6 |
| **2** | - | C7 |

### Visual Dependency Graph

```
CONTROL (vmcp-control)          GATEWAY (vmcp-gateway)
─────────────────────           ─────────────────────

Wave 1:    (none)                    C5    C6
                                     │     │
                                     │     ▼
Wave 2:                              │    C7
                                     │     │
                                     └──┬──┘
                                        │
                                [Batch 6 Complete]
                                        │
                                ════════╪════════
                                       MP3
                                (C7 + D6 converge)
                                ════════╪════════
                                        │
                                        ▼
                                    Batch 7
```

### Execution Strategy

Gateway-only work. C5 and C6 can run in parallel, C7 must wait for C6.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH 6 - MULTI-WAVE EXECUTION (Gateway Only)
# ═══════════════════════════════════════════════════════════════

# --- Create Task Tickets (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-ticket WS-C5 virtual-mcp-server-mvp
/create-task-ticket WS-C6 virtual-mcp-server-mvp
/create-task-ticket WS-C7 virtual-mcp-server-mvp

# ───────────────────────────────────────────────────────────────
# WAVE 1: C5, C6 (Parallel)
# ───────────────────────────────────────────────────────────────

cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-C5 virtual-mcp-server-mvp
/complete-task WS-C5 virtual-mcp-server-mvp
/execute-task WS-C6 virtual-mcp-server-mvp
/complete-task WS-C6 virtual-mcp-server-mvp

# ⏸️ WAIT: Ensure C6 is complete before Wave 2

# ───────────────────────────────────────────────────────────────
# WAVE 2: C7
# ───────────────────────────────────────────────────────────────

cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-C7 virtual-mcp-server-mvp
/complete-task WS-C7 virtual-mcp-server-mvp

# ───────────────────────────────────────────────────────────────
# POST-BATCH 6: Sync and Merge Point MP3
# ───────────────────────────────────────────────────────────────

cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp

# See MERGE_POINTS.md for MP3 actions before Batch 7
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 67% (2 parallel in Wave 1, 1 in Wave 2) |
| **Waves** | 2 |
| **Bottleneck** | C7 (depends on C6) |
| **Merge Point** | **MP3** (C7 + D6 converge) after this batch |
| **Unblocks** | Batch 7 (E2, E3, F1) |

---

## Batch 7: Audit & E2E Setup (3 tasks)

### Dependencies

| Task | Description | Dependencies | Worktree |
|------|-------------|--------------|----------|
| E2 | Implement audit logger service | E1 ✅ | vmcp-control |
| E3 | Implement audit middleware | **E2**, C6 ✅ | vmcp-gateway |
| F1 | Create Sarah's Journey E2E test | All ✅ | vmcp-gateway |

### Wave Analysis

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | E2 | F1 |
| **2** | - | E3 |

### Visual Dependency Graph

```
CONTROL (vmcp-control)          GATEWAY (vmcp-gateway)
─────────────────────           ─────────────────────

Wave 1:       E2 ─────────┐          F1
              │           │          │
              │           │          │
Wave 2:       │           ▼          │
              │          E3          │
              │           │          │
              └─────┬─────┴──────────┘
                    │
            [Batch 7 Complete]
                    │
                    ▼
                Batch 8
```

### Execution Strategy

E2 (control) and F1 (gateway) can run in parallel. E3 must wait for E2.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH 7 - MULTI-WAVE EXECUTION
# ═══════════════════════════════════════════════════════════════

# --- Create Task Tickets (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-ticket WS-E2 virtual-mcp-server-mvp
/create-task-ticket WS-E3 virtual-mcp-server-mvp
/create-task-ticket WS-F1 virtual-mcp-server-mvp

# ───────────────────────────────────────────────────────────────
# WAVE 1: E2 || F1
# ───────────────────────────────────────────────────────────────

# Terminal 1: vmcp-control
cd /Users/imaxxs/repositories/vmcp-control
/execute-task WS-E2 virtual-mcp-server-mvp
/complete-task WS-E2 virtual-mcp-server-mvp

# Terminal 2: vmcp-gateway
cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-F1 virtual-mcp-server-mvp
/complete-task WS-F1 virtual-mcp-server-mvp

# ⏸️ WAIT: Ensure E2 is complete before Wave 2

# ───────────────────────────────────────────────────────────────
# WAVE 2: E3
# ───────────────────────────────────────────────────────────────

cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-E3 virtual-mcp-server-mvp
/complete-task WS-E3 virtual-mcp-server-mvp

# --- Sync Status ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 67% (2 parallel in Wave 1, 1 in Wave 2) |
| **Waves** | 2 |
| **Bottleneck** | E3 (depends on E2) |
| **Unblocks** | Batch 8 (E4, E5, F2, F3, F4) |

---

## Batch 8: Security & Demos (5 tasks)

### Dependencies

| Task | Description | Dependencies | Worktree |
|------|-------------|--------------|----------|
| E4 | Implement fail-closed security | C3 ✅ | vmcp-gateway |
| E5 | Implement constraint checker | C6 ✅ | vmcp-gateway |
| F2 | Create Demo 1: Unified Connection | B6 ✅, D3 ✅, D4 ✅ | vmcp-gateway |
| F3 | Create Demo 2: Filtered Visibility | C5 ✅ | vmcp-gateway |
| F4 | Create Demo 3: Delegation Execution | C7 ✅ | vmcp-gateway |

### Wave Analysis

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | - | E4, E5, F2, F3, F4 |

**All 5 tasks can run in parallel!** (All dependencies satisfied from previous batches)

### Visual Dependency Graph

```
CONTROL (vmcp-control)          GATEWAY (vmcp-gateway)
─────────────────────           ─────────────────────

Wave 1:    (none)               E4  E5  F2  F3  F4
                                │   │   │   │   │
                                └───┴───┴───┴───┘
                                        │
                                [Batch 8 Complete]
                                        │
                                ════════╪════════
                                       MP4
                                (E3 + all backends)
                                ════════╪════════
                                        │
                                        ▼
                                    Batch 9
```

### Execution Strategy

All Gateway work. All 5 tasks can run in parallel.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH 8 - WAVE 1 (All Parallel, Gateway Only)
# ═══════════════════════════════════════════════════════════════

# --- Create Task Tickets (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-ticket WS-E4 virtual-mcp-server-mvp
/create-task-ticket WS-E5 virtual-mcp-server-mvp
/create-task-ticket WS-F2 virtual-mcp-server-mvp
/create-task-ticket WS-F3 virtual-mcp-server-mvp
/create-task-ticket WS-F4 virtual-mcp-server-mvp

# --- Execute Tasks (all parallel) ---
cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-E4 virtual-mcp-server-mvp
/complete-task WS-E4 virtual-mcp-server-mvp
/execute-task WS-E5 virtual-mcp-server-mvp
/complete-task WS-E5 virtual-mcp-server-mvp
/execute-task WS-F2 virtual-mcp-server-mvp
/complete-task WS-F2 virtual-mcp-server-mvp
/execute-task WS-F3 virtual-mcp-server-mvp
/complete-task WS-F3 virtual-mcp-server-mvp
/execute-task WS-F4 virtual-mcp-server-mvp
/complete-task WS-F4 virtual-mcp-server-mvp

# ───────────────────────────────────────────────────────────────
# POST-BATCH 8: Sync and Merge Point MP4
# ───────────────────────────────────────────────────────────────

cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp

# See MERGE_POINTS.md for MP4 actions before Batch 9
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 100% (all 5 tasks parallel) |
| **Waves** | 1 |
| **Bottleneck** | None |
| **Merge Point** | **MP4** (E3 + all backends) after this batch |
| **Unblocks** | Batch 9 (E6, F5, F6, F7, F8) |

---

## Batch 9: Final Demos & Polish (5 tasks)

### Dependencies

| Task | Description | Dependencies | Worktree |
|------|-------------|--------------|----------|
| E6 | Implement audit query API | E2 ✅ | vmcp-control |
| F5 | Create Demo 4: Permission Enforcement | C6 ✅ | vmcp-gateway |
| F6 | Create Demo 5: Unified Audit | **E6** | vmcp-gateway |
| F7 | Create Demo 6: Fail-Closed | E4 ✅ | vmcp-gateway |
| F8 | Create cross-service workflow demo | D5 ✅, F1 ✅ | vmcp-gateway |

### Wave Analysis

| Wave | Control Plane | Gateway |
|------|---------------|---------|
| **1** | E6 | F5, F7, F8 |
| **2** | - | F6 |

### Visual Dependency Graph

```
CONTROL (vmcp-control)          GATEWAY (vmcp-gateway)
─────────────────────           ─────────────────────

Wave 1:       E6 ─────────┐        F5    F7    F8
              │           │        │     │     │
              │           │        │     │     │
Wave 2:       │           ▼        │     │     │
              │          F6        │     │     │
              │           │        │     │     │
              └─────┬─────┴────────┴─────┴─────┘
                    │
            [Batch 9 Complete]
                    │
                    ▼
            ✅ MVP COMPLETE!
```

### Execution Strategy

E6 (control) and F5, F7, F8 (gateway) can run in parallel. F6 must wait for E6.

### Commands

```bash
# ═══════════════════════════════════════════════════════════════
# BATCH 9 - FINAL BATCH
# ═══════════════════════════════════════════════════════════════

# --- Create Task Tickets (from main repo) ---
cd /Users/imaxxs/repositories/deepsecure-mvp
/create-task-ticket WS-E6 virtual-mcp-server-mvp
/create-task-ticket WS-F5 virtual-mcp-server-mvp
/create-task-ticket WS-F6 virtual-mcp-server-mvp
/create-task-ticket WS-F7 virtual-mcp-server-mvp
/create-task-ticket WS-F8 virtual-mcp-server-mvp

# ───────────────────────────────────────────────────────────────
# WAVE 1: E6 || F5, F7, F8
# ───────────────────────────────────────────────────────────────

# Terminal 1: vmcp-control
cd /Users/imaxxs/repositories/vmcp-control
/execute-task WS-E6 virtual-mcp-server-mvp
/complete-task WS-E6 virtual-mcp-server-mvp

# Terminal 2: vmcp-gateway
cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-F5 virtual-mcp-server-mvp
/complete-task WS-F5 virtual-mcp-server-mvp
/execute-task WS-F7 virtual-mcp-server-mvp
/complete-task WS-F7 virtual-mcp-server-mvp
/execute-task WS-F8 virtual-mcp-server-mvp
/complete-task WS-F8 virtual-mcp-server-mvp

# ⏸️ WAIT: Ensure E6 is complete before Wave 2

# ───────────────────────────────────────────────────────────────
# WAVE 2: F6
# ───────────────────────────────────────────────────────────────

cd /Users/imaxxs/repositories/vmcp-gateway
/execute-task WS-F6 virtual-mcp-server-mvp
/complete-task WS-F6 virtual-mcp-server-mvp

# ───────────────────────────────────────────────────────────────
# FINAL: Sync and Complete
# ───────────────────────────────────────────────────────────────

cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status virtual-mcp-server-mvp

# 🎉 MVP COMPLETE!
```

### Summary

| Metric | Value |
|--------|-------|
| **Parallelism** | 80% (4 parallel in Wave 1, 1 in Wave 2) |
| **Waves** | 2 |
| **Bottleneck** | F6 (depends on E6) |
| **Completion** | ✅ MVP Complete! |

---

## Overall Execution Summary

### Batch Parallelism Overview

| Batch | Tasks | Waves | Parallel % | Cross-Worktree? |
|-------|-------|-------|------------|-----------------|
| 1 | 3 | 1 | 100% | ✅ Yes |
| 2 | 5 | 1 | 100% | ✅ Yes |
| 3 | 4 | 1 | 100% | ✅ Yes |
| 4 | 9 | 4 | 44% | ✅ Yes |
| 5 | 6 | 2 | 83% | ❌ Gateway only |
| 6 | 3 | 2 | 67% | ❌ Gateway only |
| 7 | 3 | 2 | 67% | ✅ Yes |
| 8 | 5 | 1 | 100% | ❌ Gateway only |
| 9 | 5 | 2 | 80% | ✅ Yes |

### Merge Points Summary

| Point | After Batch | Converging | Actions Required |
|-------|-------------|------------|------------------|
| **MP1** | 4 | A8 + B3 | See [MERGE_POINTS.md](./MERGE_POINTS.md#mp1) |
| **MP2** | 5 | B8 + C3 | See [MERGE_POINTS.md](./MERGE_POINTS.md#mp2) |
| **MP3** | 6 | C7 + D6 | See [MERGE_POINTS.md](./MERGE_POINTS.md#mp3) |
| **MP4** | 8 | E3 + all | See [MERGE_POINTS.md](./MERGE_POINTS.md#mp4) |

### Total Commands Needed

| Command Type | Count |
|--------------|-------|
| `/create-task-ticket` | 44 (one per task) |
| `/execute-task` | 44 (one per task) |
| `/complete-task` | 44 (one per task) |
| `/sync-worktree-status` | 9 (one per batch) |
| Merge Point actions | 4 |
| **Total** | ~145 commands |

### Critical Path

```
A1 → A5 → A6 → A7 → A8 → C1 → C2 → C3 → C6 → C7 → E3 → F1 → F8
│                                                          │
└──────────────────── 15 days minimum ─────────────────────┘
```

### Worktree Distribution

| Worktree | Tasks |
|----------|-------|
| **vmcp-control** | A1-A8, C1-C2, E1-E2, E6 (14 tasks) |
| **vmcp-gateway** | B1-B8, C3-C7, D1-D6, E3-E5, F1-F8 (30 tasks) |

---

## Quick Command Reference

### Full Batch Execution Script (Copy-Paste Ready)

See individual batch sections above for detailed wave-by-wave commands.

### One-Liner to Create All Tickets for a Batch

```bash
# Batch 1
for t in A1 B1 E1; do echo "/create-task-ticket WS-$t virtual-mcp-server-mvp"; done

# Batch 4 (example of larger batch)
for t in A7 A8 B6 B7 B8 C1 C2 D1 D2; do echo "/create-task-ticket WS-$t virtual-mcp-server-mvp"; done
```

---

*Generated by `/create-batch-execution-plan` command*
