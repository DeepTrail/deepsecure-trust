# Task: [WS-ID] [Task Name]

> **Status:** `ready`
> **Batch:** [Batch number]
> **Worktree:** [vmcp-control / vmcp-gateway / both]

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | [WS-ID] |
| **Workstream** | [Workstream letter and name, e.g., "E (Vault & Credential Storage)"] |
| **Phase** | [Phase, e.g., "P1 (Real Backend Integration)"] |
| **Dependencies** | [Task IDs, or "None"] |
| **Complexity** | `S` (< 1hr) / `M` (1-3hr) / `L` (3+ hr) |
| **Service** | [deeptrail-control / deeptrail-gateway / SDK] |
| **Validates** | [What demo/user journey step this validates] |

---

## Specification

> See full specification: [../specs/[WS-ID]-spec.md](../specs/[WS-ID]-spec.md)

### Key Contracts

**[For API tasks - include endpoint summary table]:**
| Field | Value |
|-------|-------|
| **Method** | `POST` / `GET` / `PUT` / `DELETE` |
| **Path** | `/api/v1/exact/path/from/design` |
| **Auth** | Bearer token / JWT / None |

**Response (Success):**
```json
{
  "field": "type - description"
}
```

**Error Responses:**
| Status | Condition |
|--------|-----------|
| 400 | [condition] |
| 401 | [condition] |
| 404 | [condition] |

**[For non-API tasks - include method/interface summary]:**
| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `method_name` | `arg: type` | `return_type` | [description] |

---

## API Contracts

> **MANDATORY SECTION** - Include for ALL task tickets.

### [For tasks WITH API endpoints]

**Endpoint: [Endpoint Name]**

| Field | Value |
|-------|-------|
| **Method** | `GET` / `POST` / `PUT` / `DELETE` |
| **Path** | `/api/v1/exact/path/{param}` |
| **Auth** | [Auth type] |
| **Purpose** | [Brief description] |

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `param` | string | [description] |

**Request Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Bearer <token>` |

**Request Body (if applicable):**
```json
{
  "field": "value"
}
```

**Success Response (200):**
```json
{
  "field": "value"
}
```

**Error Responses:**
| Status | Error | Condition |
|--------|-------|-----------|
| 400 | `bad_request` | [condition] |
| 401 | `unauthorized` | [condition] |
| 404 | `not_found` | [condition] |

### [For tasks WITHOUT API endpoints]

> **Note:** This task implements an internal module/service, not API endpoints.
> [Brief explanation of what the task creates and why it has no API.]
> See [WS-XX] for related API endpoints.

---

## Pre-Conditions

- [x] [Dependency task] complete
- [x] [Required service/module] exists
- [x] [Other prerequisites]

---

## Task Description

### Objective

[One-sentence description of what this task accomplishes]

### Background

[2-4 sentences explaining:]
- Why this task is needed
- What problem it solves
- How it fits into the larger system

### What to Implement

1. **[Component 1]**:
   - [Details]

2. **[Component 2]**:
   - [Details]

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `[service]/app/[module]/[file].py` | Create | [purpose] |
| `[service]/tests/[module]/test_[file].py` | Create | Unit tests |
| `[service]/app/api/v1/api.py` | Modify | Register router (if API) |

---

## Acceptance Criteria

### Functional Criteria
- [ ] [Specific, measurable criterion 1]
- [ ] [Specific, measurable criterion 2]
- [ ] [Specific, measurable criterion 3]

### Security Criteria (if applicable)
- [ ] [Security requirement]

### Integration Criteria
- [ ] [Integration requirement]

### Contract Verification (REQUIRED for API tasks)
- [ ] Endpoint path matches spec: `[path from spec]`
- [ ] Response schema matches spec
- [ ] Error responses match spec

---

## Test Cases

| Test Case | Method | Endpoint/Module | Expected Status | Notes |
|-----------|--------|-----------------|-----------------|-------|
| Happy path | [METHOD] | `/api/v1/path` or `module.method` | 200 or Success | [notes] |
| Invalid input | [METHOD] | `/api/v1/path` or `module.method` | 400 or Error | [notes] |
| Unauthorized | [METHOD] | `/api/v1/path` or `module.method` | 401 or Error | [notes] |
| Not found | [METHOD] | `/api/v1/path` or `module.method` | 404 or Error | [notes] |

---

## Post-Conditions

After this task is complete:
- [ ] [Downstream task] unblocked
- [ ] [Feature/capability] enabled
- [ ] [Integration point] available

---

## Validation

### Unit Tests
```bash
cd [service-directory]
pytest tests/[module]/test_[file].py -v
```

### Manual Verification
```bash
# 1. [First verification step]
[command]
# Expected: [expected output]

# 2. [Second verification step]
[command]
# Expected: [expected output]
```

---

## References

- **Specification:** [../specs/[WS-ID]-spec.md](../specs/[WS-ID]-spec.md)
- **Design Doc:** [link to design doc]
- **Upstream:** [WS-XX] ([task name]) - [status]
- **Downstream:** [WS-YY] ([task name])
- **Related Code:**
  - `[service]/app/[module]/[file].py`
  - `[service]/app/[other_module]/[other_file].py`

---

## Execution

```bash
# Run in [worktree-name] worktree:
cd [worktree-path]
/execute-task [WS-ID] [feature-name]

# Complete this task:
/complete-task [WS-ID] [feature-name]
```

---

## Template Section Reference

> **MANDATORY SECTIONS** - All task tickets MUST include these sections:

| Section | Purpose | Notes |
|---------|---------|-------|
| **Metadata** | Task identification and categorization | Always first after title |
| **Specification** | Key contracts from spec file | Reference spec, include key details |
| **API Contracts** | API endpoint details OR "no API" note | MANDATORY - see format below |
| **Pre-Conditions** | What must be complete before starting | Checklist format |
| **Task Description** | Objective + Background + What to Implement | Always include all 3 subsections |
| **Files to Create/Modify** | Table of files to touch | Include Action column |
| **Acceptance Criteria** | Functional + Security + Integration criteria | Checklist format |
| **Test Cases** | Test case table | Include all expected test scenarios |
| **Post-Conditions** | What this task enables/unblocks | Checklist format |
| **Validation** | Unit Tests + Manual Verification | MUST have both subsections |
| **References** | Spec, design doc, upstream/downstream | Link format |
| **Execution** | Commands to run task | Copy-paste ready |

### API Contracts Section Format

**For tasks WITH API endpoints:**
```markdown
## API Contracts

### Endpoint: [Name]
| Field | Value |
|-------|-------|
| **Method** | `GET` / `POST` |
| **Path** | `/api/v1/path` |
| **Auth** | [Auth type] |

[Include request/response schemas and error table]
```

**For tasks WITHOUT API endpoints:**
```markdown
## API Contracts

> **Note:** This task implements an internal module/service, not API endpoints.
> [Brief explanation of what the task creates.]
> See [WS-XX] for related API endpoints.
```

### Validation Section Format

```markdown
## Validation

### Unit Tests
\`\`\`bash
cd [service-directory]
pytest tests/[module]/test_[file].py -v
\`\`\`

### Manual Verification
\`\`\`bash
# 1. [Verification step]
[command]
# Expected: [output]
\`\`\`
```
