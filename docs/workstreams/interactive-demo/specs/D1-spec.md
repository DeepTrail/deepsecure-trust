# Task Specification: D1 Implement Step Handlers

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** Interactive Demo Plan - Step Handlers
>
> **Complexity:** L (Large) - This is the largest task in the workstream

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | D1 |
| **Task Name** | Implement all 10 step handlers |
| **Type** | Component (Handler Functions) |
| **Location** | `demos/interactive/step_handlers.py` |
| **Validates** | Complete interactive demo flow |

---

## Component Specification

### Module: `demos.interactive.step_handlers`

| Field | Value |
|-------|-------|
| **Module** | `demos.interactive.step_handlers` |
| **Type** | Handler functions + registry |
| **Purpose** | Implement each step of Sarah's Journey interactively |
| **Pattern** | Function registry with async handlers |

---

## Handler Registry

```python
from typing import Callable, Awaitable
from demos.interactive.context import DemoContext

# Type alias for step handlers
StepHandler = Callable[[DemoContext], Awaitable[None]]

# Registry mapping step numbers to handlers
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

## Step Handler Signatures

Each handler follows this pattern:

```python
async def handle_step_N_description(ctx: DemoContext) -> None:
    """Handle step N: [Step Title].
    
    [Description of what happens in this step]
    
    Args:
        ctx: DemoContext with current state, API client, UI, and role switcher
    """
    ...
```

---

## Step Definitions

### Step 1: Organization Setup (IT Admin)

| Field | Value |
|-------|-------|
| **Primary Persona** | IT Admin (Alex Martinez) |
| **Function** | `handle_step_1_org_setup` |
| **API Calls** | Create organization, Create project |
| **Interactive** | Confirm org/project names |

```python
async def handle_step_1_org_setup(ctx: DemoContext) -> None:
    """Handle step 1: Organization Setup.
    
    IT Admin sets up organization and project in DeepSecure.
    """
    # 1. Switch to IT Admin
    ctx.switcher.switch_to("it_admin", step=1, title="Organization Setup")
    
    # 2. Confirm org name
    org_name = ctx.ui.select(
        prompt="Organization name:",
        choices=["Acme Corp", "TechStart Inc", "Custom..."],
        default="Acme Corp",
    )
    
    # 3. API call: Create organization
    response = await ctx.api.request("POST", "/api/v1/organizations", json={"name": org_name})
    ctx.org_id = response.json()["id"]
    
    # 4. Create project
    # ...
```

---

### Step 2: Install SDK (Sarah)

| Field | Value |
|-------|-------|
| **Primary Persona** | Sarah Chen |
| **Function** | `handle_step_2_install_sdk` |
| **API Calls** | None (local setup) |
| **Interactive** | Show SDK installation, confirm |

---

### Step 3: Connect External Tools (Sarah)

| Field | Value |
|-------|-------|
| **Primary Persona** | Sarah Chen |
| **Function** | `handle_step_3_connect_tools` |
| **API Calls** | Add external provider credentials |
| **Interactive** | Multi-select tools to connect |

```python
async def handle_step_3_connect_tools(ctx: DemoContext) -> None:
    """Handle step 3: Connect External Tools."""
    ctx.switcher.switch_to("sarah", step=3, title="Connect External Tools")
    
    # Multi-select tools
    tools = ctx.ui.multi_select(
        prompt="Select tools to connect:",
        choices=["OpenAI", "GitHub", "Slack", "Salesforce", "HubSpot"],
        default=["OpenAI", "GitHub"],
    )
    ctx.connected_tools = tools
    
    # For each tool, store credentials
    for tool in tools:
        # API call to store provider credential
        await ctx.api.request("POST", "/api/v1/vault/secrets", json={...})
