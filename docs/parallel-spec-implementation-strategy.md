# Parallel Spec/Ticket and Implementation Strategy

> **Problem:** When spec/ticket creation and implementation run as parallel subagents, drift emerges because the implementation agent works from the high-level design doc while the spec agent refines and sharpens requirements. The result is gaps that require a costly reconciliation pass.
>
> **Lesson Learned:** Batch 4 of `frontend-architecture` — implementation ran in parallel with spec creation. Post-hoc audit found ~15 gaps across 9 tasks, requiring 153 new tests and significant page rewrites.

---

## The Root Cause

```
t=0  ──┬── Subagent A: Create specs/tickets ──→ Refines interfaces, adds acceptance criteria
       │                                          (source: design doc + spec template)
       │
       └── Subagent B: Implement code ──────────→ Works from design doc ONLY
                                                   (no access to spec refinements)
t=N  ──── Both finish → audit reveals drift
```

The implementation agent never sees the spec's refined TypeScript interfaces, component prop contracts, acceptance criteria, or UI requirements. It relies on the higher-level, less precise design doc.

---

## Options

### Option 1: Sequential — Wait for Specs Before Implementing

```
t=0  ── Subagent A: Create specs/tickets
t=N  ── Subagent B: Implement (reads completed specs)
```

| Dimension | Assessment |
|-----------|------------|
| **Drift risk** | Zero — implementation reads final spec |
| **Wall-clock time** | 2x slower — no parallelism |
| **Orchestration complexity** | Simple — linear pipeline |
| **When to use** | High-complexity tasks; specs will deviate significantly from design doc |

### Option 2: Parallel + Post-Reconciliation Audit

```
t=0  ──┬── Subagent A: Create specs
       └── Subagent B: Implement from design doc
t=N  ── Audit: diff spec vs implementation → fix gaps
```

| Dimension | Assessment |
|-----------|------------|
| **Drift risk** | High — reconciliation can be expensive |
| **Wall-clock time** | Fast — full parallelism |
| **Orchestration complexity** | Medium — requires audit step |
| **When to use** | Design doc is detailed enough that specs are refinements, not rewrites |

This is what Batch 4 used. It got ~80% right but the 20% required substantial rework.

### Option 3: Staggered Pipeline — Spec Leads, Implementation Follows Per-Task

```
t=0  ── Spec subagent starts all specs
t=1  ── First spec done → Implementation subagent starts that task
t=2  ── Second spec done → Implementation picks it up next
...continues until all done
```

| Dimension | Assessment |
|-----------|------------|
| **Drift risk** | Zero — each task implements against its own spec |
| **Wall-clock time** | Partial parallelism — faster than sequential, slower than full parallel |
| **Orchestration complexity** | High — requires polling or event-driven coordination |
| **When to use** | Best of both worlds when you can tolerate orchestration complexity |

### Option 4: Spec-First Skeleton + Parallel Fill (Recommended)

```
t=0  ── Main agent: Create lightweight contract skeletons (~2 min each)
t=1  ──┬── Subagent A: Flesh out full specs/tickets from skeletons
       └── Subagent B: Implement from skeletons (has interfaces + acceptance criteria)
t=N  ── Light audit (skeletons already aligned, drift is minimal)
```

| Dimension | Assessment |
|-----------|------------|
| **Drift risk** | Low — both agents share the same contract |
| **Wall-clock time** | Fast — small upfront cost, then full parallelism |
| **Orchestration complexity** | Low — only change is skeleton extraction before launch |
| **When to use** | Default strategy for most batches |

### Option 5: Shared Contract File — Both Agents Read the Same Source

```
t=0  ── Main agent: Write a shared contract file (interfaces, API shapes, criteria)
t=1  ──┬── Subagent A: Create specs/tickets (references contract)
       └── Subagent B: Implement (references contract)
```

| Dimension | Assessment |
|-----------|------------|
| **Drift risk** | Very low — single source of truth |
| **Wall-clock time** | Fast — parallel after contract is written |
| **Orchestration complexity** | Medium — contract file is extra artifact to maintain |
| **When to use** | Batches with many tasks and well-defined API contracts |

Similar to Option 4, but produces a single file rather than per-task skeletons. The trade-off is that one large contract file can become unwieldy for large batches.

---

## Comparison Matrix

| Option | Drift Risk | Speed | Complexity | Best For |
|--------|-----------|-------|------------|----------|
| 1. Sequential | None | Slowest | Simple | Complex/novel tasks |
| 2. Parallel + Audit | High | Fastest | Medium | When design doc is precise |
| 3. Staggered Pipeline | None | Medium | High | Event-driven orchestration |
| **4. Skeleton + Parallel** | **Low** | **Fast** | **Low** | **Default for most batches** |
| 5. Shared Contract | Very Low | Fast | Medium | API-heavy batches |

---

## Recommendation: Option 4 — Spec-First Skeleton

### Why This Wins

1. **Addresses the root cause.** The Batch 4 problem was that the implementation agent lacked access to refined interfaces and acceptance criteria. The skeleton provides exactly that.

2. **Minimal overhead.** The main agent already reads the design doc and knows the task shapes. Extracting a skeleton takes ~2 minutes per task — far less than the reconciliation cost.

3. **Preserved parallelism.** After skeletons are written, both subagents run in full parallel. Wall-clock time is barely slower than Option 2.

4. **The skeleton IS the contract.** If the full spec adds details beyond the skeleton, those are "nice-to-have" refinements, not structural changes. Implementation will still be correct.

