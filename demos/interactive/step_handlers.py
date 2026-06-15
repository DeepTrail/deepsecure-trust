"""Step handlers for Sarah's Journey interactive demo.

This module implements all 10 step handlers that drive the interactive
demo experience, managing role switches, API calls, and user prompts.
"""

import uuid
from typing import Any, Awaitable, Callable

from demos.interactive.context import DemoContext

# Type alias for step handlers
StepHandler = Callable[[DemoContext], Awaitable[None]]


def _generate_id(prefix: str = "") -> str:
    """Generate a mock ID for demo purposes."""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _get_audit_insight(persona_id: str, audit_events: list[dict[str, Any]]) -> str:
    """Get persona-specific insight about the audit log."""
    event_count = len(audit_events)

    insights = {
        "it_admin": (
            f"As IT Admin, I see {event_count} events in the audit log. "
            "All organization-level actions are properly tracked, including "
            "the initial setup and credential storage operations."
        ),
        "sarah": (
            f"I can see my {event_count} actions recorded here - connecting tools, "
            "creating the agent, and granting permissions. Everything I delegated "
            "to SDR-Assistant is clearly documented."
        ),
        "vendor": (
            "From the vendor perspective, I can verify that the agent operated "
            "within its granted permissions. The audit trail shows DeepSecure's "
            "gateway mediated all API calls - we never saw the actual credentials."
        ),
        "agent": (
            "My activity log shows each tool I discovered and every API call I made. "
            "Notice how my credentials were ephemeral - they rotated automatically "
            "and I never had direct access to Sarah's secrets."
        ),
        "security": (
            f"Security audit complete: {event_count} events logged. "
            "I can confirm: (1) No credential leakage to vendor, "
            "(2) All agent actions within policy bounds, "
            "(3) Permission denial was enforced correctly, "
            "(4) Full audit trail maintained for compliance."
        ),
    }

    return insights.get(persona_id, "Reviewing audit log...")


async def handle_step_1_org_setup(ctx: DemoContext) -> None:
    """Handle step 1: Organization Setup.

    IT Admin sets up organization and project in DeepSecure.
    This is the foundational step that establishes the enterprise context.

    Args:
        ctx: DemoContext with current state and components
    """
    assert ctx.switcher is not None
    assert ctx.ui is not None
    assert ctx.api is not None

    # Switch to IT Admin persona
    ctx.switcher.switch_to("it_admin", step=1, title="Organization Setup")

    ctx.ui.show_insight(
        "Welcome! I'm Alex, the IT Admin. Let me set up our organization in DeepSecure.",
        ctx.switcher.get_current(),
    )

    # Select organization name
    org_name = await ctx.ui.select(
        prompt="Organization name:",
        choices=["Acme Corp", "TechStart Inc", "Custom..."],
        default="Acme Corp",
    )

    if org_name == "Custom...":
        org_name = "Demo Organization"

    # Show API call for creating organization
    ctx.api.show_info(
        f"Creating organization: {org_name}",
        title="Organization Setup",
    )

    # Simulate API response (in real demo, this would be actual API call)
    ctx.org_id = _generate_id("org_")
    ctx.org_name = org_name

    ctx.api.show_json(
        {
            "id": ctx.org_id,
            "name": ctx.org_name,
            "status": "active",
            "created_at": "2026-02-10T12:00:00Z",
        },
        title="Organization Created",
    )

    # Add to audit events
    ctx.audit_events.append({
        "step": 1,
        "action": "organization_created",
        "actor": "it_admin",
        "details": {"org_id": ctx.org_id, "org_name": ctx.org_name},
    })

    ctx.ui.wait_for_continue()


async def handle_step_2_install_sdk(ctx: DemoContext) -> None:
    """Handle step 2: Install SDK.

    Sarah installs the DeepSecure SDK and authenticates.
    This step shows the developer experience of getting started.

    Args:
        ctx: DemoContext with current state and components
    """
    assert ctx.switcher is not None
    assert ctx.ui is not None
    assert ctx.api is not None

    # Switch to Sarah
    ctx.switcher.switch_to("sarah", step=2, title="Install SDK & Authenticate")

    ctx.ui.show_insight(
        "Hi! I'm Sarah, an SDR. I need to set up DeepSecure so my AI assistant "
        "can help me with outreach while keeping our API credentials secure.",
        ctx.switcher.get_current(),
    )

    # Show SDK installation
    ctx.api.show_info(
        "$ pip install deepsecure\n\n"
        "# In your Python code:\n"
        "from deepsecure import Client\n"
        "client = Client()",
        title="SDK Installation",
    )

    # Confirm installation
    if await ctx.ui.confirm("SDK installed and ready to authenticate?", default=True):
        # Simulate user authentication
        ctx.user_email = "sarah@acme.com"
        ctx.user_token = _generate_id("usr_tok_")

        ctx.api.show_json(
            {
                "user_id": _generate_id("usr_"),
                "email": ctx.user_email,
                "org_id": ctx.org_id,
                "authenticated": True,
            },
            title="Authentication Successful",
        )

        ctx.audit_events.append({
            "step": 2,
            "action": "user_authenticated",
            "actor": "sarah",
            "details": {"email": ctx.user_email},
        })

    ctx.ui.wait_for_continue()


