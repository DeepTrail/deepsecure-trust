#!/usr/bin/env bash
# hermes-observer.sh — Phase 1: Hermes Observer daemon
# Usage: hermes-observer.sh <start|stop|status|run-once>
#
# Observer role: scheduling AFK jobs, sending notifications, storing
# cross-session learnings. No code authority — Claude Code does all coding.
set -euo pipefail

CONFIG_FILE=".hermes/config.yaml"
PID_FILE=".hermes/observer.pid"
LOG_FILE=".hermes/observer.log"
POLL_INTERVAL=300

ACTION=${1:-status}

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Config not found: $CONFIG_FILE"
    echo "Run: scripts/hermes-setup.sh"
    exit 1
fi

log() {
    local msg="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

check_hermes() {
    if ! command -v hermes >/dev/null 2>&1; then
        echo "❌ Hermes not installed. Run: scripts/hermes-setup.sh"
        exit 1
    fi
}

is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

notify() {
    local title="$1"
    local message="$2"
    local level="${3:-info}"
    scripts/notify.sh "$title" "$message" "$level" 2>/dev/null || true
}

check_schedules() {
    local schedule_file=".hermes/skills/afk-schedule.yaml"
    if [ ! -f "$schedule_file" ]; then
        log "No schedule file found: $schedule_file"
        return 0
    fi

    local now_hour
    now_hour=$(date +%H)
    local now_day
    now_day=$(date +%u)

    log "Checking schedules (hour=$now_hour, day=$now_day)"

    # Parse schedule entries and check if any are due
    python3 -c "
import yaml, sys, os
from datetime import datetime

try:
    with open('$schedule_file') as f:
        config = yaml.safe_load(f)
except Exception as e:
    print(f'Schedule parse error: {e}', file=sys.stderr)
    sys.exit(0)

if not config or 'schedules' not in config:
    sys.exit(0)

now = datetime.now()
for sched in config.get('schedules', []):
    name = sched.get('name', 'unnamed')
    hour = sched.get('hour')
    days = sched.get('days', [1,2,3,4,5])
    enabled = sched.get('enabled', True)

    if not enabled:
        continue

    if now.isoweekday() in days and hour is not None and now.hour == hour:
        workstream = sched.get('workstream', '')
        print(f'DUE:{name}:{workstream}')
" 2>/dev/null || true
}

store_learning() {
    local learning="$1"
    local session_id="${2:-$(date +%Y%m%d_%H%M%S)}"

    python3 -c "
import sqlite3, os

db_path = '.hermes/memory.db'
conn = sqlite3.connect(db_path)
conn.execute('''CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

# Create FTS5 virtual table if not exists
try:
    conn.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS learnings_fts
        USING fts5(content, content=learnings, content_rowid=id)''')
except Exception:
    pass

conn.execute('INSERT INTO learnings (session_id, content) VALUES (?, ?)',
             ('$session_id', '''$learning'''))
conn.commit()
conn.close()
" 2>/dev/null || log "⚠️  Failed to store learning"
}

review_sessions() {
    local review_file=".hermes/skills/cross-session-review.yaml"
    if [ ! -f "$review_file" ]; then
        return 0
    fi

    log "Running cross-session review"

    # Check for recurring patterns in recent Ralph progress files
    python3 -c "
import json, glob, os
from collections import Counter

progress_files = glob.glob('docs/workstreams/*/ralph_progress.json')
patterns = Counter()

for pf in progress_files:
    try:
        with open(pf) as f:
            data = json.load(f)
        meta = data.get('metadata', {})
        if meta.get('circuit_breaker') == 'OPEN':
            ws = data.get('workstream', 'unknown')
            patterns[f'circuit_breaker_open:{ws}'] += 1
        iters = meta.get('total_iterations', 0)
        if iters >= 8:
            patterns[f'high_iteration_count:{ws}'] += 1
    except (json.JSONDecodeError, KeyError):
        continue

if patterns:
    print('Cross-session patterns detected:')
    for pattern, count in patterns.most_common(5):
        print(f'  {pattern}: {count} occurrences')
else:
    print('No concerning patterns detected')
" 2>/dev/null || log "⚠️  Cross-session review failed"
}

observer_loop() {
    log "Observer started (PID $$, interval ${POLL_INTERVAL}s)"
    echo $$ > "$PID_FILE"
    notify "Hermes Observer" "Observer started (PID $$)" info

    trap 'log "Observer stopping"; rm -f "$PID_FILE"; notify "Hermes Observer" "Observer stopped" info; exit 0' SIGTERM SIGINT

    while true; do
        # Check schedules
        DUE=$(check_schedules)
        if [ -n "$DUE" ]; then
            while IFS= read -r line; do
                if [[ "$line" == DUE:* ]]; then
                    local name workstream
                    name=$(echo "$line" | cut -d: -f2)
                    workstream=$(echo "$line" | cut -d: -f3)
                    log "Schedule due: $name (workstream: $workstream)"
                    notify "AFK Schedule" "Job due: $name ($workstream)" info
                fi
            done <<< "$DUE"
        fi

        # Cross-session review
        review_sessions

        sleep "$POLL_INTERVAL"
    done
}

run_once() {
    log "Observer single run"

    echo "--- Schedule Check ---"
    check_schedules

    echo ""
    echo "--- Cross-Session Review ---"
    review_sessions

    echo ""
    echo "--- Memory Stats ---"
    if [ -f ".hermes/memory.db" ]; then
        python3 -c "
import sqlite3
conn = sqlite3.connect('.hermes/memory.db')
try:
    count = conn.execute('SELECT COUNT(*) FROM learnings').fetchone()[0]
    print(f'Learnings stored: {count}')
except Exception:
    print('Learnings table: not initialized')
conn.close()
" 2>/dev/null || echo "Memory DB: not accessible"
    else
        echo "Memory DB: not created yet"
    fi
}

case "$ACTION" in
    start)
        check_hermes
        if is_running; then
            echo "Observer already running (PID $(cat "$PID_FILE"))"
            exit 0
        fi
        observer_loop &
        disown
        echo "✅ Observer started in background (PID $!)"
        echo "$!" > "$PID_FILE"
        ;;
    stop)
        if is_running; then
            local pid
            pid=$(cat "$PID_FILE")
            kill "$pid" 2>/dev/null || true
            rm -f "$PID_FILE"
            echo "✅ Observer stopped (PID $pid)"
        else
            echo "Observer not running"
        fi
        ;;
    status)
        if is_running; then
            echo "✅ Observer running (PID $(cat "$PID_FILE"))"
            if [ -f "$LOG_FILE" ]; then
                echo ""
                echo "--- Recent logs ---"
                tail -5 "$LOG_FILE"
            fi
        else
            echo "❌ Observer not running"
            echo "Start with: scripts/hermes-observer.sh start"
        fi
        ;;
    run-once)
        run_once
        ;;
    *)
        echo "Usage: hermes-observer.sh <start|stop|status|run-once>"
        exit 1
        ;;
esac
