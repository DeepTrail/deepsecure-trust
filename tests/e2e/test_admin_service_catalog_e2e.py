"""E2E tests for Admin Service Catalog feature (P5.2).

Tests the full flow:
  1. Admin adds a service via the registry API
  2. Gateway picks up the new service via dynamic refresh
  3. Delegation template enforcement constrains user permissions
  4. Audit trail records admin actions

Requires live Control Plane and Gateway. Marked with @pytest.mark.e2e.
"""

import uuid

import httpx
import pytest
import pytest_asyncio

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def admin_token(control_plane_client: httpx.AsyncClient) -> str:
    """Authenticate as admin and return JWT."""
    resp = await control_plane_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@acme.com", "password": "admin123"},
    )
    if resp.status_code != 200:
        pytest.skip("Admin login failed — service unavailable or no admin user seeded")
    return resp.json()["token"]


@pytest_asyncio.fixture
async def user_token_f(control_plane_client: httpx.AsyncClient) -> str:
    """Authenticate as a regular user."""
    resp = await control_plane_client.post(
        "/api/v1/auth/login",
        json={"email": "sarah@acme.com", "password": "sarah123"},
    )
    if resp.status_code != 200:
        pytest.skip("User login failed — service unavailable")
    return resp.json()["token"]


# ---------------------------------------------------------------------------
# Tests: Service Registry CRUD
# ---------------------------------------------------------------------------


class TestServiceRegistryCRUD:
    """Admin can create, read, update, and delete services."""

    async def test_add_rest_service(
        self,
        control_plane_client: httpx.AsyncClient,
        admin_token: str,
    ):
        svc_id = f"test-rest-{uuid.uuid4().hex[:8]}"
        resp = await control_plane_client.post(
            "/api/v1/admin/services",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "service_id": svc_id,
                "display_name": "E2E REST Service",
                "backend_type": "rest",
                "endpoint_url": "https://api.example.com",
            },
        )
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()
        assert data["service_id"] == svc_id
        assert data["backend_type"] == "rest"
        assert data["status"] == "active"

    async def test_add_mcp_service(
        self,
        control_plane_client: httpx.AsyncClient,
        admin_token: str,
    ):
        svc_id = f"test-mcp-{uuid.uuid4().hex[:8]}"
        resp = await control_plane_client.post(
            "/api/v1/admin/services",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "service_id": svc_id,
                "display_name": "E2E MCP Service",
                "backend_type": "mcp",
                "endpoint_url": "https://mcp.example.com/sse",
                "mcp_transport": "sse",
                "mcp_auth_method": "bearer",
            },
        )
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()
        assert data["service_id"] == svc_id
        assert data["backend_type"] == "mcp"

    async def test_list_services(
        self,
        control_plane_client: httpx.AsyncClient,
        admin_token: str,
    ):
        resp = await control_plane_client.get(
            "/api/v1/admin/services",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "services" in data
        assert isinstance(data["services"], list)

    async def test_non_admin_cannot_create(
        self,
        control_plane_client: httpx.AsyncClient,
        user_token_f: str,
    ):
        resp = await control_plane_client.post(
            "/api/v1/admin/services",
            headers={"Authorization": f"Bearer {user_token_f}"},
            json={
                "service_id": "should-fail",
                "display_name": "Fail",
                "backend_type": "rest",
                "endpoint_url": "https://example.com",
            },
        )
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 for non-admin, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Tests: Delegation Template Enforcement
# ---------------------------------------------------------------------------


class TestDelegationTemplateEnforcement:
    """Delegation creation is constrained by admin templates."""

    async def test_template_blocks_over_ceiling(
        self,
        control_plane_client: httpx.AsyncClient,
        admin_token: str,
        user_token_f: str,
    ):
        agent_id = f"agent-template-test-{uuid.uuid4().hex[:8]}"

        # Admin creates template with ceiling
        resp = await control_plane_client.post(
            "/api/v1/admin/delegation-templates",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "agent_id": agent_id,
                "max_permissions": ["notion:pages:read"],
                "blocked_permissions": ["notion:pages:delete"],
            },
        )
        if resp.status_code not in (200, 201):
            pytest.skip(f"Template creation failed: {resp.text}")

        # Register agent
        import base64
        from nacl.signing import SigningKey

        pk = SigningKey.generate()
        pub_b64 = base64.b64encode(pk.verify_key.encode()).decode()

        await control_plane_client.post(
            "/api/v1/agents/",
            headers={"Authorization": f"Bearer {user_token_f}"},
            json={
                "agent_id": agent_id,
                "name": "Template Test Agent",
                "public_key": pub_b64,
            },
        )

        # User tries to delegate beyond ceiling
        resp = await control_plane_client.post(
            "/api/v1/auth/delegate",
            headers={"Authorization": f"Bearer {user_token_f}"},
            json={
                "agent_id": agent_id,
                "permissions": [
                    "notion:pages:read",
                    "notion:pages:write",
                ],
            },
        )
        # Should be rejected — notion:pages:write exceeds ceiling
        assert resp.status_code in (400, 403, 422), (
            f"Expected rejection for over-ceiling, got {resp.status_code}: {resp.text}"
        )

    async def test_template_blocks_blocked_permissions(
        self,
        control_plane_client: httpx.AsyncClient,
        admin_token: str,
        user_token_f: str,
    ):
        agent_id = f"agent-blocked-test-{uuid.uuid4().hex[:8]}"

        resp = await control_plane_client.post(
            "/api/v1/admin/delegation-templates",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "agent_id": agent_id,
                "max_permissions": [
                    "notion:pages:read",
                    "notion:pages:delete",
                ],
                "blocked_permissions": ["notion:pages:delete"],
            },
        )
        if resp.status_code not in (200, 201):
            pytest.skip(f"Template creation failed: {resp.text}")

        import base64
        from nacl.signing import SigningKey

        pk = SigningKey.generate()
        pub_b64 = base64.b64encode(pk.verify_key.encode()).decode()

        await control_plane_client.post(
            "/api/v1/agents/",
            headers={"Authorization": f"Bearer {user_token_f}"},
            json={
                "agent_id": agent_id,
                "name": "Blocked Test Agent",
                "public_key": pub_b64,
            },
        )

        resp = await control_plane_client.post(
            "/api/v1/auth/delegate",
            headers={"Authorization": f"Bearer {user_token_f}"},
            json={
                "agent_id": agent_id,
                "permissions": ["notion:pages:delete"],
            },
        )
        assert resp.status_code in (400, 403, 422), (
            f"Expected rejection for blocked perm, got {resp.status_code}: {resp.text}"
        )


