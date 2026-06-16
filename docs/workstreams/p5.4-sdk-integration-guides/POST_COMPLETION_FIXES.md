# Post-Completion Fixes — p5.4-sdk-integration-guides

Issues discovered and fixed during E2E testing after the P5.4 SDK + Integration Guides workstream was completed and deployed to GCP Cloud Run.

> **Date range:** June 8–16, 2026  
> **Branch:** `feature/p5.4-sdk-integration-guides` → `dev`  
> **Affected services:** deepsecure SDK, deepsecure-proxy, gemini-agent (Dockerfile.sdk + entrypoint_sdk.py), deeptrail-control, deeptrail-gateway, frontend  
> **Testing scope:** Local E2E (docker compose), GCP Live deployment (Cloud Run), SDK entrypoint replacement, multi-LLM fallback, OAuth lifecycle, gateway health monitoring

---

## Fix 1: `to_mcp_json()` Double `/mcp` in Gateway URL

| Field | Detail |
|-------|--------|
| **Symptom** | `BootstrapResult.to_mcp_json()` generated a URL like `https://app.deepsecure.one/mcp/mcp` when the `gateway_url` already ended with `/mcp`. |
| **Root Cause** | The method unconditionally appended `/mcp` to the gateway URL without checking whether the path was already present. |
| **Fix** | Modified `deepsecure/_core/bootstrap.py` to `rstrip("/")` the gateway URL, then only append `/mcp` if the URL doesn't already end with it. Added explicit unit tests for both cases. |
| **Files Changed** | `deepsecure/_core/bootstrap.py`, `tests/_core/test_bootstrap.py` |

---

## Fix 2: `deepsecure-proxy` Platform Enum Mismatch

| Field | Detail |
|-------|--------|
| **Symptom** | Running `deepsecure-proxy` with `--platform local` raised `DeepSecureError: Unsupported platform: local`. |
| **Root Cause** | `JWTManager` in `deepsecure-proxy` passed the `platform` argument as a raw string (`"local"`) to `BootstrapClient.bootstrap()`, which expects a `Platform` enum member (`Platform.LOCAL`). |
| **Fix** | Modified `deepsecure-proxy/deepsecure_proxy/jwt_manager.py` to convert the string platform value to its corresponding `Platform` enum member before passing to `bootstrap()`. |
| **Files Changed** | `deepsecure-proxy/deepsecure_proxy/jwt_manager.py` |

---

## Fix 3: `ModuleNotFoundError: No module named 'keyring'` in SDK Agent Container

| Field | Detail |
|-------|--------|
| **Symptom** | The Gemini agent container using `Dockerfile.sdk` failed on startup with `ModuleNotFoundError: No module named 'keyring'`. The SDK was installed as `pip install deepsecure` (core only, no `[cli]` extra), but core modules had hard imports of `keyring`. |
| **Root Cause** | Four core SDK modules had unconditional top-level imports of optional dependencies that are only available with the `[cli]` extra: |
| | **3a** — `deepsecure/_core/identity_manager.py`: `import keyring` at module level |
| | **3b** — `deepsecure/_core/identity_provider.py`: `import keyring` at module level |
| | **3c** — `deepsecure/_core/config.py`: `import keyring` and `import keyring.errors` at module level |
| | **3d** — `deepsecure/utils.py`: `import typer` and `from rich.console import Console` at module level |
| **Fix** | Made all four imports conditional using `try/except ImportError` patterns: |
| | **3a–3b** — Guarded `import keyring` with `_HAS_KEYRING` flag; functions that use keyring check the flag and gracefully degrade. |
| | **3c** — Added `_HAS_KEYRING` flag to `config.py`; `get_api_token()` returns `None`, `set_api_token()` and `delete_api_token()` print warnings when keyring is unavailable. |
| | **3d** — Added `_HAS_TYPER` and `_HAS_RICH` flags to `utils.py`; created `_FallbackConsole` for environments without `rich`. |
| **Files Changed** | `deepsecure/_core/identity_manager.py`, `deepsecure/_core/identity_provider.py`, `deepsecure/_core/config.py`, `deepsecure/utils.py` |

