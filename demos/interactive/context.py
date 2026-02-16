"""Demo context state manager for Sarah's Journey interactive demo.

This module provides centralized state management across all 10 journey steps,
tracking progress and providing persona-specific context views.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from demos.interactive.api_client import APIClient
    from demos.interactive.prompts import PromptUI
    from demos.interactive.role_switcher import RoleSwitcher


# Step-to-persona mapping for automatic persona switching
STEP_PRIMARY_PERSONA: dict[int, str] = {
    1: "it_admin",
    2: "sarah",
    3: "sarah",
    4: "sarah",
    5: "agent",
    6: "agent",
    7: "agent",
    8: "agent",
    9: "agent",
    10: "sarah",  # Final audit review starts with Sarah
}


@dataclass
class DemoContext:
    """Central state manager for the interactive demo.

    Tracks all state generated during Sarah's Journey, including:
    - Authentication tokens and session IDs
    - Connected services and permissions
    - Tool discovery and execution results
    - Audit events

    The context is accumulated across steps and provides
    persona-specific views of relevant state.

    Attributes:
        api: APIClient for making HTTP requests (set by main entry point)
        ui: PromptUI for interactive prompts (set by main entry point)
        switcher: RoleSwitcher for persona transitions (set by main entry point)
        current_step: Current step number (0 = not started, 1-10 = active)
        current_persona: ID of currently active persona
        org_id: Organization ID from Step 1
        org_name: Organization display name from Step 1
        user_token: Sarah's user JWT from Step 2
        user_email: Sarah's email from Step 2
        connected_services: List of OAuth service names from Step 3
        delegation_id: Delegation session ID from Step 4
        delegated_permissions: List of permission strings from Step 4
        agent_id: Agent's unique identifier from Step 5
        agent_jwt: Agent's JWT token from Step 5
        mcp_session_id: MCP session ID from Step 6
        discovered_tools: List of tool metadata dicts from Step 7
        tool_call_results: List of tool execution results from Step 8
        denied_tool: Tool name that was denied in Step 9
        denial_reason: Reason for denial in Step 9
        audit_events: List of audit event dicts from Step 10
    """

    # Core components (set by main entry point before running handlers)
    api: APIClient | None = None
    ui: PromptUI | None = None
    switcher: RoleSwitcher | None = None

    # Runtime configuration
    auto_mode: bool = False  # Auto-advance without user prompts
    verbose: bool = False  # Enable verbose output

    # Current state
    current_step: int = 0
    current_persona: str = "sarah"

    # Step 1: Enterprise Configuration (IT Admin)
    org_id: str | None = None
    org_name: str | None = None

    # Step 2: User Authentication (Sarah)
    user_token: str | None = None
    user_email: str | None = None

    # Step 3: OAuth Connection (Sarah)
    connected_services: list[str] = field(default_factory=list)

    # Step 4: Permission Delegation (Sarah -> Vendor)
    delegation_id: str | None = None
    delegated_permissions: list[str] = field(default_factory=list)

    # Step 5-6: Agent Authentication & MCP Connection (Agent)
    agent_id: str | None = None
    agent_jwt: str | None = None
    mcp_session_id: str | None = None

    # Step 7-8: Tool Discovery & Execution (Agent)
    discovered_tools: list[dict[str, Any]] = field(default_factory=list)
    tool_call_results: list[dict[str, Any]] = field(default_factory=list)

    # Step 9: Permission Denial (Agent attempts, Security reviews)
    denied_tool: str | None = None
    denial_reason: str | None = None

    # Step 10: Audit Review (All personas)
    audit_events: list[dict[str, Any]] = field(default_factory=list)

    def get_summary_for_persona(self, persona_id: str) -> dict[str, Any]:
        """Return context summary relevant to a specific persona.

        Each persona sees different aspects of the state:
        - IT Admin: org configuration
        - Sarah: her tokens, services, delegations
        - Vendor: delegation details, agent registration
        - Agent: agent credentials, MCP session, tools
        - Security: all events, denials, audit trail

        Args:
            persona_id: The persona ID ("it_admin", "sarah", etc.)

        Returns:
            Dictionary with persona-relevant state fields
        """
        if persona_id == "it_admin":
            return {
                "role": "Enterprise Administrator",
                "org_id": self.org_id,
                "org_name": self.org_name,
                "message": "Organization configured successfully"
                if self.org_id
                else "Awaiting configuration",
            }

        if persona_id == "sarah":
            return {
                "role": "Sales Development Representative",
                "email": self.user_email,
                "connected_services": self.connected_services,
                "delegated_to": "SDR-Assistant" if self.delegation_id else None,
                "permissions": self.delegated_permissions,
            }

        if persona_id == "vendor":
            return {
                "role": "AI Platform Provider",
                "delegation_id": self.delegation_id,
                "agent_id": self.agent_id,
                "agent_registered": self.agent_id is not None,
                "permissions_received": self.delegated_permissions,
            }

        if persona_id == "agent":
            return {
                "role": "SDR-Assistant Agent",
                "agent_id": self.agent_id,
                "mcp_session": self.mcp_session_id,
                "tools_discovered": len(self.discovered_tools),
                "tool_calls_made": len(self.tool_call_results),
                "status": "active" if self.mcp_session_id else "inactive",
            }

        if persona_id == "security":
            return {
                "role": "Security & Compliance",
                "total_events": len(self.audit_events),
                "denied_operations": 1 if self.denied_tool else 0,
                "last_denial": {
                    "tool": self.denied_tool,
                    "reason": self.denial_reason,
                }
                if self.denied_tool
                else None,
                "audit_status": "clean",
            }

        # Unknown persona - return minimal info
        return {"role": "Unknown", "persona_id": persona_id}

    def advance_step(self) -> None:
        """Move to the next step.

        Increments current_step by 1.
        Updates current_persona based on step-to-persona mapping.

        Raises:
            ValueError: If already at step 10
        """
        if self.current_step >= 10:
            raise ValueError("Cannot advance past step 10")

        self.current_step += 1
        self.current_persona = STEP_PRIMARY_PERSONA.get(
            self.current_step, self.current_persona
        )

    def go_to_step(self, step: int) -> None:
        """Jump to a specific step.

        Used for navigation (e.g., going back to review).
        Updates current_persona based on step-to-persona mapping.

        Args:
            step: Target step number (1-10)

        Raises:
            ValueError: If step is out of range
        """
        if not 1 <= step <= 10:
            raise ValueError(f"Step must be between 1 and 10, got {step}")

        self.current_step = step
        self.current_persona = STEP_PRIMARY_PERSONA.get(step, self.current_persona)

    def to_dict(self) -> dict[str, Any]:
        """Serialize entire context for display or persistence.

        Returns:
            Dictionary with all context fields
        """
        return {
            "current_step": self.current_step,
            "current_persona": self.current_persona,
            "org_id": self.org_id,
            "org_name": self.org_name,
            "user_token": self.user_token,
            "user_email": self.user_email,
            "connected_services": self.connected_services,
            "delegation_id": self.delegation_id,
            "delegated_permissions": self.delegated_permissions,
            "agent_id": self.agent_id,
            "agent_jwt": self.agent_jwt,
            "mcp_session_id": self.mcp_session_id,
            "discovered_tools": self.discovered_tools,
            "tool_call_results": self.tool_call_results,
            "denied_tool": self.denied_tool,
            "denial_reason": self.denial_reason,
            "audit_events": self.audit_events,
        }

    def reset(self) -> None:
        """Reset context to initial state.

        Clears all accumulated state and returns to step 0.
        Used when restarting the demo.
        """
        self.current_step = 0
        self.current_persona = "sarah"
        self.org_id = None
        self.org_name = None
        self.user_token = None
        self.user_email = None
        self.connected_services = []
        self.delegation_id = None
        self.delegated_permissions = []
        self.agent_id = None
        self.agent_jwt = None
        self.mcp_session_id = None
        self.discovered_tools = []
        self.tool_call_results = []
        self.denied_tool = None
        self.denial_reason = None
        self.audit_events = []
