# Task: D1 Implement Step Handlers

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | D1 |
| **Status** | `pending` |
| **Dependencies** | A1 ✅ (Persona), A2 ✅ (DemoContext), B1 ✅ (PromptUI), B2 (RoleSwitcher), C1 ✅ (APIClient) |
| **Complexity** | L (Large) - Largest task in workstream |
| **Batch** | 3 |
| **Wave** | 2 (after B2) |
| **Worktree** | deepsecure-mvp (main repo) |

---

## Specification

> See full specification: [D1-spec.md](../specs/D1-spec.md)

### Key Contracts

| Contract | Value |
|----------|-------|
| **Module** | `demos.interactive.step_handlers` |
| **Type** | Handler functions + registry |
| **File** | `demos/interactive/step_handlers.py` |
| **Pattern** | Function registry with async handlers |

### Handler Registry

```python
StepHandler = Callable[[DemoContext], Awaitable[None]]

STEP_HANDLERS: dict[int, StepHandler] = {
    1: handle_step_1_org_setup,
    2: handle_step_2_install_sdk,
    3: handle_step_3_connect_tools,
    4: handle_step_4_create_agent,
    5: handle_step_5_register_agent,
    6: handle_step_6_grant_permissions,
    7: handle_step_7_make_api_calls,
    8: handle_step_8_agent_runtime,
    9: handle_step_9_credential_rotation,
    10: handle_step_10_audit_review,
}
```

---

## Pre-Conditions

- [x] A1 complete: `demos/interactive/personas.py` exists with Persona, PERSONAS, get_persona
- [x] A2 complete: `demos/interactive/context.py` exists with DemoContext
- [x] B1 complete: `demos/interactive/prompts.py` exists with PromptUI
- [ ] B2 complete: `demos/interactive/role_switcher.py` exists with RoleSwitcher
- [x] C1 complete: `demos/interactive/api_client.py` exists with APIClient

---

## Task Description

Create the `step_handlers.py` module containing all 10 step handler functions for Sarah's Journey demo.

### 1. Create the Module

Create `demos/interactive/step_handlers.py` with:
- StepHandler type alias
- STEP_HANDLERS registry dict
- All 10 handler functions

### 2. Implement Handler Registry

```python
from typing import Callable, Awaitable
from demos.interactive.context import DemoContext

StepHandler = Callable[[DemoContext], Awaitable[None]]

STEP_HANDLERS: dict[int, StepHandler] = {
    1: handle_step_1_org_setup,
    # ... all 10 handlers
}
```

### 3. Implement All 10 Step Handlers

Each handler must be `async def` and accept `DemoContext`:

| Step | Function | Primary Persona | Key Actions |
|------|----------|-----------------|-------------|
| 1 | `handle_step_1_org_setup` | IT Admin | Create org/project |
| 2 | `handle_step_2_install_sdk` | Sarah | Show SDK installation |
| 3 | `handle_step_3_connect_tools` | Sarah | Multi-select tools, store creds |
| 4 | `handle_step_4_create_agent` | Sarah + Vendor | Create agent, split view |
| 5 | `handle_step_5_register_agent` | Sarah + Vendor | Agent challenge/verify |
| 6 | `handle_step_6_grant_permissions` | Sarah + Vendor | Multi-select perms, split view |
| 7 | `handle_step_7_make_api_calls` | Sarah | Gateway proxy request |
| 8 | `handle_step_8_agent_runtime` | Agent | Agent perspective, cred fetch |
| 9 | `handle_step_9_credential_rotation` | Sarah + Vendor | Trigger rotation |
| 10 | `handle_step_10_audit_review` | All 5 | Round-robin review |

---

## Step Details

### Step 1: Organization Setup (IT Admin)

```python
async def handle_step_1_org_setup(ctx: DemoContext) -> None:
    """Handle step 1: Organization Setup."""
    # 1. Switch to IT Admin
    # 2. Confirm org name via ui.select()
    # 3. API call: POST /api/v1/organizations
    # 4. Store ctx.org_id, ctx.org_name
```

### Step 2: Install SDK (Sarah)

```python
async def handle_step_2_install_sdk(ctx: DemoContext) -> None:
    """Handle step 2: Install SDK."""
    # 1. Switch to Sarah
    # 2. Show SDK installation commands
    # 3. Confirm completion
```

### Step 3: Connect External Tools (Sarah)

```python
async def handle_step_3_connect_tools(ctx: DemoContext) -> None:
    """Handle step 3: Connect External Tools."""
    # 1. Switch to Sarah
    # 2. Multi-select tools (OpenAI, GitHub, Slack, etc.)
    # 3. API calls to store credentials
    # 4. Store ctx.connected_services
```

### Step 4: Create Agent Identity (Split View)

```python
async def handle_step_4_create_agent(ctx: DemoContext) -> None:
    """Handle step 4: Create Agent Identity."""
    # 1. Sarah's view: select agent name
    # 2. API call: POST /api/v1/agents
    # 3. Store ctx.agent_id
    # 4. Vendor's view: show new agent appeared
```

### Step 5: Register Agent (Split View)

