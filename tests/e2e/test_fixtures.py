"""
Test Fixtures for Sarah's Journey E2E Tests.

Provides test data definitions for:
- Organization (Acme Corp)
- User (Sarah)
- Agent (SDR-Assistant)
- Services (Notion, Slack)
- Permissions and Delegations

This module defines the test scenario data that maps to
the design document's Sarah's Journey specification.
"""

from dataclasses import dataclass, field
from typing import Any


# =============================================================================
# Organization Fixtures
# =============================================================================


@dataclass
class TestOrganization:
    """Test organization configuration."""

    id: str = "org-acme-001"
    name: str = "Acme Corp"
    domain: str = "acme.com"
    idp: str = "https://acme.okta.com"


# =============================================================================
# User Fixtures
# =============================================================================


@dataclass
class TestUser:
    """Test user configuration (Sarah)."""

    id: str = "user-sarah-001"
    email: str = "sarah@acme.com"
    name: str = "Sarah Chen"
    password: str = "secure_password"
    organization_id: str = "org-acme-001"


# =============================================================================
# Agent Fixtures
# =============================================================================


import time


@dataclass
class TestAgent:
    """Test agent configuration (SDR-Assistant)."""

    id: str = field(default_factory=lambda: f"agent-sdr-{int(time.time())}")
    name: str = "SDR-Assistant"
    description: str = "Sales Development Representative AI Assistant"
    organization_id: str = "org-acme-001"


# =============================================================================
# Service Fixtures
# =============================================================================


@dataclass
class TestService:
    """Test service configuration."""

    id: str
    name: str
    oauth_scopes: list[str] = field(default_factory=list)
    test_token: str = ""


# Pre-defined test services
NOTION_SERVICE = TestService(
    id="notion",
    name="Notion",
    oauth_scopes=["read_pages", "search_content", "read_databases"],
    test_token="test_notion_token_12345",
)

SLACK_SERVICE = TestService(
    id="slack",
    name="Slack",
    oauth_scopes=["search:read", "channels:read", "users:read"],
    test_token="test_slack_token_67890",
)

HUBSPOT_SERVICE = TestService(
    id="hubspot",
    name="HubSpot",
    oauth_scopes=["crm.objects.contacts.read", "crm.objects.deals.read"],
    test_token="test_hubspot_token_abcde",
)

GDRIVE_SERVICE = TestService(
    id="gdrive",
    name="Google Drive",
    oauth_scopes=["drive.readonly"],
    test_token="test_gdrive_token_google_001",
)

GCALENDAR_SERVICE = TestService(
    id="gcalendar",
    name="Google Calendar",
    oauth_scopes=["calendar.readonly", "calendar.events.readonly"],
    test_token="test_gcalendar_token_google_002",
)

GMAIL_SERVICE = TestService(
    id="gmail",
    name="Gmail",
    oauth_scopes=["gmail.readonly"],
    test_token="test_gmail_token_google_003",
)


# =============================================================================
# Permission Fixtures
# =============================================================================


# Permissions Sarah delegates to SDR-Assistant
SARAH_DELEGATED_PERMISSIONS = [
    # Notion - Read and Search only
    "notion:pages:search",
    "notion:pages:read",
    "notion:databases:query",
    # Slack - Read only
    "slack:messages:search",
    "slack:channels:list",
    "slack:users:list",
]

# Permissions Sarah does NOT delegate
NON_DELEGATED_PERMISSIONS = [
    # Notion - Write operations
    "notion:pages:create",
    "notion:pages:update",
    "notion:pages:delete",
    # Slack - Write operations
    "slack:messages:post",
    "slack:channels:create",
    # HubSpot - Not connected at all
    "hubspot:contacts:read",
]


# =============================================================================
# Tool Fixtures
# =============================================================================


# Expected tools visible after filtering
EXPECTED_VISIBLE_TOOLS = [
    "notion.search_pages",
    "notion.read_page",
    "notion.query_database",
    "slack.search_messages",
    "slack.list_channels",
    "slack.list_users",
]

# Tools that should NOT be visible
EXPECTED_HIDDEN_TOOLS = [
    "notion.create_page",
    "notion.update_page",
    "notion.delete_page",
    "slack.post_message",
    "slack.create_channel",
    "hubspot.search_contacts",
]


# =============================================================================
# Google Permission Fixtures
# =============================================================================