---

## Fix 4: Cloud Run "Application Failed to Start" — ARM64 vs AMD64 Architecture Mismatch

| Field | Detail |
|-------|--------|
| **Symptom** | After deploying `Dockerfile.sdk` to Cloud Run, the job failed immediately with "Application failed to start" and no application output in logs. Even a debug `ENTRYPOINT ["/bin/sh", "-c", "echo hello"]` failed with "exec likely failed". |
| **Root Cause** | Building the Docker image on Apple Silicon (M-series) without `--platform` flag produced a `linux/arm64` image. Cloud Run runs on `linux/amd64` infrastructure and cannot execute ARM64 binaries. |
| **Fix** | Rebuilt the image using `docker buildx build --platform linux/amd64` to explicitly target the AMD64 architecture. Added build-time smoke test (`python3 -c "from deepsecure._core.bootstrap import BootstrapClient, Platform; print('SDK import OK')"`) to the Dockerfile to catch import failures early. |
| **Files Changed** | `agents/gemini/Dockerfile.sdk` (added smoke test RUN), `infra/build-and-push.sh` (platform flag) |

---

## Fix 5: Entrypoint Using Non-Venv `python3` — PATH Resolution Ambiguity

| Field | Detail |
|-------|--------|
| **Symptom** | Initial `Dockerfile.sdk` used `ENTRYPOINT ["python3", "/app/entrypoint_sdk.py"]`. On Cloud Run, the system `python3` was resolved instead of the venv `python3`, potentially missing SDK packages. |
| **Root Cause** | While `ENV PATH="/opt/deepsecure-venv/bin:$PATH"` was set in the Dockerfile, Cloud Run's execution environment may not preserve all `ENV` directives identically, leading to ambiguity in which `python3` binary was invoked. |
| **Fix** | Changed `ENTRYPOINT` to use the absolute path: `["/opt/deepsecure-venv/bin/python3", "/app/entrypoint_sdk.py"]`. This eliminates PATH resolution ambiguity entirely. |
| **Files Changed** | `agents/gemini/Dockerfile.sdk` |

---

## Fix 6: `_fetch_delegations()` Returns Empty Permissions — Wrong API Response Field Names

| Field | Detail |
|-------|--------|
| **Symptom** | After successful OIDC bootstrap on GCP, the SDK `entrypoint_sdk.py` correctly fetched delegations but logged "No matching prompts for permissions: []" for every delegation. All permission lists were empty. |
| **Root Cause** | Two field name mismatches between the SDK and the actual API response: |
| | **6a** — SDK read `item.get("permissions", [])` but the API returns permissions in the `delegated_permissions` field. |
| | **6b** — SDK read `item.get("service", "unknown")` for the delegator identity but the API returns it in the `delegator` field. |
| **Evidence** | The working bash `entrypoint.sh` used `jq -r '.delegated_permissions[]'`, confirming the correct field name. |
| **Fix** | Updated `_fetch_delegations()` in `deepsecure/_core/bootstrap.py` to use `item.get("delegated_permissions") or item.get("permissions", [])` for permissions and `item.get("service") or item.get("delegator", "unknown")` for the delegator identity. Fallback to original field names maintained for backward compatibility. |
| **Files Changed** | `deepsecure/_core/bootstrap.py` |

---

## Fix 7: Gemini API Quota Exhaustion (External — Not a Code Bug)

