# Multi-LLM Fallback: Analysis, Issues, and Fixes

> Date: 2026-06-11 (updated)
> Status: **Claude + Codex BOTH WORKING end-to-end** — `tools/call` confirmed for both, heartbeats flowing, execution completes successfully
> Plan: `plans/multi-llm_agent_fallback_d79abc89.plan.md`

## 1. Background

All three production agents (`gemini-deepsecure-agent`, `engineering-audit`, `thunderbolt-deepsecure-agent`) run as Cloud Run jobs using `entrypoint_sdk.py`. Each agent:

1. Bootstraps via DeepSecure SDK (OIDC → JWT → delegations)
2. Selects prompts based on delegation permissions
3. Executes prompts via an LLM CLI subprocess
4. The LLM CLI connects to the DeepSecure MCP gateway for tool calls
5. Successful `tools/call` through the gateway triggers a heartbeat → **Active** state

The multi-LLM plan added Claude Code CLI and OpenAI Codex CLI as fallbacks when Gemini's billing cap (429) blocks execution.

## 2. Agent Lifecycle: Why "Active" Matters

The UI lifecycle is computed, not stored:

| State | Condition | What triggers it |
|-------|-----------|------------------|
| **Registered** | Agent exists | `POST /api/v1/agents/` |
| **Delegated** | Has active delegation | Delegation created in UI |
| **Authenticated** | Has any `AgentSession` ever | Bootstrap challenge-response |
| **Active** | `AgentSession.last_activity_at` within 24h | Gateway `tools/call` → heartbeat |

The heartbeat path:

```
LLM calls MCP tools/call → gateway proxies to backend →
  on success: asyncio.create_task(_send_heartbeat(agent_id)) →
    POST /api/v1/agents/internal/sessions/{agent_id}/heartbeat →
      updates AgentSession.last_activity_at →
        LifecycleService.compute_state() returns "active"
```

Source: `deeptrail-gateway/app/mcp/handlers/tools_call.py` lines 140-155, 818-820.

**Key insight**: `initialize` and `tools/list` do NOT trigger heartbeats. Only `tools/call` does.

## 3. Agent Identity Mapping

The UI shows UUIDs; Cloud Run jobs use slug-based `AGENT_ID` values. Bootstrap resolves the mapping:

| UI Display | UI Agent ID | Cloud Run AGENT_ID | Cloud Run Job |
|------------|-------------|-------------------|---------------|
| Debugging Agent | `agent-494fb073-310b-4410-bf63-211755cf9b12` | `debugging-agent-sa` | `gemini-deepsecure-agent` |
| Engineering Audit Agent | `agent-705248dc-7419-4195-b598-a10e346cba7f` | `engineering-audit-agent` | `engineering-audit` |
| Thunderbolt Agent | `agent-abf9bbd8-c71a-4be7-9e19-d8124e88f830` | `thunderbolt-agent` | `thunderbolt-deepsecure-agent` |

Gateway logs confirm the mapping via `tools/list` which shows the resolved UUID.

## 4. Gemini Billing Cap (Root Blocker)

All three agents fail on Gemini with HTTP 429:

```
"Your billing account has exceeded its monthly spending cap.
 Please go to AI Studio at https://ai.studio/billing to manage your billing."
```

Gemini CLI retries with backoff (up to ~8 attempts) before exiting with code 1. This burns 30-90 seconds per prompt before fallback kicks in.

**Fix**: Raise the AI Studio billing cap, or accept the fallback path.

## 5. Issues Found and Fixed

### 5.1 Claude Missing `--mcp-config` Flag

**Symptom**: Claude exited 0 with text: *"There's no deepsecure MCP server or notion tools available in this environment."*

**Root cause**: The `claude -p` command did not include `--mcp-config`, so in headless mode Claude couldn't discover the MCP server.

**Code before**:
```python
cmd = [
    "claude", "-p", prompt,
    "--output-format", "text",
    "--allowedTools", "mcp__deepsecure__*",
]
```

**Fix applied**:
```python
cmd = [
    "claude", "-p", prompt,
    "--output-format", "text",
    "--bare",
    "--mcp-config", MCP_CONFIG_PATH,
    "--allowedTools", "mcp__deepsecure__*",
]
```

Added `--bare` (recommended for scripted/CI use — skips hooks, plugins, auto-discovery; only explicit flags take effect) and `--mcp-config` pointing to the JSON config file written by `configure_mcp()`.

