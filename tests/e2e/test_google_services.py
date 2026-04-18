"""
Google Services E2E Test - WS-D7

Validates the complete Google services journey:
- Connect Google Drive, Calendar, and Gmail as services
- Delegate limited Google permissions to an agent
- Agent calls Google tools through MCP Gateway
- Non-delegated Google tools are denied

This mirrors test_sarah_journey.py (Notion + Slack) but for Google Workspace.

Usage:
    # Run with live services (post-MP1 merge)
    docker compose up -d
    pytest tests/e2e/test_google_services.py -v

Markers:
    @pytest.mark.e2e: Full E2E tests requiring live services
    @pytest.mark.slow: Slow tests (complete journey)
"""

from typing import Any

import httpx
import pytest

from .conftest import sign_challenge
from .test_fixtures import (
    GOOGLE_EXPECTED_HIDDEN_TOOLS,
    GOOGLE_EXPECTED_VISIBLE_TOOLS,
    GoogleJourneyScenario,
    MCP_PERMISSION_DENIED_CODE,
    get_mcp_initialize_request,
    get_mcp_tools_call_request,
    get_mcp_tools_list_request,
)


# =============================================================================
# Step: Connect Google Services
# =============================================================================


@pytest.mark.e2e
class TestGoogleServiceConnection:
    """Verify each Google service can be connected."""

    @pytest.mark.asyncio
    async def test_connect_gdrive(
        self,
        control_plane_client: httpx.AsyncClient,
        google_user_token: str,
        google_scenario: GoogleJourneyScenario,
        services_available: bool,
    ):
        if not services_available:
            pytest.skip("Services not available")

        gdrive = google_scenario.services[0]
        response = await control_plane_client.post(
            "/api/v1/users/me/services/connect",
            headers={"Authorization": f"Bearer {google_user_token}"},
            json={
                "service_id": gdrive.id,
                "oauth_token": {
                    "access_token": gdrive.test_token,
                    "token_type": "bearer",
                    "scope": " ".join(gdrive.oauth_scopes),
                },
            },
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_connect_gcalendar(
        self,
        control_plane_client: httpx.AsyncClient,
        google_user_token: str,
        google_scenario: GoogleJourneyScenario,
        services_available: bool,
    ):
        if not services_available:
            pytest.skip("Services not available")

        gcalendar = google_scenario.services[1]
        response = await control_plane_client.post(
            "/api/v1/users/me/services/connect",
            headers={"Authorization": f"Bearer {google_user_token}"},
            json={
                "service_id": gcalendar.id,
                "oauth_token": {
                    "access_token": gcalendar.test_token,
                    "token_type": "bearer",
                    "scope": " ".join(gcalendar.oauth_scopes),
                },
            },
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_connect_gmail(
        self,
        control_plane_client: httpx.AsyncClient,
        google_user_token: str,
        google_scenario: GoogleJourneyScenario,
        services_available: bool,
    ):
        if not services_available:
            pytest.skip("Services not available")

        gmail = google_scenario.services[2]
        response = await control_plane_client.post(
            "/api/v1/users/me/services/connect",
            headers={"Authorization": f"Bearer {google_user_token}"},
            json={
                "service_id": gmail.id,
                "oauth_token": {
                    "access_token": gmail.test_token,
                    "token_type": "bearer",
                    "scope": " ".join(gmail.oauth_scopes),
                },
            },
        )
        assert response.status_code == 200


# =============================================================================
# Step: Tool Discovery
# =============================================================================


@pytest.mark.e2e
class TestGoogleToolDiscovery:
    """Verify tools/list shows delegated Google tools and hides non-delegated."""

    @pytest.mark.asyncio
    async def test_google_tools_visible_in_tools_list(
        self,
        gateway_client: httpx.AsyncClient,
        google_agent_jwt: str,
        services_available: bool,
    ):
        if not services_available:
            pytest.skip("Services not available")

        await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_initialize_request(),
        )

        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_tools_list_request(),
        )

        assert response.status_code == 200
        result = response.json()
        assert "result" in result
        tools = result["result"]["tools"]
        tool_names = [t["name"] for t in tools]

        google_tools = [
            n for n in tool_names
            if n.startswith(("gdrive.", "gcalendar.", "gmail."))
        ]
        assert len(google_tools) >= 3, (
            f"Expected ≥3 Google tools, got {len(google_tools)}: {google_tools}"
        )

    @pytest.mark.asyncio
    async def test_non_delegated_google_tools_hidden(
        self,
        gateway_client: httpx.AsyncClient,
        google_agent_jwt: str,
        services_available: bool,
    ):
        if not services_available:
            pytest.skip("Services not available")

        await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_initialize_request(),
        )

        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_tools_list_request(),
        )

        tools = response.json()["result"]["tools"]
        tool_names = [t["name"] for t in tools]

        for hidden in GOOGLE_EXPECTED_HIDDEN_TOOLS[:3]:
            assert hidden not in tool_names, f"Non-delegated tool {hidden} visible!"

    @pytest.mark.asyncio
    async def test_google_tool_schemas_valid(
        self,
        gateway_client: httpx.AsyncClient,
        google_agent_jwt: str,
        services_available: bool,
    ):
        if not services_available:
            pytest.skip("Services not available")

        await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_initialize_request(),
        )

        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_tools_list_request(),
        )

        tools = response.json()["result"]["tools"]
        google_tools = [
            t for t in tools
            if t["name"].startswith(("gdrive.", "gcalendar.", "gmail."))
        ]

        for tool in google_tools:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool['name']} missing 'description'"
            assert "inputSchema" in tool, f"Tool {tool['name']} missing 'inputSchema'"