| Field | Detail |
|-------|--------|
| **Symptom** | After successful SDK bootstrap and delegation fetching on GCP, Gemini CLI tool calls failed with HTTP 429 `TerminalQuotaError` — "Quota for model gemini-3.5-flash exceeded: daily quota". |
| **Root Cause** | The Gemini API free tier daily quota was exhausted from prior testing runs. This is an external resource limit, not a DeepSecure SDK or agent logic bug. |
| **Impact** | The SDK correctly handled the error and continued with subsequent delegations/rounds, demonstrating graceful degradation. The bootstrap flow, delegation fetching, MCP configuration, and gateway warm-up all succeeded — only the final Gemini LLM inference step failed due to quota. |
| **Resolution** | Wait for quota reset or upgrade the Gemini API plan. The SDK entrypoint was verified as working correctly. |
| **Files Changed** | None |

---

## Summary

| # | Issue | Category | Severity | Status |
|---|-------|----------|----------|--------|
| 1 | `to_mcp_json()` double `/mcp` in URL | SDK — URL construction | Medium | Fixed |
| 2 | Proxy platform string vs enum mismatch | deepsecure-proxy — Type | Medium | Fixed |
| 3a | `identity_manager.py` hard import of `keyring` | SDK — Optional dep | High | Fixed |
| 3b | `identity_provider.py` hard import of `keyring` | SDK — Optional dep | High | Fixed |
| 3c | `config.py` hard import of `keyring` | SDK — Optional dep | High | Fixed |
| 3d | `utils.py` hard import of `typer`/`rich` | SDK — Optional dep | High | Fixed |
| 4 | ARM64 image on AMD64 Cloud Run | DevOps — Build | Critical | Fixed |
| 5 | Non-venv `python3` in ENTRYPOINT | Dockerfile — PATH | Medium | Fixed |
| 6a | `delegated_permissions` field name mismatch | SDK — API contract | High | Fixed |
| 6b | `delegator` field name mismatch | SDK — API contract | Medium | Fixed |
| 7 | Gemini API quota exhaustion | External — Quota | N/A | Not a bug |
| 8 | Bootstrap network timeout on cold start | Agent — Resilience | High | Fixed |
| 9 | `gcloud` env var parsing for `LLM_PROVIDERS` | DevOps — Deploy | High | Fixed |
| 10 | Multi-LLM fallback + DB config merge conflict | Agent — Core | Critical | Fixed |
| 11 | Prompt timeout too aggressive (300s → 120s) | Agent — Config | Medium | Fixed |
| 12 | Google OAuth tokens silently expiring | Vault — Token lifecycle | Critical | Fixed |
| 13 | Slack `list_channels` missing scopes | Gateway — Backends | Medium | Fixed |
| 14 | OAuth sweep ignoring already-expired tokens | Vault — Token lifecycle | Critical | Fixed |
| 15 | Gateway falsely reported as OFFLINE | Health — Monitoring | Medium | Fixed |

---

## Fix 8: Bootstrap Network Timeout on Cold Start

| Field | Detail |
|-------|--------|
| **Symptom** | Agent Cloud Run Job failed on startup with `httpx.ReadTimeout: The read operation timed out` when calling `/api/v1/auth/bootstrap/gcp`. Control Plane was in a cold start. |
| **Root Cause** | `BootstrapClient._post()` used a single HTTP call with no retries. When the Control Plane container was cold, the first request timed out before the service was ready. |
| **Fix** | Added `bootstrap_with_retry()` in `entrypoint_sdk.py` with exponential backoff (3 attempts, 5s/10s/20s delays). The agent now survives Control Plane cold starts. |
| **Files Changed** | `agents/gemini/entrypoint_sdk.py` |

---

## Fix 9: `gcloud` Env Var Parsing for `LLM_PROVIDERS`

| Field | Detail |
|-------|--------|
| **Symptom** | `gcloud run jobs update --set-env-vars LLM_PROVIDERS=gemini,claude,codex` misparsed the commas as env var separators, creating three separate variables instead of one. |
| **Root Cause** | `gcloud` uses commas as delimiters in `--set-env-vars`. The `LLM_PROVIDERS` value contains commas that conflict. |
| **Fix** | Modified `deploy-agent.sh` to use `^;^` as the gcloud delimiter and `entrypoint_sdk.py` to parse semicolons back to commas. |
| **Files Changed** | `infra/deploy-agent.sh`, `agents/gemini/entrypoint_sdk.py` |

