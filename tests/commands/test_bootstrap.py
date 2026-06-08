"""Tests for deepsecure.commands.bootstrap — CLI interface."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from deepsecure._core.bootstrap import BootstrapResult, Delegation, Platform
from deepsecure.commands.bootstrap import app

runner = CliRunner()

PATCH_TARGET = "deepsecure._core.bootstrap.BootstrapClient"


def _mock_result(**overrides) -> BootstrapResult:
    defaults = dict(
        agent_id="agent-test",
        jwt="jwt-value-123",
        platform=Platform.GCP,
        control_url="http://ctrl:8000",
        gateway_url="http://gw:8002",
        delegations=[
            Delegation(delegation_id="d1", service="gh", permissions=["repo"], jwt="del-jwt"),
        ],
        expires_in=3600,
    )
    defaults.update(overrides)
    return BootstrapResult(**defaults)


def _setup_mock(MockClient, result=None, side_effect=None):
    mock_ctx = MagicMock()
    if side_effect:
        mock_ctx.bootstrap.side_effect = side_effect
    else:
        mock_ctx.bootstrap.return_value = result or _mock_result()
    mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    MockClient.return_value = mock_ctx
    return mock_ctx


class TestBootstrapCLI:

    @patch(PATCH_TARGET)
    def test_jwt_output(self, MockClient):
        _setup_mock(MockClient)
        result = runner.invoke(app, ["--agent-id", "agent-test", "--platform", "gcp", "--output", "jwt", "--quiet"])
        assert result.exit_code == 0
        assert "jwt-value-123" in result.output

    @patch(PATCH_TARGET)
    def test_mcp_json_output(self, MockClient):
        _setup_mock(MockClient)
        result = runner.invoke(app, ["-a", "agent-test", "-p", "gcp", "-o", "mcp-json", "-q"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "mcpServers" in parsed
        assert parsed["mcpServers"]["deepsecure"]["url"] == "http://gw:8002/mcp"

    @patch(PATCH_TARGET)
    def test_env_output(self, MockClient):
        _setup_mock(MockClient)
        result = runner.invoke(app, ["-a", "agent-test", "-p", "gcp", "-o", "env", "-q"])
        assert result.exit_code == 0
        assert 'export DEEPSECURE_AGENT_JWT="jwt-value-123"' in result.output
        assert 'export DEEPSECURE_GATEWAY_URL="http://gw:8002"' in result.output

    @patch(PATCH_TARGET)
    def test_no_delegations_flag(self, MockClient):
        mock_ctx = _setup_mock(MockClient, result=_mock_result(delegations=[]))
        result = runner.invoke(app, ["-a", "agent-test", "--no-delegations", "-q"])
        assert result.exit_code == 0
        mock_ctx.bootstrap.assert_called_once()
        _, kwargs = mock_ctx.bootstrap.call_args
        assert kwargs["fetch_delegations"] is False

    def test_invalid_platform(self):
        result = runner.invoke(app, ["-a", "agent-x", "-p", "azure"])
        assert result.exit_code == 1
        assert "invalid platform" in result.output.lower()

    @patch(PATCH_TARGET)
    def test_bootstrap_error_exit_code_1(self, MockClient):
        _setup_mock(MockClient, side_effect=Exception("connection refused"))
        result = runner.invoke(app, ["-a", "agent-x", "-p", "gcp", "-q"])
        assert result.exit_code == 1
        assert "connection refused" in result.output.lower()

    @patch(PATCH_TARGET)
    def test_verbose_output(self, MockClient):
        _setup_mock(MockClient)
        result = runner.invoke(app, ["-a", "agent-test", "-p", "gcp"])
        assert result.exit_code == 0
        assert "Bootstrapping" in result.output or "jwt-value-123" in result.output

    @patch(PATCH_TARGET)
    def test_auto_platform(self, MockClient):
        mock_ctx = _setup_mock(MockClient, result=_mock_result(platform=Platform.LOCAL))
        result = runner.invoke(app, ["-a", "agent-test", "-q"])
        assert result.exit_code == 0
        mock_ctx.bootstrap.assert_called_once()
        args, _ = mock_ctx.bootstrap.call_args
        assert args[1] == Platform.AUTO