### What Goes in a Skeleton

Each skeleton is a lightweight markdown file with the critical contract:

```markdown
# Skeleton: WS-C5 Audit Trail Page

## Component Interface
​```typescript
interface AuditEvent {
  id: string;
  event_type: string;
  token_layer: "user" | "agent" | "delegation" | "gateway";
  agent_id: string | null;
  user_id: string | null;
  timestamp: string;
  details: Record<string, unknown>;
  attribution_chain?: AttributionLink[];
}

interface AuditFilters {
  event_type?: string;
  agent_id?: string;
  token_layer?: string;
  from_date?: string;
  to_date?: string;
}
​```

## API Endpoints
- `GET /api/proxy/audit/events?{filters}` — List events
- `GET /api/proxy/audit/events/{event_id}` — Event detail

## Key UI Elements
- Filter bar (event_type, agent_id, token_layer, date range)
- Event list with token layer badges (user=blue, agent=green, delegation=purple, gateway=orange)
- Event detail panel (metadata, details JSON, attribution chain)
- Pagination

## Acceptance Criteria
- [ ] Lists events in chronological order
- [ ] Token layer badges with distinct colors
- [ ] Filter by event_type, agent_id, token_layer, date range
- [ ] Click event shows detail panel with attribution chain
- [ ] PageSkeleton during loading
- [ ] ErrorCard on failure with retry
- [ ] EmptyState when no events match

## Files
- `frontend/src/app/(dashboard)/dashboard/audit/page.tsx`
- `frontend/src/app/(dashboard)/dashboard/audit/__tests__/page.test.tsx`
```

### What Does NOT Go in a Skeleton

- Narrative descriptions or background context
- Full test case tables
- Validation commands
- References and upstream/downstream links
- Implementation notes

These belong in the full spec and ticket — but the implementation doesn't need them to produce correct code.

---

## Implementation: Changes to `/run-batch`

### Current Flow (Steps 3-5)

```
Step 3: Create specs ─────────────────→ (all specs)
Step 4: Create tickets ───────────────→ (all tickets)
Step 5: Execute waves ────────────────→ (implementation)
```

### New Flow (Steps 3-5)

```
Step 3: Extract skeletons ────────────→ (main agent, ~2 min/task)
Step 4: Launch in parallel:
        ├── Subagent A: Create specs + tickets (reads skeletons)
        └── Subagent B: Execute waves (reads skeletons)
Step 5: Light reconciliation check ───→ (verify no structural drift)
```

### New Step 3: Extract Contract Skeletons

**Before** launching any subagents, the main agent creates a skeleton for each task in the batch:

```
docs/workstreams/[feature-name]/skeletons/WS-[ID]-skeleton.md
```

**Source material:**
- `BATCH_EXECUTION_PLAN.md` — task descriptions and dependencies
- `BREAKDOWN.md` or design doc — interfaces, API contracts, component specs
- Existing codebase — current types, patterns, imports

**Extraction takes ~2 minutes per task. For a 9-task batch, this is ~18 minutes — compare to ~2 hours of reconciliation for Option 2.**

### New Step 4: Parallel Subagent Launch

Both subagents receive the skeleton paths in their prompts:

**Spec/Ticket Subagent:**
```
Create full specs and tickets for tasks [list].
Skeletons are at: docs/workstreams/[feature]/skeletons/WS-*-skeleton.md
Use skeletons as the contract foundation. Expand with:
- Full narrative descriptions
- Test case tables
- Validation commands
- References
```

**Implementation Subagent:**
```
Implement tasks [list] per wave order.
Contract skeletons at: docs/workstreams/[feature]/skeletons/WS-*-skeleton.md
The skeleton defines:
- TypeScript interfaces (implement exactly)
- Acceptance criteria (satisfy all)
- Files to create/modify
- API endpoints (use exactly)
```

### New Step 5: Light Reconciliation

After both subagents complete:

1. Diff each spec's acceptance criteria against the skeleton's criteria
2. Verify implementation exports match skeleton interfaces
3. Confirm all skeleton-listed files were created
4. Flag any structural drift (new interfaces, changed endpoints)

**Expected drift: <5%.** If drift exceeds 10%, fall back to Option 1 (sequential) for the next batch.

---

## Decision Framework: Which Option to Use

```
Is the design doc precise with TypeScript interfaces?
├── YES → Option 4 (Skeleton + Parallel) — default
└── NO
    ├── Are there >5 tasks in the batch?
    │   ├── YES → Option 4 (invest in skeleton extraction)
    │   └── NO → Option 1 (Sequential — small batch, low overhead)
    └── Is this a novel/experimental feature?
        ├── YES → Option 1 (Sequential — specs will diverge heavily)
        └── NO → Option 4 (Skeleton + Parallel)
```

---

## Metrics to Track

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Skeleton extraction time** | <3 min/task | Wall-clock from batch parse to skeleton commit |
| **Post-reconciliation gaps** | <5% of acceptance criteria | Count of criteria needing fix after parallel run |
| **Rework time** | <10% of implementation time | Time spent in reconciliation / total implementation time |
| **Build/test pass rate** | 100% after reconciliation | `npm run build && npm test` |

---

## History

| Date | Event |
|------|-------|
| 2026-05-06 | Batch 4 `frontend-architecture` — Option 2 used, 15 gaps found, 153 tests added in reconciliation |
| 2026-05-06 | Decision: adopt Option 4 (Skeleton + Parallel) as default strategy |
