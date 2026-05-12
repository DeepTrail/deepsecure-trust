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

Downstream consumers of task specs:
  /create-task-ticket, /execute-task, /complete-task
```

## Quality Bar

The quality bar is set by these proven gold-standard task specs:

- `docs/workstreams/idp-enhanced-sso/specs/WS-A1-spec.md` — Config field: Existing Pattern, Field Contract
- `docs/workstreams/idp-enhanced-sso/specs/WS-B1-spec.md` — Data model: Full Alembic migration (upgrade/downgrade code), Encryption Pattern
- `docs/workstreams/idp-enhanced-sso/specs/WS-D1-spec.md` — Config modification: Existing Pattern reference, Config Field Summary
- `docs/workstreams/interactive-demo/specs/A1-spec.md` — Dataclass component: Step-to-Persona Mapping, Helper Functions, 227 lines
- `docs/workstreams/interactive-demo/specs/C1-spec.md` — Async HTTP client: Display Format Examples, URL Resolution logic, 390 lines
- `docs/workstreams/mvp-production-readiness/specs/WS-E3-spec.md` — API endpoint: Implementation Notes (Service Flow), Files to Create/Modify
- `docs/workstreams/mvp-production-readiness/specs/WS-H1-spec.md` — Middleware: Cross-file JWT Threading, Error Handling Matrix, Constructor/Method Changes, 304 lines

**Read at least 2-3 of these before writing your first spec.** If your spec is shorter or less detailed
than the relevant gold-standard example, add more detail.

## Usage

```
/create-task-spec [batch-id] [feature-name]
```

**Parameters:**
- `[batch-id]`: Which batch to create specs for (e.g., `P0-B1`, `P1-B2`)
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

    /plan

Plan mode ensures:
- Read-only exploration of design docs
- Collaborative discussion of specifications
- No premature implementation

### 2. Read Required Inputs

**a. Read the Batch Execution Plan:**

    docs/workstreams/[feature-name]/BATCH_EXECUTION_PLAN.md

Extract for the specified batch:
- Task IDs and descriptions
- Dependencies and complexity
- Files to create/modify

**b. Read the Workstream:**

    docs/workstreams/[feature-name]/WORKSTREAM.md

Extract:
- Task details and acceptance criteria
- Validation mapping (which demos/user journey steps)

**c. Read the Design Doc:**

    [path from WORKSTREAM.md metadata]

Extract:
- API contracts (endpoints, request/response schemas)
- Data model specifications
- Protocol specifications (if applicable)
- Technical requirements

**d. Explore the codebase for existing patterns (CRITICAL):**

For each task, BEFORE writing the spec, grep/read the relevant source files to identify:
- Existing classes, functions, or modules the task modifies or extends
- Code conventions (naming, import patterns, base classes used)
- Similar implementations that the new code should follow

This is what produces the "Existing Pattern" section in gold-standard specs.

### 3. Create Specs Directory

```bash
mkdir -p docs/workstreams/[feature-name]/specs
```

### 4. For Each Task in the Batch

Generate a specification file using the template patterns.

**Determine spec type based on task:**

| Task Type | Spec Sections Needed |
|-----------|---------------------|
| API Endpoint | API Contract (with Request Headers), Test Endpoint Mapping, Error Responses, Implementation Notes |
| Data Model | Data Model Specification, Alembic Migration, Encryption/Security Pattern |
| Service/Handler | Protocol Specification, Error Handling Matrix, Cross-File Flow |
| Middleware | Existing Pattern, Constructor/Method Changes, Error Handling Matrix, Cross-File Flow |
| Config Change | Existing Pattern, Field Contract, Environment Variables |
| React Component | Frontend Component Spec (Props, Hooks, Route), Visual Examples |
| Next.js Route | Route Spec (SSR/SSG, Auth, Layout), BFF Contract |
| Demo Script | Component Specification, CLI Interface, Step Handlers, Display Format Examples |
| Documentation/README | N/A (skip spec, use ticket directly) |

**Determine whether the task CREATES or MODIFIES:**

| Task Action | Additional Sections Required |
|-------------|----------------------------|
| Creates new code | Interface Contract, Full class/function spec |
| Modifies existing code | Existing Pattern, Constructor/Method Signature Changes (showing `# NEW` markers) |
| Wires/integrates components | Cross-File Implementation Flow, Error Handling Matrix |

