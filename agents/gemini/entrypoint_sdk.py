#!/usr/bin/env python3
"""SDK-based entrypoint for the DeepSecure Gemini Agent.

Replaces the 265-line bash entrypoint.sh with equivalent functionality
using the deepsecure SDK bootstrap client. Requires the deepsecure
package to be installed (pip install deepsecure).

Environment variables (same as entrypoint.sh):
  DEEPSECURE_CONTROL_URL  (default: https://app.deepsecure.one)
  DEEPSECURE_GATEWAY_URL  (default: https://app.deepsecure.one/mcp)
  AGENT_ID                (default: debugging-agent-sa)
  AGENT_MAX_ROUNDS        (default: 3)
  AGENT_PROMPTS_PER_DELEGATION (default: 2)
  AGENT_INTERVAL_SECONDS  (default: 300)
  AGENT_JWT               (optional: skip OIDC bootstrap)
  GEMINI_MODEL            (optional: override model)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import List, Optional

from deepsecure._core.bootstrap import BootstrapClient, BootstrapResult, Platform

CONTROL_URL = os.environ.get("DEEPSECURE_CONTROL_URL", "https://app.deepsecure.one")
GATEWAY_URL = os.environ.get("DEEPSECURE_GATEWAY_URL", "https://app.deepsecure.one/mcp")
AGENT_ID = os.environ.get("AGENT_ID", "debugging-agent-sa")
MAX_ROUNDS = int(os.environ.get("AGENT_MAX_ROUNDS", "3"))
PROMPTS_PER_DELEGATION = int(os.environ.get("AGENT_PROMPTS_PER_DELEGATION", "2"))
INTERVAL = int(os.environ.get("AGENT_INTERVAL_SECONDS", "300"))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "")

TAGGED_PROMPTS = [
    ("notion", "You have access to tools via the deepsecure MCP server. Call notion.search_pages with query 'strategy' and limit 5. For each result, show the page title and ID. Then pick the first result and call notion.read_page with that page_id to read its properties."),
    ("slack", "You have access to tools via the deepsecure MCP server. Call slack.list_channels with limit 10 and types 'public_channel'. Pick the first channel and call slack.get_channel_history with that channel ID and limit 5 to read the last 5 messages. Then call slack.send_message to post '[DeepSecure Agent] Daily sync complete' to that channel."),
    ("gmail", "You have access to tools via the deepsecure MCP server. Call gmail.search_messages with query 'is:unread' and limit 5. List the sender and subject of each email found."),
    ("gdrive", "You have access to tools via the deepsecure MCP server. Call gdrive.search_files with query 'quarterly report' and limit 5. List the file name, type, and last modified date for each result."),
    ("gcalendar", "You have access to tools via the deepsecure MCP server. Call gcalendar.list_events with calendar_id 'primary' and limit 5. Summarize each event: title, start time, and attendees."),
    ("slack,notion,gmail", "You have access to tools via the deepsecure MCP server. First call slack.list_channels (limit 3), then call notion.search_pages with query 'meeting notes' (limit 3), then call gmail.search_messages with query 'action items' (limit 3). Write a brief summary of what you found across all three services."),
    ("exa", "You have access to tools via the deepsecure MCP server. IMPORTANT: Tool names use dot notation like 'backend.tool_name'. For Exa tools, the names are exactly 'exa.web_search_exa' and 'exa.web_fetch_exa' (dot-separated, not colon or slash). Call the tool named exa.web_search_exa with query 'DeepSecure AI agent security platform' and numResults 3. Show the title and URL of each result."),
]


def ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def configure_gemini(jwt: str) -> None:
    """Add the deepsecure MCP server to Gemini CLI config."""
    os.makedirs(os.path.expanduser("~/.gemini"), exist_ok=True)
    cmd = [
        "gemini", "mcp", "add", "deepsecure", GATEWAY_URL,
        "--type", "http",
        "--scope", "user",
        "--trust",
        "--timeout", "30000",
        "-H", f"Authorization: Bearer {jwt}",
    ]
    subprocess.run(cmd, capture_output=True, text=True)


def warm_gateway(jwt: str) -> None:
    """Send an MCP initialize to pre-warm the gateway session."""
    import httpx

    try:
        httpx.post(
            GATEWAY_URL,
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 0,
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "warmup", "version": "1.0.0"},
                },
            },
            headers={"Authorization": f"Bearer {jwt}"},
            timeout=10,
        )
    except Exception:
        pass


def select_prompts(permissions: List[str]) -> List[str]:
    """Return prompts whose required services are all present in permissions."""
    perm_string = json.dumps(permissions)
    matched: List[str] = []
    for tags_str, prompt in TAGGED_PROMPTS:
        required = [s.strip() for s in tags_str.split(",")]
        if all(f'"{svc}:' in perm_string for svc in required):
            matched.append(prompt)
    return matched


def run_gemini_prompt(prompt: str) -> None:
    """Execute a single Gemini CLI prompt."""
    cmd = ["gemini", "-y", "--sandbox=false", "--allowed-mcp-server-names", "deepsecure", "-p", prompt]
    if GEMINI_MODEL:
        cmd.extend(["--model", GEMINI_MODEL])
    proc = subprocess.run(cmd, capture_output=False, text=True)
    if proc.returncode != 0:
        log(f"WARNING: gemini CLI returned {proc.returncode} (may be tool error, continuing)")


def main() -> None:
    print("=========================================")
    print(" DeepSecure Gemini Agent (SDK Entrypoint)")
    print(f" Agent ID: {AGENT_ID}")
    print(f" Max Rounds: {MAX_ROUNDS}")
    print(f" Prompts/Delegation: {PROMPTS_PER_DELEGATION}")
    print(f" Interval: {INTERVAL}s")
    print("=========================================")

    pre_set_jwt = os.environ.get("AGENT_JWT")
    platform = Platform.LOCAL if pre_set_jwt else Platform.GCP

    client = BootstrapClient(control_url=CONTROL_URL, gateway_url=GATEWAY_URL)

    for round_num in range(1, MAX_ROUNDS + 1):
        log(f"===== Round {round_num}/{MAX_ROUNDS} =====")

        if pre_set_jwt:
            from deepsecure._core.bootstrap import BootstrapResult, Delegation
            result = BootstrapResult(
                agent_id=AGENT_ID,
                jwt=pre_set_jwt,
                platform=platform,
                control_url=CONTROL_URL,
                gateway_url=GATEWAY_URL,
                delegations=[],
                expires_in=3600,
            )
        else:
            log(f"Phase 1: Bootstrapping via {platform.value}...")
            result = client.bootstrap(AGENT_ID, platform)
            log(f"Phase 1 complete. JWT obtained, {len(result.delegations)} delegation(s).")

        if not result.delegations:
            log("FATAL: No active delegations. Cannot operate.")
            sys.exit(1)

        for d_idx, delegation in enumerate(result.delegations):
            log(f"--- Delegation {d_idx + 1}/{len(result.delegations)}: {delegation.service} ({delegation.delegation_id}) ---")

            jwt = delegation.jwt or result.jwt

            configure_gemini(jwt)
            warm_gateway(jwt)

            prompts = select_prompts(delegation.permissions)
            if not prompts:
                log(f"No matching prompts for permissions: {delegation.permissions}")
                continue

            log(f"{len(prompts)} prompts match this delegation's permissions")

            for p_idx, prompt in enumerate(prompts[:PROMPTS_PER_DELEGATION]):
                log(f"Running prompt {p_idx + 1}: {prompt[:80]}...")
                run_gemini_prompt(prompt)

            log(f"Completed {min(len(prompts), PROMPTS_PER_DELEGATION)} prompt(s) for delegation")

        if round_num < MAX_ROUNDS:
            log(f"Sleeping {INTERVAL}s before next round...")
            time.sleep(INTERVAL)

    log(f"=== Agent completed {MAX_ROUNDS} rounds. Exiting cleanly. ===")


if __name__ == "__main__":
    main()
