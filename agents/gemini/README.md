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
  -e AGENT_ID=debugging-agent-sa \
  -e GEMINI_API_KEY=<your-key> \
  -e AGENT_MAX_ITERATIONS=1 \
  gemini-agent
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSECURE_CONTROL_URL` | `https://app.deepsecure.one` | Control plane URL for bootstrap |
| `DEEPSECURE_GATEWAY_URL` | `https://app.deepsecure.one/mcp` | MCP gateway URL |
| `AGENT_ID` | `debugging-agent-sa` | Agent identity |
| `GEMINI_API_KEY` | (required) | Google Gemini API key |
| `AGENT_MAX_ITERATIONS` | `6` | Number of tool call iterations |
| `AGENT_INTERVAL_SECONDS` | `300` | Sleep between iterations (seconds) |

## Deployment (GCP)

See `infra/deploy-agent.sh` for the full deployment script.

```bash
# Build and push to Artifact Registry
docker build -t us-central1-docker.pkg.dev/deepsecure-saas/deepsecure/gemini-agent:latest .
docker push us-central1-docker.pkg.dev/deepsecure-saas/deepsecure/gemini-agent:latest

# Create Cloud Run Job
gcloud run jobs create gemini-deepsecure-agent \
  --image=us-central1-docker.pkg.dev/deepsecure-saas/deepsecure/gemini-agent:latest \
  --region=us-central1 \
  --service-account=debugging-agent-sa@deepsecure-saas.iam.gserviceaccount.com \
  --task-timeout=2400s \
  --max-retries=1 \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
  --set-env-vars="DEEPSECURE_CONTROL_URL=https://app.deepsecure.one,DEEPSECURE_GATEWAY_URL=https://app.deepsecure.one/mcp,AGENT_INTERVAL_SECONDS=300,AGENT_MAX_ITERATIONS=6"
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