```

---

### Step 4: Create Agent Identity (Sarah + Vendor Split)

| Field | Value |
|-------|-------|
| **Primary Persona** | Sarah Chen |
| **Secondary Persona** | Vendor (Jordan Lee) |
| **Function** | `handle_step_4_create_agent` |
| **API Calls** | Create agent identity |
| **Interactive** | Confirm agent name, show vendor perspective |

```python
async def handle_step_4_create_agent(ctx: DemoContext) -> None:
    """Handle step 4: Create Agent Identity (split view)."""
    # Sarah's view
    ctx.switcher.switch_to("sarah", step=4, title="Create Agent Identity")
    
    agent_name = ctx.ui.select(
        prompt="Agent name:",
        choices=["sdr-assistant", "marketing-bot", "sales-helper"],
        default="sdr-assistant",
    )
    
    # API call: Create agent
    response = await ctx.api.request("POST", "/api/v1/agents", json={"name": agent_name})
    ctx.agent_id = response.json()["id"]
    
    # Vendor's view (split)
    ctx.switcher.show_vendor_perspective(step=4, title="Vendor Sees New Agent")
    ctx.ui.show_insight(
        "A new agent just registered! I can see its identity but not its credentials.",
        ctx.switcher.get_current(),
    )
```

---

### Step 5: Register Agent (Sarah + Vendor Split)

| Field | Value |
|-------|-------|
| **Primary Persona** | Sarah Chen |
| **Secondary Persona** | Vendor (Jordan Lee) |
| **Function** | `handle_step_5_register_agent` |
| **API Calls** | Agent challenge/verify |
| **Interactive** | Show cryptographic handshake |

---

### Step 6: Grant Permissions (Sarah + Vendor Split)

| Field | Value |
|-------|-------|
| **Primary Persona** | Sarah Chen |
| **Secondary Persona** | Vendor (Jordan Lee) |
| **Function** | `handle_step_6_grant_permissions` |
| **API Calls** | Create policy, attach to agent |
| **Interactive** | Multi-select permissions, show vendor view |

```python
async def handle_step_6_grant_permissions(ctx: DemoContext) -> None:
    """Handle step 6: Grant Permissions (split view)."""
    ctx.switcher.switch_to("sarah", step=6, title="Grant Permissions")
    
    # Multi-select permissions
    permissions = ctx.ui.multi_select(
        prompt="Select permissions for agent:",
        choices=[
            "openai:chat:*",
            "github:repos:read",
            "slack:messages:send",
            "salesforce:contacts:read",
        ],
        default=["openai:chat:*", "github:repos:read"],
    )
    ctx.granted_permissions = permissions
    
    # API call: Create and attach policy
    await ctx.api.request("POST", "/api/v1/policies", json={...})
    
    # Vendor perspective
    ctx.switcher.show_vendor_perspective(step=6, title="Vendor Sees Permissions")
    ctx.ui.show_insight(
        f"Agent now has {len(permissions)} permissions. I can verify but not bypass them.",
        ctx.switcher.get_current(),
    )
```

---

### Step 7: Make API Calls (Sarah)

| Field | Value |
|-------|-------|
| **Primary Persona** | Sarah Chen |
| **Function** | `handle_step_7_make_api_calls` |
| **API Calls** | Gateway proxy request |
| **Interactive** | Select API to call, show request/response |

---

### Step 8: Agent Runtime (Agent)

| Field | Value |
|-------|-------|
| **Primary Persona** | SDR-Assistant Agent |
| **Function** | `handle_step_8_agent_runtime` |
| **API Calls** | Agent authenticates, makes calls |
| **Interactive** | Show agent's perspective, credential fetch |

```python
async def handle_step_8_agent_runtime(ctx: DemoContext) -> None:
    """Handle step 8: Agent Runtime."""
    ctx.switcher.switch_to("agent", step=8, title="Agent Runtime")
    
    ctx.ui.show_insight(
        "I'm the SDR-Assistant agent. Watch me fetch credentials and make API calls.",
        ctx.switcher.get_current(),
    )
    
    # Show credential bootstrap
    ctx.ui.show_json(
        {"action": "fetch_ephemeral_credentials", "ttl": "5m"},
        title="Agent: Requesting Credentials",
    )
    
    # API call: Agent token exchange
    response = await ctx.api.request("POST", "/api/v1/auth/agent/token", ...)
    
    # Show making external API call through gateway
    # ...
