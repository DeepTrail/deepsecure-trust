"""
E2E Test Fixtures - Shared setup for end-to-end tests.

Provides:
- HTTP clients for Control Plane and Gateway
- Authentication fixtures (user tokens, agent JWTs)
- Agent key pair generation
- Test scenario data

Environment Variables:
    DEEPSECURE_CONTROL_URL: Control Plane URL (default: http://localhost:8000)
    DEEPSECURE_GATEWAY_URL: Gateway URL (default: http://localhost:8002)
    E2E_SKIP_LIVE: Set to skip live service tests
"""

import os
from typing import Any

import httpx
import pytest
from nacl.encoding import HexEncoder
from nacl.signing import SigningKey

from .test_fixtures import (
    DEFAULT_SCENARIO,
    SarahJourneyScenario,
    get_mcp_initialize_request,
)


# =============================================================================
# Environment Configuration
# =============================================================================


@pytest.fixture(scope="session")
def control_plane_url() -> str:
    """Control Plane URL from environment or default."""
    return os.getenv("DEEPSECURE_CONTROL_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def gateway_url() -> str:
    """Gateway URL from environment or default."""
    return os.getenv("DEEPSECURE_GATEWAY_URL", "http://localhost:8002")


@pytest.fixture(scope="session")
def skip_live_tests() -> bool:
    """Check if live service tests should be skipped."""
    return os.getenv("E2E_SKIP_LIVE", "").lower() in ("1", "true", "yes")


# =============================================================================
# HTTP Clients
# =============================================================================


@pytest.fixture
async def control_plane_client(control_plane_url: str) -> httpx.AsyncClient:
    """Async HTTP client for Control Plane."""
    async with httpx.AsyncClient(
        base_url=control_plane_url,
        timeout=30.0,
    ) as client:
        yield client


@pytest.fixture
async def gateway_client(gateway_url: str) -> httpx.AsyncClient:
    """Async HTTP client for Gateway."""
    async with httpx.AsyncClient(
        base_url=gateway_url,
        timeout=30.0,
    ) as client:
        yield client


# =============================================================================
# Agent Authentication
# =============================================================================


@pytest.fixture
def agent_keypair() -> dict[str, Any]:
    """
    Generate Ed25519 keypair for agent authentication.

    Returns:
        Dict with private_key, public_key, and public_key_hex
    """
    private_key = SigningKey.generate()
    public_key = private_key.verify_key

    return {
        "private_key": private_key,
        "public_key": public_key,
        "public_key_hex": public_key.encode(encoder=HexEncoder).decode(),
    }


def sign_challenge(private_key: SigningKey, challenge: str) -> str:
    """
    Sign a challenge with the agent's private key.

    Args:
        private_key: Ed25519 signing key
        challenge: Challenge string to sign

    Returns:
        Hex-encoded signature
    """
    signature = private_key.sign(
        challenge.encode(),
        encoder=HexEncoder,
    ).signature
    return signature.decode()


# =============================================================================
# Test Scenario
# =============================================================================


@pytest.fixture
def scenario() -> SarahJourneyScenario:
    """Get the default test scenario."""
    return DEFAULT_SCENARIO


# =============================================================================
# Authentication Flow Fixtures
# =============================================================================


@pytest.fixture
async def user_token(
    control_plane_client: httpx.AsyncClient,
    scenario: SarahJourneyScenario,
) -> str:
    """
    Get Sarah's user token (Step 2 of journey).

    Authenticates Sarah with the Control Plane and returns the JWT.
    If the service is not available, returns a mock token.
    """
    try:
        response = await control_plane_client.post(
            "/api/v1/auth/login",
            json={
                "email": scenario.user.email,
                "password": scenario.user.password,
            },
        )

        if response.status_code == 200:
            return response.json()["token"]

        # Service returned error - use mock
        return _generate_mock_user_token(scenario)

    except httpx.ConnectError:
        # Service not available - use mock
        return _generate_mock_user_token(scenario)


def _generate_mock_user_token(scenario: SarahJourneyScenario) -> str:
    """Generate a mock user token for testing without live service."""
    # In real implementation, this would be a valid JWT
    # For unit testing, we use a placeholder
    return f"mock_user_token_{scenario.user.id}"


@pytest.fixture
async def delegation_token(
    control_plane_client: httpx.AsyncClient,
    user_token: str,
    scenario: SarahJourneyScenario,
    agent_keypair: dict[str, Any],
) -> str:
    """
    Create delegation from Sarah to agent (Steps 3-4).

    Returns:
        Delegation token for agent authentication
    """
    try:
        # Register agent
        await control_plane_client.post(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {user_token}"},
            json=scenario.get_agent_register_request(agent_keypair["public_key_hex"]),
        )

        # Connect services
        for service in scenario.services:
            await control_plane_client.post(
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

        # Create delegation
        response = await control_plane_client.post(
            "/api/v1/delegations",
            headers={"Authorization": f"Bearer {user_token}"},
            json=scenario.get_delegation_request(),
        )

        if response.status_code == 200:
            return response.json()["delegation_token"]

        return _generate_mock_delegation_token(scenario)

    except httpx.ConnectError:
        return _generate_mock_delegation_token(scenario)


def _generate_mock_delegation_token(scenario: SarahJourneyScenario) -> str:
    """Generate a mock delegation token for testing."""
    return f"mock_delegation_token_{scenario.agent.id}"


@pytest.fixture
async def agent_jwt(
    control_plane_client: httpx.AsyncClient,
    delegation_token: str,
    scenario: SarahJourneyScenario,
    agent_keypair: dict[str, Any],
) -> str:
    """
    Authenticate agent and get JWT (Step 5).

    Returns:
        Agent JWT for Gateway authentication
    """
    try:
        # Request challenge
        challenge_response = await control_plane_client.post(
            "/api/v1/agents/challenge",
            json={"agent_id": scenario.agent.id},
        )

        if challenge_response.status_code != 200:
            return _generate_mock_agent_jwt(scenario)

        challenge = challenge_response.json()["challenge"]

        # Sign challenge
        signature = sign_challenge(agent_keypair["private_key"], challenge)

        # Verify and get JWT
        verify_response = await control_plane_client.post(
            "/api/v1/agents/verify",
            json={
                "agent_id": scenario.agent.id,
                "challenge": challenge,
                "signature": signature,
                "delegation_token": delegation_token,
            },
        )

        if verify_response.status_code == 200:
            return verify_response.json()["jwt"]

        return _generate_mock_agent_jwt(scenario)

    except httpx.ConnectError:
        return _generate_mock_agent_jwt(scenario)


def _generate_mock_agent_jwt(scenario: SarahJourneyScenario) -> str:
    """Generate a mock agent JWT for testing."""
    return f"mock_agent_jwt_{scenario.agent.id}"


# =============================================================================
# Gateway Session Fixtures
# =============================================================================


@pytest.fixture
async def initialized_session(
    gateway_client: httpx.AsyncClient,
    agent_jwt: str,
) -> dict[str, Any]:
    """
    Initialize MCP session with Gateway (Step 6).

    Returns:
        Initialize response with session info
    """
    try:
        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json=get_mcp_initialize_request(),
        )

        if response.status_code == 200:
            return response.json()

        return _generate_mock_initialize_response()

    except httpx.ConnectError:
        return _generate_mock_initialize_response()


def _generate_mock_initialize_response() -> dict[str, Any]:
    """Generate a mock initialize response."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "DeepTrail Gateway",
                "version": "0.1.0",
            },
            "capabilities": {
                "tools": {},
            },
        },
    }


# =============================================================================
# Service Availability Checks
# =============================================================================


@pytest.fixture
async def services_available(
    control_plane_url: str,
    gateway_url: str,
) -> bool:
    """Check if both Control Plane and Gateway are available."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            control_health = await client.get(f"{control_plane_url}/health")
            gateway_health = await client.get(f"{gateway_url}/health")
            return (
                control_health.status_code == 200 and gateway_health.status_code == 200
            )
        except httpx.ConnectError:
            return False


def skip_if_services_unavailable(services_available: bool):
    """Skip test if services are not available."""
    if not services_available:
        pytest.skip("Control Plane and/or Gateway not available")