### 5. Generate Specification File

Create `docs/workstreams/[feature-name]/specs/[WS-ID]-spec.md` using the comprehensive template
below. **Include ALL applicable sections.** Omit sections only when clearly N/A with a brief note.

---

## Spec Template

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
    | **Type** | API Endpoint / Data Model / Service / Config / React Component / Route / Middleware |
    | **Service** | [deeptrail-control / deeptrail-gateway / SDK / frontend] |
    | **Complexity** | S (< 1hr) / M (1-3hr) / L (3+ hr) |
    | **Dependencies** | [WS-X, WS-Y or None] |
    | **Validates** | [Demo X, User Journey Step Y] |

    ---

    ## Existing Pattern (REQUIRED for modification tasks)

    > **CRITICAL**: Before specifying changes, document what currently exists.
    > This tells the implementer which conventions to follow.

    Describe the current codebase state that this task modifies:
    - What file(s) already exist
    - What classes/functions are already defined
    - What patterns/conventions are in use (base classes, naming, imports)
    - What similar implementations exist that should be followed

    ### Current Code Reference

    **File:** `[service]/[path/to/existing/file.py]` (modify)

    ```python
    # Show relevant existing code structure
    class ExistingClass(BaseClass):
        existing_field: type = Field(...)
        # ... existing fields ...
    ```

    ### Pattern to Follow

    Reference an existing implementation that uses the same pattern:
    - "Follow the `VaultToken` pattern from `deeptrail-control/app/models/vault_token.py`"
    - "Follow the `NotionConfig` pattern — extend `BackendAPIConfig`, set `base_url`, add `model_config`"
    - "Follow the `useAuth` hook pattern from `frontend/src/hooks/useAuth.ts`"

    ---

    ## API Contract (for API endpoint tasks)

    ### Endpoint Definition

    | Field | Value |
    |-------|-------|
    | **Method** | `POST` / `GET` / `PUT` / `DELETE` |
    | **Path** | `/api/v1/exact/path/here` |
    | **Auth** | Bearer token / Agent JWT / Internal API token / None |
    | **Content-Type** | `application/json` |

    ### Path Parameters (if applicable)

    | Parameter | Type | Required | Description |
    |-----------|------|----------|-------------|
    | `param_name` | `str` | Yes | Description |

    ### Request Headers

    > Include ALL headers, especially non-standard ones like `X-User-ID`.

    | Header | Required | Description |
    |--------|----------|-------------|
    | `Authorization` | Yes | `Bearer <token_type>` |
    | `Content-Type` | Yes | `application/json` |
    | `X-User-ID` | Conditional | Required for internal API calls |

    ### Request Schema

    ```json
    {
      "field_name": "type - description (required)",
      "optional_field": "type - description (optional, default: value)"
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
    | 403 | [condition] | `{"error": "forbidden", "message": "..."}` |
    | 404 | [condition] | `{"error": "not_found"}` |
    | 502 | [condition] | `{"error": "provider_error", "message": "..."}` |

    ---

    ## Data Model Specification (for data model tasks)

    ### Model: `[ModelName]`

    **File:** `[service]/app/models/[model_name].py` (create/modify)

    ```python
    class ModelName(Base):
        __tablename__ = "table_name"
    ```

    ### Columns

    | Column | SQLAlchemy Type | Python Type | Required | Default | Description |
    |--------|----------------|-------------|----------|---------|-------------|
    | `id` | `String(64)` | `str` | Yes (PK) | UUID | Primary key |
    | `created_at` | `DateTime(timezone=True)` | `datetime` | Yes | `func.now()` | Creation timestamp |
    | `field_name` | `Type` | `type` | Yes/No | value | Description |

    ### Relationships

    | Relationship | Target | Type | Description |
    |--------------|--------|------|-------------|
    | `user` | `User` | Many-to-One | Owner |

    ### Indexes

    | Name | Columns | Type | Purpose |
    |------|---------|------|---------|
    | `idx_[name]` | `[columns]` | B-tree / Unique B-tree | [purpose] |

    ### Encryption / Security Pattern (if applicable)

    Describe how sensitive fields are handled:
    - Encryption method (e.g., Fernet)
    - Where encryption/decryption occurs (model vs service layer)
    - Key source (e.g., `settings.VAULT_ENCRYPTION_KEY`)

    ### Helper Methods / Properties

    ```python
    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        ...

    @property
    def is_revoked(self) -> bool:
        """Check if session has been revoked."""
        ...
    ```

    ### Alembic Migration

    > **REQUIRED** for any new table or column change.

    **File:** `[service]/alembic/versions/xxx_[description].py` (create)

    #### upgrade()

    ```python
    def upgrade() -> None:
        op.create_table(
            "table_name",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("field", sa.Type(), nullable=False),
            # ... all columns ...
        )
        op.create_index("idx_name", "table_name", ["column"], unique=False)
    ```

    #### downgrade()

    ```python
    def downgrade() -> None:
        op.drop_index("idx_name", table_name="table_name")
        op.drop_table("table_name")
    ```

    ---

    ## Constructor / Method Signature Changes (for modification tasks)

    > **REQUIRED** when modifying existing classes. Show exact before/after with `# NEW` markers.

    ### Constructor Change

    ```python
    def __init__(
        self,
        existing_param: str,
        another_param: int = 10,
        new_param: str | None = None,  # NEW
    ):
    ```

    ### Method Signature Changes

    ```python
    # Before:
    async def existing_method(self, arg1: str) -> Result:

    # After:
    async def existing_method(
        self,
        arg1: str,
        new_arg: str | None = None,  # NEW — needed for [reason]
    ) -> Result:
    ```

    ### Module-Level Functions Update (if applicable)

    ```python
    def configure_component(
        existing_param: str,
        new_param: str | None = None,  # NEW
    ) -> Component:
    ```

    ---

    ## Cross-File Implementation Flow (for integration/middleware tasks)

    > **REQUIRED** when changes span multiple files. Show the numbered step-by-step flow.

    ### Step 1: [Description]

    **File:** `[service]/[path/to/file1.py]` (line ~NNN)

    ```python
    # What to add/change in this file
    request.state.new_value = extracted_value
    ```

    ### Step 2: [Description]

    **File:** `[service]/[path/to/file2.py]`

    ```python
    # How to thread the value through
    "new_value": getattr(request.state, "new_value", None),
    ```

    ### Step 3: [Description]

    **File:** `[service]/[path/to/file3.py]`

    ```python
    # How to consume the threaded value
    new_value = context.get("new_value")
    result = await service.method(arg=new_value)
    ```

    ---

    ## Error Handling Matrix (for service integration tasks)

    > **REQUIRED** when the component calls other services. Different from "Error Responses" —
    > this documents how YOUR component handles errors from ITS dependencies.

    | Dependency Response | Component Behavior | Result / Return Value |
    |--------------------|--------------------|----------------------|
    | 200 OK | Process normally | Success path |
    | 403 Forbidden | Log warning, return None | TOKEN_NOT_FOUND |
    | 404 Not Found | Log warning, return None | TOKEN_NOT_FOUND |
    | 5xx Server Error | Log error, return None | TOKEN_NOT_FOUND |
    | Timeout | Log error, return None | TOKEN_NOT_FOUND |
    | No credentials | Log error, skip call | TOKEN_NOT_FOUND |

    ---

    ## Implementation Notes (for complex tasks)

    > **REQUIRED** for any task with Complexity M or L. Shows the implementer HOW to wire things together.

    ### Service Flow

    ```python
    # Step-by-step implementation pseudocode:
    # 1. Get current state
    current = await service.get(id)

    # 2. Validate preconditions
    if not current.has_required_field:
        raise HTTPException(400, "missing_field")

    # 3. Call dependency
    result = await dependency_service.operation(
        param=current.field,
    )

    # 4. Update state
    await service.update(id, new_data=result)
    ```

    ### Key Implementation Decisions

    | Decision | Choice | Rationale |
    |----------|--------|-----------|
    | Auth type for this endpoint | Internal API token | Gateway-to-control only |
    | Error on missing token | Return None, not raise | Graceful degradation |

    ---

    ## Protocol Specification (for protocol/message tasks)

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

    ## Component Specification (for Python component/demo tasks)

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

    ### Helper Functions / Utility Methods

    > List helper functions that support the main interface but are also part of the public API.

    ```python
    def get_item(item_id: str) -> Item:
        """Get item by ID, raising KeyError if not found."""
        return ITEMS[item_id]

    def get_items_for_category(category: str) -> list[Item]:
        """Get all items in a given category."""
        return [i for i in ITEMS.values() if i.category == category]
    ```

    | Function | Arguments | Returns | Description |
    |----------|-----------|---------|-------------|
    | `get_item` | `item_id: str` | `Item` | Lookup by ID |
    | `get_items_for_category` | `category: str` | `list[Item]` | Filter by category |

    ### Domain-Specific Mapping Tables

    > Include any mapping tables that help the implementer understand the domain relationships.
    > Examples: step-to-persona, permission-to-role, route-to-page, service-to-scope.

    | Key | Value 1 | Value 2 | Description |
    |-----|---------|---------|-------------|
    | [domain key] | [mapping] | [mapping] | [description] |

    ### Usage Example

    ```python
    # Example usage of this component
    component = ComponentName(field="value")
    result = component.method_name(arg)
    ```

    ### Display Format Examples (for visual output tasks)

    > **REQUIRED** for any task that produces visible output (terminal, HTML, UI).
    > Show ASCII mockups of what the output should look like.

    ```
    ╭─────────────────────── POST /api/v1/auth/token ───────────────────────╮
    │ Headers:                                                               │
    │   Authorization: Bearer eyJ...                                         │
    │   Content-Type: application/json                                       │
    │                                                                        │
    │ Body:                                                                  │
    │ {                                                                      │
    │   "email": "sarah@acme.com",                                          │
    │   "password": "********"                                               │
    │ }                                                                      │
    ╰────────────────────────────────────────────────────────────────────────╯
    ```

    ### Dependencies

    | Dependency | Type | Purpose |
    |------------|------|---------|
    | `[module]` | Internal | [purpose] |
    | `[package]` | External | [purpose] |

    ### CLI Interface (for demo scripts)

    ```bash
    python script.py [OPTIONS]

    Options:
      --option-name VALUE    Description [default: value]
      --flag                 Description
      -h, --help            Show help message
    ```

    ---

    ## Frontend Component Specification (for React/Next.js tasks)

    > **REQUIRED** for any task creating or modifying React components, hooks, routes, or BFF endpoints.

    ### React Component: `[ComponentName]`

    | Field | Value |
    |-------|-------|
    | **File** | `frontend/src/[path]/[ComponentName].tsx` |
    | **Type** | Page Component / Layout / UI Component / Hook |
    | **Route** | `/dashboard/path` (if page) |
    | **SSR/SSG** | SSR with auth / SSG / Client-only |
    | **Auth Required** | Yes / No |
    | **Layout** | `DashboardLayout` / `AuthLayout` / `RootLayout` |

    ### Props Interface

    ```typescript
    interface ComponentNameProps {
      requiredProp: string;
      optionalProp?: number;
      onAction: (id: string) => void;
      children?: React.ReactNode;
    }
    ```

    ### Hooks Used

    | Hook | Purpose | Return Type |
    |------|---------|-------------|
    | `useAuth()` | Get current user session | `{ user, isLoading, error }` |
    | `useSWR(key)` | Fetch data with caching | `{ data, error, isLoading }` |

    ### BFF API Route (if component needs server data)

    | Field | Value |
    |-------|-------|
    | **File** | `frontend/src/app/api/[route]/route.ts` |
    | **Method** | `GET` / `POST` |
    | **Auth** | Session cookie (httpOnly) |
    | **Upstream** | `GET /api/v1/[control-plane-path]` |

    ```typescript
    // BFF route handler
    export async function GET(request: NextRequest) {
      const session = await getSession(request);
      if (!session) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

      const data = await controlPlaneClient.get("/api/v1/path", {
        headers: { Authorization: `Bearer ${session.token}` },
      });
      return NextResponse.json(data);
    }
    ```

    ### Visual Mockup / Layout

    > Show ASCII or describe the visual layout of the component.

    ```
    ┌─────────────────────────────────────────────────┐
    │ [Sidebar]  │  Page Title                        │
    │            │  ┌──────────────────────────────┐   │
    │  Dashboard │  │  Card 1          Card 2      │   │
    │  Agents    │  │  [metric]        [metric]    │   │
    │  Settings  │  │                               │   │
    │            │  ├──────────────────────────────┤   │
    │            │  │  Data Table                   │   │
    │            │  │  Row 1 | Col A | Col B        │   │
    │            │  │  Row 2 | Col A | Col B        │   │
    │            │  └──────────────────────────────┘   │
    └─────────────────────────────────────────────────┘
    ```

    ---

    ## Technical Requirements

    ### Framework-Specific (Python)

    | Requirement | Pattern | Why |
    |-------------|---------|-----|
    | Async fixtures | `@pytest_asyncio.fixture` | Async generators require pytest-asyncio |
    | HTTP client | `httpx.AsyncClient` | Project standard |
    | Pydantic models | `BaseModel` with `Field()` | Validation and docs |

    ### Framework-Specific (Frontend — if applicable)

    | Requirement | Pattern | Why |
    |-------------|---------|-----|
    | Data fetching | `useSWR` / `fetch` in server component | Next.js App Router |
    | Forms | React Hook Form + Zod validation | Project standard |
    | Styling | Tailwind CSS utility classes | Design system |
    | Testing | Vitest + React Testing Library | Component testing |
    | API mocking | MSW (Mock Service Worker) | Isolate from backend |

    ### Dependencies

    | Dependency | Version | Purpose |
    |------------|---------|---------|
    | [package] | [version] | [purpose] |

    ### Service Dependencies

    | Service | Endpoint | Required For |
    |---------|----------|--------------|
    | [service] | [url] | [functionality] |

    ---

    ## Files to Create/Modify

    > **REQUIRED** for every spec. List ALL files this task touches.

    | File | Action | Description |
    |------|--------|-------------|
    | `[service]/app/[path]/[file].py` | Create | New module |
    | `[service]/app/[path]/[file].py` | Modify | Add new method |
    | `[service]/app/models/__init__.py` | Modify | Add import |
    | `[service]/tests/[path]/test_[file].py` | Create | Unit tests |
    | `[service]/alembic/versions/xxx_[desc].py` | Create | Migration |

    ---

    ## File Location Rules

    | Artifact | Correct Location | Notes |
    |----------|------------------|-------|
    | Backend implementation | `[service]/app/[module]/` | FastAPI `app/` prefix |
    | Backend unit tests | `[service]/tests/[module]/` | Co-located |
    | Frontend components | `frontend/src/components/[domain]/` | Domain-grouped |
    | Frontend pages | `frontend/src/app/[route]/page.tsx` | Next.js App Router |
    | Frontend hooks | `frontend/src/hooks/` | Shared hooks |
    | Frontend tests | `frontend/src/__tests__/` or co-located | Vitest |
    | E2E tests | `tests/e2e/` (ROOT) | Cross-service |

    ---

    ## Test Endpoint Mapping

    > **CRITICAL**: Tests MUST use these exact endpoints.

    | Test Case | Method | Endpoint | Expected Status | Notes |
    |-----------|--------|----------|-----------------|-------|
    | Happy path | [method] | `/api/v1/exact/path` | 200 | |
    | Invalid input | [method] | `/api/v1/exact/path` | 400 | Missing required field |
    | Unauthorized | [method] | `/api/v1/exact/path` | 401 | No/invalid token |
    | Forbidden | [method] | `/api/v1/exact/path` | 403 | Insufficient permissions |
    | Not found | [method] | `/api/v1/exact/path` | 404 | Resource doesn't exist |
    | Provider error | [method] | `/api/v1/exact/path` | 502 | Upstream service failed |

    ---

    ## Contract Verification Checklist

    Before marking implementation complete, verify:

    - [ ] Endpoint path matches spec exactly
    - [ ] Request headers match spec (including non-standard headers)
    - [ ] Request schema matches spec (field names, types, required)
    - [ ] Response schema matches spec
    - [ ] Error responses match spec (status codes, body format)
    - [ ] Tests use correct endpoint paths from spec
    - [ ] Existing pattern/conventions followed
    - [ ] Framework requirements met (async fixtures, etc.)
    - [ ] Files in correct location per "Files to Create/Modify" table
    - [ ] Migration runs cleanly (if applicable): `alembic upgrade head` / `alembic downgrade -1`
    - [ ] All helper functions/properties implemented
    - [ ] Cross-file flow threaded correctly (if applicable)

    ---

    ## References

    - **Design Doc Section:** [section reference]
    - **Related Specs:** [list related spec files with links]
    - **Pattern:** [existing implementation to follow, e.g., "VaultToken model for encryption"]
    - **Upstream Dependencies:** [list WS-IDs]
    - **Downstream Dependents:** [list WS-IDs that use this]

