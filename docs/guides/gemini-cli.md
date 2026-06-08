# Gemini CLI — DeepSecure Integration Guide

> Connect Google's Gemini CLI to DeepSecure-managed tools via the MCP gateway.

**Prerequisites:** Complete the [Quickstart Guide](./quickstart.md) first.

## Overview

Gemini CLI supports MCP servers natively via HTTP transport. DeepSecure's gateway exposes an MCP endpoint at `/mcp` that Gemini can connect to directly — no proxy needed.

## Step 1: Bootstrap

```bash
deepsecure bootstrap \
  --agent-id agent-<your-uuid> \
  --output mcp-json \
  --quiet \
  > /tmp/deepsecure-mcp.json
```

## Step 2: Configure Gemini CLI

Add the MCP server to your Gemini settings file (`~/.gemini/settings.json`):

```json
{
  "mcpServers": {
    "deepsecure": {
      "url": "https://gateway.deepsecure.one/mcp",
      "transport": "http",
      "headers": {
        "Authorization": "Bearer <JWT_FROM_STEP_1>"
      }
    }
  }
}
```

Or use the bootstrap output directly:

```bash
deepsecure bootstrap \
  -a agent-abc123 \
  -o mcp-json \
  -q \
  > ~/.gemini/settings.json
```

## Step 3: Verify

```bash
gemini
# At the prompt:
> List my available tools
```

Gemini should display the tools available through your DeepSecure delegations (e.g., `github.search_repos`, `notion.search_pages`).

## GCP Cloud Run Deployment

For agents running on GCP Cloud Run, the bootstrap command auto-detects the platform:

```bash
# In your Dockerfile or entrypoint.sh:
deepsecure bootstrap \
  --agent-id ${AGENT_ID} \
  --platform gcp \
  --output mcp-json \
  --quiet \
  > /app/mcp-config.json

gemini --settings /app/mcp-config.json
```

The `--platform gcp` flag fetches an OIDC identity token from the GCP metadata server and exchanges it for a DeepSecure Agent JWT — no keyring or static credentials needed.

## Token Refresh

The JWT issued by `deepsecure bootstrap` has a 1-hour TTL. For long-running sessions:

- **Short sessions (<1h):** Single bootstrap is sufficient
- **Cron/scheduled agents:** Re-run `deepsecure bootstrap` at the start of each invocation
- **Long-running agents:** Use the stdio MCP proxy (Phase 2): `deepsecure-proxy --agent-id X`

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "No MCP servers configured" | Settings file not found | Verify `~/.gemini/settings.json` exists |
| "401 Unauthorized" | JWT expired or invalid | Re-run `deepsecure bootstrap` to get a fresh token |
| "No tools available" | No delegations for this agent | Create a delegation in the admin UI or via API |
| Connection timeout | Gateway unreachable | Check `curl https://gateway.deepsecure.one/health` |

## Reference

- [Quickstart](./quickstart.md)
- [DeepSecure Bootstrap CLI Reference](../SDK_REFERENCE.md)
- Production entrypoint example: [`agents/gemini/entrypoint.sh`](../../agents/gemini/entrypoint.sh)
