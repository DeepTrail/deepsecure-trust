# Codex CLI — DeepSecure Integration Guide

> Connect OpenAI's Codex CLI to DeepSecure-managed tools via the MCP gateway.

**Prerequisites:** Complete the [Quickstart Guide](./quickstart.md) first.

## Overview

Codex CLI supports remote MCP servers over HTTP transport. DeepSecure's gateway exposes a standard MCP endpoint at `/mcp` that Codex can connect to using its native MCP configuration.

## Step 1: Bootstrap

```bash
deepsecure bootstrap \
  --agent-id agent-<your-uuid> \
  --output mcp-json \
  --quiet
```

## Step 2: Configure Codex CLI

Add the DeepSecure MCP server to your Codex configuration (`~/.codex/config.json` or project-level `.codex/config.json`):

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

Or write the config directly:

```bash
mkdir -p ~/.codex
deepsecure bootstrap \
  -a agent-abc123 \
  -o mcp-json \
  -q \
  > ~/.codex/config.json
```

## Step 3: Verify

```bash
codex
# At the prompt:
> What tools are available?
```

Codex should list the tools available through your DeepSecure delegations.

## Cloud Deployment (GCP)

```bash
# In your agent's entrypoint:
deepsecure bootstrap \
  --agent-id ${AGENT_ID} \
  --platform gcp \
  -o mcp-json \
  -q \
  > /app/codex-mcp.json

codex --mcp-config /app/codex-mcp.json
```

## Cloud Deployment (AWS)

```bash
# In your ECS task or Lambda:
deepsecure bootstrap \
  --agent-id ${AGENT_ID} \
  --platform aws \
  -o mcp-json \
  -q \
  > /tmp/codex-mcp.json

codex --mcp-config /tmp/codex-mcp.json
```

## Token Refresh

The JWT has a 1-hour TTL. For Codex:

- **Single-shot tasks:** Bootstrap once at the start
- **Scheduled agents:** Re-bootstrap per invocation
- **Long-running sessions:** Use the stdio MCP proxy (Phase 2): `deepsecure-proxy --agent-id X`

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "MCP server not reachable" | Wrong URL or gateway down | Check `curl https://gateway.deepsecure.one/health` |
| "Authentication failed" | JWT expired | Re-run `deepsecure bootstrap` |
| "No tools registered" | No delegations for this agent | Create a delegation in the admin UI |
| Tool call returns 403 | Missing permission in delegation | Check delegation permissions match tool requirements |

## Reference

- [Quickstart](./quickstart.md)
- [DeepSecure Bootstrap CLI Reference](../SDK_REFERENCE.md)