---

### 6. Update Workstream to Link Specs

Add to `WORKSTREAM.md`:

    ## Specifications

    | Task ID | Spec | Status |
    |---------|------|--------|
    | [WS-ID] | [specs/WS-ID-spec.md](./specs/WS-ID-spec.md) | ✅ Created |

### 7. Update STATUS.md

Add to the "Batch Progress" section:

    ### Batch [N] Specifications
    - [x] Specs created for all tasks
    - [ ] Specs reviewed and approved

---

## Template Location

`docs/workstreams/TASK_SPEC_TEMPLATE.md`

---

## Output Format

After creating specifications, output:

    ## Task Specifications Created: Batch [N]

    ### Specs Generated

    | Task ID | Spec File | Type | Complexity | Status |
    |---------|-----------|------|------------|--------|
    | [WS-ID] | `specs/[WS-ID]-spec.md` | [API/Model/Protocol/Component] | S/M/L | ✅ Created |

    ### Spec Directory

    docs/workstreams/[feature-name]/specs/
    ├── WS-A1-spec.md      ✅ Created
    ├── WS-A2-spec.md      ✅ Created
    └── WS-C1-spec.md      ✅ Created

    ### Key Contracts Defined

    **API Endpoints:**
    | Endpoint | Method | Auth | Task |
    |----------|--------|------|------|
    | `/api/v1/path` | POST | Bearer JWT | WS-A1 |

    **Data Models:**
    | Model | Table | Fields | Migration | Task |
    |-------|-------|--------|-----------|------|
    | `ModelName` | `table_name` | id, name, ... | Yes | WS-A2 |

    **Frontend Components (if applicable):**
    | Component | Route | Type | Task |
    |-----------|-------|------|------|
    | `DashboardPage` | `/dashboard` | Page (SSR) | WS-F1 |

    ### Sections Verified

    | # | Section | Present In |
    |---|---------|------------|
    | 1 | Overview (with Complexity + Dependencies) | All specs |
    | 2 | Existing Pattern | Modification specs |
    | 3 | API Contract (with Request Headers) | API specs |
    | 4 | Data Model + Migration | Model specs |
    | 5 | Constructor/Method Changes | Modification specs |
    | 6 | Cross-File Flow | Integration specs |
    | 7 | Error Handling Matrix | Service integration specs |
    | 8 | Implementation Notes | M/L complexity specs |
    | 9 | Files to Create/Modify | All specs |
    | 10 | Contract Verification Checklist | All specs |

    ### Next Steps
    1. Review specifications for accuracy
    2. Get design approval if needed
    3. Create task tickets: `/create-task-ticket [WS-ID] [feature-name]`

    ---

    Specifications ready for task ticket creation.

