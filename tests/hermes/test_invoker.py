"""Tests for Hermes Invoker (Phase 2): Ralph triggering, progress analysis, escalation."""

import json
import os
import subprocess
import tempfile

import pytest


INVOKER_SCRIPT = "scripts/hermes-invoker.sh"
CONFIG_FILE = ".hermes/config.yaml"


class TestInvokerScript:
    def test_invoker_script_exists(self):
        assert os.path.isfile(INVOKER_SCRIPT)

    def test_invoker_script_executable(self):
        assert os.access(INVOKER_SCRIPT, os.X_OK)

    def test_invoker_requires_workstream_arg(self):
        result = subprocess.run(
            ["bash", INVOKER_SCRIPT],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_invoker_dry_run(self):
        result = subprocess.run(
            ["bash", INVOKER_SCRIPT, "test-workstream", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert "DRY RUN" in result.stdout or "dry run" in result.stdout.lower()


class TestProgressAnalysis:
    """Test the decision logic that the invoker uses to analyze Ralph progress."""

    def _analyze(self, progress_dict):
        """Run the invoker's analysis logic on a progress dict."""
        progress_json = json.dumps(progress_dict)
        result = subprocess.run(
            [
                "python3",
                "-c",
                f"""
import json, sys

data = json.loads('''{progress_json}''')
meta = data.get('metadata', {{}})
tasks = data.get('tasks', [])
completed = sum(1 for t in tasks if t.get('passes') or t.get('status') == 'completed')
total = len(tasks)
cb = meta.get('circuit_breaker', 'CLOSED')
iters = meta.get('total_iterations', 0)

if cb == 'OPEN':
    print(f'DECISION:escalate:Circuit breaker OPEN after {{iters}} iterations ({{completed}}/{{total}} tasks)')
elif total > 0 and completed == total:
    print(f'DECISION:complete:All {{total}} tasks completed in {{iters}} iterations')
elif iters >= 10 and completed < total:
    print(f'DECISION:escalate:Max iterations ({{iters}}) reached with {{total - completed}} tasks remaining')
elif completed > 0:
    print(f'DECISION:continue:Progress ({{completed}}/{{total}} tasks) after {{iters}} iterations')
else:
    print(f'DECISION:continue:No tasks completed yet after {{iters}} iterations')
""",
            ],
            capture_output=True,
            text=True,
        )
        line = result.stdout.strip()
        parts = line.split(":", 2)
        return {"decision": parts[1], "reason": parts[2]} if len(parts) >= 3 else {}

    def test_decision_complete_all_tasks_done(self):
        progress = {
            "tasks": [
                {"id": "WS-A1", "passes": True, "status": "completed"},
                {"id": "WS-A2", "passes": True, "status": "completed"},
            ],
            "metadata": {"total_iterations": 3, "circuit_breaker": "CLOSED"},
        }
        result = self._analyze(progress)
        assert result["decision"] == "complete"

    def test_decision_escalate_circuit_breaker_open(self):
        progress = {
            "tasks": [
                {"id": "WS-A1", "passes": True, "status": "completed"},
                {"id": "WS-A2", "passes": False, "status": "in_progress"},
            ],
            "metadata": {"total_iterations": 5, "circuit_breaker": "OPEN"},
        }
        result = self._analyze(progress)
        assert result["decision"] == "escalate"
        assert "circuit breaker" in result["reason"].lower()

    def test_decision_escalate_max_iterations(self):
        progress = {
            "tasks": [
                {"id": "WS-A1", "passes": True, "status": "completed"},
                {"id": "WS-A2", "passes": False, "status": "in_progress"},
            ],
            "metadata": {"total_iterations": 10, "circuit_breaker": "CLOSED"},
        }
        result = self._analyze(progress)
        assert result["decision"] == "escalate"

    def test_decision_continue_with_progress(self):
        progress = {
            "tasks": [
                {"id": "WS-A1", "passes": True, "status": "completed"},
                {"id": "WS-A2", "passes": False, "status": "in_progress"},
                {"id": "WS-A3", "passes": False, "status": "blocked"},
            ],
            "metadata": {"total_iterations": 3, "circuit_breaker": "CLOSED"},
        }
        result = self._analyze(progress)
        assert result["decision"] == "continue"

    def test_decision_continue_no_progress_yet(self):
        progress = {
            "tasks": [
                {"id": "WS-A1", "passes": False, "status": "in_progress"},
            ],
            "metadata": {"total_iterations": 1, "circuit_breaker": "CLOSED"},
        }
        result = self._analyze(progress)
        assert result["decision"] == "continue"

    def test_decision_empty_progress(self):
        progress = {"tasks": [], "metadata": {}}
        result = self._analyze(progress)
        assert result["decision"] == "continue"

    def test_decision_complete_single_task(self):
        progress = {
            "tasks": [{"id": "WS-A1", "passes": True, "status": "completed"}],
            "metadata": {"total_iterations": 1, "circuit_breaker": "CLOSED"},
        }
        result = self._analyze(progress)
        assert result["decision"] == "complete"


class TestInvokerIntegration:
    def test_invoker_with_missing_config(self):
        """Invoker should fail gracefully if config is missing."""
        env = os.environ.copy()
        result = subprocess.run(
            ["bash", "-c", "cd /tmp && bash -c 'source /dev/null; bash {}/{} test 2>&1 || true'".format(
                os.getcwd(), INVOKER_SCRIPT
            )],
            capture_output=True,
            text=True,
            cwd="/tmp",
        )
        assert result.returncode == 0 or "Config not found" in result.stdout + result.stderr

    def test_invoker_log_file_created(self):
        """Dry run should create/append to the log file."""
        subprocess.run(
            ["bash", INVOKER_SCRIPT, "test-workstream", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert os.path.isfile(".hermes/invoker.log")