---

## Fix 10: Multi-LLM Fallback + DB Config Merge Conflict

| Field | Detail |
|-------|--------|
| **Symptom** | PR #59 merge conflicts in `entrypoint_sdk.py` produced: duplicate `run_prompt_with_fallback()`, missing `_FALLBACK_*` constants (causing `NameError`), and hardcoded fallback values that bypassed DB configuration. |
| **Root Cause** | Two independent features (DB-driven config from commit `5841833` + multi-LLM fallback from commit `9a15ea5`) needed to coexist. The merge resolution kept conflicting code from both sides. |
| **Fix** | PR #59 was closed. A clean merge in PR #61 combined both features: `fetch_config()` + `resolve_config()` for DB config, `detect_available_providers()` + `run_prompt_with_fallback()` for multi-LLM. PR #62 cherry-picked safe deploy-script improvements from #59. |
| **Files Changed** | `agents/gemini/entrypoint_sdk.py`, `infra/deploy-agent.sh` |

---

## Fix 11: Prompt Timeout Reduction (300s → 120s)

| Field | Detail |
|-------|--------|
| **Symptom** | Gemini CLI hit the 300s timeout on complex prompts, spending the time in investigation loops (writing scripts, inspecting configs) instead of direct tool calls. |
| **Root Cause** | 300s was too generous — it gave the LLM CLI enough time to enter its "debug and investigate" spiral. 120s is sufficient for direct tool calls (Claude completes in ~30s) while being short enough to kill investigation loops early. |
| **Fix** | Updated `PROMPT_TIMEOUT_SECONDS` from 300 to 120 on the Cloud Run Job env vars. |
| **Files Changed** | Cloud Run Job configuration (runtime env var) |

---

## Fix 12: Google OAuth Tokens Silently Expiring

| Field | Detail |
|-------|--------|
| **Symptom** | Google services (Gmail, GDrive, GCalendar) showed "Expired" in the Vault UI despite a cron job for auto-refresh. Agents hitting Google APIs got 401 errors. |
| **Root Cause** | The event-driven token refresh scheduler loses its timers after Control Plane cold starts or container restarts. No fallback mechanism existed to catch missed refreshes. |
| **Fix** | Created a Cloud Scheduler cron job (`trigger-oauth-token-refresh`) that hits `POST /api/v1/vault/internal/tokens/refresh-sweep?threshold_minutes=120` every 30 minutes. Also added the `/internal/tokens/refresh-sweep` endpoint to the Control Plane. |
| **Files Changed** | `deeptrail-control/app/api/v1/endpoints/vault.py`, `deeptrail-control/app/services/vault_client.py` |

---

## Fix 13: Slack `list_channels` Missing Scopes

| Field | Detail |
|-------|--------|
| **Symptom** | Slack `list_channels` failed for Delegation 1 (public channels only) but worked for Delegation 2 (which had broader scopes). |
| **Root Cause** | `slack_client.py` defaulted `types` parameter to `public_channel,private_channel`. Delegation 1's bot token only had `channels:read` (public), not `groups:read` (private). Requesting private channels with insufficient scopes caused the API call to fail entirely. |
| **Fix** | Changed the default `types` from `public_channel,private_channel` to `public_channel` in `slack_client.py` (3 occurrences). |
| **Files Changed** | `deeptrail-gateway/app/backends/slack_client.py` |

---

## Fix 14: OAuth Sweep Ignoring Already-Expired Tokens