---

## Spec Type Decision Tree

```
Is this task creating an API endpoint?
├── Yes → Include: API Contract (with Request Headers), Test Endpoint Mapping,
│         Error Responses, Implementation Notes
└── No
    │
    Is this task creating a data model?
    ├── Yes → Include: Data Model Specification, Alembic Migration (upgrade + downgrade),
    │         Indexes, Helper Properties, Encryption Pattern (if sensitive)
    └── No
        │
        Is this task modifying existing code?
        ├── Yes → Include: Existing Pattern, Constructor/Method Signature Changes
        │         (with # NEW markers)
        └── No
            │
            Is this task integrating/wiring components across files?
            ├── Yes → Include: Cross-File Implementation Flow (numbered steps per file),
            │         Error Handling Matrix
            └── No
                │
                Is this task creating a React/Next.js component?
                ├── Yes → Include: Frontend Component Spec (Props, Hooks, Route, Visual Mockup)
                └── No
                    │
                    Is this task creating a Python component/demo script?
                    ├── Yes → Include: Component Specification, Interface Contract,
                    │         Helper Functions, Display Format Examples, Domain Mapping Tables
                    └── No
                        │
                        Is this task for documentation/README only?
                        ├── Yes → Skip spec (use task ticket directly)
                        └── No → Include: Technical Requirements only
```