```

---

### Step 9: Credential Rotation (Sarah + Vendor Split)

| Field | Value |
|-------|-------|
| **Primary Persona** | Sarah Chen |
| **Secondary Persona** | Vendor (Jordan Lee) |
| **Function** | `handle_step_9_credential_rotation` |
| **API Calls** | Rotate credentials |
| **Interactive** | Trigger rotation, show both perspectives |

---

### Step 10: Audit Review (All Personas Round-Robin)

| Field | Value |
|-------|-------|
| **Primary Persona** | All 5 personas |
| **Function** | `handle_step_10_audit_review` |
| **API Calls** | Fetch audit log |
| **Interactive** | Each persona reviews and comments |

```python
async def handle_step_10_audit_review(ctx: DemoContext) -> None:
    """Handle step 10: Audit Review (all perspectives)."""
    # Fetch audit log
    response = await ctx.api.request("GET", "/api/v1/audit/logs")
    audit_entries = response.json()["entries"]
    
    ctx.ui.show_json(audit_entries, title="Audit Log")
    
    # Round-robin through all personas
    ctx.switcher.show_all_perspectives(step=10, title="Audit Review")
    
    # Each persona provides their insight
    for persona_id in ["it_admin", "sarah", "vendor", "agent", "security"]:
        persona = ctx.switcher.switch_to(persona_id, step=10, title="Audit Review", show_banner=False)
        
        insight = get_audit_insight(persona_id, audit_entries)
        ctx.ui.show_insight(insight, persona)
        
        ctx.ui.wait_for_continue()
```

---

## Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| `context` | Internal | DemoContext for state |
| `personas` | Internal | Persona, get_persona |
| `prompts` | Internal | PromptUI for display |
| `role_switcher` | Internal | RoleSwitcher for role changes |
| `api_client` | Internal | APIClient for HTTP calls |

---

## DemoContext Usage

Each handler receives a `DemoContext` with:

```python
@dataclass
class DemoContext:
    # Core components
    api: APIClient           # For API calls
    ui: PromptUI             # For prompts and display
    switcher: RoleSwitcher   # For role switching
    
    # State (modified during demo)
    current_step: int
    org_id: str | None
    project_id: str | None
    agent_id: str | None
    connected_tools: list[str]
    granted_permissions: list[str]
    # ... other state fields
```

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Implementation | `demos/interactive/step_handlers.py` |
| Unit tests | `tests/demos/test_step_handlers.py` |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

### Handler Registry
- [ ] `STEP_HANDLERS` dict contains all 10 handlers
- [ ] All handlers are async functions
- [ ] All handlers accept `DemoContext` parameter
- [ ] All handlers return `None`

### Per-Step Verification
- [ ] Step 1: Creates org and project, switches to IT Admin
- [ ] Step 2: Shows SDK installation
- [ ] Step 3: Multi-select tools, stores credentials
- [ ] Step 4: Creates agent, shows vendor split view
- [ ] Step 5: Agent registration with challenge/verify
- [ ] Step 6: Multi-select permissions, shows vendor split view
- [ ] Step 7: Makes API calls through gateway
- [ ] Step 8: Agent perspective, credential fetch
- [ ] Step 9: Credential rotation, split view
- [ ] Step 10: Round-robin audit review all 5 personas

### Integration
- [ ] Handlers use `ctx.switcher` for role changes
- [ ] Handlers use `ctx.ui` for prompts and display
- [ ] Handlers use `ctx.api` for HTTP requests
- [ ] Handlers update `ctx` state fields as needed

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| API call fails | Show error panel, offer retry |
| User cancels prompt | Gracefully exit step |
| Invalid step number | Raise `KeyError` from registry |

---

## Technical Requirements

| Requirement | Value |
|-------------|-------|
| Python version | 3.10+ |
| Async | All handlers must be `async def` |
| Internal deps | A1, A2, B1, B2, C1 |
| Type hints | Required on all handlers |
| Docstrings | Required on all handlers |

---

## References

- **Design Doc:** Interactive Demo Plan
- **Related Specs:** All previous specs (A1, A2, B1, B2, C1)
- **Upstream Dependencies:** A1, A2, B1, B2, C1
- **Downstream Dependents:** E1 (main entry point)
