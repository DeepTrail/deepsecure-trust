#!/usr/bin/env bash
# Create 90-day delegations for all three agents.
# Usage: USER_TOKEN=<admin-jwt> CONTROL_URL=<url> ./scripts/create_agent_delegations.sh
set -euo pipefail

CONTROL_URL="${CONTROL_URL:-https://app.deepsecure.one}"
: "${USER_TOKEN:?Set USER_TOKEN to an admin JWT}"

SLACK_NOTION_PERMS='["slack:channels:history","slack:channels:list","slack:messages:search","slack:messages:send","slack:users:search","notion:blocks:read","notion:databases:list","notion:databases:query","notion:pages:create","notion:pages:read","notion:pages:search","notion:pages:update"]'

echo "=== Creating 90-day delegation for Thunderbolt Agent ==="
curl -sf -X POST "${CONTROL_URL}/api/v1/admin/delegations" \
  -H "Authorization: Bearer ${USER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"agent-abf9bbd8-c71a-4be7-9e19-d8124e88f830\",
    \"delegator\": \"mahendra@deeptrail.com\",
    \"delegated_permissions\": ${SLACK_NOTION_PERMS},
    \"constraints\": {\"expires_in_hours\": 2160}
  }" | jq .

echo ""
echo "=== Creating 90-day delegation for Engineering Audit Agent ==="
curl -sf -X POST "${CONTROL_URL}/api/v1/admin/delegations" \
  -H "Authorization: Bearer ${USER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"agent-705248dc-7419-4195-b598-a10e346cba7f\",
    \"delegator\": \"mahendra@deeptrail.com\",
    \"delegated_permissions\": ${SLACK_NOTION_PERMS},
    \"constraints\": {\"expires_in_hours\": 2160}
  }" | jq .

echo ""
echo "=== Creating 90-day Notion+Slack delegation for Debugging Agent ==="
curl -sf -X POST "${CONTROL_URL}/api/v1/admin/delegations" \
  -H "Authorization: Bearer ${USER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"agent-494fb073-310b-4410-bf63-211755cf9b12\",
    \"delegator\": \"mahendra@deeptrail.com\",
    \"delegated_permissions\": ${SLACK_NOTION_PERMS},
    \"constraints\": {\"expires_in_hours\": 2160}
  }" | jq .

echo ""
echo "=== Done. Verify with: ==="
echo "curl -s ${CONTROL_URL}/api/v1/admin/delegations -H 'Authorization: Bearer \${USER_TOKEN}' | jq '.delegations[] | {agent_id, status, expires_at}'"
