#!/bin/bash
# kill-monitor.sh — Monitor sub-agent transcript growth, attempt process termination
# Usage: ./kill-monitor.sh <transcript1> <transcript2> <transcript3> [kill_delay]

set -euo pipefail

T1="$1"
T2="$2"
T3="$3"
KILL_DELAY=${4:-60}

RESULTS_DIR="$(cd "$(dirname "$0")/../results" && pwd)"
LOG="$RESULTS_DIR/scenario-A-monitor.log"

echo "═══════════════════════════════════════════════════" | tee "$LOG"
echo "  PARENT TERMINATION MONITOR" | tee -a "$LOG"
echo "  Started: $(date +%H:%M:%S)" | tee -a "$LOG"
echo "  Monitoring 3 transcripts" | tee -a "$LOG"
echo "  Kill attempt after: ${KILL_DELAY}s" | tee -a "$LOG"
echo "═══════════════════════════════════════════════════" | tee -a "$LOG"

count_lines() {
    wc -l < "$1" 2>/dev/null | tr -d ' '
}

check_agents() {
    local label="$1"
    local t1_lines=$(count_lines "$T1")
    local t2_lines=$(count_lines "$T2")
    local t3_lines=$(count_lines "$T3")
    echo "[$(date +%H:%M:%S)] $label — Alpha: ${t1_lines}L, Beta: ${t2_lines}L, Gamma: ${t3_lines}L" | tee -a "$LOG"
}

check_agents "BASELINE"

echo "" | tee -a "$LOG"
echo "[$(date +%H:%M:%S)] Phase 1: Monitoring growth for ${KILL_DELAY}s before kill attempt..." | tee -a "$LOG"

for ((i=0; i<KILL_DELAY; i+=15)); do
    sleep 15
    check_agents "PRE-KILL +${i}s"
done

echo "" | tee -a "$LOG"
echo "═══════════════════════════════════════════════════" | tee -a "$LOG"
echo "  KILL ATTEMPT at $(date +%H:%M:%S)" | tee -a "$LOG"
echo "═══════════════════════════════════════════════════" | tee -a "$LOG"

check_agents "AT KILL TIME"

echo "" | tee -a "$LOG"
echo "[$(date +%H:%M:%S)] Attempting to find and kill agent shell processes..." | tee -a "$LOG"

TERMINALS_DIR="$HOME/.cursor/projects/Users-imaxxs-repositories-deepsecure-mvp/terminals"
KILLED_PIDS=""

for tfile in "$TERMINALS_DIR"/*.txt; do
    PID=$(head -5 "$tfile" 2>/dev/null | grep "^pid:" | awk '{print $2}' || true)
    CMD=$(head -5 "$tfile" 2>/dev/null | grep "^command:" | head -1 || true)
    
    if [[ -n "$PID" ]] && echo "$CMD" | grep -q "sleep 30"; then
        echo "[$(date +%H:%M:%S)] Found agent sleep process: PID=$PID" | tee -a "$LOG"
        if kill -0 "$PID" 2>/dev/null; then
            echo "[$(date +%H:%M:%S)] Killing PID $PID..." | tee -a "$LOG"
            kill "$PID" 2>/dev/null && KILLED_PIDS="$KILLED_PIDS $PID" || true
        else
            echo "[$(date +%H:%M:%S)] PID $PID not running (already completed)" | tee -a "$LOG"
        fi
    fi
done

if [[ -z "$KILLED_PIDS" ]]; then
    echo "[$(date +%H:%M:%S)] No killable agent processes found. Sub-agents may use internal scheduling." | tee -a "$LOG"
else
    echo "[$(date +%H:%M:%S)] Killed PIDs:$KILLED_PIDS" | tee -a "$LOG"
fi

echo "" | tee -a "$LOG"
echo "[$(date +%H:%M:%S)] Phase 2: Monitoring growth for 150s after kill attempt..." | tee -a "$LOG"

for ((i=0; i<150; i+=15)); do
    sleep 15
    check_agents "POST-KILL +${i}s"
done

echo "" | tee -a "$LOG"
echo "═══════════════════════════════════════════════════" | tee -a "$LOG"
echo "  MONITORING COMPLETE at $(date +%H:%M:%S)" | tee -a "$LOG"
echo "═══════════════════════════════════════════════════" | tee -a "$LOG"

check_agents "FINAL"

echo "" | tee -a "$LOG"
echo "Results saved to: $LOG" | tee -a "$LOG"