| Field | Detail |
|-------|--------|
| **Symptom** | Google OAuth tokens showed "Last Refreshed: 1h ago" but status was "Expired". The cron sweep ran but tokens still expired. Required manual re-authorization every time. |
| **Root Cause** | `get_tokens_needing_refresh()` filtered with `expires_at > NOW()` — only finding tokens **about to expire**, never tokens **already expired**. If the sweep missed a single 30-min window (cold start, transient error), the token expired and the sweep could never recover it. |
| **Fix** | Changed the query to include already-expired tokens (up to 48 hours old) using `OR(about-to-expire, already-expired-within-48h)`. Added `include_expired=True` and `max_expired_hours=48` parameters. |
| **Files Changed** | `deeptrail-control/app/services/vault_client.py`, `deeptrail-control/app/api/v1/endpoints/vault.py` |

---

## Fix 15: Gateway Falsely Reported as OFFLINE

| Field | Detail |
|-------|--------|
| **Symptom** | Health Dashboard showed "GATEWAY OFFLINE — Last heartbeat 17m ago" even though the gateway Cloud Run service was healthy and responsive. |
| **Root Cause** | Cloud Run scales to zero when no traffic arrives. No running instance = no heartbeat sent. The Control Plane had a 180s stale threshold and only two states: "up" and "down". Any stale heartbeat was classified as "down" with no distinction between scale-to-zero (normal) and actual crash (problem). |
| **Fix** | Two-part fix: |
| | **15a — Cloud Scheduler keepalive**: Created `keepalive-gateway` cron job that pings the gateway `/health` endpoint every 2 minutes. Keeps the instance warm and heartbeats flowing. |
| | **15b — Smarter health status**: Added "sleeping" state to `_resolve_gateway_status()` for heartbeats stale between 3–30 min (likely scale-to-zero). "down" now only triggers after 30 min staleness (likely real outage). Frontend updated with blue "GATEWAY SLEEPING" banner and badge. |
| **Files Changed** | `deeptrail-control/app/services/service_registry_service.py`, `frontend/src/lib/types/admin.ts`, `frontend/src/app/(dashboard)/dashboard/admin/health/page.tsx` |

---

## Summary

| # | Issue | Category | Severity | Status |
|---|-------|----------|----------|--------|
| 1 | `to_mcp_json()` double `/mcp` in URL | SDK — URL construction | Medium | Fixed |
| 2 | Proxy platform string vs enum mismatch | deepsecure-proxy — Type | Medium | Fixed |
| 3a | `identity_manager.py` hard import of `keyring` | SDK — Optional dep | High | Fixed |
| 3b | `identity_provider.py` hard import of `keyring` | SDK — Optional dep | High | Fixed |
| 3c | `config.py` hard import of `keyring` | SDK — Optional dep | High | Fixed |
| 3d | `utils.py` hard import of `typer`/`rich` | SDK — Optional dep | High | Fixed |
| 4 | ARM64 image on AMD64 Cloud Run | DevOps — Build | Critical | Fixed |
| 5 | Non-venv `python3` in ENTRYPOINT | Dockerfile — PATH | Medium | Fixed |
| 6a | `delegated_permissions` field name mismatch | SDK — API contract | High | Fixed |
| 6b | `delegator` field name mismatch | SDK — API contract | Medium | Fixed |
| 7 | Gemini API quota exhaustion | External — Quota | N/A | Not a bug |
| 8 | Bootstrap network timeout on cold start | Agent — Resilience | High | Fixed |
| 9 | `gcloud` env var parsing for `LLM_PROVIDERS` | DevOps — Deploy | High | Fixed |
| 10 | Multi-LLM fallback + DB config merge conflict | Agent — Core | Critical | Fixed |
| 11 | Prompt timeout 300s → 120s | Agent — Config | Medium | Fixed |
| 12 | Google OAuth tokens silently expiring | Vault — Token lifecycle | Critical | Fixed |
| 13 | Slack `list_channels` missing scopes | Gateway — Backends | Medium | Fixed |
| 14 | OAuth sweep ignoring already-expired tokens | Vault — Token lifecycle | Critical | Fixed |
| 15 | Gateway falsely reported as OFFLINE | Health — Monitoring | Medium | Fixed |