### 5.2 MCP Config Used Wrong Transport Key

**Symptom**: Even with `--mcp-config`, Claude silently dropped the MCP server — no `initialize` or `tools/list` in gateway logs.

**Root cause**: The JSON config used `"transport": "http"` but Claude Code expects `"type": "http"`.

**Code before**:
```python
def mcp_server_config(jwt):
    return {
        "mcpServers": {
            "deepsecure": {
                "url": GATEWAY_URL,
                "transport": "http",   # WRONG KEY
                "headers": {"Authorization": f"Bearer {jwt}"},
            }
        }
    }
```

**Fix applied**:
```python
def mcp_server_config(jwt):
    return {
        "mcpServers": {
            "deepsecure": {
                "type": "http",        # CORRECT KEY
                "url": GATEWAY_URL,
                "headers": {"Authorization": f"Bearer {jwt}"},
            }
        }
    }
```

**Verification**: After this fix, gateway logs showed `initialize → notifications/initialized → tools/list` from Claude CLI for the first time.

Reference: [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) — `"type": "http"` (alias: `"streamable-http"`) is the correct key for HTTP MCP servers.

### 5.3 Codex Config Was JSON Instead of TOML

**Symptom**: Codex was never reached (see 5.4), but even if it were, its MCP config would have been ignored.

**Root cause**: Code wrote `~/.codex/config.json` (JSON format). Codex CLI reads `~/.codex/config.toml` (TOML format).

**Code before**:
```python
if provider == "codex":
    codex_dir = Path.home() / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    config_path = codex_dir / "config.json"
    config_path.write_text(json.dumps(mcp_server_config(jwt), indent=2))
```

**Fix applied**:
```python
if provider == "codex":
    codex_dir = Path.home() / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    toml_content = (
        "[mcp_servers.deepsecure]\n"
        f'url = "{GATEWAY_URL}"\n'
        "\n"
        "[mcp_servers.deepsecure.http_headers]\n"
        f'Authorization = "Bearer {jwt}"\n'
    )
    (codex_dir / "config.toml").write_text(toml_content)
```

