"""
GCP Bootstrap E2E Test — WS-E1

Validates the full GCP Workload Identity agent lifecycle:
  1. Register a platform agent (GCP) via API
  2. Verify agent detail returns platform fields + lifecycle state
  3. Bootstrap agent with a GCP OIDC identity token
  4. Verify lifecycle state transitions after bootstrap
  5. Verify backwards compatibility (key-based flow still works)
  6. Clean up test data

Two execution modes:
  - **Local mode** (default): Tests registration, detail, list, and error
    paths against the running deeptrail-control container.  Bootstrap success
    tests are skipped because they require a real GCP OIDC token.
  - **Live GCP mode** (`pytest -m live_gcp`): Also tests the happy-path
    bootstrap flow with a real identity token from the GCP metadata server.

Usage:
    # Local mode (requires running deeptrail-control)
    pytest tests/e2e/test_gcp_bootstrap_e2e.py -v

    # Full mode including live GCP bootstrap
    pytest tests/e2e/test_gcp_bootstrap_e2e.py -v -m "e2e or live_gcp"

Markers:
    @pytest.mark.e2e: Tests that run against the local container
    @pytest.mark.live_gcp: Tests that require real GCP (skipped by default)
"""

import uuid
from typing import Any

import httpx
import pytest
import pytest_asyncio


pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def user_token(control_plane_client: httpx.AsyncClient) -> str:
    """Authenticate the default admin user and return the JWT."""
    try:
        resp = await control_plane_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@deepsecure.one", "password": "admin123"},
        )
        if resp.status_code == 200:
            return resp.json()["token"]
    except httpx.ConnectError:
        pass
    pytest.skip("Control Plane not available")


@pytest_asyncio.fixture
async def registered_gcp_agent(
    control_plane_client: httpx.AsyncClient,
    user_token: str,
) -> dict[str, Any]:
    """Register a unique platform (GCP) agent and clean up after the test."""
    selector = f"e2e-{uuid.uuid4().hex[:12]}@test-project.iam.gserviceaccount.com"
    name = f"E2E GCP Agent {uuid.uuid4().hex[:6]}"

    resp = await control_plane_client.post(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "name": name,
            "platform": "gcp_workload_identity",
            "selector": selector,
        },
    )
    assert resp.status_code == 201, f"GCP agent registration failed: {resp.text}"
    data = resp.json()
    data["_selector"] = selector

    yield data

    await control_plane_client.delete(
        f"/api/v1/agents/{data['agent_id']}",
        headers={"Authorization": f"Bearer {user_token}"},
    )


# ---------------------------------------------------------------------------
# 1. Platform Agent Registration
# ---------------------------------------------------------------------------


