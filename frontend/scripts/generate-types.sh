#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/.."
OUTPUT_DIR="$FRONTEND_DIR/src/lib/api/generated"
OUTPUT_FILE="$OUTPUT_DIR/schema.d.ts"
OPENAPI_URL="${OPENAPI_URL:-http://localhost:8000/openapi.json}"

mkdir -p "$OUTPUT_DIR"

echo "🔄 Fetching OpenAPI spec from $OPENAPI_URL..."

if ! curl -sf "$OPENAPI_URL" > /dev/null 2>&1; then
  echo "❌ Cannot reach $OPENAPI_URL"
  echo "   Is the control plane running? Try: docker compose up deeptrail-control -d"
  exit 1
fi

echo "📝 Generating TypeScript types..."
npx openapi-typescript "$OPENAPI_URL" -o "$OUTPUT_FILE"

echo "✅ Types generated at $OUTPUT_FILE"
echo "   $(wc -l < "$OUTPUT_FILE") lines"
