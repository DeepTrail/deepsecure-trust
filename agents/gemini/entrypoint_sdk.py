#!/usr/bin/env python3
"""SDK-based entrypoint for the DeepSecure Gemini Agent.

Replaces the 265-line bash entrypoint.sh with equivalent functionality
using the deepsecure SDK bootstrap client. Requires the deepsecure
package to be installed (pip install deepsecure).

Config is fetched from the Control Plane at boot via
GET /api/v1/agents/{agent_id}/config.  If the fetch fails, the agent
uses hardcoded safety fallbacks for operational parameters but exits
cleanly if no tagged_prompts are available (nothing to execute).

Environment variables:
  DEEPSECURE_CONTROL_URL  (default: https://app.deepsecure.one)
  DEEPSECURE_GATEWAY_URL  (default: https://app.deepsecure.one/mcp)
  AGENT_ID                (default: debugging-deepsecure-agent)
  AGENT_JWT               (optional: skip OIDC bootstrap)
  GEMINI_MODEL            (optional: override model)

  Env-var overrides (take precedence over DB config):
  AGENT_PROMPTS_PER_DELEGATION
  AGENT_MAX_ROUNDS
  AGENT_INTERVAL_SECONDS
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from deepsecure._core.bootstrap import BootstrapClient, BootstrapResult, Platform

CONTROL_URL = os.environ.get("DEEPSECURE_CONTROL_URL", "https://app.deepsecure.one")
GATEWAY_URL = os.environ.get("DEEPSECURE_GATEWAY_URL", "https://app.deepsecure.one/mcp")
AGENT_ID = os.environ.get("AGENT_ID", "debugging-deepsecure-agent")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "")

# Hardcoded safety fallbacks — used ONLY when both DB fetch and env vars
# are unavailable. Intentionally conservative to prevent runaway jobs.
_FALLBACK_PROMPTS_PER_DELEGATION = 10
_FALLBACK_MAX_ROUNDS = 3
_FALLBACK_INTERVAL = 300


def ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


# ── Config fetching ──────────────────────────────────────────────────

def fetch_config(agent_id: str, jwt: str, control_url: str) -> Optional[Dict[str, Any]]:
    """Fetch agent config from the Control Plane.

    Retries up to 3 times with exponential backoff (1s, 2s, 4s).
    Returns the parsed JSON dict on success, None on failure.
    """
    import httpx

    url = f"{control_url}/api/v1/agents/{agent_id}/config"
    headers = {"Authorization": f"Bearer {jwt}"}
    backoff = 1

    for attempt in range(1, 4):
        try:
            resp = httpx.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            log(f"Config fetch attempt {attempt}: HTTP {resp.status_code}")
        except Exception as exc:
            log(f"Config fetch attempt {attempt}: {exc}")
        if attempt < 3:
            time.sleep(backoff)
            backoff *= 2

    return None


def resolve_config(db_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge DB config with env-var overrides and safety fallbacks.

    Priority:  env var  >  DB config  >  hardcoded fallback
    """
    base = db_config or {}

    ppd_env = os.environ.get("AGENT_PROMPTS_PER_DELEGATION")
    mr_env = os.environ.get("AGENT_MAX_ROUNDS")
    iv_env = os.environ.get("AGENT_INTERVAL_SECONDS")

    prompts_per_delegation = (
        int(ppd_env) if ppd_env
        else base.get("prompts_per_delegation", _FALLBACK_PROMPTS_PER_DELEGATION)
    )
    max_rounds = (
        int(mr_env) if mr_env
        else base.get("max_rounds", _FALLBACK_MAX_ROUNDS)
    )
    interval_seconds = (
        int(iv_env) if iv_env
        else base.get("interval_seconds", _FALLBACK_INTERVAL)
    )

    tagged_prompts: List[Dict[str, str]] = base.get("tagged_prompts", [])

    return {
        "prompts_per_delegation": prompts_per_delegation,
        "max_rounds": max_rounds,
        "interval_seconds": interval_seconds,
        "tagged_prompts": tagged_prompts,
    }