**IMPORTANT:** Many tasks fall into MULTIPLE categories. A middleware modification task may need:
Existing Pattern + Constructor Changes + Cross-File Flow + Error Handling Matrix + Implementation Notes.
Do NOT limit to a single branch — include all applicable sections.

---

## When to Skip Specifications

Only documentation-only tasks skip formal specifications:

| Task Type | Skip Spec? | Reason |
|-----------|------------|--------|
| Documentation updates | ✅ Yes | No implementation contract |
| README/docs only | ✅ Yes | No implementation contract |
| Test documentation (e.g., `tests/e2e/README.md`) | ✅ Yes | No implementation contract |
| UI/Demo scripts | ❌ No | Needs component/interface spec for consistency |
| React components | ❌ No | Must define props, hooks, route |
| Refactoring | ❌ No | Document what changes |
| New API endpoint | ❌ No | Must define contract |
| New data model | ❌ No | Must define schema + migration |
| New service | ❌ No | Must define interface |
| Config changes | ❌ No | Must define field contract + env vars |

**Rule of thumb:** If the task involves writing code (any language — Python, TypeScript, SQL), it needs a spec.

---

## Integration with Task Tickets

After creating specs, the `/create-task-ticket` command should:

1. **Reference the spec file:**

       ## Specification

       > See full specification: [specs/WS-ID-spec.md](../specs/WS-ID-spec.md)