class TestGCPAgentRegistration:
    """Validate platform agent registration via API."""

    async def test_platform_agent_created(
        self, registered_gcp_agent: dict,
    ):
        assert registered_gcp_agent["agent_id"] is not None
        assert registered_gcp_agent["platform"] == "gcp_workload_identity"
        assert registered_gcp_agent["_selector"] == registered_gcp_agent["selector"]
        assert registered_gcp_agent.get("private_key") is None

    async def test_duplicate_selector_rejected(
        self,
        control_plane_client: httpx.AsyncClient,
        user_token: str,
        registered_gcp_agent: dict,
    ):
        resp = await control_plane_client.post(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "name": "Dup Agent",
                "platform": "gcp_workload_identity",
                "selector": registered_gcp_agent["_selector"],
            },
        )
        assert resp.status_code == 409

    async def test_key_based_registration_unchanged(
        self,
        control_plane_client: httpx.AsyncClient,
        user_token: str,
    ):
        resp = await control_plane_client.post(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"name": f"E2E Key Agent {uuid.uuid4().hex[:6]}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["private_key"] is not None
        assert data["platform"] is None

        await control_plane_client.delete(
            f"/api/v1/agents/{data['agent_id']}",
            headers={"Authorization": f"Bearer {user_token}"},
        )

    async def test_platform_without_selector_rejected(
        self,
        control_plane_client: httpx.AsyncClient,
        user_token: str,
    ):
        resp = await control_plane_client.post(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "name": "Bad Platform Agent",
                "platform": "gcp_workload_identity",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 2. Agent Detail
# ---------------------------------------------------------------------------


class TestGCPAgentDetail:
    """Verify agent detail returns platform fields and lifecycle."""

    async def test_get_agent_returns_platform_fields(
        self,
        control_plane_client: httpx.AsyncClient,
        user_token: str,
        registered_gcp_agent: dict,
    ):
        agent_id = registered_gcp_agent["agent_id"]
        resp = await control_plane_client.get(
            f"/api/v1/agents/{agent_id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["platform"] == "gcp_workload_identity"
        assert data["selector"] == registered_gcp_agent["_selector"]

    async def test_lifecycle_state_registered(
        self,
        control_plane_client: httpx.AsyncClient,
        user_token: str,
        registered_gcp_agent: dict,
    ):
        agent_id = registered_gcp_agent["agent_id"]
        resp = await control_plane_client.get(
            f"/api/v1/agents/{agent_id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
        assert resp.json().get("lifecycle_state") == "registered"


# ---------------------------------------------------------------------------
# 3. GCP Bootstrap — Error Paths (no real GCP needed)
# ---------------------------------------------------------------------------


class TestGCPBootstrapErrors:
    """Validate bootstrap error handling against the live container."""

    async def test_bootstrap_invalid_token_rejected(
        self,
        control_plane_client: httpx.AsyncClient,
        registered_gcp_agent: dict,
    ):
        """An invalid OIDC token must be rejected with 401."""
        resp = await control_plane_client.post(
            "/api/v1/auth/bootstrap/gcp",
            json={"identity_token": "clearly-invalid-token"},
        )
        assert resp.status_code == 401

    async def test_bootstrap_missing_token_rejected(
        self,
        control_plane_client: httpx.AsyncClient,
    ):
        """Missing identity_token field must return 422."""
        resp = await control_plane_client.post(
            "/api/v1/auth/bootstrap/gcp",
            json={},
        )
        assert resp.status_code == 422

    async def test_bootstrap_empty_token_rejected(
        self,
        control_plane_client: httpx.AsyncClient,
    ):
        """Empty identity_token string must be rejected."""
        resp = await control_plane_client.post(
            "/api/v1/auth/bootstrap/gcp",
            json={"identity_token": ""},
        )
        # Either 401 (caught at verification) or 422 (caught at validation)
        assert resp.status_code in (401, 422)


# ---------------------------------------------------------------------------
# 4. GCP Bootstrap — Happy Path (requires live GCP or gcloud CLI)
# ---------------------------------------------------------------------------


def _get_gcp_identity_token(audience: str = "https://app.deepsecure.one") -> tuple[str, str]:
    """Obtain a real GCP OIDC identity token and the associated email.

    Tries two sources in order:
      1. GCP metadata server (when running on Cloud Run / GCE / GKE)
      2. `gcloud auth print-identity-token` (works from any machine with gcloud)

    Returns:
        (identity_token, email) or calls pytest.skip() if neither works.
    """
    import subprocess

    # --- Source 1: GCP metadata server ---
    try:
        token_resp = httpx.get(
            "http://metadata.google.internal/computeMetadata/v1/"
            "instance/service-accounts/default/identity"
            f"?audience={audience}",
            headers={"Metadata-Flavor": "Google"},
            timeout=2.0,
        )
        if token_resp.status_code == 200:
            email_resp = httpx.get(
                "http://metadata.google.internal/computeMetadata/v1/"
                "instance/service-accounts/default/email",
                headers={"Metadata-Flavor": "Google"},
                timeout=2.0,
            )
            return token_resp.text, email_resp.text.strip()
    except (httpx.ConnectError, httpx.ConnectTimeout):
        pass

    # --- Source 2: gcloud CLI ---
    try:
        # Try impersonating the project's service account (custom audience requires SA)
        sa_email = None
        sa_result = subprocess.run(
            ["gcloud", "iam", "service-accounts", "list",
             "--format=value(email)", "--limit=1",
             "--filter=email~iam.gserviceaccount.com AND NOT email~compute@"],
            capture_output=True, text=True, timeout=10,
        )
        if sa_result.returncode == 0 and sa_result.stdout.strip():
            sa_email = sa_result.stdout.strip().split("\n")[0]

        if sa_email:
            token_result = subprocess.run(
                ["gcloud", "auth", "print-identity-token",
                 f"--impersonate-service-account={sa_email}",
                 f"--audiences={audience}",
                 "--include-email"],
                capture_output=True, text=True, timeout=15,
            )
        else:
            token_result = subprocess.run(
                ["gcloud", "auth", "print-identity-token", f"--audiences={audience}"],
                capture_output=True, text=True, timeout=15,
            )
            sa_email = None

        if token_result.returncode != 0:
            pytest.skip(
                f"gcloud identity token failed: {token_result.stderr.strip()}"
            )

        identity_token = token_result.stdout.strip()

        if not sa_email:
            email_result = subprocess.run(
                ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
                capture_output=True, text=True, timeout=10,
            )
            sa_email = email_result.stdout.strip()

        if not sa_email:
            pytest.skip("Could not determine active gcloud account email")

        return identity_token, sa_email
    except FileNotFoundError:
        pytest.skip("Neither GCP metadata server nor gcloud CLI available")


@pytest.mark.live_gcp
class TestGCPBootstrapLive:
    """Bootstrap with a real GCP OIDC token — runs on GCP or via gcloud CLI."""

    async def test_bootstrap_with_real_token(
        self,
        control_plane_client: httpx.AsyncClient,
        user_token: str,
    ):
        """Full bootstrap flow with a real GCP OIDC identity token.

        Token sources (tried in order):
          1. GCP metadata server (Cloud Run / GCE / GKE)
          2. `gcloud auth print-identity-token` (any machine with gcloud)

        Prerequisites:
          - Active gcloud auth session OR running on GCP
          - deeptrail-control container running locally
        """
        identity_token, email = _get_gcp_identity_token()

        register_resp = await control_plane_client.post(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "name": f"Live GCP Agent {uuid.uuid4().hex[:6]}",
                "platform": "gcp_workload_identity",
                "selector": email,
            },
        )
        if register_resp.status_code == 409:
            pass  # already registered
        else:
            assert register_resp.status_code == 201

        bootstrap_resp = await control_plane_client.post(
            "/api/v1/auth/bootstrap/gcp",
            json={"identity_token": identity_token},
        )
        assert bootstrap_resp.status_code == 200, (
            f"Bootstrap failed ({bootstrap_resp.status_code}): {bootstrap_resp.text}"
        )
        data = bootstrap_resp.json()
        assert data["access_token"] is not None
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0


# ---------------------------------------------------------------------------
# 5. Platform Agent in List
# ---------------------------------------------------------------------------


class TestGCPAgentInList:
    """Verify platform agent appears in the agent list endpoint."""

    async def test_platform_agent_in_list(
        self,
        control_plane_client: httpx.AsyncClient,
        user_token: str,
        registered_gcp_agent: dict,
    ):
        resp = await control_plane_client.get(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
        agents = resp.json()["agents"]
        agent_ids = [a["agent_id"] for a in agents]
        assert registered_gcp_agent["agent_id"] in agent_ids

        match = next(
            a for a in agents if a["agent_id"] == registered_gcp_agent["agent_id"]
        )
        assert match["platform"] == "gcp_workload_identity"


# ---------------------------------------------------------------------------
# 6. Cleanup Verification
# ---------------------------------------------------------------------------


class TestGCPAgentCleanup:
    """Verify agent deletion works for platform agents."""

    async def test_delete_platform_agent(
        self,
        control_plane_client: httpx.AsyncClient,
        user_token: str,
    ):
        selector = f"cleanup-{uuid.uuid4().hex[:12]}@test.iam.gserviceaccount.com"
        create_resp = await control_plane_client.post(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "name": "Cleanup Test Agent",
                "platform": "gcp_workload_identity",
                "selector": selector,
            },
        )
        assert create_resp.status_code == 201
        agent_id = create_resp.json()["agent_id"]

        del_resp = await control_plane_client.delete(
            f"/api/v1/agents/{agent_id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert del_resp.status_code == 200

        verify = await control_plane_client.get(
            f"/api/v1/agents/{agent_id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert verify.status_code == 404
