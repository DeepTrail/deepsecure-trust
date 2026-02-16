# Create Task Specification

Generate immutable task specifications (API contracts, data models, protocols) for tasks in a batch.

> **Mode:** This command should run in **Plan mode** for collaborative specification design.
> 
> **Purpose:** Create the IMMUTABLE specification portion that implementation MUST match exactly.

## Workflow Position

```
/breakdown-design → /create-workstream → /create-batch-execution-plan → /create-task-spec → /create-task-ticket
                                                                              ↑
                                                                         (YOU ARE HERE)
```

## Usage

```
/create-task-spec [batch-number] [feature-name]
```

**Parameters:**
- `[batch-number]`: Which batch to create specs for (e.g., `1`, `2`)
- `[feature-name]`: The feature/workstream name (e.g., `interactive-demo`, `virtual-mcp-server-mvp`)

**Output:**
- Creates `docs/workstreams/[feature-name]/specs/[WS-ID]-spec.md` for each task in the batch

---

## Pre-Requisites

Before running this command, ensure:

1. ✅ `/create-workstream [feature-name]` has been run
2. ✅ `/create-batch-execution-plan [feature-name]` has been run
3. ✅ Design doc is available with API contracts/specifications

---

## Instructions

### 1. Switch to Plan Mode

This command should run in **Plan mode** for collaborative specification design:

```
/plan
```

Plan mode ensures:
- Read-only exploration of design docs
- Collaborative discussion of specifications
- No premature implementation

### 2. Read Required Inputs

**a. Read the Batch Execution Plan:**
```
docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md
```

Extract for the specified batch:
- Task IDs and descriptions
- Dependencies
- Files to create/modify

**b. Read the Workstream:**
```
docs/workstreams/[feature-name]/WORKSTREAM.md
```

Extract:
- Task details and acceptance criteria
- Validation mapping (which demos/user journey steps)

**c. Read the Design Doc:**
```
[path from WORKSTREAM.md metadata]
```

Extract:
- API contracts (endpoints, request/response schemas)
- Data model specifications
- Protocol specifications (if applicable)
- Technical requirements

### 3. Create Specs Directory

```bash
mkdir -p docs/workstreams/[feature-name]/specs
```

### 4. For Each Task in the Batch

Generate a specification file using the template patterns.

**Determine spec type based on task:**

| Task Type | Spec Sections Needed |
|-----------|---------------------|
| API Endpoint | API Contract, Test Endpoint Mapping, Error Responses |
| Data Model | Data Model Specification, Database Table (if persistent) |
| Service/Handler | Protocol Specification, Message Format |
| Middleware | Technical Requirements, Integration Points |
| UI Component | Component Specification, Interface Contract, Usage Examples |
| Demo Script | Component Specification, CLI Interface, Step Handlers |
| Documentation/README | N/A (skip spec, use ticket directly) |

### 5. Generate Specification File

Create `docs/workstreams/[feature-name]/specs/[WS-ID]-spec.md`:

```markdown
# Task Specification: [WS-ID] [Task Name]

> **IMMUTABLE AFTER DESIGN APPROVAL**
> 
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** [Design Doc Section Reference]

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | [WS-ID] |
| **Task Name** | [Name] |
| **Type** | API Endpoint / Data Model / Service / Protocol |
| **Service** | [deeptrail-control / deeptrail-gateway / SDK] |
| **Validates** | [Demo X, User Journey Step Y] |

---

## API Contract (if applicable)

### Endpoint Definition

| Field | Value |
|-------|-------|
| **Method** | `POST` / `GET` / `PUT` / `DELETE` |
| **Path** | `/api/v1/exact/path/here` |
| **Auth** | Bearer token / JWT / None |
| **Content-Type** | `application/json` |

### Request Schema

```json
{
  "field_name": "type - description",
  "optional_field?": "type - description"
}
```

### Response Schema (Success - 200/201)

```json
{
  "field_name": "type - description"
}
```

### Error Responses

| Status | Condition | Response Body |
|--------|-----------|---------------|
| 400 | [condition] | `{"error": "code", "message": "..."}` |
| 401 | [condition] | `{"error": "unauthorized"}` |
| 404 | [condition] | `{"error": "not_found"}` |

---

## Data Model Specification (if applicable)

### Model: `[ModelName]`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | `str` | Yes | UUID | Primary key |
| `created_at` | `datetime` | Yes | NOW() | Creation timestamp |
| `field_name` | `type` | Yes/No | value | Description |

### Relationships

| Relationship | Target | Type | Description |
|--------------|--------|------|-------------|
| `user` | `User` | Many-to-One | Owner |

### Indexes

| Name | Columns | Type | Purpose |
|------|---------|------|---------|
| `idx_[name]` | `[columns]` | B-tree | [purpose] |

---

## Protocol Specification (if applicable)

### Message Format

```json
{
  "jsonrpc": "2.0",
  "method": "exact/method/name",
  "params": {
    "field": "type - description"
  },
  "id": "request-id"
}
```

### Protocol Sequence

```
┌────────┐                    ┌────────┐
│ Client │                    │ Server │
└───┬────┘                    └───┬────┘
    │                             │
    │  1. [Message Type]          │
    │ ───────────────────────────>│
    │                             │
    │  2. [Response Type]         │
    │ <───────────────────────────│
    │                             │