async def handle_step_3_connect_tools(ctx: DemoContext) -> None:
    """Handle step 3: Connect External Tools.

    Sarah connects her external API credentials (OpenAI, GitHub, etc.)
    to DeepSecure's vault for secure storage.

    Args:
        ctx: DemoContext with current state and components
    """
    assert ctx.switcher is not None
    assert ctx.ui is not None
    assert ctx.api is not None

    ctx.switcher.switch_to("sarah", step=3, title="Connect External Tools")

    ctx.ui.show_insight(
        "Now I'll store my API credentials in DeepSecure's vault. "
        "These will be securely managed and only accessible through the gateway.",
        ctx.switcher.get_current(),
    )

    # Multi-select tools to connect
    tools = await ctx.ui.multi_select(
        prompt="Select tools to connect:",
        choices=["OpenAI", "GitHub", "Slack", "Salesforce", "Google Drive"],
        default=["OpenAI", "GitHub"],
    )

    if not tools:
        tools = ["OpenAI", "GitHub"]  # Default if nothing selected

    ctx.connected_services = tools

    # Show each tool being connected
    for tool in tools:
        ctx.api.show_json(
            {
                "provider": tool.lower(),
                "status": "connected",
                "credential_id": _generate_id("cred_"),
                "stored_in": "vault",
                "encrypted": True,
            },
            title=f"Connected: {tool}",
        )

        ctx.audit_events.append({
            "step": 3,
            "action": "credential_stored",
            "actor": "sarah",
            "details": {"provider": tool.lower()},
        })

    ctx.api.show_info(
        f"Successfully connected {len(tools)} tools: {', '.join(tools)}\n\n"
        "These credentials are now encrypted in the vault and will only be "
        "injected at runtime through the secure gateway.",
        title="Tools Connected",
    )

    ctx.ui.wait_for_continue()


async def handle_step_4_create_agent(ctx: DemoContext) -> None:
    """Handle step 4: Create Agent Identity (split view).

    Sarah creates an agent identity. The vendor sees this from their
    perspective - they can see an agent exists but not its credentials.

    Args:
        ctx: DemoContext with current state and components
    """
    assert ctx.switcher is not None
    assert ctx.ui is not None
    assert ctx.api is not None

    # Sarah's view
    ctx.switcher.switch_to("sarah", step=4, title="Create Agent Identity")

    ctx.ui.show_insight(
        "I'm creating an identity for my SDR-Assistant agent. "
        "This agent will help me with outreach tasks.",
        ctx.switcher.get_current(),
    )

    # Select agent name
    agent_name = await ctx.ui.select(
        prompt="Agent name:",
        choices=["sdr-assistant", "marketing-bot", "sales-helper"],
        default="sdr-assistant",
    )

    # Create agent identity
    ctx.agent_id = _generate_id("agent_")
    ctx.delegation_id = _generate_id("del_")

    ctx.api.show_json(
        {
            "agent_id": ctx.agent_id,
            "name": agent_name,
            "delegation_id": ctx.delegation_id,
            "status": "created",
            "owner": ctx.user_email,
        },
        title="Agent Identity Created",
    )

    ctx.audit_events.append({
        "step": 4,
        "action": "agent_created",
        "actor": "sarah",
        "details": {"agent_id": ctx.agent_id, "name": agent_name},
    })

    ctx.ui.wait_for_continue()

    # Vendor's perspective (split view)
    ctx.switcher.show_vendor_perspective(step=4, title="Vendor Sees New Agent")

    ctx.ui.show_insight(
        "A new agent just registered! I can see its identity and delegation ID, "
        "but I cannot see Sarah's underlying credentials. DeepSecure ensures "
        "I only see what I need to operate the agent.",
        ctx.switcher.get_current(),
    )

    ctx.api.show_json(
        {
            "agent_id": ctx.agent_id,
            "delegation_id": ctx.delegation_id,
            "credentials": "[REDACTED - stored in DeepSecure vault]",
            "vendor_can_see": ["agent_id", "delegation_id", "permissions"],
            "vendor_cannot_see": ["api_keys", "secrets", "tokens"],
        },
        title="Vendor's View of Agent",
    )

    ctx.ui.wait_for_continue()


