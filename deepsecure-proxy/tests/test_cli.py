"""Tests for deepsecure-proxy CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from deepsecure_proxy.cli import app

runner = CliRunner()


class TestProxyCLI:
    def test_help_exits_0(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "agent-id" in result.output
        assert "gateway-url" in result.output

    def test_missing_agent_id_fails(self):
        result = runner.invoke(app, [])
        assert result.exit_code != 0
