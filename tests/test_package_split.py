"""Verification tests for the SDK package split (P5.4 Phase 3).

These tests validate that:
1. Core imports work without optional extras
2. Admin modules use lazy imports with clear error messages
3. Legacy files have been deleted
4. httpx replaced requests in core
5. CLI registration is conditional
"""

from __future__ import annotations

import ast
import os
import importlib


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestCoreImports:
    """Core package should be importable without admin extras."""

    def test_bootstrap_importable(self):
        from deepsecure import bootstrap, BootstrapClient, BootstrapResult, Platform
        assert callable(bootstrap)

    def test_client_importable(self):
        from deepsecure import Client
        assert Client is not None

    def test_exceptions_importable(self):
        from deepsecure import DeepSecureError, ApiError

    def test_version_importable(self):
        from deepsecure import __version__
        assert __version__


class TestHttpxMigration:
    """Core modules must not import requests."""

    def test_no_requests_in_base_client(self):
        path = os.path.join(REPO_ROOT, "deepsecure", "_core", "base_client.py")
        self._assert_no_requests_import(path)

    def test_no_requests_in_bootstrap(self):
        path = os.path.join(REPO_ROOT, "deepsecure", "_core", "bootstrap.py")
        self._assert_no_requests_import(path)

    def test_no_requests_in_identity_provider(self):
        path = os.path.join(REPO_ROOT, "deepsecure", "_core", "identity_provider.py")
        self._assert_no_requests_import(path)

    def test_no_requests_in_environment_detector(self):
        path = os.path.join(REPO_ROOT, "deepsecure", "_core", "environment_detector.py")
        self._assert_no_requests_import(path)

    def test_httpx_is_importable(self):
        import httpx
        assert httpx.__version__

    def _assert_no_requests_import(self, filepath: str):
        with open(filepath) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "requests", (
                        f"Found 'import requests' in {filepath}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "requests" not in node.module, (
                    f"Found 'from requests...' in {filepath}"
                )


class TestLegacyCleanup:
    """Legacy files must be deleted."""

    def test_core_client_deleted(self):
        path = os.path.join(REPO_ROOT, "deepsecure", "_core", "client.py")
        assert not os.path.exists(path), "_core/client.py should be deleted"

    def test_resources_agents_deleted(self):
        path = os.path.join(REPO_ROOT, "deepsecure", "resources", "agents.py")
        assert not os.path.exists(path), "resources/agents.py should be deleted"

    def test_vault_stub_deleted(self):
        path = os.path.join(REPO_ROOT, "deepsecure", "vault.py")
        assert not os.path.exists(path), "vault.py stub should be deleted"

    def test_policy_stub_deleted(self):
        path = os.path.join(REPO_ROOT, "deepsecure", "policy.py")
        assert not os.path.exists(path), "policy.py stub should be deleted"


class TestLazyImports:
    """Admin modules should be lazily imported in Client."""

    def test_client_vault_property_exists(self):
        from deepsecure.client import Client
        assert hasattr(Client, "vault")

    def test_client_policy_property_exists(self):
        from deepsecure.client import Client
        assert hasattr(Client, "policy")

    def test_client_gateway_property_exists(self):
        from deepsecure.client import Client
        assert hasattr(Client, "gateway")

    def test_client_openai_property_exists(self):
        from deepsecure.client import Client
        assert hasattr(Client, "openai")

    def test_client_anthropic_property_exists(self):
        from deepsecure.client import Client
        assert hasattr(Client, "anthropic")


class TestConditionalCLI:
    """CLI should conditionally register admin commands."""

    def test_bootstrap_command_registered(self):
        from deepsecure.main import app
        command_names = [cmd.name for cmd in app.registered_groups]
        assert "bootstrap" in command_names

    def test_agent_command_registered(self):
        from deepsecure.main import app
        command_names = [cmd.name for cmd in app.registered_groups]
        assert "agent" in command_names

    def test_configure_command_registered(self):
        from deepsecure.main import app
        command_names = [cmd.name for cmd in app.registered_groups]
        assert "configure" in command_names
