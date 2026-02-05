# Breakdown Design Document into Workstreams and Tasks

Analyze the provided design document and create a complete task breakdown.

## Instructions

1. **Read the design document** provided by the user (or use the file path given)

2. **Identify architectural boundaries:**
   - Services/modules involved
   - External dependencies (APIs, databases, third-party services)
   - Shared state or resources between components

3. **Create workstreams** following these rules:
   - Group related tasks that share dependencies
   - Identify which workstreams can run in PARALLEL
   - Identify which workstreams are SEQUENTIAL (blocked by others)
   - Name workstreams clearly (e.g., "WS-A: Token Service", "WS-B: Gateway Integration")

4. **Break down each workstream into tasks:**
   - Each task should be completable in 1-3 hours
   - Use task IDs: WS-A1, WS-A2, WS-B1, etc.
   - Specify dependencies between tasks
   - Include acceptance criteria for each task
   - List files to create/modify

5. **Create the dependency graph** using ASCII visualization

6. **Identify the critical path** (longest sequential chain)

7. **Output format:**

```markdown
## Workstream Breakdown for: [Design Name]

### Summary
- Total Workstreams: X
- Total Tasks: Y
- Total Batches: Z
- Critical Path: [list of task IDs]
- Merge Points: [number]
- Estimated Total Effort: [S/M/L tasks breakdown]

### Workstream A: [Name] (PARALLEL with B, C)

| Task ID | Description | Dependencies | Complexity | Files | Acceptance Criteria |
|---------|-------------|--------------|------------|-------|---------------------|
| WS-A1 | ... | None | S | `path/to/file.py` (create) | ... |
| WS-A2 | ... | WS-A1 | M | `path/to/other.py` (modify) | ... |

### Workstream B: [Name] (PARALLEL with A)
...

### Workstream C: [Name] (BLOCKED BY A, B)
...

### Batch Execution Model

| Batch | Tasks (Parallel) | Depends On | Blocking For |
|-------|------------------|------------|--------------|
| 1 | A1, B1 | None | Batch 2 |
| 2 | A2, A3, B2 | Batch 1 | Batch 3 |
| 3 | C1, C2 | Batch 2 | Batch 4 |

### Merge Points

| Point | Converging Tasks | Enables | Git Action |
|-------|------------------|---------|------------|
| MP1 | A3 + B2 | C1 | Merge ws-a, ws-b |
| MP2 | C3 + D2 | E1 | Merge ws-c, ws-d |

### Critical Path Analysis

```
Primary:   A1 → A2 → A3 → C1 → C3 → E1 → F1
Secondary: B1 → B2 → D1 → D3 → F1 (if dual-track)
```

[Explanation of the critical path and parallelization opportunities]

### Acceptance Mapping

#### Demo/Milestone → Task Matrix
| Demo | Description | Validating Tasks |
|------|-------------|------------------|
| Demo 1 | [from design doc] | A1, B3, D1 |
| Demo 2 | [from design doc] | C2, C4 |

#### User Journey → Task Matrix (if applicable)
| Step | Action | Implementing Tasks |
|------|--------|-------------------|
| 1 | [from design doc] | A1 |
| 2 | [from design doc] | A3, B3 |

### Dependency Graph
[ASCII diagram]
```

8. **Save the breakdown output** to a reference file:
   - Ask the user: "Would you like to save this breakdown to a file for reference?"
   - If yes, save to: `docs/[feature-name]-breakdown.md`
   - Use naming convention: `[design-doc-name]-breakdown.md`
   - Example: `deepsecure-virtual-mcp-server-mvp.md` → `deepsecure-virtual-mcp-server-mvp-breakdown.md`

9. **Update status files:**
   
   a. **Create `docs/[design-name]/EXECUTION_STATUS.md`** from template if not exists
   
   b. **Update `docs/[design-name]/EXECUTION_STATUS.md`** (per-design execution):
      - Update Phase 2 step 2a (`/breakdown-design`) to ✅ with link to breakdown file
      - Add entry to "Command Execution Log"
   
   c. **Update `docs/EXECUTION_STATUS.md`** (global portfolio):
      - Add design to "Active Designs" if not already present
      - Update phase and progress columns

10. **Ask the user** if they want to:
   - Create the workstream folder structure (`/create-workstream`)
   - Generate individual task tickets for Batch 1
   - Proceed with any modifications to the breakdown

## Reference Files
- Design template: `docs/design/DESIGN_TEMPLATE.md`
- Task breakdown framework: `docs/TASK_BREAKDOWN.md`
- Workflow guide: `docs/WORKFLOW_GUIDE.md` (batch model, merge points, acceptance mapping)
- Workstream template: `docs/workstreams/WORKSTREAM_TEMPLATE.md`
- Project rules: `.cursorrules`

## Real-World Example
- Design: `docs/design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md`
- Breakdown: `docs/deepsecure-virtual-mcp-server-mvp-breakdown.md`

## DeepSecure-Specific Patterns

When breaking down DeepSecure features, consider these common patterns:

**SDK Feature:**
```
WS-A: Core (_core/) → WS-B: Public API → WS-C: CLI → WS-D: Tests → WS-E: Examples
```

**Backend Change:**
```
WS-A: Schema/Migrations → WS-B: Control Plane → WS-C: Gateway → WS-D: SDK → WS-E: E2E Tests
```

**Cross-Service:**
```
WS-A: Contracts → WS-B: Control (parallel) → WS-C: Gateway (parallel) → WS-D: Integration
```