2. **Copy key contracts into ticket:**
   - Endpoint path and method
   - Key request/response fields
   - Critical test cases
   - Files to create/modify table

3. **Link acceptance criteria to spec:**

       ### Contract Verification (from spec)
       - [ ] Endpoint matches: `/api/v1/exact/path`
       - [ ] Response schema matches spec
       - [ ] Existing pattern followed
       - [ ] Migration runs cleanly

---

## ⚠️ Common Rationalizations (REJECT These)

| Rationalization | Why It's Wrong |
|----------------|----------------|
| "This task is simple, no spec needed" | Simple tasks still need field contracts and file locations |
| "The design doc already has the contract" | Specs extract and pin the EXACT contract; design docs are narrative |
| "I'll just follow the existing code" | Document WHICH existing code to follow (Existing Pattern section) |
| "No API so no spec needed" | Config changes, models, components all need specs |
| "Frontend tasks don't need specs" | Props interfaces, route specs, and BFF contracts are specs |
| "I'll add the migration later" | Migration is part of the data model spec — include upgrade + downgrade |
| "Helper functions are obvious" | List them explicitly so downstream tasks can depend on them |

## 🚩 Red Flags Your Spec Is Missing Detail

- Spec is under 40 lines → Almost certainly missing sections
- No code examples → Missing Interface Contract or Implementation Notes
- "Files to Create/Modify" section missing → Implementer won't know where to put code
- Modification task with no "Existing Pattern" → Implementer will guess at conventions
- API spec with no "Request Headers" → Non-standard headers will be missed
- Integration task with no "Error Handling Matrix" → Error paths untested