```

### State Transitions

| Current State | Event | Next State | Side Effects |
|---------------|-------|------------|--------------|
| [state] | [event] | [state] | [effects] |

---

## Component Specification (for UI/Demo tasks)

### Class/Module: `[ComponentName]`

| Field | Value |
|-------|-------|
| **Module** | `[package.module]` |
| **Type** | Class / Function / Dataclass |
| **Purpose** | [brief description] |

### Interface Contract

```python
@dataclass
class ComponentName:
    """[Docstring describing the component]."""
    
    field_name: type  # Description
    optional_field: type | None = None  # Description
    
    def method_name(self, arg: type) -> return_type:
        """[Method description]."""
        ...
```

### Public Methods

| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `method_name` | `arg: type` | `return_type` | [description] |

### Usage Example

```python
# Example usage of this component
component = ComponentName(field="value")
result = component.method_name(arg)
```

### Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| `[module]` | Internal | [purpose] |
| `[package]` | External | [purpose] |

### CLI Interface (for demo scripts)

```bash
# Command-line usage
python script.py [OPTIONS]

Options:
  --option-name VALUE    Description [default: value]
  --flag                 Description
  -h, --help            Show help message
```

---

## Technical Requirements

### Framework-Specific

| Requirement | Pattern | Why |
|-------------|---------|-----|
| Async fixtures | `@pytest_asyncio.fixture` | Async generators require pytest-asyncio |
| HTTP client | `httpx.AsyncClient` | Project standard |
| Pydantic models | `BaseModel` with `Field()` | Validation and docs |

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| [package] | [version] | [purpose] |

### Service Dependencies

| Service | Endpoint | Required For |
|---------|----------|--------------|
| [service] | [url] | [functionality] |

---

## File Location Rules

| Artifact | Correct Location | Notes |
|----------|------------------|-------|
| Implementation | `[service]/app/[module]/` | FastAPI `app/` prefix |
| Unit tests | `[service]/tests/[module]/` | Co-located |
| E2E tests | `tests/e2e/` (ROOT) | Cross-service |

---

## Test Endpoint Mapping

> **CRITICAL**: Tests MUST use these exact endpoints.

| Test Case | Method | Endpoint | Expected Status | Notes |
|-----------|--------|----------|-----------------|-------|
| Happy path | [method] | `/api/v1/exact/path` | 200 | |
| Invalid input | [method] | `/api/v1/exact/path` | 400 | Missing required field |
| Unauthorized | [method] | `/api/v1/exact/path` | 401 | No/invalid token |
| Not found | [method] | `/api/v1/exact/path` | 404 | Resource doesn't exist |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] Endpoint path matches spec exactly
- [ ] Request schema matches spec (field names, types, required)
- [ ] Response schema matches spec
- [ ] Error responses match spec (status codes, body format)
- [ ] Tests use correct endpoint paths from spec
- [ ] Framework requirements met (async fixtures, etc.)
- [ ] Files in correct location

---

## References

- **Design Doc Section:** [section reference]
- **Related Specs:** [list related spec files]
- **Upstream Dependencies:** [list WS-IDs]
- **Downstream Dependents:** [list WS-IDs that use this]
```

### 6. Update Workstream to Link Specs

Add to `WORKSTREAM.md`:

```markdown
## Specifications

| Task ID | Spec | Status |
|---------|------|--------|
| [WS-ID] | [specs/WS-ID-spec.md](./specs/WS-ID-spec.md) | ✅ Created |
```

### 7. Update STATUS.md

Add to the "Batch Progress" section:

```markdown
### Batch [N] Specifications
- [x] Specs created for all tasks
- [ ] Specs reviewed and approved
```

---

## Template Location

`docs/workstreams/TASK_SPEC_TEMPLATE.md`

---

## Output Format

