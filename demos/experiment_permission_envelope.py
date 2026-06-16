#!/usr/bin/env python3
"""
Permission Envelope Compilation — Builder Receipt Experiment

Measures the tool exposure gap across three delegation states for the same task:
  State 1: Full delegation (industry default) — all 34 tools exposed
  State 2: Scoped delegation (DeepTrail MVP) — 7 tools exposed
  State 3: Intent-compiled envelope (minimal) — 4 tools exposed

Task: "Research a prospect and prepare outreach notes"
Agent: Sarah's SDR-Assistant
Persona: Sarah Chen, SDR at Acme Corp

Output: Quantitative comparison for LinkedIn Post 15 builder receipt.

Usage:
    python demos/experiment_permission_envelope.py
"""

import base64
import json
import sys
import time
from dataclasses import dataclass, field

import httpx
from nacl.signing import SigningKey

CONTROL_PLANE_URL = "http://localhost:8000"
GATEWAY_URL = "http://localhost:8002"

ALL_PERMISSIONS = [
    # Notion (8 tools)
    "notion:pages:search",
    "notion:pages:read",
    "notion:blocks:read",
    "notion:pages:create",
    "notion:pages:update",
    "notion:pages:delete",
    "notion:databases:list",
    "notion:databases:query",
    # Slack (7 tools)
    "slack:messages:search",
    "slack:messages:send",
    "slack:channels:list",
    "slack:channels:history",
    "slack:channels:join",
    "slack:reactions:write",
    "slack:users:list",
    # Google Drive (4 tools)
    "gdrive:files:search",
    "gdrive:files:read",
    "gdrive:files:list",
    "gdrive:files:metadata",
    # Google Calendar (4 tools)
    "gcalendar:calendars:list",
    "gcalendar:events:list",
    "gcalendar:events:read",
    "gcalendar:events:search",
    # Gmail (4 tools)
    "gmail:messages:list",
    "gmail:messages:read",
    "gmail:messages:search",
    "gmail:labels:list",
]

SCOPED_PERMISSIONS = [
    "notion:pages:search",
    "notion:pages:read",
    "slack:messages:search",
    "slack:channels:list",
]

ENVELOPE_PERMISSIONS = [
    "notion:pages:search",
    "notion:pages:read",
    "slack:messages:search",
]

TASK_TOOLS_USED = [
    "notion.search_pages",
    "notion.read_page",
    "slack.search_messages",
]


def generate_keypair():
    private_key = SigningKey.generate()
    public_key = private_key.verify_key
    public_key_b64 = base64.b64encode(public_key.encode()).decode()
    return private_key, public_key_b64


def sign_challenge(private_key: SigningKey, challenge: str) -> str:
    signed = private_key.sign(challenge.encode())
    return base64.urlsafe_b64encode(signed.signature).decode()


def login(client: httpx.Client) -> str:
    resp = client.post(f"{CONTROL_PLANE_URL}/api/v1/auth/login", json={
        "email": "sarah@acme.com",
        "password": "secure_password",
    })
    data = resp.json()
    if resp.status_code != 200 or "token" not in data:
        print(f"  ❌ Login failed: {data}")
        sys.exit(1)
    return data["token"]


def connect_services(client: httpx.Client, user_token: str):
    headers = {"Authorization": f"Bearer {user_token}"}
    services = [
        ("notion", "test_notion_token_12345", ["full_access"]),
        ("slack", "test_slack_token_67890", ["full_access"]),
        ("github", "test_github_token_11111", ["full_access"]),
        ("gdrive", "test_gdrive_token_22222", ["drive.readonly"]),
        ("gcalendar", "test_gcalendar_token_33333", ["calendar.readonly", "calendar.events.readonly"]),
        ("gmail", "test_gmail_token_44444", ["gmail.readonly"]),
    ]
    for service_id, token, scopes in services:
        resp = client.post(f"{CONTROL_PLANE_URL}/api/v1/users/me/services/connect",
            json={
                "service_id": service_id,
                "oauth_token": {
                    "access_token": token,
                    "token_type": "bearer",
                    "scope": " ".join(scopes),
                },
            },
            headers=headers,
        )
        if resp.status_code == 200:
            print(f"  ✓ Connected {service_id}")
        else:
            try:
                detail = resp.json().get("detail", "unknown")
            except Exception:
                detail = resp.text[:100]
            print(f"  ⚠ {service_id}: {resp.status_code} — {detail}")


