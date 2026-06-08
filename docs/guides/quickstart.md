# DeepSecure Bootstrap — Quickstart

> Get an AI agent connected to DeepSecure-managed tools in 5 minutes.

## Prerequisites

| Requirement | How to verify |
|-------------|--------------|
| Python 3.10+ | `python --version` |
| `deepsecure` installed | `pip install deepsecure` |
| Running DeepSecure backend **or** cloud deployment | `curl http://localhost:8000/health` (local) or `curl https://api.deepsecure.one/health` (cloud) |
| A registered agent | Created via `deepsecure agent create --name my-agent` or provisioned in the admin UI |

## Step 1: Install the SDK

```bash
pip install deepsecure
```

For local development (keyring-based auth):

```bash
pip install deepsecure[cli]
```

## Step 2: Register an Agent (if needed)

```bash
deepsecure agent create --name my-agent
```

This generates an Ed25519 keypair, stores the private key in your OS keyring, and registers the public key with the control plane.

## Step 3: Bootstrap

The `deepsecure bootstrap` command converts your platform identity into a DeepSecure Agent JWT.

**Auto-detect platform (recommended):**

```bash
deepsecure bootstrap --agent-id agent-<your-uuid>
```

**Specify platform explicitly:**

```bash
# Local development (keyring)
deepsecure bootstrap --agent-id agent-abc123 --platform local

# GCP (Cloud Run, GKE, Compute Engine)
deepsecure bootstrap --agent-id agent-abc123 --platform gcp

# AWS (ECS, Lambda, EC2)
deepsecure bootstrap --agent-id agent-abc123 --platform aws
```

## Step 4: Choose an Output Format

| Format | Flag | Use case |
|--------|------|----------|
| Raw JWT | `--output jwt` (default) | Pipe into scripts, set env vars manually |
| MCP JSON | `--output mcp-json` | Copy-paste into Gemini, Claude Code, Codex config |
| Shell exports | `--output env` | `eval $(deepsecure bootstrap ... --output env)` |

**Example — MCP config for any CLI tool:**

```bash
deepsecure bootstrap \
  --agent-id agent-abc123 \
  --output mcp-json \
  --quiet
```

Output:

```json
{
  "mcpServers": {
    "deepsecure": {
      "url": "https://gateway.deepsecure.one/mcp",
      "transport": "http",
      "headers": {
        "Authorization": "Bearer eyJhbGciOiJIUz..."
      }
    }
  }
}
```

## Step 5: Connect Your CLI Tool

Copy the MCP JSON output into your tool's configuration:

- **Gemini CLI** → See [Gemini CLI Integration Guide](./gemini-cli.md)
- **Claude Code** → See [Claude Code CLI Integration Guide](./claude-code-cli.md)
- **Codex CLI** → See [Codex CLI Integration Guide](./codex-cli.md)

## Step 6: Verify

```bash
# Quick smoke test — list tools via the gateway
curl -s -X POST https://gateway.deepsecure.one/mcp \
  -H "Authorization: Bearer $(deepsecure bootstrap -a agent-abc123 -o jwt -q)" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'
```

## Programmatic Use (Python SDK)

```python
from deepsecure import bootstrap

result = bootstrap("agent-abc123", platform="auto")

print(result.jwt)           # Raw JWT token
print(result.to_mcp_json()) # MCP config dict
print(result.to_env())      # Shell export statements
print(result.delegations)   # List of delegations with per-service JWTs
```

## Next Steps

- [Gemini CLI Guide](./gemini-cli.md) — Connect Google's Gemini CLI
- [Claude Code CLI Guide](./claude-code-cli.md) — Connect Anthropic's Claude Code
- [Codex CLI Guide](./codex-cli.md) — Connect OpenAI's Codex CLI
- Stdio MCP Proxy — For long-running sessions with automatic JWT refresh (Phase 2)