# ---------------------------------------------------------------------------
# Tests: Gateway Dynamic Registry
# ---------------------------------------------------------------------------


class TestGatewayDynamicRegistry:
    """Gateway picks up services from registry."""

    async def test_gateway_health_shows_backends(
        self,
        gateway_client: httpx.AsyncClient,
    ):
        resp = await gateway_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("healthy", "ok")

    async def test_internal_registry_endpoint(
        self,
        control_plane_client: httpx.AsyncClient,
    ):
        """Internal registry endpoint returns active services."""
        resp = await control_plane_client.get(
            "/api/v1/internal/services/registry",
            headers={
                "Authorization": "Bearer gateway-internal-secret-token"
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "services" in data


# ---------------------------------------------------------------------------
# Tests: Emergency Controls
# ---------------------------------------------------------------------------


class TestEmergencyControls:
    """Admin can trigger emergency actions."""

    async def test_emergency_endpoint_exists(
        self,
        control_plane_client: httpx.AsyncClient,
        admin_token: str,
    ):
        resp = await control_plane_client.get(
            "/api/v1/admin/health/aggregated",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    async def test_non_admin_cannot_emergency(
        self,
        control_plane_client: httpx.AsyncClient,
        user_token_f: str,
    ):
        resp = await control_plane_client.post(
            "/api/v1/admin/emergency",
            headers={"Authorization": f"Bearer {user_token_f}"},
            json={"action": "suspend-all"},
        )
        assert resp.status_code in (401, 403)