GOOGLE_DELEGATED_PERMISSIONS = [
    "gdrive:files:search",
    "gdrive:files:list",
    "gcalendar:events:list",
    "gcalendar:events:read",
    "gmail:messages:search",
    "gmail:messages:list",
]

GOOGLE_NON_DELEGATED_PERMISSIONS = [
    "gdrive:files:read",
    "gdrive:files:metadata",
    "gcalendar:calendars:list",
    "gmail:messages:read",
    "gmail:labels:list",
]


# =============================================================================
# Google Tool Fixtures
# =============================================================================


GOOGLE_EXPECTED_VISIBLE_TOOLS = [
    "gdrive.search_files",
    "gdrive.list_files",
    "gcalendar.list_events",
    "gcalendar.get_event",
    "gmail.search_messages",
    "gmail.list_messages",
]

GOOGLE_EXPECTED_HIDDEN_TOOLS = [
    "gdrive.read_file",
    "gdrive.get_file_metadata",
    "gcalendar.list_calendars",
    "gmail.read_message",
    "gmail.list_labels",
]


# =============================================================================
# Test Scenario Data
# =============================================================================


@dataclass
class SarahJourneyScenario:
    """Complete test scenario data for Sarah's Journey."""

    organization: TestOrganization = field(default_factory=TestOrganization)
    user: TestUser = field(default_factory=TestUser)
    agent: TestAgent = field(default_factory=TestAgent)
    services: list[TestService] = field(
        default_factory=lambda: [NOTION_SERVICE, SLACK_SERVICE]
    )
    delegated_permissions: list[str] = field(
        default_factory=lambda: SARAH_DELEGATED_PERMISSIONS.copy()
    )

    def get_delegation_request(self) -> dict[str, Any]:
        """Get delegation request payload."""
        return {
            "agent_id": self.agent.id,
            "permissions": self.delegated_permissions,
            "constraints": {
                "rate_limit": 100,
                "expires_in_hours": 8,
            },
        }

    def get_agent_register_request(self, public_key: str) -> dict[str, Any]:
        """Get agent registration request payload.
        
        Args:
            public_key: Base64-encoded Ed25519 public key (32 bytes).
        """
        return {
            "agent_id": self.agent.id,
            "name": self.agent.name,
            "public_key": public_key,
        }


# Default test scenario
DEFAULT_SCENARIO = SarahJourneyScenario()


@dataclass
class GoogleJourneyScenario:
    """Test scenario for Google services E2E journey."""

    organization: TestOrganization = field(default_factory=TestOrganization)
    user: TestUser = field(default_factory=TestUser)
    agent: TestAgent = field(default_factory=TestAgent)
    services: list[TestService] = field(
        default_factory=lambda: [GDRIVE_SERVICE, GCALENDAR_SERVICE, GMAIL_SERVICE]
    )
    delegated_permissions: list[str] = field(
        default_factory=lambda: GOOGLE_DELEGATED_PERMISSIONS.copy()
    )

    def get_delegation_request(self) -> dict[str, Any]:
        """Get delegation request payload for Google permissions."""
        return {
            "agent_id": self.agent.id,
            "permissions": self.delegated_permissions,
            "constraints": {
                "rate_limit": 100,
                "expires_in_hours": 8,
            },
        }

    def get_agent_register_request(self, public_key: str) -> dict[str, Any]:
        """Get agent registration request payload."""
        return {
            "agent_id": self.agent.id,
            "name": self.agent.name,
            "public_key": public_key,
        }


DEFAULT_GOOGLE_SCENARIO = GoogleJourneyScenario()


# =============================================================================
# MCP Protocol Fixtures
# =============================================================================


def get_mcp_initialize_request(
    request_id: int = 1,
    client_name: str = "SDR-Assistant",
    client_version: str = "1.0",
) -> dict[str, Any]:
    """Get MCP initialize request payload."""
    return {
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": request_id,
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": client_name,
                "version": client_version,
            },
        },
    }


def get_mcp_tools_list_request(request_id: int = 2) -> dict[str, Any]:
    """Get MCP tools/list request payload."""
    return {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": request_id,
        "params": {},
    }


def get_mcp_tools_call_request(
    tool_name: str,
    arguments: dict[str, Any],
    request_id: int = 3,
) -> dict[str, Any]:
    """Get MCP tools/call request payload."""
    return {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": request_id,
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }


# =============================================================================
# Expected Responses
# =============================================================================


MCP_PERMISSION_DENIED_CODE = -32001
MCP_CREDENTIAL_ERROR_CODE = -32003