```python
async def handle_step_5_register_agent(ctx: DemoContext) -> None:
    """Handle step 5: Register Agent."""
    # 1. Show cryptographic handshake
    # 2. Agent challenge/verify flow
    # 3. Both perspectives observe
```

### Step 6: Grant Permissions (Split View)

```python
async def handle_step_6_grant_permissions(ctx: DemoContext) -> None:
    """Handle step 6: Grant Permissions."""
    # 1. Sarah multi-selects permissions
    # 2. API call: Create and attach policy
    # 3. Store ctx.delegated_permissions
    # 4. Vendor sees permissions granted
```

### Step 7: Make API Calls (Sarah)

```python
async def handle_step_7_make_api_calls(ctx: DemoContext) -> None:
    """Handle step 7: Make API Calls."""
    # 1. Select API to call
    # 2. Gateway proxy request
    # 3. Show request/response
```

### Step 8: Agent Runtime (Agent)

```python
async def handle_step_8_agent_runtime(ctx: DemoContext) -> None:
    """Handle step 8: Agent Runtime."""
    # 1. Switch to Agent persona
    # 2. Show credential bootstrap
    # 3. Agent token exchange
    # 4. External API call through gateway
```

### Step 9: Credential Rotation (Split View)

```python
async def handle_step_9_credential_rotation(ctx: DemoContext) -> None:
    """Handle step 9: Credential Rotation."""
    # 1. Trigger rotation
    # 2. Show both Sarah and Vendor perspectives
    # 3. Demonstrate zero-downtime rotation
```

### Step 10: Audit Review (Round-Robin)

```python
async def handle_step_10_audit_review(ctx: DemoContext) -> None:
    """Handle step 10: Audit Review."""
    # 1. Fetch audit log
    # 2. Round-robin through all 5 personas
    # 3. Each provides their insight
    # 4. Store ctx.audit_events
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `demos/interactive/step_handlers.py` | Create | All 10 step handlers + registry |
| `demos/interactive/__init__.py` | Modify | Export STEP_HANDLERS |

---

## Acceptance Criteria

### Handler Registry
- [ ] `STEP_HANDLERS` dict contains all 10 handlers (keys 1-10)
- [ ] `StepHandler` type alias defined
- [ ] All handlers accessible via `STEP_HANDLERS[step_num]`

### Handler Signatures
- [ ] All handlers are `async def`
- [ ] All handlers accept `DemoContext` parameter
- [ ] All handlers return `None`
- [ ] All handlers have docstrings
- [ ] All handlers have type hints

### Per-Step Verification
- [ ] Step 1: Creates org, switches to IT Admin, stores ctx.org_id
- [ ] Step 2: Shows SDK installation, Sarah persona
- [ ] Step 3: Multi-select tools, stores ctx.connected_services
- [ ] Step 4: Creates agent, split view with vendor
- [ ] Step 5: Agent registration challenge/verify
- [ ] Step 6: Multi-select permissions, split view
- [ ] Step 7: Gateway proxy request
- [ ] Step 8: Agent perspective, credential fetch
- [ ] Step 9: Credential rotation, split view
- [ ] Step 10: Round-robin audit review all 5 personas

### Integration
- [ ] Handlers use `ctx.switcher` for role changes
- [ ] Handlers use `ctx.ui` for prompts and display
- [ ] Handlers use `ctx.api` for HTTP requests
- [ ] Handlers update `ctx` state fields correctly

### Code Quality
- [ ] Ruff check passes
- [ ] All imports resolve correctly
- [ ] No circular imports

---

## Post-Conditions

After this task:
- All 10 step handlers implemented and registered
- E1 (main entry point) can orchestrate the full demo flow
- Complete interactive journey is executable

---

## Validation Mapping

| Validates | Description |
|-----------|-------------|
| **Demo** | Complete Sarah's Journey interactive flow |
| **Steps** | All 10 steps from org setup to audit review |
| **Personas** | All 5 personas participate correctly |
| **Split Views** | Steps 4, 5, 6, 9 show multiple perspectives |

---

## Test Commands

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp

# Verify import works
python -c "from demos.interactive.step_handlers import STEP_HANDLERS; print(f'✅ {len(STEP_HANDLERS)} handlers registered')"

# Verify all handlers are async
python -c "
import asyncio
from demos.interactive.step_handlers import STEP_HANDLERS

for step, handler in STEP_HANDLERS.items():
    assert asyncio.iscoroutinefunction(handler), f'Step {step} handler is not async'
print('✅ All handlers are async')
"

# Verify handler signatures
python -c "
import inspect
from demos.interactive.step_handlers import STEP_HANDLERS

for step, handler in STEP_HANDLERS.items():
    sig = inspect.signature(handler)
    params = list(sig.parameters.keys())
    assert 'ctx' in params, f'Step {step} missing ctx parameter'
print('✅ All handlers have ctx parameter')
"
```

---

## Execution Command

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/execute-task D1 interactive-demo
```

---

## References

- **Design Doc:** Interactive Demo Plan
- **Specification:** [D1-spec.md](../specs/D1-spec.md)
- **Dependencies:** A1, A2, B1, B2, C1
- **Downstream:** E1 (main entry point uses STEP_HANDLERS)
