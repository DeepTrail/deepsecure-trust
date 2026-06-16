# Gemini CLI Agent for DeepSecure

A containerized AI agent that bootstraps via GCP Workload Identity, connects to DeepSecure's MCP gateway, and calls real tools (Slack, Notion, Gmail, Google Drive, Google Calendar) in a loop.

## Architecture

```
Cloud Scheduler (every 6h)
    │
    ▼
Cloud Run Job (max 30 min)
    │
    ├── Bootstrap (GCP OIDC → Agent JWT)
    ├── Configure Gemini CLI MCP settings
    ├── LOOP (6 iterations × 5 min interval):
    │   ├── gemini -p "<tool call prompt>"
    │   ├── sleep 300
    │   └── (re-bootstrap every 10 iterations for JWT refresh)
    └── Exit cleanly
```

## Local Development

### Build

```bash
docker build -t gemini-agent .
```

### Run (1 iteration, against production)

```bash
docker run --rm \
  -e DEEPSECURE_CONTROL_URL=https://app.deepsecure.one \
  -e DEEPSECURE_GATEWAY_URL=https://app.deepsecure.one/mcp \
  -e AGENT_ID=debugging-deepsecure-agent \
  -e GEMINI_API_KEY=<your-key> \
  -e AGENT_MAX_ROUNDS=1 \
  gemini-agent
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSECURE_CONTROL_URL` | `https://app.deepsecure.one` | Control plane URL for bootstrap |
| `DEEPSECURE_GATEWAY_URL` | `https://app.deepsecure.one/mcp` | MCP gateway URL |
| `AGENT_ID` | `debugging-deepsecure-agent` | Agent identity |
| `GEMINI_API_KEY` | (required) | Google Gemini API key |
| `AGENT_MAX_ROUNDS` | `3` | Number of tool call rounds |
| `AGENT_PROMPTS_PER_DELEGATION` | `2` | Prompts per delegation per round |
| `AGENT_INTERVAL_SECONDS` | `60` | Sleep between rounds (seconds) |

### Agent Naming Convention

All agents follow the `{slug}-deepsecure-agent` pattern:

| Agent | AGENT_SLUG | AGENT_ID | JOB_NAME | SA |
|-------|------------|----------|----------|----|
| Debugging | `debugging` | `debugging-deepsecure-agent` | `debugging-deepsecure-agent-job` | `debugging-agent-sa@...` |
| Engineering Audit | `engineering-audit` | `engineering-audit-deepsecure-agent` | `engineering-audit-deepsecure-agent-job` | `engineering-audit-sa@...` |
| Thunderbolt | `thunderbolt` | `thunderbolt-deepsecure-agent` | `thunderbolt-deepsecure-agent-job` | `thunderbolt-agent-sa@...` |

## Deployment (GCP)

See `infra/deploy-agent.sh` for the full deployment script. It derives all
resource names from `AGENT_SLUG`:

Naming convention (`TENANT_NAME=deepsecure` by default):

| Agent Name | `AGENT_SLUG` | `AGENT_ID` | `JOB_NAME` | `SCHEDULER_NAME` | Service Account |
|---|---|---|---|---|---|
| Debugging Agent | `debugging` | `debugging-deepsecure-agent` | `debugging-deepsecure-agent-job` | `trigger-debugging-deepsecure-agent` | `debugging-sa@...` |
| Engineering Audit | `engineering-audit` | `engineering-audit-deepsecure-agent` | `engineering-audit-deepsecure-agent-job` | `trigger-engineering-audit-deepsecure-agent` | `engineering-audit-sa@...` |
| Thunderbolt | `thunderbolt` | `thunderbolt-deepsecure-agent` | `thunderbolt-deepsecure-agent-job` | `trigger-thunderbolt-deepsecure-agent` | `thunderbolt-sa@...` |

```bash

# Deploy all 3 agents (build image once)
AGENT_SLUG=debugging          ./infra/deploy-agent.sh
AGENT_SLUG=engineering-audit  SKIP_BUILD=1 ./infra/deploy-agent.sh
AGENT_SLUG=thunderbolt        SKIP_BUILD=1 ./infra/deploy-agent.sh
```

## Tool Call Prompts

Each iteration calls a specific service following the `discover → read → write` pattern:

1. **Notion** — search pages + read content
2. **Slack** — list channels + read history + post message
3. **Gmail** — search unread messages
4. **Google Drive** — search files
5. **Google Calendar** — list events
6. **Cross-service** — multi-tool summary across Slack, Notion, Gmail

## Design References

- Design doc: `docs/design/gcp-background-agent.md`
- Spec: `docs/spec/gcp-background-agent-spec.md`
- Sarah's Journey demo: `scripts/demo_sarah_journey.sh`