---

## ⚠️ Verification Checklist (MANDATORY)

After creating all specs for a batch, verify completeness:

```bash
FEATURE="[feature-name]"
BATCH="[batch-id]"

echo "=== Spec File Verification ==="
ls docs/workstreams/${FEATURE}/specs/ 2>/dev/null | wc -l
echo "spec files created"

echo ""
echo "=== Per-Spec Section Verification ==="
for SPEC in docs/workstreams/${FEATURE}/specs/*-spec.md; do
  echo ""
  echo "--- $(basename $SPEC) ---"
  grep -q "## Overview" $SPEC && echo "✅ Overview" || echo "❌ MISSING Overview"
  grep -q "Complexity" $SPEC && echo "✅ Complexity in Overview" || echo "⚠️  Missing Complexity"
  grep -q "Dependencies" $SPEC && echo "✅ Dependencies in Overview" || echo "⚠️  Missing Dependencies"
  grep -q "## Existing Pattern\|## Current Code\|### Pattern to Follow" $SPEC && echo "✅ Existing Pattern" || echo "⚠️  No Existing Pattern (OK if new code)"
  grep -q "## API Contract\|## Data Model\|## Component Specification\|## Frontend Component\|## Protocol Specification" $SPEC && echo "✅ Main Spec Section" || echo "❌ MISSING Main Spec Section"
  grep -q "## Files to Create/Modify" $SPEC && echo "✅ Files to Create/Modify" || echo "❌ MISSING Files to Create/Modify"
  grep -q "## Contract Verification Checklist" $SPEC && echo "✅ Verification Checklist" || echo "❌ MISSING Verification Checklist"
  grep -q "## References" $SPEC && echo "✅ References" || echo "❌ MISSING References"
  grep -q "Implementation Notes\|Service Flow\|Implementation Flow" $SPEC && echo "✅ Implementation Notes" || echo "⚠️  No Implementation Notes (OK if Complexity S)"
  grep -q "Error Handling Matrix" $SPEC && echo "✅ Error Handling Matrix" || echo "⚠️  No Error Handling Matrix (OK if no service calls)"
  grep -q "Migration\|upgrade()\|downgrade()" $SPEC && echo "✅ Migration" || echo "⚠️  No Migration (OK if no DB changes)"
  LINES=$(wc -l < $SPEC)
  echo "📏 $LINES lines"
  [ $LINES -lt 40 ] && echo "🚩 WARNING: Spec under 40 lines — likely missing detail"
done

echo ""
echo "=== WORKSTREAM.md Spec Links ==="
grep -c "specs/.*-spec.md" docs/workstreams/${FEATURE}/WORKSTREAM.md
echo "spec links in WORKSTREAM.md"

echo "=== Complete ==="
```

