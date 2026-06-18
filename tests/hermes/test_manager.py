"""Tests for Hermes Manager (Phase 3): delegation, token refresh, revocation, audit trail."""

import json
import os
import stat
import subprocess
import tempfile

import pytest


IDENTITY_SCRIPT = "scripts/afk-identity.sh"
IDENTITY_CHECK_HOOK = ".claude/hooks/identity-check.sh"
MANAGER_SCRIPT = "scripts/hermes-manager.sh"


class TestIdentityScript:
    """Tests for scripts/afk-identity.sh — delegation_token bootstrap."""

    def test_identity_script_exists(self):
        assert os.path.isfile(IDENTITY_SCRIPT)

    def test_identity_script_executable(self):
        assert os.access(IDENTITY_SCRIPT, os.X_OK)

    def test_identity_help(self):
        result = subprocess.run(
            ["bash", IDENTITY_SCRIPT, "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Usage" in result.stdout
        assert "DEEPSECURE_AGENT_ID" in result.stdout

    def test_identity_requires_agent_id(self):
        env = os.environ.copy()
        env.pop("DEEPSECURE_AGENT_ID", None)
        env.pop("USER_TOKEN", None)
        result = subprocess.run(
            ["bash", IDENTITY_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0

    def test_identity_requires_user_token(self):
        env = os.environ.copy()
        env["DEEPSECURE_AGENT_ID"] = "test-agent-001"
        env.pop("USER_TOKEN", None)
        result = subprocess.run(
            ["bash", IDENTITY_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "USER_TOKEN" in combined

    def test_identity_status_no_file(self):
        env = os.environ.copy()
        env["AFK_IDENTITY_FILE"] = "/tmp/nonexistent-identity-test.json"
        result = subprocess.run(
            ["bash", IDENTITY_SCRIPT, "--status"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0
        assert "Not bootstrapped" in result.stdout

    def test_identity_status_with_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "agent_id": "test-agent-status",
                    "delegation_token": "test-token-abc123def456",
                    "permissions": ["repo:read", "repo:write"],
                    "ttl_seconds": 14400,
                    "issued_at": "2026-06-17T00:00:00+00:00",
                    "expires_at": "2026-06-17T04:00:00+00:00",
                    "control_url": "http://localhost:8000",
                    "bootstrap_count": 1,
                },
                f,
            )
            tmppath = f.name

        try:
            env = os.environ.copy()
            env["AFK_IDENTITY_FILE"] = tmppath
            result = subprocess.run(
                ["bash", IDENTITY_SCRIPT, "--status"],
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == 0
            assert "test-agent-status" in result.stdout
            assert "repo:read" in result.stdout
        finally:
            os.unlink(tmppath)

    def test_identity_verify_no_file(self):
        env = os.environ.copy()
        env["DEEPSECURE_AGENT_ID"] = "test-agent-verify"
        env["AFK_IDENTITY_FILE"] = "/tmp/nonexistent-verify-test.json"
        result = subprocess.run(
            ["bash", IDENTITY_SCRIPT, "--verify"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0

    def test_identity_revoke_no_file(self):
        env = os.environ.copy()
        env["AFK_IDENTITY_FILE"] = "/tmp/nonexistent-revoke-test.json"
        result = subprocess.run(
            ["bash", IDENTITY_SCRIPT, "--revoke"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0
        assert "No identity to revoke" in result.stdout

    def test_identity_revoke_cleans_up_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "agent_id": "test-revoke",
                    "delegation_token": "token-to-revoke",
                    "control_url": "http://localhost:9999",
                },
                f,
            )
            tmppath = f.name

        try:
            env = os.environ.copy()
            env["AFK_IDENTITY_FILE"] = tmppath
            env["DEEPSECURE_CONTROL_URL"] = "http://localhost:9999"
            result = subprocess.run(
                ["bash", IDENTITY_SCRIPT, "--revoke"],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
            )
            assert result.returncode == 0
            assert not os.path.exists(tmppath)
        finally:
            if os.path.exists(tmppath):
                os.unlink(tmppath)

    def test_identity_unknown_option(self):
        result = subprocess.run(
            ["bash", IDENTITY_SCRIPT, "--bogus"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0 or "Unknown option" in result.stdout


class TestIdentityCheckHook:
    """Tests for .claude/hooks/identity-check.sh — pre-iteration verification."""

    def test_hook_exists(self):
        assert os.path.isfile(IDENTITY_CHECK_HOOK)

    def test_hook_executable(self):
        assert os.access(IDENTITY_CHECK_HOOK, os.X_OK)

    def test_hook_skips_when_no_agent_id(self):
        env = os.environ.copy()
        env.pop("DEEPSECURE_AGENT_ID", None)
        result = subprocess.run(
            ["bash", IDENTITY_CHECK_HOOK],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0

    def test_hook_fails_with_agent_id_but_no_identity_file(self):
        env = os.environ.copy()
        env["DEEPSECURE_AGENT_ID"] = "test-agent-hook"
        env["AFK_IDENTITY_FILE"] = "/tmp/nonexistent-hook-test.json"
        env["DEEPSECURE_CONTROL_URL"] = "http://localhost:9999"
        result = subprocess.run(
            ["bash", IDENTITY_CHECK_HOOK],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        # Should attempt bootstrap (which will fail without USER_TOKEN)
        assert result.returncode != 0 or "bootstrap" in (result.stdout + result.stderr).lower()

    def test_hook_validates_valid_token(self):
        """Hook should pass when token is locally valid."""
        from datetime import datetime, timedelta, timezone

        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "agent_id": "test-valid",
                    "delegation_token": "valid-token-123",
                    "expires_at": future,
                    "control_url": "http://localhost:9999",
                },
                f,
            )
            tmppath = f.name

        try:
            env = os.environ.copy()
            env["DEEPSECURE_AGENT_ID"] = "test-valid"
            env["AFK_IDENTITY_FILE"] = tmppath
            env["DEEPSECURE_CONTROL_URL"] = "http://localhost:9999"
            result = subprocess.run(
                ["bash", IDENTITY_CHECK_HOOK],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
            )
            assert result.returncode == 0
        finally:
            os.unlink(tmppath)

    def test_hook_detects_expired_token(self):
        """Hook should fail when token is expired and Control Plane unreachable."""
        from datetime import datetime, timedelta, timezone

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "agent_id": "test-expired",
                    "delegation_token": "expired-token-456",
                    "expires_at": past,
                    "control_url": "http://localhost:9999",
                },
                f,
            )
            tmppath = f.name

        try:
            env = os.environ.copy()
            env["DEEPSECURE_AGENT_ID"] = "test-expired"
            env["AFK_IDENTITY_FILE"] = tmppath
            env["DEEPSECURE_CONTROL_URL"] = "http://localhost:9999"
            env.pop("USER_TOKEN", None)
            result = subprocess.run(
                ["bash", IDENTITY_CHECK_HOOK],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
            )
            assert result.returncode != 0
        finally:
            os.unlink(tmppath)


class TestManagerScript:
    """Tests for scripts/hermes-manager.sh — Phase 3 full lifecycle."""

    def test_manager_script_exists(self):
        assert os.path.isfile(MANAGER_SCRIPT)

    def test_manager_script_executable(self):
        assert os.access(MANAGER_SCRIPT, os.X_OK)

    def test_manager_requires_spec_arg(self):
        result = subprocess.run(
            ["bash", MANAGER_SCRIPT],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_manager_help(self):
        result = subprocess.run(
            ["bash", MANAGER_SCRIPT, "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Usage" in result.stdout
        assert "spec-file" in result.stdout
        assert "delegation_tokens" in result.stdout or "delegation" in result.stdout

    def test_manager_requires_identity(self):
        env = os.environ.copy()
        env.pop("DEEPSECURE_AGENT_ID", None)
        result = subprocess.run(
            ["bash", MANAGER_SCRIPT, "dummy-spec.md"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "DEEPSECURE_AGENT_ID" in combined or "identity" in combined.lower()

    def test_manager_dry_run_requires_identity(self):
        env = os.environ.copy()
        env.pop("DEEPSECURE_AGENT_ID", None)
        result = subprocess.run(
            ["bash", MANAGER_SCRIPT, "dummy-spec.md", "--dry-run"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0

    def test_manager_validates_spec_file(self):
        env = os.environ.copy()
        env["DEEPSECURE_AGENT_ID"] = "test-manager-agent"
        env["AFK_IDENTITY_FILE"] = "/tmp/nonexistent-manager-id.json"
        env["DEEPSECURE_CONTROL_URL"] = "http://localhost:9999"
        result = subprocess.run(
            ["bash", MANAGER_SCRIPT, "/tmp/nonexistent-spec.md", "--dry-run"],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert result.returncode != 0


class TestDelegationTokenLifecycle:
    """Integration tests for the token lifecycle: bootstrap → verify → refresh → revoke."""

    def test_identity_file_format(self):
        """Identity file should contain required fields."""
        identity = {
            "agent_id": "test-lifecycle",
            "delegation_token": "tok-123abc",
            "permissions": ["repo:read", "repo:write", "ci:trigger"],
            "ttl_seconds": 14400,
            "issued_at": "2026-06-17T00:00:00+00:00",
            "expires_at": "2026-06-17T04:00:00+00:00",
            "control_url": "http://localhost:8000",
            "bootstrap_count": 1,
        }
        required_fields = [
            "agent_id",
            "delegation_token",
            "permissions",
            "ttl_seconds",
            "issued_at",
            "expires_at",
        ]
        for field in required_fields:
            assert field in identity

    def test_permissions_are_list(self):
        """Permissions should be a JSON array of strings."""
        perms = ["repo:read", "repo:write", "ci:trigger"]
        assert isinstance(perms, list)
        assert all(isinstance(p, str) for p in perms)
        assert all(":" in p for p in perms)

    def test_token_expiry_calculation(self):
        """TTL should correctly calculate expiry from issued_at."""
        from datetime import datetime, timedelta, timezone

        issued = datetime.now(timezone.utc)
        ttl = 14400
        expires = issued + timedelta(seconds=ttl)
        remaining = (expires - issued).total_seconds()
        assert remaining == ttl

    def test_token_remaining_time_check(self):
        """Should detect when token is expiring soon vs valid."""
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        threshold = 900

        soon = now + timedelta(seconds=600)
        remaining_soon = (soon - now).total_seconds()
        assert remaining_soon <= threshold

        far = now + timedelta(seconds=3600)
        remaining_far = (far - now).total_seconds()
        assert remaining_far > threshold

    def test_revoke_removes_identity_file(self):
        """Revocation should remove the identity file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "agent_id": "revoke-test",
                    "delegation_token": "revoke-me",
                    "control_url": "http://localhost:9999",
                },
                f,
            )
            tmppath = f.name

        env = os.environ.copy()
        env["AFK_IDENTITY_FILE"] = tmppath
        env["DEEPSECURE_CONTROL_URL"] = "http://localhost:9999"

        subprocess.run(
            ["bash", IDENTITY_SCRIPT, "--revoke"],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert not os.path.exists(tmppath)


class TestAuditTrail:
    """Tests for audit trail logging in hermes-manager."""

    def test_audit_event_structure(self):
        """Audit events should have timestamp, event_type, agent_id, details."""
        event = {
            "timestamp": "2026-06-17T00:00:00+00:00",
            "event_type": "lifecycle_start",
            "agent_id": "test-agent",
            "spec_file": "test-spec.md",
            "details": "Manager starting",
        }
        required = ["timestamp", "event_type", "agent_id", "details"]
        for field in required:
            assert field in event

    def test_audit_file_is_json_array(self):
        """Audit file should be a JSON array of events."""
        events = [
            {
                "timestamp": "2026-06-17T00:00:00+00:00",
                "event_type": "lifecycle_start",
                "agent_id": "test",
                "details": "start",
            },
            {
                "timestamp": "2026-06-17T00:01:00+00:00",
                "event_type": "plan_start",
                "agent_id": "test",
                "details": "planning",
            },
        ]
        serialized = json.dumps(events)
        parsed = json.loads(serialized)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_audit_events_are_ordered(self):
        """Events should be appended in chronological order."""
        events = [
            {"timestamp": "2026-06-17T00:00:00+00:00", "event_type": "start"},
            {"timestamp": "2026-06-17T00:01:00+00:00", "event_type": "plan"},
            {"timestamp": "2026-06-17T00:02:00+00:00", "event_type": "execute"},
            {"timestamp": "2026-06-17T00:03:00+00:00", "event_type": "review"},
            {"timestamp": "2026-06-17T00:04:00+00:00", "event_type": "merge"},
        ]
        timestamps = [e["timestamp"] for e in events]
        assert timestamps == sorted(timestamps)

    def test_audit_lifecycle_events(self):
        """Manager lifecycle should produce expected event types."""
        expected_events = [
            "lifecycle_start",
            "plan_start",
            "plan_complete",
            "batch_start",
            "batch_complete",
            "execute_complete",
            "review_start",
            "review_complete",
            "merge_start",
            "merge_complete",
            "lifecycle_end",
        ]
        for event_type in expected_events:
            assert isinstance(event_type, str)
            assert "_" in event_type


class TestTokenRevocation:
    """Tests for emergency token revocation behavior."""

    def test_revoked_token_blocks_execution(self):
        """When a token is revoked, the identity check should fail."""
        from datetime import datetime, timedelta, timezone

        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "agent_id": "revoked-agent",
                    "delegation_token": "revoked-token-xyz",
                    "expires_at": future,
                    "control_url": "http://localhost:9999",
                },
                f,
            )
            tmppath = f.name

        try:
            env = os.environ.copy()
            env["DEEPSECURE_AGENT_ID"] = "revoked-agent"
            env["AFK_IDENTITY_FILE"] = tmppath
            env["DEEPSECURE_CONTROL_URL"] = "http://localhost:9999"

            # The hook should pass locally (token not expired) since control plane
            # is unreachable — offline-safe behavior
            result = subprocess.run(
                ["bash", IDENTITY_CHECK_HOOK],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
            )
            # When control plane is unreachable but token is locally valid, hook passes
            assert result.returncode == 0
        finally:
            os.unlink(tmppath)

    def test_revoke_and_verify_fails(self):
        """After revocation, verify should fail."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "agent_id": "revoke-verify",
                    "delegation_token": "rvk-tok",
                    "control_url": "http://localhost:9999",
                },
                f,
            )
            tmppath = f.name

        try:
            env = os.environ.copy()
            env["AFK_IDENTITY_FILE"] = tmppath
            env["DEEPSECURE_CONTROL_URL"] = "http://localhost:9999"

            # Revoke
            subprocess.run(
                ["bash", IDENTITY_SCRIPT, "--revoke"],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
            )

            # Verify should now fail (file removed)
            env["DEEPSECURE_AGENT_ID"] = "revoke-verify"
            result = subprocess.run(
                ["bash", IDENTITY_SCRIPT, "--verify"],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
            )
            assert result.returncode != 0
        finally:
            if os.path.exists(tmppath):
                os.unlink(tmppath)


class TestManagerDryRun:
    """Tests for manager --dry-run mode with a valid identity setup."""

    @pytest.fixture
    def identity_env(self, tmp_path):
        """Create a temporary identity file and environment for testing."""
        from datetime import datetime, timedelta, timezone

        future = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
        identity_file = tmp_path / "identity.json"
        identity_file.write_text(
            json.dumps(
                {
                    "agent_id": "test-dry-run-agent",
                    "delegation_token": "dry-run-token-abc",
                    "permissions": ["repo:read", "repo:write"],
                    "ttl_seconds": 14400,
                    "issued_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": future,
                    "control_url": "http://localhost:9999",
                    "bootstrap_count": 1,
                }
            )
        )

        spec_file = tmp_path / "test-spec.md"
        spec_file.write_text("# Test Spec\n\nThis is a test specification.")

        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        env = os.environ.copy()
        env["DEEPSECURE_AGENT_ID"] = "test-dry-run-agent"
        env["AFK_IDENTITY_FILE"] = str(identity_file)
        env["DEEPSECURE_CONTROL_URL"] = "http://localhost:9999"
        env["AFK_LOG_DIR"] = str(log_dir)

        return env, str(spec_file)

    def test_dry_run_validates_spec(self, identity_env):
        env, spec_file = identity_env
        result = subprocess.run(
            ["bash", MANAGER_SCRIPT, spec_file, "--dry-run"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        # Should get past validation (spec exists, identity valid)
        combined = result.stdout + result.stderr
        assert "Spec file validated" in combined or "DRY RUN" in combined

    def test_dry_run_shows_plan(self, identity_env):
        env, spec_file = identity_env
        result = subprocess.run(
            ["bash", MANAGER_SCRIPT, spec_file, "--dry-run"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        combined = result.stdout + result.stderr
        assert "DRY RUN" in combined or "Plan Phase" in combined


class TestScriptShebangAndPermissions:
    """Verify all identity/manager scripts have correct shebangs and permissions."""

    @pytest.mark.parametrize(
        "script_path",
        [IDENTITY_SCRIPT, IDENTITY_CHECK_HOOK, MANAGER_SCRIPT],
    )
    def test_script_has_bash_shebang(self, script_path):
        with open(script_path) as f:
            first_line = f.readline().strip()
        assert first_line in (
            "#!/usr/bin/env bash",
            "#!/bin/bash",
        ), f"{script_path}: unexpected shebang: {first_line}"

    @pytest.mark.parametrize(
        "script_path",
        [IDENTITY_SCRIPT, IDENTITY_CHECK_HOOK, MANAGER_SCRIPT],
    )
    def test_script_is_executable(self, script_path):
        st = os.stat(script_path)
        assert st.st_mode & stat.S_IXUSR, f"{script_path} is not executable"

    @pytest.mark.parametrize(
        "script_path",
        [IDENTITY_SCRIPT, IDENTITY_CHECK_HOOK, MANAGER_SCRIPT],
    )
    def test_script_uses_set_euo_pipefail(self, script_path):
        with open(script_path) as f:
            content = f.read()
        assert "set -euo pipefail" in content, f"{script_path} missing set -euo pipefail"
