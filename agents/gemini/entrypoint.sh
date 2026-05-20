#!/usr/bin/env bash
set -euo pipefail

# === Configuration ===
CONTROL_URL="${DEEPSECURE_CONTROL_URL:-https://app.deepsecure.one}"
GATEWAY_URL="${DEEPSECURE_GATEWAY_URL:-https://app.deepsecure.one/mcp}"
AGENT_ID="${AGENT_ID:-debugging-agent-sa}"
MAX_ITERATIONS="${AGENT_MAX_ITERATIONS:-6}"
INTERVAL="${AGENT_INTERVAL_SECONDS:-300}"
BOOTSTRAP_REFRESH_INTERVAL=10

# === Prompt Design ===
# Prompts mirror the Sarah's Journey demo (scripts/demo_sarah_journey.sh ACT 5):
# Pattern: discover → read → write for each service
# Tool names must match exactly what the gateway exposes via tools/list
PROMPTS=(
  # Iteration 1: Notion — search docs, read content
  "You have access to tools via the deepsecure MCP server. Call notion.search_pages with query 'strategy' and limit 5. For each result, show the page title and ID. Then pick the first result and call notion.read_page with that page_id to read its properties."

  # Iteration 2: Slack — list channels, read history, post update
  "You have access to tools via the deepsecure MCP server. Call slack.list_channels with limit 10 and types 'public_channel'. Pick the first channel and call slack.get_channel_history with that channel ID and limit 5 to read the last 5 messages. Then call slack.send_message to post '[DeepSecure Agent] Daily sync complete' to that channel."

  # Iteration 3: Gmail — search recent emails
  "You have access to tools via the deepsecure MCP server. Call gmail.search_messages with query 'is:unread' and limit 5. List the sender and subject of each email found."

  # Iteration 4: Google Drive — search recent files
  "You have access to tools via the deepsecure MCP server. Call gdrive.search_files with query 'quarterly report' and limit 5. List the file name, type, and last modified date for each result."

  # Iteration 5: Google Calendar — list today's events
  "You have access to tools via the deepsecure MCP server. Call gcalendar.list_events with calendar_id 'primary' and limit 5. Summarize each event: title, start time, and attendees."

  # Iteration 6: Cross-service summary
  "You have access to tools via the deepsecure MCP server. First call slack.list_channels (limit 3), then call notion.search_pages with query 'meeting notes' (limit 3), then call gmail.search_messages with query 'action items' (limit 3). Write a brief summary of what you found across all three services."
)

# === Bootstrap Function ===
bootstrap() {
  # If AGENT_JWT is pre-set (local testing), skip OIDC bootstrap
  if [ -n "${AGENT_JWT:-}" ]; then
    echo "[$(date -Iseconds)] Using pre-set AGENT_JWT (local/test mode)"
    return 0
  fi

  echo "[$(date -Iseconds)] Bootstrapping agent ${AGENT_ID}..."

  # Get OIDC token from GCP Metadata Server
  OIDC_TOKEN=$(curl -sf \
    -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${CONTROL_URL}" \
  ) || {
    echo "ERROR: Failed to get OIDC token from metadata server"
    exit 1
  }

  # Exchange OIDC token for Agent JWT via DeepSecure bootstrap
  BOOTSTRAP_RESPONSE=$(curl -sf \
    -X POST "${CONTROL_URL}/api/v1/auth/bootstrap/gcp" \
    -H "Content-Type: application/json" \
    -d "{\"identity_token\": \"${OIDC_TOKEN}\"}" \
  ) || {
    echo "ERROR: Bootstrap failed"
    exit 1
  }

  AGENT_JWT=$(echo "${BOOTSTRAP_RESPONSE}" | jq -r '.access_token')
  if [ -z "${AGENT_JWT}" ] || [ "${AGENT_JWT}" = "null" ]; then
    echo "ERROR: No access_token in bootstrap response"
    echo "Response: ${BOOTSTRAP_RESPONSE}"
    exit 1
  fi

  echo "[$(date -Iseconds)] Bootstrap successful. JWT obtained."
}

# === Configure Gemini CLI MCP ===
configure_gemini() {
  mkdir -p ~/.gemini
  # Use gemini mcp add (official CLI) to register the server
  gemini mcp add deepsecure "${GATEWAY_URL}" \
    --type http \
    --scope user \
    --trust \
    --timeout 30000 \
    -H "Authorization: Bearer ${AGENT_JWT}" \
    2>&1 || true
  echo "[$(date -Iseconds)] Gemini CLI configured with MCP server → ${GATEWAY_URL}"
}

# === Main Loop ===
echo "========================================="
echo " DeepSecure Gemini Agent"
echo " Agent ID: ${AGENT_ID}"
echo " Iterations: ${MAX_ITERATIONS}"
echo " Interval: ${INTERVAL}s"
echo "========================================="

bootstrap
configure_gemini

# Warm up the gateway to avoid cold-start timeout in Gemini CLI's MCP client
echo "[$(date -Iseconds)] Warming up gateway..."
curl -sf -o /dev/null -X POST "${GATEWAY_URL}" \
  -H "Authorization: Bearer ${AGENT_JWT}" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":0,"params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"warmup","version":"1.0.0"}}}' || true
echo "[$(date -Iseconds)] Gateway warm."

for ((i=1; i<=MAX_ITERATIONS; i++)); do
  echo ""
  echo "[$(date -Iseconds)] === Iteration ${i}/${MAX_ITERATIONS} ==="

  # Re-bootstrap periodically to refresh JWT before expiry
  if (( i > 1 && i % BOOTSTRAP_REFRESH_INTERVAL == 0 )); then
    echo "[$(date -Iseconds)] Refreshing JWT (every ${BOOTSTRAP_REFRESH_INTERVAL} iterations)..."
    bootstrap
    configure_gemini
  fi

  # Select prompt (cycle through array)
  PROMPT_INDEX=$(( (i - 1) % ${#PROMPTS[@]} ))
  PROMPT="${PROMPTS[$PROMPT_INDEX]}"
  echo "[$(date -Iseconds)] Running prompt ${PROMPT_INDEX}: ${PROMPT:0:80}..."

  # Execute Gemini CLI with the prompt
  gemini -y --sandbox=false --allowed-mcp-server-names deepsecure -p "${PROMPT}" 2>&1 || {
    echo "[$(date -Iseconds)] WARNING: gemini CLI returned non-zero (may be tool error, continuing)"
  }

  # Sleep between iterations (skip after last)
  if (( i < MAX_ITERATIONS )); then
    echo "[$(date -Iseconds)] Sleeping ${INTERVAL}s..."
    sleep "${INTERVAL}"
  fi
done

echo ""
echo "[$(date -Iseconds)] === Agent completed ${MAX_ITERATIONS} iterations. Exiting cleanly. ==="
