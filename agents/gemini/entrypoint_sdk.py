#!/usr/bin/env python3
"""SDK-based entrypoint for DeepSecure background agents with multi-LLM fallback.

Bootstraps via DeepSecure SDK, fetches config (tagged_prompts + operational
params) from the Control Plane DB, then runs prompts through Gemini, Claude
Code, or Codex CLI (in priority order) with automatic fallback when a
provider fails.

Config is fetched from the Control Plane at boot via
GET /api/v1/agents/{agent_id}/config.  If the fetch fails, the agent
uses hardcoded safety fallbacks for operational parameters but exits
cleanly if no tagged_prompts are available (nothing to execute).

Environment variables:
  DEEPSECURE_CONTROL_URL  (default: https://app.deepsecure.one)
  DEEPSECURE_GATEWAY_URL  (default: https://app.deepsecure.one/mcp)
  AGENT_ID                (default: debugging-deepsecure-agent)
  AGENT_JWT               (optional: skip OIDC bootstrap)
  LLM_PROVIDERS           (default: gemini,claude,codex)
  GEMINI_MODEL            (optional: override Gemini model)
  PROMPT_TIMEOUT_SECONDS  (default: 300, per-prompt subprocess timeout)
  GEMINI_API_KEY          (required for gemini provider)
  ANTHROPIC_API_KEY       (required for claude provider)
  OPENAI_API_KEY          (required for codex provider)

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
from pathlib import Path
from typing import Any, Dict, List, Optional

from deepsecure._core.bootstrap import BootstrapClient, Platform

CONTROL_URL = os.environ.get("DEEPSECURE_CONTROL_URL", "https://app.deepsecure.one")
GATEWAY_URL = os.environ.get("DEEPSECURE_GATEWAY_URL", "https://app.deepsecure.one/mcp")
AGENT_ID = os.environ.get("AGENT_ID", "debugging-deepsecure-agent")

MAX_ROUNDS = int(os.environ.get("AGENT_MAX_ROUNDS", "3"))
PROMPTS_PER_DELEGATION = int(os.environ.get("AGENT_PROMPTS_PER_DELEGATION", "2"))
INTERVAL = int(os.environ.get("AGENT_INTERVAL_SECONDS", "300"))
LLM_PROVIDERS = os.environ.get("LLM_PROVIDERS", "gemini,claude,codex")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "")
PROMPT_TIMEOUT = int(os.environ.get("PROMPT_TIMEOUT_SECONDS", "300"))

PROVIDER_KEY_ENV: Dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "codex": "OPENAI_API_KEY",
}

MCP_CONFIG_PATH = "/tmp/deepsecure-mcp.json"

TOOL_FAILURE_PHRASES = [
    "tools aren't available",
    "tools not available",
    "not actually available",
    "tools don't exist",
    "no deepsecure",
    "no mcp server",
    "can't complete this",
    "unable to complete",
    "i'm not able to do this",
    "no matching deferred tools",
    "not able to do this",
    "isn't configured",
    "failed to start",
    "tools won't be available",
    "check the mcp server connection",
    "no mcp tools",
    "mcp server is not",
    "isn't registered",
    "not registered",
    "didn't start",
    "verify the mcp server",
    "there's no deepsecure",
    "there is no deepsecure",
    "no such tool available",
    "deferred-tool registry",
    "not connected or configured",
    "check your mcp",
    "tools are not",
    "not registered/connected",
    "are not available",
    "are **not available",
    "i only have bash",
    "only have bash, edit",
]


def ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)

# ── DB Config fetching ───────────────────────────────────────────────

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


# ── Multi-LLM provider detection & MCP config ───────────────────────

def mcp_server_config(jwt: str) -> dict:
    return {
        "mcpServers": {
            "deepsecure": {
                "type": "http",
                "url": GATEWAY_URL,
                "headers": {"Authorization": f"Bearer {jwt}"},
            }
        }
    }


def detect_available_providers() -> List[str]:
    """Return providers that have API keys present, in LLM_PROVIDERS priority order."""
    priority = [p.strip() for p in LLM_PROVIDERS.split(",") if p.strip()]
    available: List[str] = []
    for provider in priority:
        key_env = PROVIDER_KEY_ENV.get(provider)
        if key_env and os.environ.get(key_env):
            available.append(provider)
        elif provider in PROVIDER_KEY_ENV:
            log(f"Skipping provider '{provider}': {key_env} not set")
    return available


def configure_mcp(provider: str, jwt: str) -> None:
    """Configure MCP gateway access for the given LLM CLI."""
    config_json = json.dumps(mcp_server_config(jwt), indent=2)
    Path(MCP_CONFIG_PATH).write_text(config_json)

    if provider == "gemini":
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
        return

    if provider == "claude":
        os.environ["CLAUDE_CODE_USE_BEDROCK"] = "0"
        os.environ["MCP_TIMEOUT"] = "60000"
        os.environ["MCP_CONNECTION_NONBLOCKING"] = "false"
        claude_dir = Path.home() / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        (claude_dir / "settings.json").write_text(config_json)
        return

    if provider == "codex":
        codex_dir = Path.home() / ".codex"
        codex_dir.mkdir(parents=True, exist_ok=True)

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key:
            proc = subprocess.run(
                ["codex", "login", "--with-api-key"],
                input=api_key, capture_output=True, text=True, timeout=10,
            )
            if proc.returncode == 0:
                log("Codex login (API key stored in auth.json)")
            else:
                log(f"WARNING: codex login failed: {proc.stderr.strip()}")

        os.environ["DEEPSECURE_MCP_JWT"] = jwt
        toml_content = (
            "[mcp_servers.deepsecure]\n"
            f'url = "{GATEWAY_URL}"\n'
            'bearer_token_env_var = "DEEPSECURE_MCP_JWT"\n'
            'default_tools_approval_mode = "auto"\n'
            "enabled = true\n"
        )
        (codex_dir / "config.toml").write_text(toml_content)
        return

    raise ValueError(f"Unknown provider: {provider}")

# ── Gateway warm-up ──────────────────────────────────────────────────

def warm_gateway(jwt: str) -> bool:
    """Send an MCP initialize to pre-warm the gateway session.  Returns True on success."""
    import httpx

    try:
        resp = httpx.post(
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
            timeout=15,
        )
        log(f"Gateway warm-up: HTTP {resp.status_code}")
        return resp.status_code == 200
    except Exception as exc:
        log(f"Gateway warm-up failed: {exc}")
        return False

# ── Prompt selection & execution ─────────────────────────────────────

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


def run_provider_prompt(provider: str, prompt: str) -> bool:
    """Execute a prompt via the given LLM CLI.

    Returns True only when the CLI exits 0 AND the output does not contain
    phrases indicating MCP tools were unavailable (prevents a text-only
    "success" from short-circuiting the fallback chain).
    """
    if provider == "gemini":
        cmd = [
            "gemini", "-y", "--sandbox=false",
            "--allowed-mcp-server-names", "deepsecure",
            "-p", prompt,
        ]
        if GEMINI_MODEL:
            cmd.extend(["--model", GEMINI_MODEL])
    elif provider == "claude":
        cmd = [
            "claude", "-p", prompt,
            "--output-format", "text",
            "--mcp-config", MCP_CONFIG_PATH,
            "--allowedTools", "mcp__deepsecure__*",
        ]
    elif provider == "codex":
        cmd = [
            "codex", "exec",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            prompt,
        ]
    else:
        log(f"Unknown provider: {provider}")
        return False

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=PROMPT_TIMEOUT)
        output = (proc.stdout or "") + (proc.stderr or "")

        lines = output.strip().splitlines() if output.strip() else []
        head = lines[:5]
        tail = lines[-10:] if len(lines) > 15 else lines[5:]
        for line in head:
            print(f"  [{provider}:head] {line}", flush=True)
        if len(lines) > 15:
            print(f"  [{provider}] ... ({len(lines) - 15} lines omitted) ...", flush=True)
        for line in tail:
            print(f"  [{provider}] {line}", flush=True)

        if proc.returncode != 0:
            log(f"WARNING: {provider} CLI returned {proc.returncode}")
            return False

        output_lower = output.lower()
        for phrase in TOOL_FAILURE_PHRASES:
            if phrase in output_lower:
                log(f"WARNING: {provider} exit 0 but tools unavailable (matched: '{phrase}')")
                return False

        return True
    except subprocess.TimeoutExpired:
        log(f"TIMEOUT: {provider} prompt killed after {PROMPT_TIMEOUT}s")
        return False
    except FileNotFoundError:
        log(f"ERROR: {provider} CLI not found in PATH")
        return False


def run_prompt_with_fallback(providers: List[str], jwt: str, prompt: str) -> bool:
    """Try each provider in order until one succeeds."""
    for provider in providers:
        log(f"Trying provider: {provider}")
        if provider in ("claude", "codex"):
            warm_gateway(jwt)
        configure_mcp(provider, jwt)
        if run_provider_prompt(provider, prompt):
            log(f"Prompt succeeded with provider: {provider}")
            return True
        log(f"Provider {provider} failed, trying next...")
    return False

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=PROMPT_TIMEOUT)
        output = (proc.stdout or "") + (proc.stderr or "")

        lines = output.strip().splitlines() if output.strip() else []
        head = lines[:5]
        tail = lines[-10:] if len(lines) > 15 else lines[5:]
        for line in head:
            print(f"  [{provider}:head] {line}", flush=True)
        if len(lines) > 15:
            print(f"  [{provider}] ... ({len(lines) - 15} lines omitted) ...", flush=True)
        for line in tail:
            print(f"  [{provider}] {line}", flush=True)

        if proc.returncode != 0:
            log(f"WARNING: {provider} CLI returned {proc.returncode}")
            return False

        output_lower = output.lower()
        for phrase in TOOL_FAILURE_PHRASES:
            if phrase in output_lower:
                log(f"WARNING: {provider} exit 0 but tools unavailable (matched: '{phrase}')")
                return False

        return True
    except subprocess.TimeoutExpired:
        log(f"TIMEOUT: {provider} prompt killed after {PROMPT_TIMEOUT}s")
        return False
    except FileNotFoundError:
        log(f"ERROR: {provider} CLI not found in PATH")
        return False


def run_prompt_with_fallback(providers: List[str], jwt: str, prompt: str) -> bool:
    """Try each provider in order until one succeeds."""
    for provider in providers:
        log(f"Trying provider: {provider}")
        if provider in ("claude", "codex"):
            warm_gateway(jwt)
        configure_mcp(provider, jwt)
        if run_provider_prompt(provider, prompt):
            log(f"Prompt succeeded with provider: {provider}")
            return True
        log(f"Provider {provider} failed, trying next...")
    return False


# ── Bootstrap with retry ─────────────────────────────────────────────

def bootstrap_with_retry(
    client: BootstrapClient,
    agent_id: str,
    platform: Platform,
    max_attempts: int = 3,
) -> BootstrapResult:
    """Bootstrap with retry + exponential backoff for cold-start tolerance."""
    backoff = 5
    for attempt in range(1, max_attempts + 1):
        try:
            return client.bootstrap(agent_id, platform)
        except Exception as exc:
            log(f"Bootstrap attempt {attempt}/{max_attempts} failed: {exc}")
            if attempt < max_attempts:
                log(f"Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2
    log("FATAL: Bootstrap failed after all retries.")
    sys.exit(1)


# ── Main ─────────────────────────────────────────────────────────────

def main() -> None:
    providers = detect_available_providers()
    if not providers:
        log("FATAL: No LLM providers available (missing API keys).")
        sys.exit(1)

    print("=========================================")
    print(" DeepSecure Agent (SDK + Multi-LLM)")
    print(f" Agent ID: {AGENT_ID}")
    print(f" Max Rounds: {MAX_ROUNDS}")
    print(f" Prompts/Delegation: {PROMPTS_PER_DELEGATION}")
    print(f" Interval: {INTERVAL}s")
    print(f" Prompt Timeout: {PROMPT_TIMEOUT}s")
    print(f" LLM Providers: {', '.join(providers)}")
    print("=========================================")

    pre_set_jwt = os.environ.get("AGENT_JWT")
    platform = Platform.LOCAL if pre_set_jwt else Platform.GCP

    client = BootstrapClient(control_url=CONTROL_URL, gateway_url=GATEWAY_URL)

    # ── Bootstrap (Phase 0) to get a JWT for config fetch ──
    if pre_set_jwt:
        boot_jwt = pre_set_jwt
        resolved_agent_id = AGENT_ID
    else:
        log("Phase 0: Bootstrapping to obtain JWT for config fetch...")
        boot_result = bootstrap_with_retry(client, AGENT_ID, platform)
        boot_jwt = boot_result.jwt
        resolved_agent_id = boot_result.agent_id
        log(f"Phase 0 complete. JWT obtained. Resolved agent_id: {resolved_agent_id}")

    # ── Fetch config from DB via Control Plane ──
    log("Fetching agent config from Control Plane...")
    raw_config = fetch_config(resolved_agent_id, boot_jwt, CONTROL_URL)
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
            result = bootstrap_with_retry(client, AGENT_ID, platform)
            log(f"Phase 1 complete. JWT obtained, {len(result.delegations)} delegation(s).")

        if not result.delegations:
            log("FATAL: No active delegations. Cannot operate.")
            sys.exit(1)

        for d_idx, delegation in enumerate(result.delegations):
            log(
                f"--- Delegation {d_idx + 1}/{len(result.delegations)}: "
                f"{delegation.service} ({delegation.delegation_id}) ---"
            )

            jwt = delegation.jwt or result.jwt

            warm_gateway(jwt)

            prompts = select_prompts(tagged_prompts, delegation.permissions)
            if not prompts:
                log(f"No matching prompts for permissions: {delegation.permissions}")
                continue

            log(f"{len(prompts)} prompts match this delegation's permissions")

            succeeded = 0
            for p_idx, prompt in enumerate(prompts[:PROMPTS_PER_DELEGATION]):

                log(f"Running prompt {p_idx + 1}: {prompt[:80]}...")
                if run_prompt_with_fallback(providers, jwt, prompt):
                    succeeded += 1

            total = min(len(prompts), PROMPTS_PER_DELEGATION)
            log(f"Completed {succeeded}/{total} prompt(s) for delegation")

        if round_num < max_rounds:
            log(f"Sleeping {interval}s before next round...")
            time.sleep(interval)

    log(f"=== Agent completed {max_rounds} rounds. Exiting cleanly. ===")


if __name__ == "__main__":
    main()
