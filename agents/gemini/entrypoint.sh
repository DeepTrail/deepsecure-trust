#!/usr/bin/env bash
set -euo pipefail

# === Configuration ===
CONTROL_URL="${DEEPSECURE_CONTROL_URL:-https://app.deepsecure.one}"
GATEWAY_URL="${DEEPSECURE_GATEWAY_URL:-https://app.deepsecure.one/mcp}"
AGENT_ID="${AGENT_ID:-debugging-deepsecure-agent}"
MAX_ROUNDS="${AGENT_MAX_ROUNDS:-3}"
PROMPTS_PER_DELEGATION="${AGENT_PROMPTS_PER_DELEGATION:-2}"
INTERVAL="${AGENT_INTERVAL_SECONDS:-300}"

# === Prompt Library ===
# Each prompt is tagged with the service(s) it requires.
# Format: "service1,service2|prompt text"
TAGGED_PROMPTS=(
  "notion|You have access to tools via the deepsecure MCP server. Call notion.search_pages with query 'strategy' and limit 5. For each result, show the page title and ID. Then pick the first result and call notion.read_page with that page_id to read its properties."
  "slack|You have access to tools via the deepsecure MCP server. Call slack.list_channels with limit 10 and types 'public_channel'. Pick the first channel and call slack.get_channel_history with that channel ID and limit 5 to read the last 5 messages. Then call slack.send_message to post '[DeepSecure Agent] Daily sync complete' to that channel."
  "gmail|You have access to tools via the deepsecure MCP server. Call gmail.search_messages with query 'is:unread' and limit 5. List the sender and subject of each email found."
  "gdrive|You have access to tools via the deepsecure MCP server. Call gdrive.search_files with query 'quarterly report' and limit 5. List the file name, type, and last modified date for each result."
  "gcalendar|You have access to tools via the deepsecure MCP server. Call gcalendar.list_events with calendar_id 'primary' and limit 5. Summarize each event: title, start time, and attendees."
  "slack,notion,gmail|You have access to tools via the deepsecure MCP server. First call slack.list_channels (limit 3), then call notion.search_pages with query 'meeting notes' (limit 3), then call gmail.search_messages with query 'action items' (limit 3). Write a brief summary of what you found across all three services."
  "exa|You have access to tools via the deepsecure MCP server. IMPORTANT: Tool names use dot notation like 'backend.tool_name'. For Exa tools, the names are exactly 'exa.web_search_exa' and 'exa.web_fetch_exa' (dot-separated, not colon or slash). Call the tool named exa.web_search_exa with query 'DeepSecure AI agent security platform' and numResults 3. Show the title and URL of each result."
)

# === Bootstrap Function (Phase 1: OIDC → Discovery JWT) ===
bootstrap() {
  if [ -n "${AGENT_JWT:-}" ]; then
    echo "[$(date -Iseconds)] Using pre-set AGENT_JWT (local/test mode)"
    DISCOVERY_JWT="${AGENT_JWT}"
    DISCOVERY_JWT_ISSUED=$(date +%s)
    return 0
  fi

  echo "[$(date -Iseconds)] Phase 1: OIDC bootstrap for agent ${AGENT_ID}..."

  OIDC_TOKEN=$(curl -sf \
    -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${CONTROL_URL}" \
  ) || {
    echo "ERROR: Failed to get OIDC token from metadata server"
    exit 1
  }

  BOOTSTRAP_RESPONSE=$(curl -sf \
    -X POST "${CONTROL_URL}/api/v1/auth/bootstrap/gcp" \
    -H "Content-Type: application/json" \
    -d "{\"identity_token\": \"${OIDC_TOKEN}\"}" \
  ) || {
    echo "ERROR: Bootstrap failed"
    exit 1
  }

  DISCOVERY_JWT=$(echo "${BOOTSTRAP_RESPONSE}" | jq -r '.access_token')
  if [ -z "${DISCOVERY_JWT}" ] || [ "${DISCOVERY_JWT}" = "null" ]; then
    echo "ERROR: No access_token in bootstrap response"
    echo "Response: ${BOOTSTRAP_RESPONSE}"
    exit 1
  fi

  DISCOVERY_JWT_ISSUED=$(date +%s)
  echo "[$(date -Iseconds)] Phase 1 complete. Discovery JWT obtained."
}

