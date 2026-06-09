# Claude Code CLI — DeepSecure Integration Guide

> Connect Anthropic's Claude Code to DeepSecure-managed tools via the MCP gateway.

**Prerequisites:** Complete the [Quickstart Guide](./quickstart.md) first.

## Overview

Claude Code supports remote MCP servers over HTTP. DeepSecure's gateway exposes a standard MCP endpoint at `/mcp` that Claude Code can connect to using the `url` transport.

## Step 1: Bootstrap

```bash
deepsecure bootstrap \
  --agent-id agent-<your-uuid> \
  --output mcp-json \
  --quiet
```

## Step 2: Configure Claude Code

Add the DeepSecure MCP server to your Claude Code settings (`.claude/settings.json` or project-level `.mcp.json`):

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
mkdir -p .claude
deepsecure bootstrap \
  -a agent-abc123 \
  -o mcp-json \
  -q \
  > .claude/settings.json
```

## Step 3: Verify

```bash
claude
# At the prompt:
> What tools do I have access to?
```

Claude Code should list the tools available through your DeepSecure delegations.

## Cloud Deployment (GCP)

```bash
# In your agent's entrypoint:
deepsecure bootstrap \
  --agent-id ${AGENT_ID} \
  --platform gcp \
  -o mcp-json \
  -q \
  > .claude/settings.json

claude --mcp-config .claude/settings.json
```

## Cloud Deployment (AWS)

```bash
# In your ECS task definition or Lambda handler:
deepsecure bootstrap \
  --agent-id ${AGENT_ID} \
  --platform aws \
  -o mcp-json \
  -q \
  > /tmp/mcp-config.json

claude --mcp-config /tmp/mcp-config.json
```

## Token Refresh

The JWT has a 1-hour TTL. For long-running Claude Code sessions:

- **Interactive sessions:** Re-run `deepsecure bootstrap` and update the config when the token expires
- **Automated agents:** Re-bootstrap at the start of each task
- **Long-running sessions:** Use the stdio MCP proxy (Phase 2): `deepsecure-proxy --agent-id X`

## Using with CLAUDE.md

Add bootstrap instructions to your project's `CLAUDE.md` so Claude Code knows how to connect:

```markdown
## MCP Tools

This project uses DeepSecure for tool access. The MCP config at `.claude/settings.json`
provides access to tools via the DeepSecure gateway. Available tools depend on the
agent's delegations (configured in the DeepSecure admin UI).
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "Failed to connect to MCP server" | Wrong URL or gateway down | Check `curl https://gateway.deepsecure.one/health` |
| "401 Unauthorized" | JWT expired | Re-run `deepsecure bootstrap` |
| "No tools found" | No delegations | Create a delegation in the admin UI |
| Timeout on tool calls | Gateway processing delay | Check gateway logs; increase timeout in Claude Code settings |

## Reference

- [Quickstart](./quickstart.md)
- [DeepSecure Bootstrap CLI Reference](../SDK_REFERENCE.md)
