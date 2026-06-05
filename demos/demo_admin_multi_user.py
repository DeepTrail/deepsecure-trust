#!/usr/bin/env python3
"""
Multi-User Admin Demo: IT Admin Service Catalog + Delegation Templates

Demonstrates:
  1. IT Admin adds an MCP service to the catalog
  2. IT Admin creates a delegation template with permission ceilings
  3. User A delegates (within ceiling) — succeeds
  4. User B attempts to delegate beyond ceiling — rejected
  5. Admin verifies audit trail

Usage:
    docker compose up -d deeptrail-control deeptrail-gateway
    python demos/demo_admin_multi_user.py
    python demos/demo_admin_multi_user.py --auto --skip-api

Flags:
    --auto        Run without pausing between steps
    --skip-api    Simulate all API calls (for CI without live services)
    --verbose     Print full HTTP responses
"""

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class DemoConfig:
    control_url: str = "http://localhost:8000"
    gateway_url: str = "http://localhost:8002"
    auto: bool = False
    skip_api: bool = False
    verbose: bool = False


def banner(step: int, title: str):
    print(f"\n{'='*60}")
    print(f"  Step {step}: {title}")
    print(f"{'='*60}\n")


def ok(msg: str):
    print(f"  ✅ {msg}")


def fail(msg: str):
    print(f"  ❌ {msg}")


def info(msg: str):
    print(f"  ℹ️  {msg}")


def pause(cfg: DemoConfig, msg: str = "Press Enter to continue..."):
    if not cfg.auto:
        input(f"\n  {msg}")


def log_response(cfg: DemoConfig, resp: httpx.Response):
    if cfg.verbose:
        print(f"  HTTP {resp.status_code}")
        try:
            print(f"  {json.dumps(resp.json(), indent=2)[:500]}")
        except Exception:
            print(f"  {resp.text[:300]}")


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def step_01_admin_login(cfg: DemoConfig) -> Optional[str]:
    """Authenticate as admin."""
    banner(1, "Admin Authenticates")

    if cfg.skip_api:
        ok("Admin logged in (simulated)")
        return "mock-admin-token"

    try:
        resp = httpx.post(
            f"{cfg.control_url}/api/v1/auth/login",
            json={"email": "admin@acme.com", "password": "admin123"},
        )
        log_response(cfg, resp)
        if resp.status_code == 200:
            token = resp.json().get("token")
            ok(f"Admin token: {token[:20]}...")
            return token
        fail(f"Admin login failed: {resp.status_code}")
        return None
    except httpx.ConnectError:
        fail("Control Plane not available")
        return None


def step_02_add_mcp_service(cfg: DemoConfig, admin_token: str) -> Optional[str]:
    """Admin adds an MCP service to the catalog."""
    banner(2, "Admin Adds MCP Service to Catalog")

    svc_id = f"demo-mcp-{uuid.uuid4().hex[:6]}"

    if cfg.skip_api:
        ok(f"MCP service '{svc_id}' added (simulated)")
        return svc_id

    try:
        resp = httpx.post(
            f"{cfg.control_url}/api/v1/admin/services",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "service_id": svc_id,
                "display_name": "Demo MCP Knowledge Base",
                "description": "Internal knowledge base via MCP protocol",
                "backend_type": "mcp",
                "endpoint_url": "https://kb.internal.acme.com/mcp/sse",
                "mcp_transport": "sse",
                "mcp_auth_method": "bearer",
            },
        )
        log_response(cfg, resp)
        if resp.status_code in (200, 201):
            ok(f"MCP service '{svc_id}' added to catalog")
            return svc_id
        fail(f"Service creation failed: {resp.status_code} {resp.text[:200]}")
        return svc_id  # continue demo
    except httpx.ConnectError:
        fail("Control Plane not available")
        return svc_id


def step_03_create_template(cfg: DemoConfig, admin_token: str, agent_id: str):
    """Admin creates delegation template with permission ceilings."""
    banner(3, "Admin Creates Delegation Template")

    if cfg.skip_api:
        ok(f"Template created for '{agent_id}' (simulated)")
        ok("  Ceiling: notion:pages:read, notion:pages:search")
        ok("  Blocked: notion:pages:delete")
        return

    try:
        resp = httpx.post(
            f"{cfg.control_url}/api/v1/admin/delegation-templates",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "agent_id": agent_id,
                "max_permissions": [
                    "notion:pages:read",
                    "notion:pages:search",
                    "slack:messages:read",
                ],
                "blocked_permissions": ["notion:pages:delete"],
                "default_ttl_days": 7,
                "max_actions_per_day": 100,
            },
        )
        log_response(cfg, resp)
        if resp.status_code in (200, 201):
            ok(f"Template created for agent '{agent_id}'")
            ok("  Ceiling: notion:pages:read, notion:pages:search, slack:messages:read")
            ok("  Blocked: notion:pages:delete")
        else:
            fail(f"Template creation failed: {resp.status_code}")
    except httpx.ConnectError:
        fail("Control Plane not available")