---

## Example: Interactive Demo (Specs Required for Consistency)

For the interactive demo workstream, tasks define Python classes/components:

```
P0-B1: A1 (personas), A2 (context), C1 (api_client)
       └── These are Python dataclasses and classes
       └── Create specs for interface contracts and consistency
```

**Spec content for UI/demo tasks:**
- `A1 (personas)`: Persona dataclass fields, PERSONAS dict, Helper Functions, Step-to-Persona Mapping
- `A2 (context)`: DemoContext dataclass fields, methods, Dependencies
- `C1 (api_client)`: APIClient class interface, methods, Display Format Examples, URL Resolution

```bash
# Create specs for P0-B1
/plan
/create-task-spec P0-B1 interactive-demo
```

---

## Example: API Workstream (Specs Required)

For API-heavy workstreams like `virtual-mcp-server-mvp`:

```
P1-B1: C1 (agent challenge endpoint), C2 (verify endpoint)
       └── These are API endpoints
       └── Each spec includes: API Contract + Request Headers + Implementation Notes + Error Handling Matrix
       └── Create specs: /create-task-spec P1-B1 virtual-mcp-server-mvp
```

---

## Example: Frontend Architecture (Specs Required)

For frontend workstreams with React/Next.js:

```
P0-B1: F1 (Next.js scaffold), F2 (design tokens)
       └── F1 needs: Frontend Component Spec with project structure, route layout
       └── F2 needs: Component Spec with CSS variable contract, Tailwind config
       └── Create specs: /create-task-spec P0-B1 frontend-architecture
```

---

## Related Commands

| Command | Purpose |
|---------|---------|
| `/create-batch-execution-plan` | Provides batch/task info (input) |
| `/create-workstream` | Provides workstream context (input) |
| `/create-task-ticket` | Uses specs to create full tickets (output) |
| `/execute-task` | Implements against the spec |
| `/complete-task` | Verifies implementation matches spec |

---

## Mode Reminder

**Always run this command in Plan mode:**

    /plan

This ensures collaborative specification design before implementation begins.