---

## Lessons Learned

1. **Optional dependencies must have conditional imports throughout the entire import chain** — it's not enough to make `keyring` optional in `pyproject.toml`; every module that `import keyring` at the top level must guard the import with `try/except ImportError`. A single unguarded import anywhere in the chain defeats the "optional" designation.

2. **Always build Docker images with `--platform linux/amd64` when targeting Cloud Run** — Apple Silicon Macs default to `linux/arm64` builds. This produces images that pass local tests but fail silently on Cloud Run with "exec likely failed" — no useful error message. Add `--platform linux/amd64` to all `docker build` commands in CI and deployment scripts.

3. **Use absolute paths for ENTRYPOINT in Dockerfiles** — relying on `PATH` environment variables for interpreter resolution introduces ambiguity. `["/opt/deepsecure-venv/bin/python3", ...]` is explicit and debuggable; `["python3", ...]` depends on the runtime environment preserving PATH.

4. **Verify SDK field names against actual API responses, not design docs** — the SDK was built from the design spec which used `permissions` and `service`, but the actual API returns `delegated_permissions` and `delegator`. Always validate against a live API response (e.g., `curl` + `jq`) before finalizing field mappings.

5. **Add build-time smoke tests to Dockerfiles** — the `RUN python3 -c "from deepsecure._core.bootstrap import BootstrapClient, Platform"` line catches import failures during `docker build`, not during Cloud Run execution where debugging is slower and more expensive.

6. **Test the entire import chain, not just the target module** — `from deepsecure._core.bootstrap import BootstrapClient` succeeded locally because `keyring` was installed in the dev environment. Testing `import deepsecure` in a clean venv (without `[cli]` extras) would have caught the transitive import failures immediately.

7. **When debugging Cloud Run failures, check the image architecture first** — "Application failed to start" with no application logs is the signature of an architecture mismatch. Before investigating code or configuration, run `docker inspect <image> | jq '.[0].Architecture'` to verify.

8. **Provide backward-compatible fallbacks when fixing field name mismatches** — using `item.get("delegated_permissions") or item.get("permissions", [])` maintains compatibility if the API field names change or if the SDK is used against an older API version.

9. **Cloud Run scale-to-zero kills background tasks** — heartbeat loops, health pollers, and cache subscribers all stop when the instance is terminated. Any monitoring that depends on periodic signals from Cloud Run services must account for scale-to-zero. Use external keepalive pings (Cloud Scheduler) or distinguish "sleeping" from "down".

10. **Sweep/cleanup queries must include already-failed items** — filtering `expires_at > NOW()` in a token refresh sweep means tokens that have already expired can never be recovered automatically. Always include a recovery window for items that missed the proactive window.

11. **Merge conflicts in entrypoints are the highest-risk category** — `entrypoint_sdk.py` is the single file that orchestrates all agent behavior. Merge conflicts here can silently reintroduce hardcoded values that bypass DB configuration, duplicate functions, or remove constants. Always close conflicting PRs and create clean merges instead of resolving in-place.

12. **Interactive CLI tools repurposed for headless batch execution carry their interactive assumptions** — Gemini CLI's investigation loops (writing scripts, inspecting configs) are valuable in interactive mode but catastrophic in bounded batch execution. The tools available to the LLM determine its behavior more than the prompt does.

---

## E2E Testing Results

### Phase 1: Local E2E (docker compose + Ed25519)