Reference: [Codex config reference](https://developers.openai.com/codex/config-reference) — config lives in `~/.codex/config.toml`, MCP servers use `[mcp_servers.<name>]` TOML tables.

**Note**: Codex CLI does NOT support `--mcp-config`. It reads from `config.toml` only.

### 5.4 Exit-Code-Only Success Detection

**Symptom**: Claude exited 0 with a text-only response saying "tools not available", but the fallback chain treated it as success. Codex was never tried.

**Root cause**: `run_provider_prompt()` checked only `proc.returncode != 0`. Claude exits 0 even when it cannot fulfill the task — it just explains why in text.

**Code before**:
```python
proc = subprocess.run(cmd, capture_output=False, text=True, timeout=PROMPT_TIMEOUT)
if proc.returncode != 0:
    return False
return True
```

**Fix applied**:
```python
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=PROMPT_TIMEOUT)
output = (proc.stdout or "") + (proc.stderr or "")

# Log tail for debugging in Cloud Run
tail = output.strip().splitlines()[-15:] if output.strip() else []
for line in tail:
    print(f"  [{provider}] {line}", flush=True)

if proc.returncode != 0:
    return False

# Scan for tool-failure indicators
output_lower = output.lower()
for phrase in TOOL_FAILURE_PHRASES:
    if phrase in output_lower:
        log(f"WARNING: {provider} exit 0 but tools unavailable (matched: '{phrase}')")
        return False

return True
```

Also changed `capture_output=False` → `capture_output=True` to enable output inspection. The last 15 lines of output are logged with a `[provider]` prefix for Cloud Run log visibility.

**Verification**: Logs now show `WARNING: claude exit 0 but tools unavailable (matched: 'can't complete this')` and the fallback proceeds to Codex.

### 5.5 Codex `--ask-for-approval` Flag Removed

**Symptom**: `codex exec` failed with exit code 2: `error: unexpected argument '--ask-for-approval' found`.

**Root cause**: The `--ask-for-approval` flag was removed from Codex CLI. The `exec` subcommand is inherently non-interactive.

**Fix applied**: Removed the flag entirely from the command.

### 5.6 Codex Missing `--skip-git-repo-check` and Auth Config

**Symptom**: `Not inside a trusted directory and --skip-git-repo-check was not specified.`

**Root cause**: Docker containers don't have a git repo. Codex refused to run without explicit opt-in.

**Fix applied**:
```python
cmd = [
    "codex", "exec",
    "--skip-git-repo-check",
    "--dangerously-bypass-approvals-and-sandbox",
    prompt,
]
```

Also updated TOML config to use `bearer_token_env_var` for MCP auth:
```toml
[mcp_servers.deepsecure]
url = "https://app.deepsecure.one/mcp"
bearer_token_env_var = "DEEPSECURE_MCP_JWT"
default_tools_approval_mode = "auto"
enabled = true
```

### 5.12 Codex Requires `codex login --with-api-key` (Not Just Env Var)

**Symptom**: Codex CLI got `401 Unauthorized: Missing bearer or basic authentication in header` on the WebSocket endpoint, despite `OPENAI_API_KEY` being set in the environment.

**Root cause**: `codex doctor` revealed `auth mode: none` on the WebSocket connection even though `OPENAI_API_KEY` was detected. Codex v0.139.0 requires the API key to be stored via `codex login --with-api-key` into `~/.codex/auth.json` — the env var alone isn't wired into the WebSocket handshake.

**Fix applied** — added to `configure_mcp("codex", ...)`:
```python
api_key = os.environ.get("OPENAI_API_KEY", "")
if api_key:
    proc = subprocess.run(
        ["codex", "login", "--with-api-key"],
        input=api_key, capture_output=True, text=True, timeout=10,
    )
    if proc.returncode == 0:
        log("Codex login (API key stored in auth.json)")
```

### 5.13 Codex Sandbox Cancelled MCP Tool Calls

**Symptom**: With `--sandbox workspace-write`, Codex connected to MCP and started `notion.search_pages`, but then reported "user cancelled MCP tool call" and the call failed — even though the gateway processed it successfully (200 OK).

**Root cause**: Codex's `workspace-write` sandbox restricts network access and MCP tool execution. The `default_tools_approval_mode = "auto"` in `config.toml` was not sufficient to override the sandbox's tool cancellation in `exec` mode.

**Fix applied**: Changed from `--sandbox workspace-write` to `--dangerously-bypass-approvals-and-sandbox`, which skips all confirmation prompts and sandbox restrictions. This is acceptable because the agent runs in an isolated Cloud Run container.

**Before**: `"user cancelled MCP tool call"` — sandbox killed the call
**After**: Full `tools/call` success — `notion.search_pages` and `notion.read_page` return real data

### 5.7 ARM64 Image Pushed to Cloud Run (amd64 required)

**Symptom**: Container crashed immediately with "Application failed to start" — zero Python output.

**Root cause**: `docker build` on Apple Silicon creates `linux/arm64` images. Cloud Run requires `linux/amd64`.

**Fix applied**: Use `docker buildx build --platform linux/amd64` (matches `infra/deploy-agent.sh`).

### 5.8 `--set-env-vars` Replaced All Env Vars

**Symptom**: After `gcloud run jobs update --set-env-vars "..."`, secrets survived (they use `secretKeyRef`) but plain env vars like `AGENT_ID`, `DEEPSECURE_CONTROL_URL`, `LLM_PROVIDERS` were lost.

**Fix applied**: Always use the full env var set from `deploy-agent.sh` when updating, using `^;^` delimiter for comma-containing values.

### 5.9 Claude `--bare` Mode Skipped MCP Connection

**Symptom**: Claude exited 0 with "I only have Bash, Edit, and Read" — MCP tools not loaded despite `--mcp-config`.

**Root cause**: `--bare` mode uses a bounded wait for MCP connections. If the gateway is cold (Cloud Run cold start after Gemini's 120s timeout), the MCP connection fails silently within the bounded timeout. Claude proceeds without MCP tools.

**Fix applied** (multi-part):
1. **Removed `--bare`** — let Claude auto-discover MCP from `~/.claude/settings.json` (which `configure_mcp` already writes). Standard mode has more robust MCP connection handling.
2. **Increased `MCP_TIMEOUT`** from 30000 to 60000 (60s) to account for gateway cold starts.
3. **Set `MCP_CONNECTION_NONBLOCKING=false`** to ensure Claude blocks until MCP is connected.
4. **Added `warm_gateway()` call before each Claude/Codex attempt** in the fallback loop (not just once per delegation), to keep the gateway warm after Gemini's 120s timeout burns.

### 5.10 Expanded Tool Failure Detection

Added more Claude-specific phrases that indicate tool unavailability:
```python
"are not available",
"are **not available",
"i only have bash",
"only have bash, edit",
```

### 5.11 Better Output Logging

Changed from last-15-lines-only to head+tail logging:
```
[claude:head] Done. Here's the full summary:     ← first 5 lines
[claude:head] ## Search results for "strategy"
[claude] ... (11 lines omitted) ...              ← middle omitted
[claude] | **Title** | Company Strategy 2026       ← last 10 lines
```

This captures MCP connection diagnostics at the start and results at the end.

## 6. Current State After Fixes

### What's Working

| Component | Status | Evidence |
|-----------|--------|----------|
| Multi-LLM fallback chain | **Working** | Logs show gemini → claude → codex progression |
| Tool-failure detection | **Working** | `matched: 'unable to complete'` in logs, Claude no longer short-circuits |
| Codex gets tried | **Working** | `Trying provider: codex` appears in logs with full output |
| Claude MCP connection | **Working** | Gateway shows `initialize → tools/list → tools/call` from Claude CLI |
| Claude `tools/call` | **WORKING** | `notion.search_pages` and `notion.read_page` both return 200 success |
| **Codex `tools/call`** | **WORKING** | `notion.search_pages` and `notion.read_page` both return 200 success via `codex-mcp-client v0.139.0` |
| **Codex login** | **WORKING** | `codex login --with-api-key` stores auth in `auth.json`, enabling WebSocket auth |
| Agent heartbeats | **WORKING** | `POST /sessions/agent-705248dc.../heartbeat` → 204 flowing |
| Codex TOML config | **Fixed** | Writes `~/.codex/config.toml` with `bearer_token_env_var` |
| Gateway warm-up | **Working** | `Gateway warm-up: HTTP 200` logged before each Claude/Codex attempt |
| Agent ID mapping | **Correct** | Gateway resolves to correct UUIDs |
| All 3 API keys present | **Confirmed** | Startup shows `LLM Providers: gemini, claude, codex` |
| Image architecture | **Fixed** | `buildx --platform linux/amd64` for Cloud Run compatibility |
| Execution lifecycle | **Working** | `engineering-audit-hkk6d` (Claude), `engineering-audit-jccnk` (Codex) completed successfully |

### What's Not Working (External/Billing Issues)

| Component | Status | Details |
|-----------|--------|---------|
| Gemini `tools/call` | **Blocked** | 429 billing cap — no API calls possible |
| Slack tools | **Backend issue** | `TypeError` in Slack backend + missing OAuth scopes |
| Debugging Agent tools | **0 tools** | Delegation doesn't cover Notion/Slack prompt services |

## 7. Open Issues (Next Steps)

### 7.1 [RESOLVED] Claude Lists Tools But Doesn't Call Them

**Fixed**: Removing `--bare`, increasing `MCP_TIMEOUT` to 60s, setting `MCP_CONNECTION_NONBLOCKING=false`, and adding `warm_gateway()` before each Claude attempt resolved the issue. Claude now successfully calls `notion.search_pages` and `notion.read_page` through the MCP gateway.

**Verified execution**: `engineering-audit-hkk6d` — Claude connected, discovered 12 tools, called 2 tools, returned real Notion data ("Company Strategy 2026").

### 7.2 [RESOLVED] Codex Exit Code 1 → Now WORKING

**Original root cause**: `insufficient_quota` — billing credits depleted on OpenAI account.

**Resolution path** (3 issues fixed in sequence):
1. **Billing credits added** → unblocked API calls
2. **`codex login --with-api-key`** added to `configure_mcp()` → fixed WebSocket 401 auth (env var alone wasn't enough)
3. **`--dangerously-bypass-approvals-and-sandbox`** replaced `--sandbox workspace-write` → fixed "user cancelled MCP tool call" sandbox issue

**Verified execution**: `engineering-audit-jccnk` — Codex connected as `codex-mcp-client v0.139.0`, called `notion.search_pages` (8 successful calls), `notion.read_page` (4 successful calls), returned real Notion data ("Company Strategy 2026", page properties, timestamps). 17,218 tokens used.

### 7.3 Debugging Agent Has 0 Tools

Unchanged — delegation needs Notion+Slack permissions.

### 7.4 Gemini Billing Cap

Gemini account has exceeded billing limits:
- **Gemini**: 429 "exceeded monthly spending cap" → [AI Studio billing](https://ai.studio/billing)

**Claude (Anthropic)** and **Codex (OpenAI)** both have active billing and work end-to-end.

### 7.5 Slack Backend Bug

Claude connected to Slack tools but got backend errors:
1. `TypeError: '>' not supported between instances of 'int' and 'str'` — parameter type coercion bug in Slack MCP backend
2. `Token is missing required scopes` — Slack app token needs `channels:read`, `channels:history`, `chat:write` OAuth scopes

## 8. Files Changed

| File | Changes |
|------|---------|
| `agents/gemini/Dockerfile.sdk` | Added `@anthropic-ai/claude-code@latest @openai/codex@latest` npm installs, version smoke test |
| `agents/gemini/entrypoint_sdk.py` | Multi-LLM fallback chain, `type: "http"` MCP config, `--mcp-config` for Claude (no `--bare`), TOML + `codex login` for Codex, `--dangerously-bypass-approvals-and-sandbox`, tool-failure phrase detection, head+tail output logging, `warm_gateway()` per-provider |
| `infra/deploy-agent.sh` | 3 secrets (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`), `LLM_PROVIDERS` env var, SA slug→email mapping, `^;^` delimiter for gcloud |
| `agents/gemini/entrypoint.sh` | Preserved as fallback (not deleted) |
| `agents/gemini/README.md` | Updated to reflect multi-LLM architecture |

## 9. GCP Resource State

### Cloud Run Jobs

All three jobs use image `gemini-agent-sdk:latest` with `entrypoint_sdk.py`:

| Job | AGENT_ID | Service Account | Secrets |
|-----|----------|-----------------|---------|
| `gemini-deepsecure-agent` | `debugging-agent-sa` | `debugging-agent-sa@deepsecure-saas.iam` | 3 API keys |
| `engineering-audit` | `engineering-audit-agent` | `engineering-audit-sa@deepsecure-saas.iam` | 3 API keys |
| `thunderbolt-deepsecure-agent` | `thunderbolt-agent` | `thunderbolt-agent-sa@deepsecure-saas.iam` | 3 API keys |

### GCP Secret Manager

| Secret | Used By |
|--------|---------|
| `gemini-api-key` | `GEMINI_API_KEY` — blocked by billing cap |
| `anthropic-api-key` | `ANTHROPIC_API_KEY` — working (Claude connects) |
| `openai-api-key` | `OPENAI_API_KEY` — working (Codex `tools/call` confirmed) |

## 10. Recommended Next Actions (Priority Order)

1. **Raise Gemini billing cap** — unblocks the primary provider path immediately
2. **Fix Slack backend** — add missing OAuth scopes (`channels:read`, `channels:history`, `chat:write`) and fix `TypeError` bug
3. **Fix Debugging Agent delegation** — add Notion+Slack delegation so it gets >0 tools
4. **Consider `compute_state_bulk` bug** — bulk query doesn't filter `is_active=True` (minor inconsistency with single-agent `compute_state`)

## 11. Lessons Learned

| Lesson | Impact |
|--------|--------|
| Claude Code uses `"type"` not `"transport"` for MCP config | Silent connection failure — no error, just missing tools |
| Codex uses TOML (`config.toml`) not JSON for config | Wrong file format = config ignored |
| CLI exit code 0 ≠ task success for LLMs | Must inspect output for semantic failure indicators |
| `--bare` is recommended for Claude headless but changes MCP loading behavior | Need `--mcp-config` explicit flag; auto-discovery skipped |
| `--ask-for-approval` removed from Codex CLI | Breaking change in `@openai/codex@latest` |
| Codex has no `--mcp-config` flag | Must use `config.toml` or `codex mcp add` |
| Codex env var `OPENAI_API_KEY` not enough for WebSocket auth | Must run `codex login --with-api-key` to store in `auth.json` |
| Codex `--sandbox workspace-write` cancels MCP tool calls | Use `--dangerously-bypass-approvals-and-sandbox` in isolated containers |
| Gateway `tools/list` ≠ Active state | Only `tools/call` triggers the heartbeat that sets Active |