# =============================================================================
# Step: Tool Execution
# =============================================================================


@pytest.mark.e2e
class TestGoogleToolExecution:
    """Verify delegated tool calls succeed."""

    @pytest.mark.asyncio
    async def test_gdrive_search_files(
        self,
        gateway_client: httpx.AsyncClient,
        google_agent_jwt: str,
        services_available: bool,
    ):
        if not services_available:
            pytest.skip("Services not available")

        await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_initialize_request(),
        )

        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_tools_call_request(
                tool_name="gdrive.search_files",
                arguments={"query": "quarterly report"},
            ),
        )

        assert response.status_code == 200
        result = response.json()
        assert "result" in result, f"Expected result, got: {result}"
        assert "error" not in result
        assert "content" in result["result"]

    @pytest.mark.asyncio
    async def test_gcalendar_list_events(
        self,
        gateway_client: httpx.AsyncClient,
        google_agent_jwt: str,
        services_available: bool,
    ):
        if not services_available:
            pytest.skip("Services not available")

        await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_initialize_request(),
        )

        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_tools_call_request(
                tool_name="gcalendar.list_events",
                arguments={"calendar_id": "primary", "limit": 5},
            ),
        )

        assert response.status_code == 200
        result = response.json()
        assert "result" in result, f"Expected result, got: {result}"
        assert "error" not in result
        assert "content" in result["result"]

    @pytest.mark.asyncio
    async def test_gmail_search_messages(
        self,
        gateway_client: httpx.AsyncClient,
        google_agent_jwt: str,
        services_available: bool,
    ):
        if not services_available:
            pytest.skip("Services not available")

        await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_initialize_request(),
        )

        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_tools_call_request(
                tool_name="gmail.search_messages",
                arguments={"query": "meeting notes", "limit": 5},
            ),
        )

        assert response.status_code == 200
        result = response.json()
        assert "result" in result, f"Expected result, got: {result}"
        assert "error" not in result
        assert "content" in result["result"]


# =============================================================================
# Step: Permission Denial
# =============================================================================