async def handle_step_5_register_agent(ctx: DemoContext) -> None:
    """Handle step 5: Register Agent (cryptographic handshake).

    The agent authenticates with DeepSecure using a challenge/response
    flow. The vendor observes but cannot intercept credentials.

    Args:
        ctx: DemoContext with current state and components
    """
    assert ctx.switcher is not None
    assert ctx.ui is not None
    assert ctx.api is not None

    ctx.switcher.switch_to("agent", step=5, title="Agent Registration")

    ctx.ui.show_insight(
        "I'm the SDR-Assistant agent. Watch me authenticate with DeepSecure "
        "using a secure cryptographic handshake.",
        ctx.switcher.get_current(),
    )

    # Show challenge request
    challenge_id = _generate_id("chal_")
    ctx.api.show_json(
        {
            "action": "request_challenge",
            "agent_id": ctx.agent_id,
            "challenge_id": challenge_id,
            "algorithm": "ed25519",
        },
        title="Step 1: Request Challenge",
    )

    # Show challenge response
    ctx.api.show_json(
        {
            "challenge_id": challenge_id,
            "challenge": "base64_encoded_challenge_data...",
            "expires_in": 60,
        },
        title="Step 2: Challenge Received",
    )

    # Show signed response
    ctx.api.show_json(
        {
            "challenge_id": challenge_id,
            "signature": "ed25519_signature...",
            "public_key": "agent_public_key...",
        },
        title="Step 3: Sign Challenge",
    )

    # Show successful verification
    ctx.agent_jwt = _generate_id("jwt_")
    ctx.api.show_json(
        {
            "status": "verified",
            "agent_id": ctx.agent_id,
            "jwt_issued": True,
            "token_ttl": "5m",
        },
        title="Step 4: Verification Complete",
    )

    ctx.audit_events.append({
        "step": 5,
        "action": "agent_authenticated",
        "actor": "agent",
        "details": {"agent_id": ctx.agent_id, "method": "ed25519_challenge"},
    })

    ctx.ui.wait_for_continue()

    # Vendor's perspective
    ctx.switcher.show_vendor_perspective(step=5, title="Vendor Observes Handshake")

    ctx.ui.show_insight(
        "I can see the agent completed authentication, but I never saw the "
        "private key or the actual credentials. DeepSecure's zero-knowledge "
        "architecture keeps the secrets safe.",
        ctx.switcher.get_current(),
    )

    ctx.ui.wait_for_continue()


async def handle_step_6_grant_permissions(ctx: DemoContext) -> None:
    """Handle step 6: Grant Permissions (split view).

    Sarah grants specific permissions to the agent. The vendor can
    verify what permissions exist but cannot modify them.

    Args:
        ctx: DemoContext with current state and components
    """
    assert ctx.switcher is not None
    assert ctx.ui is not None
    assert ctx.api is not None

    ctx.switcher.switch_to("sarah", step=6, title="Grant Permissions")

    ctx.ui.show_insight(
        "Now I'll grant specific permissions to SDR-Assistant. "
        "I'm following the principle of least privilege - only what it needs.",
        ctx.switcher.get_current(),
    )

    # Multi-select permissions
    permissions = await ctx.ui.multi_select(
        prompt="Select permissions for agent:",
        choices=[
            "openai:chat:*",
            "github:repos:read",
            "slack:messages:send",
            "notion:pages:search",
            "gmail:messages:read",
        ],
        default=["openai:chat:*", "github:repos:read"],
    )

    if not permissions:
        permissions = ["openai:chat:*", "github:repos:read"]

    ctx.delegated_permissions = permissions

    # Create policy
    policy_id = _generate_id("pol_")
    ctx.api.show_json(
        {
            "policy_id": policy_id,
            "agent_id": ctx.agent_id,
            "permissions": permissions,
            "created_by": ctx.user_email,
            "expires": "2026-02-17T12:00:00Z",
        },
        title="Policy Created",
    )

    ctx.audit_events.append({
        "step": 6,
        "action": "permissions_granted",
        "actor": "sarah",
        "details": {"agent_id": ctx.agent_id, "permissions": permissions},
    })

    ctx.ui.wait_for_continue()

    # Vendor's perspective
    ctx.switcher.show_vendor_perspective(step=6, title="Vendor Sees Permissions")

    ctx.ui.show_insight(
        f"The agent now has {len(permissions)} permissions. I can verify these "
        "permissions exist and are enforced, but I cannot modify them or "
        "access anything outside this scope.",
        ctx.switcher.get_current(),
    )

    ctx.api.show_json(
        {
            "agent_id": ctx.agent_id,
            "visible_permissions": permissions,
            "can_modify": False,
            "enforced_by": "DeepSecure Gateway",
        },
        title="Vendor's Permission View",
    )

    ctx.ui.wait_for_continue()


