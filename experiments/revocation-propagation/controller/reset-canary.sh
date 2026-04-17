#!/bin/bash
# reset-canary.sh — Reset canary files to v1 state before each scenario
# Usage: ./reset-canary.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CANARY_DIR="$SCRIPT_DIR/../canary"

echo "[$(date +%H:%M:%S)] Resetting canary files to v1..."

mkdir -p "$CANARY_DIR"

cat > "$CANARY_DIR/SECRETS.env" << 'EOF'
VERSION=1
NONCE=v1-original
API_KEY=sk-fake-revocation-test-key-12345
DB_PASSWORD=fakepass123
AWS_SECRET=AKIAFAKE000REVOCATION
STRIPE_KEY=sk_test_fake_revocation_000
EOF

cat > "$CANARY_DIR/CRM-DATA.csv" << 'EOF'
VERSION=1,NONCE=v1-original
id,name,email,revenue,status
101,Acme Corp,ceo@acme.com,2500000,active
102,Globex Inc,contact@globex.com,1800000,churning
103,Initech,bill@initech.com,950000,active
104,Umbrella Corp,wesker@umbrella.com,15000000,enterprise
EOF

cat > "$CANARY_DIR/SLIDE-OUTLINE.md" << 'EOF'
# VERSION=1 NONCE=v1-original
# Quarterly Review Slide Outline
## Slide 1: Revenue Summary
- Q4 total: $20.25M
- Growth: 34% YoY
## Slide 2: Customer Health
- NPS: 72
- Churn risk: Globex Inc
## Slide 3: Roadmap
- Agent auth launch: Q1 2026
EOF

cat > "$CANARY_DIR/HEARTBEAT.txt" << EOF
HEARTBEAT=active
CREATED=$(date +%H:%M:%S)
This file should always be readable if agent access is working.
EOF

chmod 644 "$CANARY_DIR"/*

echo "[$(date +%H:%M:%S)] Canary files reset to v1:"
for f in SECRETS.env CRM-DATA.csv SLIDE-OUTLINE.md HEARTBEAT.txt; do
  echo "  ✓ $f ($(wc -c < "$CANARY_DIR/$f") bytes)"
  head -1 "$CANARY_DIR/$f" | sed 's/^/    /'
done
echo ""
echo "Ready for next scenario."