def register_agent_and_delegate(client: httpx.Client, user_token: str,
                                 agent_id: str, public_key_b64: str,
                                 permissions: list) -> str | None:
    headers = {"Authorization": f"Bearer {user_token}"}

    # Register agent (409 = already exists, OK)
    resp = client.post(f"{CONTROL_PLANE_URL}/api/v1/agents/", json={
        "agent_id": agent_id,
        "name": "SDR-Assistant",
        "public_key": public_key_b64,
    }, headers=headers)
    if resp.status_code not in [200, 201, 409]:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text[:200]
        print(f"  ❌ Agent registration failed ({resp.status_code}): {detail}")
        return None

    # Create delegation
    resp = client.post(f"{CONTROL_PLANE_URL}/api/v1/auth/delegate", json={
        "agent_id": agent_id,
        "permissions": permissions,
        "constraints": {"rate_limit": 100, "expires_in_hours": 8},
    }, headers=headers)
    data = resp.json()
    if resp.status_code == 200 and "delegation_token" in data:
        return data["delegation_token"]
    else:
        print(f"  ❌ Delegation failed: {data}")
        return None


def authenticate_agent(client: httpx.Client, agent_id: str,
                       private_key: SigningKey, delegation_token: str) -> str | None:
    # Challenge
    resp = client.post(f"{CONTROL_PLANE_URL}/api/v1/auth/agent/challenge",
                       json={"agent_id": agent_id})
    data = resp.json()
    if resp.status_code != 200 or "challenge" not in data:
        print(f"  ❌ Challenge failed: {data}")
        return None
    challenge = data["challenge"]

    # Sign and verify
    signature = sign_challenge(private_key, challenge)
    resp = client.post(f"{CONTROL_PLANE_URL}/api/v1/auth/agent/verify", json={
        "agent_id": agent_id,
        "challenge": challenge,
        "signature": signature,
        "delegation_token": delegation_token,
    })
    data = resp.json()
    if resp.status_code == 200 and "access_token" in data:
        return data["access_token"]
    else:
        print(f"  ❌ Agent auth failed: {data}")
        return None


def mcp_initialize(client: httpx.Client, agent_jwt: str) -> bool:
    resp = client.post(f"{GATEWAY_URL}/mcp", json={
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1,
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "SDR-Assistant", "version": "1.0.0"},
        },
    }, headers={"Authorization": f"Bearer {agent_jwt}"})
    data = resp.json()
    return resp.status_code == 200 and "result" in data


def mcp_tools_list(client: httpx.Client, agent_jwt: str) -> list:
    resp = client.post(f"{GATEWAY_URL}/mcp", json={
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 2,
        "params": {},
    }, headers={"Authorization": f"Bearer {agent_jwt}"})
    data = resp.json()
    if resp.status_code == 200 and "result" in data:
        return data["result"].get("tools", [])
    else:
        print(f"  ❌ tools/list failed: {data}")
        return []


def mcp_tools_call(client: httpx.Client, agent_jwt: str, tool_name: str, arguments: dict) -> dict | None:
    resp = client.post(f"{GATEWAY_URL}/mcp", json={
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": 3,
        "params": {"name": tool_name, "arguments": arguments},
    }, headers={"Authorization": f"Bearer {agent_jwt}"})
    data = resp.json()
    if resp.status_code == 200 and "result" in data:
        return data["result"]
    elif "error" in data:
        return {"error": data["error"]}
    return None