@pytest.mark.e2e
class TestGoogleToolDenial:
    """Verify non-delegated Google tools are denied."""

    @pytest.mark.asyncio
    async def test_non_delegated_gdrive_tool_denied(
        self,
        gateway_client: httpx.AsyncClient,
        google_agent_jwt: str,
        services_available: bool,
    ):
        if not services_available:
            pytest.skip("Services not available")

        await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_initialize_request(),
        )

        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_tools_call_request(
                tool_name="gdrive.read_file",
                arguments={"file_id": "test-file-123"},
            ),
        )

        assert response.status_code == 200
        result = response.json()
        assert "error" in result, f"Expected error, got: {result}"
        assert result["error"]["code"] == MCP_PERMISSION_DENIED_CODE

    @pytest.mark.asyncio
    async def test_non_delegated_gmail_tool_denied(
        self,
        gateway_client: httpx.AsyncClient,
        google_agent_jwt: str,
        services_available: bool,
    ):
        if not services_available:
            pytest.skip("Services not available")

        await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_initialize_request(),
        )

        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_tools_call_request(
                tool_name="gmail.read_message",
                arguments={"message_id": "test-msg-456"},
            ),
        )

        assert response.status_code == 200
        result = response.json()
        assert "error" in result, f"Expected error, got: {result}"
        assert result["error"]["code"] == MCP_PERMISSION_DENIED_CODE


# =============================================================================
# Step: Credential Security
# =============================================================================


@pytest.mark.e2e
class TestGoogleCredentialSecurity:
    """Verify OAuth tokens are not exposed in tool responses."""

    @pytest.mark.asyncio
    async def test_google_credentials_not_in_response(
        self,
        gateway_client: httpx.AsyncClient,
        google_agent_jwt: str,
        google_scenario: GoogleJourneyScenario,
        services_available: bool,
    ):
        if not services_available:
            pytest.skip("Services not available")

        await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_initialize_request(),
        )

        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {google_agent_jwt}"},
            json=get_mcp_tools_call_request(
                tool_name="gdrive.search_files",
                arguments={"query": "test"},
            ),
        )

        response_text = str(response.json()).lower()
        assert "access_token" not in response_text
        assert "oauth" not in response_text
        assert "bearer" not in response_text

        for service in google_scenario.services:
            assert service.test_token.lower() not in response_text, (
                f"Test token for {service.id} leaked in response"
            )


# =============================================================================
# Complete Journey
# =============================================================================