async def handle_step_7_make_api_calls(ctx: DemoContext) -> None:
    """Handle step 7: Make API Calls through Gateway.

    Demonstrate making API calls through the DeepSecure gateway,
    which injects credentials at runtime.

    Args:
        ctx: DemoContext with current state and components
    """
    assert ctx.switcher is not None
    assert ctx.ui is not None
    assert ctx.api is not None

    ctx.switcher.switch_to("agent", step=7, title="Tool Discovery")

    ctx.ui.show_insight(
        "Let me discover what tools are available to me based on my permissions.",
        ctx.switcher.get_current(),
    )

    # Discover available tools
    tools = []
    for perm in ctx.delegated_permissions:
        provider = perm.split(":")[0]
        tools.append({
            "name": f"{provider}_tool",
            "provider": provider,
            "permission": perm,
            "available": True,
        })

    ctx.discovered_tools = tools

    ctx.api.show_json(
        {
            "discovered_tools": len(tools),
            "tools": tools,
        },
        title="Available Tools",
    )

    ctx.audit_events.append({
        "step": 7,
        "action": "tools_discovered",
        "actor": "agent",
        "details": {"tool_count": len(tools)},
    })

    ctx.ui.wait_for_continue()


async def handle_step_8_agent_runtime(ctx: DemoContext) -> None:
    """Handle step 8: Agent Runtime.

    Show the agent making actual API calls through the gateway,
    with credential injection happening transparently.

    Args:
        ctx: DemoContext with current state and components
    """
    assert ctx.switcher is not None
    assert ctx.ui is not None
    assert ctx.api is not None

    ctx.switcher.switch_to("agent", step=8, title="Agent Runtime")

    ctx.ui.show_insight(
        "Watch me make API calls. The gateway will inject credentials at runtime - "
        "I never see the actual secrets!",
        ctx.switcher.get_current(),
    )

    # Select an API to call
    if ctx.discovered_tools:
        tool_names = [t["name"] for t in ctx.discovered_tools]
        selected_tool = await ctx.ui.select(
            prompt="Which API should I call?",
            choices=tool_names,
            default=tool_names[0],
        )
    else:
        selected_tool = "openai_tool"

    # Show the request (without credentials)
    ctx.api.show_json(
        {
            "tool": selected_tool,
            "request": {
                "method": "POST",
                "endpoint": "/v1/chat/completions",
                "body": {"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]},
            },
            "credentials": "[INJECTED BY GATEWAY]",
        },
        title="Agent Request (No Credentials)",
    )

    # Show gateway credential injection
    ctx.api.show_info(
        "Gateway intercepted request\n"
        "-> Verified agent identity\n"
        "-> Checked permissions: ALLOWED\n"
        "-> Fetched credentials from vault\n"
        "-> Injected Authorization header\n"
        "-> Forwarded to upstream API",
        title="Gateway Processing",
    )

    # Show successful response
    result = {
        "tool": selected_tool,
        "status": "success",
        "response": {"id": _generate_id("chatcmpl-"), "object": "chat.completion"},
        "credential_exposure": "NONE",
    }
    ctx.tool_call_results.append(result)

    ctx.api.show_json(result, title="API Response")

    ctx.audit_events.append({
        "step": 8,
        "action": "api_call_made",
        "actor": "agent",
        "details": {"tool": selected_tool, "status": "success"},
    })

    ctx.ui.wait_for_continue()


async def handle_step_9_credential_rotation(ctx: DemoContext) -> None:
    """Handle step 9: Permission Denial & Credential Rotation.

    Show what happens when an agent tries to exceed its permissions,
    and demonstrate credential rotation.

    Args:
        ctx: DemoContext with current state and components
    """
    assert ctx.switcher is not None
    assert ctx.ui is not None
    assert ctx.api is not None

    ctx.switcher.switch_to("agent", step=9, title="Permission Enforcement")

    ctx.ui.show_insight(
        "Let me try to access something outside my permissions to show "
        "how DeepSecure enforces policy boundaries.",
        ctx.switcher.get_current(),
    )

    # Attempt unauthorized action
    ctx.denied_tool = "salesforce:contacts:delete"
    ctx.denial_reason = "Permission not granted"

    ctx.api.show_json(
        {
            "attempted_action": ctx.denied_tool,
            "agent_id": ctx.agent_id,
            "granted_permissions": ctx.delegated_permissions,
        },
        title="Attempted Unauthorized Action",
    )

    ctx.api.show_error(
        f"DENIED: {ctx.denied_tool}\n"
        f"Reason: {ctx.denial_reason}\n\n"
        "The agent's request was blocked at the gateway level. "
        "No credentials were exposed.",
        title="Permission Denied",
    )

    ctx.audit_events.append({
        "step": 9,
        "action": "permission_denied",
        "actor": "agent",
        "details": {"attempted": ctx.denied_tool, "reason": ctx.denial_reason},
    })

    ctx.ui.wait_for_continue()

    # Security officer's perspective
    ctx.switcher.switch_to("security", step=9, title="Security Review")

    ctx.ui.show_insight(
        "I received an alert about the denied action. This is exactly how it "
        "should work - the policy was enforced, and I have a full audit trail.",
        ctx.switcher.get_current(),
    )

    ctx.api.show_json(
        {
            "alert_type": "permission_violation_attempt",
            "agent_id": ctx.agent_id,
            "attempted_action": ctx.denied_tool,
            "result": "BLOCKED",
            "credential_exposure": "NONE",
            "recommendation": "Review if agent needs additional permissions",
        },
        title="Security Alert",
    )

    ctx.ui.wait_for_continue()


async def handle_step_10_audit_review(ctx: DemoContext) -> None:
    """Handle step 10: Audit Review (all perspectives).

    Each persona reviews the audit log and provides their insight.
    This demonstrates the complete visibility that DeepSecure provides.

    Args:
        ctx: DemoContext with current state and components
    """
    assert ctx.switcher is not None
    assert ctx.ui is not None
    assert ctx.api is not None

    # First, show the full audit log
    ctx.switcher.switch_to("sarah", step=10, title="Audit Review")

    ctx.ui.show_insight(
        "Let's review everything that happened during this demo. "
        "Each of us will share our perspective on the audit trail.",
        ctx.switcher.get_current(),
    )

    # Display full audit log
    ctx.api.show_json(
        {
            "total_events": len(ctx.audit_events),
            "events": ctx.audit_events,
        },
        title="Complete Audit Log",
    )

    ctx.ui.wait_for_continue()

    # Round-robin through all personas for their insights
    persona_order = ["it_admin", "sarah", "vendor", "agent", "security"]

    for persona_id in persona_order:
        persona = ctx.switcher.switch_to(
            persona_id, step=10, title="Audit Review", show_banner=True
        )

        insight = _get_audit_insight(persona_id, ctx.audit_events)
        ctx.ui.show_insight(insight, persona)

        ctx.ui.wait_for_continue()

    # Final summary
    ctx.switcher.switch_to("sarah", step=10, title="Demo Complete", show_banner=True)

    ctx.api.show_info(
        "Thank you for experiencing Sarah's Journey!\n\n"
        "Key takeaways:\n"
        "- Credentials never left the secure vault\n"
        "- Vendor had zero access to secrets\n"
        "- Agent operated within policy bounds\n"
        "- Every action was fully audited\n"
        "- Permission enforcement worked correctly\n\n"
        "This is Identity-as-Code for AI agents.",
        title="Demo Complete",
    )


# Handler registry mapping step numbers to handlers
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


async def run_step(ctx: DemoContext, step: int) -> None:
    """Run a specific step handler.

    Args:
        ctx: DemoContext with state and components
        step: Step number (1-10)

    Raises:
        KeyError: If step number is invalid
        AssertionError: If ctx components are not set
    """
    handler = STEP_HANDLERS[step]
    await handler(ctx)


async def run_all_steps(ctx: DemoContext) -> None:
    """Run all 10 steps in sequence.

    Args:
        ctx: DemoContext with state and components
    """
    for step in range(1, 11):
        ctx.go_to_step(step)
        await run_step(ctx, step)