# === Re-bootstrap if discovery JWT is near expiry (1h TTL, refresh at 50min) ===
DISCOVERY_JWT_TTL=3600
DISCOVERY_JWT_REFRESH_MARGIN=600
ensure_discovery_jwt() {
  local now
  now=$(date +%s)
  local age=$(( now - DISCOVERY_JWT_ISSUED ))
  if (( age >= DISCOVERY_JWT_TTL - DISCOVERY_JWT_REFRESH_MARGIN )); then
    echo "[$(date -Iseconds)] Discovery JWT age=${age}s, refreshing (TTL=${DISCOVERY_JWT_TTL}s)..."
    bootstrap
  fi
}

# === Fetch Delegations (Phase 2) ===
fetch_delegations() {
  DELEGATIONS_JSON=$(curl -sf \
    -H "Authorization: Bearer ${DISCOVERY_JWT}" \
    "${CONTROL_URL}/api/v1/auth/agent/delegations" \
  ) || {
    echo "ERROR: Failed to fetch delegations"
    return 1
  }

  DELEGATION_COUNT=$(echo "${DELEGATIONS_JSON}" | jq 'length')
  if [ "${DELEGATION_COUNT}" = "0" ] || [ -z "${DELEGATION_COUNT}" ]; then
    echo "============================================"
    echo " FATAL: No active delegations for agent ${AGENT_ID}"
    echo " The agent cannot operate without delegated permissions."
    echo " Create a delegation via the admin UI or API."
    echo "============================================"
    exit 1
  fi

  echo "[$(date -Iseconds)] Phase 2: Found ${DELEGATION_COUNT} active delegation(s)."
}

# === Get Delegation-Scoped JWT ===
get_delegation_jwt() {
  local delegation_id="$1"
  local delegator="$2"

  DELEGATION_RESPONSE=$(curl -sf \
    -X POST "${CONTROL_URL}/api/v1/auth/agent/delegation-token" \
    -H "Authorization: Bearer ${DISCOVERY_JWT}" \
    -H "Content-Type: application/json" \
    -d "{\"delegation_id\": \"${delegation_id}\"}" \
  ) || {
    echo "[$(date -Iseconds)] WARNING: Failed to get delegation token for ${delegation_id} (${delegator}), skipping"
    return 1
  }

  DELEGATION_JWT=$(echo "${DELEGATION_RESPONSE}" | jq -r '.access_token')
  if [ -z "${DELEGATION_JWT}" ] || [ "${DELEGATION_JWT}" = "null" ]; then
    echo "[$(date -Iseconds)] WARNING: No access_token in delegation-token response for ${delegation_id}"
    return 1
  fi

  echo "[$(date -Iseconds)] Got scoped JWT for delegation ${delegation_id} (owner=${delegator})"
  return 0
}

# === Configure Gemini CLI MCP ===
configure_gemini() {
  local jwt="$1"
  mkdir -p ~/.gemini
  gemini mcp add deepsecure "${GATEWAY_URL}" \
    --type http \
    --scope user \
    --trust \
    --timeout 30000 \
    -H "Authorization: Bearer ${jwt}" \
    2>&1 || true
}

# === Warm Gateway ===
warm_gateway() {
  local jwt="$1"
  curl -sf -o /dev/null -X POST "${GATEWAY_URL}" \
    -H "Authorization: Bearer ${jwt}" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"initialize","id":0,"params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"warmup","version":"1.0.0"}}}' || true
}

# === Select Prompts Matching Delegation Permissions ===
select_prompts() {
  local permissions="$1"
  MATCHING_PROMPTS=()

  for tagged in "${TAGGED_PROMPTS[@]}"; do
    local tags="${tagged%%|*}"
    local prompt="${tagged#*|}"

    local all_match=true
    IFS=',' read -ra required_services <<< "${tags}"
    for svc in "${required_services[@]}"; do
      if ! echo "${permissions}" | grep -q "\"${svc}:"; then
        all_match=false
        break
      fi
    done

    if [ "${all_match}" = true ]; then
      MATCHING_PROMPTS+=("${prompt}")
    fi
  done
}

# === Main ===
echo "========================================="
echo " DeepSecure Gemini Agent (Round-Robin)"
echo " Agent ID: ${AGENT_ID}"
echo " Max Rounds: ${MAX_ROUNDS}"
echo " Prompts/Delegation: ${PROMPTS_PER_DELEGATION}"
echo " Interval: ${INTERVAL}s"
echo "========================================="