After creating specifications, output:

```markdown
## Task Specifications Created: Batch [N]

### Specs Generated

| Task ID | Spec File | Type | Status |
|---------|-----------|------|--------|
| [WS-ID] | `specs/[WS-ID]-spec.md` | [API/Model/Protocol] | ✅ Created |
| [WS-ID] | `specs/[WS-ID]-spec.md` | [API/Model/Protocol] | ✅ Created |

### Spec Directory
```
docs/workstreams/[feature-name]/specs/
├── WS-A1-spec.md      ✅ Created
├── WS-A2-spec.md      ✅ Created
└── WS-C1-spec.md      ✅ Created
```

### Key Contracts Defined

**API Endpoints:**
| Endpoint | Method | Task |
|----------|--------|------|
| `/api/v1/path` | POST | WS-A1 |

**Data Models:**
| Model | Fields | Task |
|-------|--------|------|
| `ModelName` | id, name, ... | WS-A2 |

### Next Steps
1. Review specifications for accuracy
2. Get design approval if needed
3. Create task tickets: `/create-task-ticket [WS-ID] [feature-name]`

---

Specifications ready for task ticket creation.
```

---

## Spec Type Decision Tree

```
Is this task creating an API endpoint?
├── Yes → Include: API Contract, Test Endpoint Mapping, Error Responses
└── No
    │
    Is this task creating a data model?
    ├── Yes → Include: Data Model Specification, Relationships, Indexes
    └── No
        │
        Is this task creating a service/handler?
        ├── Yes → Include: Protocol Specification, State Transitions
        └── No
            │
            Is this task creating a UI component/demo script?
            ├── Yes → Include: Component Specification, Interface Contract
            └── No
                │
                Is this task for documentation/README only?
                ├── Yes → Skip spec (use task ticket directly)
                └── No → Include: Technical Requirements only
```

---

## When to Skip Specifications

Only documentation-only tasks skip formal specifications:

| Task Type | Skip Spec? | Reason |
|-----------|------------|--------|
| Documentation updates | ✅ Yes | No implementation contract |
| README/docs only | ✅ Yes | No implementation contract |
| Test documentation (e.g., `tests/e2e/README.md`) | ✅ Yes | No implementation contract |
| UI/Demo scripts | ❌ No | Needs component/interface spec for consistency |
| Refactoring | ❌ No | Document what changes |
| New API endpoint | ❌ No | Must define contract |
| New data model | ❌ No | Must define schema |
| New service | ❌ No | Must define interface |

**Rule of thumb:** If the task involves writing Python code, it needs a spec.

---

## Integration with Task Tickets

After creating specs, the `/create-task-ticket` command should:

1. **Reference the spec file:**
   ```markdown
   ## Specification
   
   > See full specification: [specs/WS-ID-spec.md](../specs/WS-ID-spec.md)
   ```

2. **Copy key contracts into ticket:**
   - Endpoint path and method
   - Key request/response fields
   - Critical test cases

3. **Link acceptance criteria to spec:**
   ```markdown
   ### Contract Verification (from spec)
   - [ ] Endpoint matches: `/api/v1/exact/path`
   - [ ] Response schema matches spec
   ```

---

## Example: Interactive Demo (Specs Required for Consistency)

For the interactive demo workstream, tasks define Python classes/components:

```
Batch 1: A1 (personas), A2 (context), C1 (api_client)
         └── These are Python dataclasses and classes
         └── Create specs for interface contracts and consistency
```

**Spec content for UI/demo tasks:**
- `A1 (personas)`: Persona dataclass fields, PERSONAS dict structure
- `A2 (context)`: DemoContext dataclass fields, methods
- `C1 (api_client)`: APIClient class interface, methods, usage

```bash
# Create specs for Batch 1
/plan
/create-task-spec 1 interactive-demo
```

---

## Example: API Workstream (Specs Required)

For API-heavy workstreams like `virtual-mcp-server-mvp`:

```
Batch 4: C1 (agent challenge endpoint), C2 (verify endpoint)
         └── These are API endpoints
         └── Create specs: /create-task-spec 4 virtual-mcp-server-mvp
```

---

## Related Commands

| Command | Purpose |
|---------|---------|
| `/create-batch-execution-plan` | Provides batch/task info (input) |
| `/create-workstream` | Provides workstream context (input) |
| `/create-task-ticket` | Uses specs to create full tickets (output) |
| `/execute-task` | Implements against the spec |

---

## Mode Reminder

**Always run this command in Plan mode:**

```
/plan
```

This ensures collaborative specification design before implementation begins.