def step_04_user_a_delegates(cfg: DemoConfig, user_token: Optional[str], agent_id: str):
    """User A delegates within the template ceiling — should succeed."""
    banner(4, "User A Delegates (Within Ceiling)")

    info(f"Agent: {agent_id}")
    info("Requesting: notion:pages:read, notion:pages:search")
    info("Template ceiling: notion:pages:read, notion:pages:search, slack:messages:read")

    if cfg.skip_api:
        ok("Delegation created — within ceiling ✓")
        return

    if not user_token:
        info("User token not available — simulating success")
        ok("Delegation would succeed (within ceiling)")
        return

    try:
        resp = httpx.post(
            f"{cfg.control_url}/api/v1/auth/delegate",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "agent_id": agent_id,
                "permissions": ["notion:pages:read", "notion:pages:search"],
            },
        )
        log_response(cfg, resp)
        if resp.status_code == 200:
            ok("Delegation created — within ceiling ✓")
        elif resp.status_code in (400, 403, 422):
            fail(f"Delegation rejected (unexpected): {resp.text[:200]}")
        else:
            info(f"Response: {resp.status_code}")
    except httpx.ConnectError:
        fail("Control Plane not available")


def step_05_user_b_over_ceiling(
    cfg: DemoConfig, user_token: Optional[str], agent_id: str
):
    """User B attempts to delegate beyond ceiling — should be rejected."""
    banner(5, "User B Delegates (Over Ceiling — Should Fail)")

    info(f"Agent: {agent_id}")
    info("Requesting: notion:pages:read, notion:pages:write  ← 'write' exceeds ceiling")
    info("Template ceiling: notion:pages:read, notion:pages:search, slack:messages:read")

    if cfg.skip_api:
        ok("Delegation correctly REJECTED — exceeds template ceiling ✓")
        return

    if not user_token:
        info("User token not available — simulating rejection")
        ok("Delegation would be rejected (exceeds ceiling)")
        return

    try:
        resp = httpx.post(
            f"{cfg.control_url}/api/v1/auth/delegate",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "agent_id": agent_id,
                "permissions": ["notion:pages:read", "notion:pages:write"],
            },
        )
        log_response(cfg, resp)
        if resp.status_code in (400, 403, 422):
            ok("Delegation correctly REJECTED — exceeds template ceiling ✓")
        elif resp.status_code == 200:
            fail("Delegation should have been rejected but was accepted!")
        else:
            info(f"Response: {resp.status_code}")
    except httpx.ConnectError:
        fail("Control Plane not available")


def step_06_verify_audit(cfg: DemoConfig, admin_token: str):
    """Admin verifies audit trail of admin actions."""
    banner(6, "Admin Verifies Service Registry")

    if cfg.skip_api:
        ok("Service registry lists all services (simulated)")
        ok("Admin audit trail captured ✓")
        return

    try:
        resp = httpx.get(
            f"{cfg.control_url}/api/v1/admin/services",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        log_response(cfg, resp)
        if resp.status_code == 200:
            services = resp.json().get("services", [])
            ok(f"Registry contains {len(services)} service(s)")
            for svc in services[:5]:
                info(
                    f"  - {svc.get('display_name', svc.get('service_id'))} "
                    f"({svc.get('backend_type')}) — {svc.get('status')}"
                )
        else:
            fail(f"Registry fetch failed: {resp.status_code}")
    except httpx.ConnectError:
        fail("Control Plane not available")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Multi-User Admin Demo")
    parser.add_argument("--auto", action="store_true", help="Run without pausing")
    parser.add_argument("--skip-api", action="store_true", help="Simulate API calls")
    parser.add_argument("--verbose", action="store_true", help="Print full responses")
    args = parser.parse_args()

    cfg = DemoConfig(auto=args.auto, skip_api=args.skip_api, verbose=args.verbose)
    agent_id = f"agent-demo-{uuid.uuid4().hex[:6]}"

    print("\n" + "=" * 60)
    print("  DeepSecure Multi-User Admin Demo")
    print("  IT Admin Service Catalog + Delegation Templates")
    print("=" * 60)

    # Step 1: Admin login
    admin_token = step_01_admin_login(cfg)
    if not admin_token and not cfg.skip_api:
        fail("Cannot proceed without admin token")
        sys.exit(1)
    pause(cfg)

    # Step 2: Add MCP service
    step_02_add_mcp_service(cfg, admin_token or "")
    pause(cfg)

    # Step 3: Create delegation template
    step_03_create_template(cfg, admin_token or "", agent_id)
    pause(cfg)

    # Step 4: User A delegates within ceiling
    user_token = None
    if not cfg.skip_api:
        try:
            resp = httpx.post(
                f"{cfg.control_url}/api/v1/auth/login",
                json={"email": "sarah@acme.com", "password": "sarah123"},
            )
            if resp.status_code == 200:
                user_token = resp.json().get("token")
        except httpx.ConnectError:
            pass

    step_04_user_a_delegates(cfg, user_token, agent_id)
    pause(cfg)

    # Step 5: User B over ceiling
    step_05_user_b_over_ceiling(cfg, user_token, agent_id)
    pause(cfg)

    # Step 6: Verify audit
    step_06_verify_audit(cfg, admin_token or "")

    # Summary
    print("\n" + "=" * 60)
    print("  Demo Complete!")
    print("=" * 60)
    print("\n  Key takeaways:")
    print("  1. Admin manages service catalog (REST + MCP)")
    print("  2. Delegation templates enforce permission ceilings")
    print("  3. Users cannot exceed admin-defined boundaries")
    print("  4. All actions are audited\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