| Test | Result | Notes |
|------|--------|-------|
| Agent registration | ✅ | Clean state setup with delete-if-exists pattern |
| Ed25519 bootstrap | ✅ | Challenge-response flow works |
| `BootstrapResult.to_mcp_json()` | ✅ | After Fix 1 |
| `BootstrapResult.to_env()` | ✅ | Correct env var format |
| Delegation fetching | ✅ | After Fix 6 |
| `deepsecure-proxy` stdio relay | ✅ | After Fix 2 |

### Phase 2: GCP Live Deployment (Cloud Run + OIDC)

| Test | Result | Notes |
|------|--------|-------|
| Control + Gateway redeployment | ✅ | Latest code deployed |
| All 3 agents triggered | ✅ | Cloud Scheduler triggered successfully |
| Agent lifecycle → Active | ✅ | Verified in UI |

### Phase 3: SDK Entrypoint Replacement (Dockerfile.sdk)

| Test | Result | Notes |
|------|--------|-------|
| `Dockerfile.sdk` build (amd64) | ✅ | After Fix 4 |
| SDK import smoke test | ✅ | Build-time verification |
| OIDC bootstrap via SDK | ✅ | After Fixes 3, 5 |
| Delegation round-robin | ✅ | After Fix 6 — all delegations processed |
| Gemini CLI tool calls | ⚠️ | Bootstrap + MCP config succeeded; Gemini quota exhausted (Fix 7) |
| `entrypoint.sh` preserved | ✅ | Original bash file retained |

### Phase 4: Multi-LLM Fallback + Production Hardening (June 15–16)

| Test | Result | Notes |
|------|--------|-------|
| Multi-LLM fallback chain (Gemini → Claude → Codex) | ✅ | Gemini timeout → Claude picked up in ~30s |
| DB-driven config (max_rounds, prompts_per_delegation) | ✅ | Config fetched from Control Plane API |
| Bootstrap with retry (cold start resilience) | ✅ | Exponential backoff survives Control Plane cold starts |
| Thunderbolt agent: 10/10 prompts, 2/2 delegations | ✅ | Full E2E across Notion, Slack, Gmail, GDrive, GCal, GitHub |
| Debugging agent: 7 prompts, 3 delegations | ✅ | Claude fallback verified on Slack/Google timeouts |
| OAuth token auto-refresh sweep | ✅ | 3/3 expired Google tokens recovered automatically |
| Gateway keepalive (Cloud Scheduler) | ✅ | Gateway stays warm, heartbeats every 2 min |
| Smarter health status (sleeping vs down) | ✅ | Frontend shows blue "SLEEPING" instead of red "OFFLINE" |

### New Artifacts Created

| File | Purpose |
|------|---------|
| `agents/gemini/entrypoint_sdk.py` | Python SDK replacement for bash `entrypoint.sh` |
| `agents/gemini/Dockerfile.sdk` | Dual-runtime (Node + Python) container image |
| `docs/guides/sdk-bootstrap-flow.md` | End-to-end bootstrap flow documentation |
| `tests/e2e/test_bootstrap_e2e.py` | Local E2E tests for bootstrap + proxy |
| `docs/MULTI_LLM_FALLBACK_ANALYSIS.md` | Analysis of multi-LLM fallback behavior |

### Cloud Scheduler Jobs Created

| Job Name | Schedule | Purpose |
|----------|----------|---------|
| `trigger-oauth-token-refresh` | `*/30 * * * *` | Proactive OAuth token refresh sweep |
| `keepalive-gateway` | `*/2 * * * *` | Prevent gateway scale-to-zero, keep heartbeats flowing |

### Deployed Revisions (June 16)

| Service | Revision | Image Tag | Changes |
|---------|----------|-----------|---------|
| `deeptrail-control` | `00048-fkm` | `sleeping-status` | Fix 14 (sweep recovery) + Fix 15b (sleeping status) |
| `frontend` | `00028-4sx` | `sleeping-status` | Fix 15b (sleeping/down UI distinction) |
| `deeptrail-gateway` | `00035-b66` | (prior deploy) | Fix 13 (Slack default types) |