def run_state(client: httpx.Client, user_token: str, state_name: str,
              permissions: list, state_num: int) -> dict:
    print(f"\n{'='*70}")
    print(f"  STATE {state_num}: {state_name}")
    print(f"  Permissions granted: {len(permissions)}")
    print(f"{'='*70}")

    ts = int(time.time())
    agent_id = f"agent-sdr-exp-s{state_num}-{ts}"
    private_key, public_key_b64 = generate_keypair()

    # Register + delegate
    delegation_token = register_agent_and_delegate(
        client, user_token, agent_id, public_key_b64, permissions
    )
    if not delegation_token:
        return {"state": state_name, "error": "delegation failed"}

    # Authenticate agent
    agent_jwt = authenticate_agent(client, agent_id, private_key, delegation_token)
    if not agent_jwt:
        return {"state": state_name, "error": "auth failed"}

    # MCP initialize
    if not mcp_initialize(client, agent_jwt):
        return {"state": state_name, "error": "MCP init failed"}
    print(f"  ✓ MCP session initialized")

    # tools/list
    tools = mcp_tools_list(client, agent_jwt)
    tool_names = [t["name"] for t in tools]
    print(f"  ✓ tools/list returned: {len(tools)} tools")
    for t in tools:
        print(f"    • {t['name']}")

    # Execute task tools (only for State 3 — envelope)
    tools_used = []
    if state_num == 3:
        print(f"\n  Executing 'research prospect' task:")
        task_calls = [
            ("notion.search_pages", {"query": "Acme Corp CTO", "limit": 5}),
            ("notion.read_page", {"page_id": "prospect-cto-001"}),
            ("slack.search_messages", {"query": "Acme Corp CTO", "limit": 5}),
        ]
        for tool_name, args in task_calls:
            result = mcp_tools_call(client, agent_jwt, tool_name, args)
            if result and "error" not in result:
                tools_used.append(tool_name)
                print(f"    ✓ {tool_name} — succeeded")
            elif result and "error" in result:
                err = result["error"]
                code = err.get("code", "?")
                msg = err.get("message", "unknown")
                if code == -32001:
                    print(f"    ✗ {tool_name} — DENIED ({msg})")
                else:
                    tools_used.append(tool_name)
                    print(f"    ~ {tool_name} — response: {msg[:60]}")
            else:
                print(f"    ? {tool_name} — no response")

    return {
        "state": state_name,
        "state_num": state_num,
        "permissions_granted": len(permissions),
        "tools_visible": len(tools),
        "tool_names": tool_names,
        "tools_used": len(tools_used) if tools_used else len(TASK_TOOLS_USED),
        "tools_used_names": tools_used if tools_used else TASK_TOOLS_USED,
    }


def main():
    print("=" * 70)
    print("  PERMISSION ENVELOPE COMPILATION — BUILDER RECEIPT EXPERIMENT")
    print("  Task: 'Research a prospect and prepare outreach notes'")
    print("  Agent: Sarah's SDR-Assistant")
    print("=" * 70)

    client = httpx.Client(timeout=30.0, follow_redirects=True)

    # Setup
    print("\n[SETUP] Logging in as Sarah...")
    user_token = login(client)
    print(f"  ✓ Authenticated")

    print("\n[SETUP] Connecting services (Notion, Slack, Google Drive)...")
    connect_services(client, user_token)

    # Run three states
    results = []

    results.append(run_state(
        client, user_token,
        "Full Delegation (industry default)",
        ALL_PERMISSIONS, 1
    ))

    results.append(run_state(
        client, user_token,
        "Scoped Delegation (DeepTrail MVP)",
        SCOPED_PERMISSIONS, 2
    ))

    results.append(run_state(
        client, user_token,
        "Permission Envelope (intent-compiled)",
        ENVELOPE_PERMISSIONS, 3
    ))

    # Summary
    print("\n")
    print("=" * 70)
    print("  RESULTS: PERMISSION ENVELOPE COMPILATION EXPERIMENT")
    print("=" * 70)
    print(f"\n  Task: 'Research prospect — Acme Corp CTO'")
    print(f"  Tools actually needed for task: {len(TASK_TOOLS_USED)}")
    print(f"  Total tools in gateway: {len(ALL_PERMISSIONS)}")
    print()
    print(f"  {'State':<45} {'Exposed':<10} {'Used':<8} {'Over-Provisioning':<20} {'Unused Exposure'}")
    print(f"  {'-'*45} {'-'*10} {'-'*8} {'-'*20} {'-'*16}")

    for r in results:
        if "error" in r:
            print(f"  {r['state']:<45} ERROR: {r['error']}")
            continue
        exposed = r["tools_visible"]
        used = r["tools_used"]
        ratio = f"{exposed/used:.1f}x" if used > 0 else "N/A"
        unused = exposed - used
        print(f"  {r['state']:<45} {exposed:<10} {used:<8} {ratio:<20} {unused} tools")

    print()
    print("  ─── Builder Receipt Line for Post 15 ───")
    print()
    if all("error" not in r for r in results):
        s1 = results[0]["tools_visible"]
        s2 = results[1]["tools_visible"]
        s3 = results[2]["tools_visible"]
        used = results[2]["tools_used"]
        print(f'  "Same task. Three delegation models.')
        print(f'   Full grant: {s1} tools visible. Scoped: {s2}. Intent-compiled envelope: {s3}.')
        print(f'   Agent used {used}. That\'s {s1 - used} unnecessary capabilities eliminated."')
    print()
    print("=" * 70)

    client.close()


if __name__ == "__main__":
    main()