# ── MCP / Gemini helpers ────────────────────────────────────────────

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


def select_prompts(
    tagged_prompts: List[Dict[str, str]],
    permissions: List[str],
) -> List[str]:
    """Return prompts whose required services are all present in permissions."""
    perm_string = json.dumps(permissions)
    matched: List[str] = []
    for tp in tagged_prompts:
        required = [s.strip() for s in tp["services"].split(",")]
        if all(f'"{svc}:' in perm_string for svc in required):
            matched.append(tp["prompt"])
    return matched


def run_gemini_prompt(prompt: str) -> None:
    """Execute a single Gemini CLI prompt."""
    cmd = ["gemini", "-y", "--sandbox=false", "--allowed-mcp-server-names", "deepsecure", "-p", prompt]
    if GEMINI_MODEL:
        cmd.extend(["--model", GEMINI_MODEL])
    proc = subprocess.run(cmd, capture_output=False, text=True)
    if proc.returncode != 0:
        log(f"WARNING: gemini CLI returned {proc.returncode} (may be tool error, continuing)")


# ── Main ─────────────────────────────────────────────────────────────

def main() -> None:
    print("=========================================")
    print(" DeepSecure Gemini Agent (SDK Entrypoint)")
    print(f" Agent ID: {AGENT_ID}")
    print("=========================================")

    pre_set_jwt = os.environ.get("AGENT_JWT")
    platform = Platform.LOCAL if pre_set_jwt else Platform.GCP

    client = BootstrapClient(control_url=CONTROL_URL, gateway_url=GATEWAY_URL)

    # ── Bootstrap (first round) to get a JWT ──
    if pre_set_jwt:
        boot_jwt = pre_set_jwt
    else:
        log("Phase 0: Bootstrapping to obtain JWT for config fetch...")
        boot_result = client.bootstrap(AGENT_ID, platform)
        boot_jwt = boot_result.jwt
        log("Phase 0 complete. JWT obtained.")

    # ── Fetch config from DB via Control Plane ──
    log("Fetching agent config from Control Plane...")
    raw_config = fetch_config(AGENT_ID, boot_jwt, CONTROL_URL)
    if raw_config is None:
        log("WARNING: Config fetch failed. Using safety fallbacks.")
    else:
        log("Config fetched successfully.")

    config = resolve_config(raw_config)

    max_rounds = config["max_rounds"]
    prompts_per_delegation = config["prompts_per_delegation"]
    interval = config["interval_seconds"]
    tagged_prompts = config["tagged_prompts"]

    if not tagged_prompts:
        log("FATAL: No prompts configured. Set tagged_prompts via /agents/{id}/config.")
        sys.exit(0)

    log(f" Max Rounds: {max_rounds}")
    log(f" Prompts/Delegation: {prompts_per_delegation}")
    log(f" Interval: {interval}s")
    log(f" Tagged Prompts: {len(tagged_prompts)}")

    for round_num in range(1, max_rounds + 1):
        log(f"===== Round {round_num}/{max_rounds} =====")

        if pre_set_jwt:
            from deepsecure._core.bootstrap import Delegation
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

            prompts = select_prompts(tagged_prompts, delegation.permissions)
            if not prompts:
                log(f"No matching prompts for permissions: {delegation.permissions}")
                continue

            log(f"{len(prompts)} prompts match this delegation's permissions")

            for p_idx, prompt in enumerate(prompts[:prompts_per_delegation]):
                log(f"Running prompt {p_idx + 1}: {prompt[:80]}...")
                run_gemini_prompt(prompt)

            log(f"Completed {min(len(prompts), prompts_per_delegation)} prompt(s) for delegation")

        if round_num < max_rounds:
            log(f"Sleeping {interval}s before next round...")
            time.sleep(interval)

    log(f"=== Agent completed {max_rounds} rounds. Exiting cleanly. ===")


if __name__ == "__main__":
    main()
