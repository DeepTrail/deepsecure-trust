# Workstreams Directory

This directory contains workstreams, task tickets, and completion reports for feature implementations.

## Directory Structure

```
docs/workstreams/
├── README.md                           # This file
├── TASK_TICKET_TEMPLATE.md             # Template for task tickets
├── COMPLETION_REPORT_TEMPLATE.md       # Template for completion reports
├── WORKSTREAM_TEMPLATE.md              # Template for workstream overview
│
└── [feature-name]/                     # One folder per feature/project
    ├── WORKSTREAM.md                   # Workstream overview and tracking
    ├── tasks/                          # Task tickets
    │   ├── WS-A1-task-name.md
    │   ├── WS-A2-task-name.md
    │   └── ...
    └── reports/                        # Completion reports
        ├── WS-A1-completion.md
        ├── WS-A2-completion.md
        └── ...
```

## Workflow

```
┌─────────────────┐
│   Design Doc    │  Define API CONTRACTS (canonical source)
│ (docs/design/)  │  Specify FILE LOCATIONS
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Workstream    │  Create WORKSTREAM.md
│    Breakdown    │  Copy API contracts from design doc
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Task Tickets   │  Include SPECIFICATION section
│    Created      │  (immutable, from design doc)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Execute      │  Implement to match spec EXACTLY
│     Tasks       │  Verify endpoints match
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   CONTRACT      │  ← NEW: BLOCKING STEP
│  VERIFICATION   │  Endpoints match? Files in right place?
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Completion    │  Document CONTRACT verification
│    Reports      │  Document FILE LOCATION verification
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Update         │  Add learnings to CLAUDE.md
│  CLAUDE.md      │  (especially contract/location issues)
└─────────────────┘
```

### Critical Verification Points

| Step | Verification | Common Failure |
|------|--------------|----------------|
| Task Execution | Endpoint matches design doc | 404 errors in tests |
| Task Execution | Async fixtures correct | `AttributeError: 'async_generator'` |
| Completion | Files in correct location | E2E tests not found |
| Merge Point | Tests use correct endpoints | Tests fail after merge |

## Templates

### Creating a New Workstream

1. Create a folder: `docs/workstreams/[feature-name]/`
2. Copy `WORKSTREAM_TEMPLATE.md` to `[feature-name]/WORKSTREAM.md`
3. Create subfolders: `tasks/` and `reports/`
4. Fill in workstream details and task breakdown

### Creating a Task Ticket

1. Copy `TASK_TICKET_TEMPLATE.md` to `[feature-name]/tasks/[WS-ID]-[task-name].md`
2. Fill in all metadata and acceptance criteria
3. Update the workstream's task table with a link

### Creating a Completion Report

1. Copy `COMPLETION_REPORT_TEMPLATE.md` to `[feature-name]/reports/[WS-ID]-completion.md`
2. Fill in implementation details, test results, and learnings
3. Update the workstream's progress tracking

## Task States

| State | Description |
|-------|-------------|
| `draft` | Task ticket created but not fully specified |
| `ready` | Task is fully specified and ready to start |
| `in_progress` | Actively being worked on |
| `review` | Implementation complete, awaiting review |
| `completed` | Task done, completion report filed |
| `blocked` | Cannot proceed due to external dependency |
| `cancelled` | Task no longer needed |

## Naming Conventions

- **Workstream IDs**: `WS-A`, `WS-B`, `WS-C`, etc.
- **Task IDs**: `WS-A1`, `WS-A2`, `WS-B1`, etc.
- **File names**: lowercase with hyphens, e.g., `WS-A1-implement-token-service.md`

## File Organization Rules

> **CRITICAL**: These rules prevent common test failures.

### Cross-Service vs Service-Specific

| Artifact Type | Correct Location | Wrong Location | Why |
|---------------|------------------|----------------|-----|
| MVP E2E tests | `tests/e2e/` (ROOT) | `[service]/tests/e2e/` | Spans multiple services |
| MVP demos | `demos/` (ROOT) | `[service]/demos/` | Demonstrates full system |
| Demo tests | `tests/demos/` (ROOT) | `[service]/tests/demos/` | Tests cross-service demos |
| Service unit tests | `[service]/tests/` | Root level | Service-specific |

### Technical Requirements

| Requirement | Correct | Wrong | Error If Wrong |
|-------------|---------|-------|----------------|
| Async fixtures | `@pytest_asyncio.fixture` | `@pytest.fixture` | `AttributeError: 'async_generator'` |
| HTTP client | `httpx.AsyncClient` | `requests` | Blocks async tests |
| Fixture scope | `scope="function"` | `scope="session"` | Connection issues |

## Active Workstreams

<!-- Update this list as workstreams are created -->

| Feature | Status | Progress | Link |
|---------|--------|----------|------|
| Virtual MCP Server MVP | `in_progress` | 0% (0/44 tasks) | [WORKSTREAM.md](./virtual-mcp-server-mvp/WORKSTREAM.md) |
| Interactive Demo | `planning` | 0% (0/9 tasks) | [WORKSTREAM.md](./interactive-demo/WORKSTREAM.md) |
| IdP Selector for Demo | `planning` | 0% (0/8 tasks) | [WORKSTREAM.md](./idp-selector/WORKSTREAM.md) |

## Completed Workstreams

<!-- Move completed workstreams here for reference -->

| Feature | Completed | Tasks | Link |
|---------|-----------|-------|------|
| _None yet_ | - | - | - |