@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteGoogleJourney:
    """Complete E2E test running the full Google services journey."""

    @pytest.mark.asyncio
    async def test_complete_google_services_journey(
        self,
        control_plane_client: httpx.AsyncClient,
        gateway_client: httpx.AsyncClient,
        services_available: bool,
    ):
        if not services_available:
            pytest.skip("Services not available for complete journey test")

        import base64

        from nacl.signing import SigningKey

        from .test_fixtures import (
            GCALENDAR_SERVICE,
            GDRIVE_SERVICE,
            GMAIL_SERVICE,
            GOOGLE_DELEGATED_PERMISSIONS,
            TestAgent,
            TestUser,
        )

        user = TestUser()
        agent = TestAgent()
        services = [GDRIVE_SERVICE, GCALENDAR_SERVICE, GMAIL_SERVICE]

        # Dedicated keypair for this self-contained journey (avoids conflict
        # with the session-scoped agent_keypair used by fixture-based tests).
        private_key = SigningKey.generate()
        public_key_b64 = base64.b64encode(private_key.verify_key.encode()).decode()

        # Step 1: Authenticate
        auth_response = await control_plane_client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": user.password},
        )
        assert auth_response.status_code == 200, "Login failed"
        user_token = auth_response.json()["token"]

        # Step 2: Connect Google services
        for service in services:
            connect_response = await control_plane_client.post(
                "/api/v1/users/me/services/connect",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "service_id": service.id,
                    "oauth_token": {
                        "access_token": service.test_token,
                        "token_type": "bearer",
                        "scope": " ".join(service.oauth_scopes),
                    },
                },
            )
            assert connect_response.status_code == 200, (
                f"Failed to connect {service.id}"
            )

        # Step 3: Register agent and delegate
        register_response = await control_plane_client.post(
            "/api/v1/agents/",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "agent_id": agent.id,
                "name": agent.name,
                "public_key": public_key_b64,
            },
        )
        assert register_response.status_code in [200, 201], (
            f"Agent registration failed: {register_response.status_code} "
            f"{register_response.text}"
        )

        delegation_response = await control_plane_client.post(
            "/api/v1/auth/delegate",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "agent_id": agent.id,
                "permissions": GOOGLE_DELEGATED_PERMISSIONS,
                "constraints": {"rate_limit": 100, "expires_in_hours": 8},
            },
        )
        assert delegation_response.status_code == 200, "Delegation failed"
        delegation_token = delegation_response.json()["delegation_token"]

        # Step 4: Agent authenticates
        challenge_response = await control_plane_client.post(
            "/api/v1/auth/agent/challenge",
            json={"agent_id": agent.id},
        )
        assert challenge_response.status_code == 200, (
            f"Challenge failed: {challenge_response.status_code} "
            f"{challenge_response.text}"
        )
        challenge = challenge_response.json()["challenge"]

        signature = sign_challenge(private_key, challenge)

        verify_response = await control_plane_client.post(
            "/api/v1/auth/agent/verify",
            json={
                "agent_id": agent.id,
                "challenge": challenge,
                "signature": signature,
                "delegation_token": delegation_token,
            },
        )
        assert verify_response.status_code == 200, "Agent verification failed"
        agent_jwt = verify_response.json()["access_token"]

        # Step 5: MCP Initialize
        init_response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json=get_mcp_initialize_request(),
        )
        assert init_response.status_code == 200, "MCP initialize failed"

        # Step 6: Discover Google tools
        tools_response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json=get_mcp_tools_list_request(),
        )
        assert tools_response.status_code == 200, "Tools list failed"
        tools = tools_response.json()["result"]["tools"]
        tool_names = [t["name"] for t in tools]

        google_tools = [
            n for n in tool_names
            if n.startswith(("gdrive.", "gcalendar.", "gmail."))
        ]
        assert len(google_tools) >= 3, f"Expected ≥3 Google tools, got {google_tools}"

        # Step 7: Execute delegated tools (one per service)
        for tool_name, args in [
            ("gdrive.search_files", {"query": "test"}),
            ("gcalendar.list_events", {"calendar_id": "primary", "limit": 5}),
            ("gmail.search_messages", {"query": "test", "limit": 5}),
        ]:
            call_response = await gateway_client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {agent_jwt}"},
                json=get_mcp_tools_call_request(tool_name=tool_name, arguments=args),
            )
            assert call_response.status_code == 200, f"{tool_name} call failed"
            call_result = call_response.json()
            assert "result" in call_result, f"{tool_name}: expected result, got {call_result}"

        # Step 8: Non-delegated tool denied
        denied_response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json=get_mcp_tools_call_request(
                tool_name="gdrive.read_file",
                arguments={"file_id": "test"},
            ),
        )
        assert "error" in denied_response.json(), "Non-delegated tool not denied"
        assert denied_response.json()["error"]["code"] == MCP_PERMISSION_DENIED_CODE

        # Step 9: Credential security check
        search_result = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json=get_mcp_tools_call_request(
                tool_name="gdrive.search_files",
                arguments={"query": "credential-check"},
            ),
        )
        response_text = str(search_result.json()).lower()
        assert "access_token" not in response_text
        assert "test_gdrive_token" not in response_text

        print("\n✅ Google Services Journey Complete - All Steps Passed!")


# =============================================================================
# Unit/Mock Tests (Run without live services)
# =============================================================================


class TestGoogleScenarioConfiguration:
    """Unit tests for Google scenario configuration (no live services needed)."""

    def test_google_scenario_has_valid_permissions(
        self, google_scenario: GoogleJourneyScenario
    ):
        assert len(google_scenario.delegated_permissions) >= 4
        assert "gdrive:files:search" in google_scenario.delegated_permissions
        assert "gcalendar:events:list" in google_scenario.delegated_permissions
        assert "gmail:messages:search" in google_scenario.delegated_permissions

    def test_google_scenario_services_configured(
        self, google_scenario: GoogleJourneyScenario
    ):
        assert len(google_scenario.services) == 3
        service_ids = [s.id for s in google_scenario.services]
        assert "gdrive" in service_ids
        assert "gcalendar" in service_ids
        assert "gmail" in service_ids

    def test_google_tool_lists_consistent(self):
        visible_set = set(GOOGLE_EXPECTED_VISIBLE_TOOLS)
        hidden_set = set(GOOGLE_EXPECTED_HIDDEN_TOOLS)
        assert not visible_set & hidden_set, "Overlap between visible and hidden tools"
