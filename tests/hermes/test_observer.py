"""Tests for Hermes Observer (Phase 1): scheduling, notifications, memory."""

import json
import os
import sqlite3
import subprocess
import tempfile

import pytest
import yaml


OBSERVER_SCRIPT = "scripts/hermes-observer.sh"
SETUP_SCRIPT = "scripts/hermes-setup.sh"
CONFIG_FILE = ".hermes/config.yaml"
SCHEDULE_FILE = ".hermes/skills/afk-schedule.yaml"
REVIEW_FILE = ".hermes/skills/cross-session-review.yaml"


class TestHermesSetup:
    def test_setup_script_exists(self):
        assert os.path.isfile(SETUP_SCRIPT)

    def test_setup_script_executable(self):
        assert os.access(SETUP_SCRIPT, os.X_OK)

    def test_setup_verify_mode(self):
        result = subprocess.run(
            ["bash", SETUP_SCRIPT, "--verify"],
            capture_output=True,
            text=True,
        )
        assert "config.yaml" in result.stdout

    def test_setup_help(self):
        result = subprocess.run(
            ["bash", SETUP_SCRIPT, "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Usage" in result.stdout


class TestHermesConfig:
    def test_config_file_exists(self):
        assert os.path.isfile(CONFIG_FILE)

    def test_config_valid_yaml(self):
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)
        assert config is not None
        assert "agent" in config
        assert "memory" in config
        assert "delegation" in config

    def test_config_agent_section(self):
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)
        agent = config["agent"]
        assert agent["name"] == "deepsecure-hermes"
        assert "version" in agent

    def test_config_memory_backend(self):
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)
        memory = config["memory"]
        assert memory["backend"] == "sqlite"
        assert memory["search"] == "fts5"

    def test_config_delegation_primary(self):
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)
        delegation = config["delegation"]
        assert delegation["primary"] == "claude-code"
        assert len(delegation["models"]) >= 1
        assert delegation["models"][0]["name"] == "claude"

    def test_config_notifications(self):
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)
        channels = config["notifications"]["channels"]
        channel_types = [c["type"] for c in channels]
        assert "slack" in channel_types
        assert "telegram" in channel_types


class TestObserverScript:
    def test_observer_script_exists(self):
        assert os.path.isfile(OBSERVER_SCRIPT)

    def test_observer_script_executable(self):
        assert os.access(OBSERVER_SCRIPT, os.X_OK)

    def test_observer_status_when_not_running(self):
        result = subprocess.run(
            ["bash", OBSERVER_SCRIPT, "status"],
            capture_output=True,
            text=True,
        )
        assert "not running" in result.stdout.lower() or "running" in result.stdout.lower()

    def test_observer_run_once(self):
        result = subprocess.run(
            ["bash", OBSERVER_SCRIPT, "run-once"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert "Schedule Check" in result.stdout or "Cross-Session Review" in result.stdout

    def test_observer_invalid_action(self):
        result = subprocess.run(
            ["bash", OBSERVER_SCRIPT, "invalid-action"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "Usage" in result.stdout or "Usage" in result.stderr


class TestScheduleConfig:
    def test_schedule_file_exists(self):
        assert os.path.isfile(SCHEDULE_FILE)

    def test_schedule_valid_yaml(self):
        with open(SCHEDULE_FILE) as f:
            config = yaml.safe_load(f)
        assert config is not None
        assert "schedules" in config

    def test_schedule_entries_have_required_fields(self):
        with open(SCHEDULE_FILE) as f:
            config = yaml.safe_load(f)
        for sched in config["schedules"]:
            assert "name" in sched
            assert "hour" in sched
            assert "days" in sched
            assert "enabled" in sched

    def test_schedule_entries_disabled_by_default(self):
        with open(SCHEDULE_FILE) as f:
            config = yaml.safe_load(f)
        for sched in config["schedules"]:
            assert sched["enabled"] is False, (
                f"Schedule '{sched['name']}' should be disabled by default"
            )


class TestCrossSessionReview:
    def test_review_file_exists(self):
        assert os.path.isfile(REVIEW_FILE)

    def test_review_valid_yaml(self):
        with open(REVIEW_FILE) as f:
            config = yaml.safe_load(f)
        assert config is not None
        assert "review" in config

    def test_review_has_sources(self):
        with open(REVIEW_FILE) as f:
            config = yaml.safe_load(f)
        sources = config["review"]["sources"]
        assert len(sources) >= 2
        source_types = [s["type"] for s in sources]
        assert "ralph_progress" in source_types
        assert "cost_log" in source_types

    def test_review_checks_have_required_fields(self):
        with open(REVIEW_FILE) as f:
            config = yaml.safe_load(f)
        for source in config["review"]["sources"]:
            for check in source.get("checks", []):
                assert "name" in check
                assert "severity" in check
                assert "action" in check


class TestMemoryStore:
    def test_sqlite_memory_creation(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                """CREATE TABLE IF NOT EXISTS learnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            conn.execute(
                "INSERT INTO learnings (session_id, content) VALUES (?, ?)",
                ("test-session", "Test learning content"),
            )
            conn.commit()

            count = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
            assert count == 1

            row = conn.execute(
                "SELECT session_id, content FROM learnings"
            ).fetchone()
            assert row[0] == "test-session"
            assert row[1] == "Test learning content"
            conn.close()
        finally:
            os.unlink(db_path)

    def test_sqlite_fts5_search(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                """CREATE VIRTUAL TABLE IF NOT EXISTS learnings_fts
                    USING fts5(session_id, content)"""
            )
            conn.execute(
                "INSERT INTO learnings_fts (session_id, content) VALUES (?, ?)",
                ("session-1", "Circuit breaker opened for mvp-foundation"),
            )
            conn.execute(
                "INSERT INTO learnings_fts (session_id, content) VALUES (?, ?)",
                ("session-2", "All tests passing after fix"),
            )
            conn.commit()

            results = conn.execute(
                "SELECT * FROM learnings_fts WHERE learnings_fts MATCH 'circuit breaker'"
            ).fetchall()
            assert len(results) == 1
            assert "circuit" in results[0][1].lower()
            conn.close()
        finally:
            os.unlink(db_path)