bootstrap
fetch_delegations

for ((round=1; round<=MAX_ROUNDS; round++)); do
  echo ""
  echo "[$(date -Iseconds)] ===== Round ${round}/${MAX_ROUNDS} ====="

  DELEGATION_IDS=( $(echo "${DELEGATIONS_JSON}" | jq -r '.[].delegation_id') )
  DELEGATORS=( $(echo "${DELEGATIONS_JSON}" | jq -r '.[].delegator') )
  DELEGATION_EXPIRIES=( $(echo "${DELEGATIONS_JSON}" | jq -r '.[].expires_at') )

  for ((d=0; d<${#DELEGATION_IDS[@]}; d++)); do
    DEL_ID="${DELEGATION_IDS[$d]}"
    DEL_OWNER="${DELEGATORS[$d]}"
    DEL_EXPIRY="${DELEGATION_EXPIRIES[$d]}"

    echo ""
    echo "[$(date -Iseconds)] --- Delegation $((d+1))/${#DELEGATION_IDS[@]}: ${DEL_OWNER} (${DEL_ID}) ---"

    # Client-side expiry check (Layer 4: avoid unnecessary API call)
    if [ -n "${DEL_EXPIRY}" ] && [ "${DEL_EXPIRY}" != "null" ]; then
      EXPIRY_EPOCH=$(date -d "${DEL_EXPIRY}" +%s 2>/dev/null || date -jf "%Y-%m-%dT%H:%M:%S" "${DEL_EXPIRY%%.*}" +%s 2>/dev/null || echo "0")
      NOW_EPOCH=$(date +%s)
      if (( EXPIRY_EPOCH > 0 && NOW_EPOCH >= EXPIRY_EPOCH )); then
        echo "[$(date -Iseconds)] Skipping expired delegation ${DEL_ID} (expired ${DEL_EXPIRY})"
        continue
      fi
    fi

    # Refresh discovery JWT if near expiry before requesting delegation token
    ensure_discovery_jwt

    if ! get_delegation_jwt "${DEL_ID}" "${DEL_OWNER}"; then
      continue
    fi

    configure_gemini "${DELEGATION_JWT}"
    warm_gateway "${DELEGATION_JWT}"

    DEL_PERMISSIONS=$(echo "${DELEGATIONS_JSON}" | jq -c ".[$d].delegated_permissions")
    select_prompts "${DEL_PERMISSIONS}"

    if [ ${#MATCHING_PROMPTS[@]} -eq 0 ]; then
      echo "[$(date -Iseconds)] No matching prompts for permissions: ${DEL_PERMISSIONS}"
      continue
    fi

    echo "[$(date -Iseconds)] ${#MATCHING_PROMPTS[@]} prompts match this delegation's permissions"

    PROMPTS_RUN=0
    for prompt in "${MATCHING_PROMPTS[@]}"; do
      if (( PROMPTS_RUN >= PROMPTS_PER_DELEGATION )); then
        break
      fi

      echo "[$(date -Iseconds)] Running prompt $((PROMPTS_RUN+1)): ${prompt:0:80}..."

      MODEL_FLAG=""
      if [ -n "${GEMINI_MODEL:-}" ]; then
        MODEL_FLAG="--model ${GEMINI_MODEL}"
      fi
      gemini -y --sandbox=false ${MODEL_FLAG} --allowed-mcp-server-names deepsecure -p "${prompt}" 2>&1 || {
        echo "[$(date -Iseconds)] WARNING: gemini CLI returned non-zero (may be tool error, continuing)"
      }

      PROMPTS_RUN=$((PROMPTS_RUN + 1))
    done

    echo "[$(date -Iseconds)] Completed ${PROMPTS_RUN} prompt(s) for ${DEL_OWNER}"
  done

  # Re-fetch delegations to pick up new ones / drop expired
  if (( round < MAX_ROUNDS )); then
    echo ""
    echo "[$(date -Iseconds)] Sleeping ${INTERVAL}s before next round..."
    sleep "${INTERVAL}"

    echo "[$(date -Iseconds)] Re-fetching delegations..."
    ensure_discovery_jwt
    fetch_delegations
  fi
done

echo ""
echo "[$(date -Iseconds)] === Agent completed ${MAX_ROUNDS} rounds. Exiting cleanly. ==="
