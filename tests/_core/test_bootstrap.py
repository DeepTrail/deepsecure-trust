"""Tests for deepsecure._core.bootstrap — BootstrapClient + helpers."""

from __future__ import annotations

import base64
import json
import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from deepsecure._core.bootstrap import (
    BootstrapClient,
    BootstrapResult,
    Delegation,
    Platform,
    _is_aws,
    _is_gcp,
    _sign_challenge,
    bootstrap,
)
from deepsecure.exceptions import DeepSecureError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_httpx(monkeypatch):
    """Patch httpx.Client so no real HTTP happens."""
    mock_client = MagicMock(spec=httpx.Client)
    monkeypatch.setattr("deepsecure._core.bootstrap.httpx.Client", lambda **kw: mock_client)
    return mock_client


def _json_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=data,
        request=httpx.Request("POST", "http://test"),
    )


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

class TestPlatformDetection:

    def test_gcp_detected_via_k_service(self, monkeypatch):
        monkeypatch.setenv("K_SERVICE", "my-service")
        monkeypatch.delenv("AWS_EXECUTION_ENV", raising=False)
        assert _is_gcp() is True
        assert _is_aws() is False

    def test_gcp_detected_via_project(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-project")
        monkeypatch.delenv("K_SERVICE", raising=False)
        assert _is_gcp() is True

    def test_aws_detected_via_execution_env(self, monkeypatch):
        monkeypatch.delenv("K_SERVICE", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("GCE_METADATA_HOST", raising=False)
        monkeypatch.setenv("AWS_EXECUTION_ENV", "AWS_ECS_FARGATE")
        assert _is_aws() is True
        assert _is_gcp() is False

    def test_aws_detected_via_lambda(self, monkeypatch):
        monkeypatch.delenv("K_SERVICE", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("GCE_METADATA_HOST", raising=False)
        monkeypatch.delenv("AWS_EXECUTION_ENV", raising=False)
        monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "my-fn")
        assert _is_aws() is True

    def test_aws_detected_via_ecs_metadata(self, monkeypatch):
        monkeypatch.delenv("K_SERVICE", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("GCE_METADATA_HOST", raising=False)
        monkeypatch.delenv("AWS_EXECUTION_ENV", raising=False)
        monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
        monkeypatch.setenv("ECS_CONTAINER_METADATA_URI", "http://169.254.170.2/v3")
        assert _is_aws() is True

    def test_local_when_no_cloud_env(self, monkeypatch):
        for var in ("K_SERVICE", "GOOGLE_CLOUD_PROJECT", "GCE_METADATA_HOST",
                     "AWS_EXECUTION_ENV", "ECS_CONTAINER_METADATA_URI", "AWS_LAMBDA_FUNCTION_NAME"):
            monkeypatch.delenv(var, raising=False)
        assert _is_gcp() is False
        assert _is_aws() is False

    def test_auto_detect_gcp(self, monkeypatch):
        monkeypatch.setenv("K_SERVICE", "svc")
        monkeypatch.delenv("AWS_EXECUTION_ENV", raising=False)
        assert BootstrapClient._detect_platform() == Platform.GCP

    def test_auto_detect_aws(self, monkeypatch):
        for var in ("K_SERVICE", "GOOGLE_CLOUD_PROJECT", "GCE_METADATA_HOST"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("AWS_EXECUTION_ENV", "AWS_ECS_FARGATE")
        assert BootstrapClient._detect_platform() == Platform.AWS

    def test_auto_detect_local(self, monkeypatch):
        for var in ("K_SERVICE", "GOOGLE_CLOUD_PROJECT", "GCE_METADATA_HOST",
                     "AWS_EXECUTION_ENV", "ECS_CONTAINER_METADATA_URI", "AWS_LAMBDA_FUNCTION_NAME"):
            monkeypatch.delenv(var, raising=False)
        assert BootstrapClient._detect_platform() == Platform.LOCAL


# ---------------------------------------------------------------------------
# GCP bootstrap
# ---------------------------------------------------------------------------

class TestGcpBootstrap:

    @patch("deepsecure._core.bootstrap._gcp_fetch_identity_token", return_value="oidc-tok")
    def test_gcp_bootstrap_happy_path(self, mock_oidc, mock_httpx):
        mock_httpx.post.return_value = _json_response({
            "access_token": "jwt-gcp",
            "agent_id": "agent-abc",
            "expires_in": 3600,
        })
        mock_httpx.get.return_value = _json_response([])

        client = BootstrapClient(control_url="http://test:8000", gateway_url="http://test:8002")
        result = client.bootstrap("agent-abc", Platform.GCP)

        assert result.jwt == "jwt-gcp"
        assert result.agent_id == "agent-abc"
        assert result.platform == Platform.GCP
        assert result.expires_in == 3600

        mock_httpx.post.assert_any_call(
            "http://test:8000/api/v1/auth/bootstrap/gcp",
            headers={},
            json={"identity_token": "oidc-tok"},
        )

    @patch("deepsecure._core.bootstrap._gcp_fetch_identity_token", side_effect=DeepSecureError("metadata down"))
    def test_gcp_bootstrap_metadata_failure(self, mock_oidc, mock_httpx):
        client = BootstrapClient(control_url="http://test:8000")
        with pytest.raises(DeepSecureError, match="metadata down"):
            client.bootstrap("agent-abc", Platform.GCP)


# ---------------------------------------------------------------------------
# AWS bootstrap
# ---------------------------------------------------------------------------

class TestAwsBootstrap:

    @patch("deepsecure._core.bootstrap._aws_fetch_identity_token", return_value="arn:aws:sts::123:assumed-role/foo")
    def test_aws_bootstrap_happy_path(self, mock_aws, mock_httpx):
        mock_httpx.post.return_value = _json_response({
            "access_token": "jwt-aws",
            "agent_id": "agent-aws",
            "expires_in": 3600,
        })
        mock_httpx.get.return_value = _json_response([])

        client = BootstrapClient(control_url="http://test:8000", gateway_url="http://test:8002")
        result = client.bootstrap("agent-aws", Platform.AWS)

        assert result.jwt == "jwt-aws"
        assert result.platform == Platform.AWS

    @patch("deepsecure._core.bootstrap._aws_fetch_identity_token", side_effect=DeepSecureError("boto3 missing"))
    def test_aws_bootstrap_no_boto3(self, mock_aws, mock_httpx):
        client = BootstrapClient(control_url="http://test:8000")
        with pytest.raises(DeepSecureError, match="boto3"):
            client.bootstrap("agent-x", Platform.AWS)


# ---------------------------------------------------------------------------
# Local (keyring) bootstrap
# ---------------------------------------------------------------------------

class TestLocalBootstrap:

    @patch("deepsecure._core.bootstrap._sign_challenge", return_value="sig-b64")
    @patch("deepsecure._core.bootstrap._local_get_private_key", return_value="privkey-b64")
    def test_local_bootstrap_happy_path(self, mock_key, mock_sign, mock_httpx):
        challenge_resp = _json_response({"challenge": "random-challenge"})
        verify_resp = _json_response({
            "access_token": "jwt-local",
            "agent_id": "agent-local",
            "expires_in": 3600,
        })
        delegations_resp = _json_response([])

        mock_httpx.post.side_effect = [challenge_resp, verify_resp]
        mock_httpx.get.return_value = delegations_resp

        client = BootstrapClient(control_url="http://test:8000", gateway_url="http://test:8002")
        result = client.bootstrap("agent-local", Platform.LOCAL)

        assert result.jwt == "jwt-local"
        assert result.platform == Platform.LOCAL

        calls = mock_httpx.post.call_args_list
        assert "/api/v1/auth/agent/challenge" in calls[0].args[0]
        assert "/api/v1/auth/agent/verify" in calls[1].args[0]

    @patch("deepsecure._core.bootstrap._local_get_private_key", side_effect=DeepSecureError("No private key"))
    def test_local_bootstrap_missing_key(self, mock_key, mock_httpx):
        client = BootstrapClient(control_url="http://test:8000")
        with pytest.raises(DeepSecureError, match="No private key"):
            client.bootstrap("agent-missing", Platform.LOCAL)


# ---------------------------------------------------------------------------
# Delegation fetching
# ---------------------------------------------------------------------------

class TestDelegations:

    @patch("deepsecure._core.bootstrap._gcp_fetch_identity_token", return_value="tok")
    def test_delegations_fetched(self, mock_oidc, mock_httpx):
        bootstrap_resp = _json_response({"access_token": "jwt", "agent_id": "a"})
        delegations_resp = _json_response([
            {"delegation_id": "d1", "service": "github", "permissions": ["repo"]},
            {"delegation_id": "d2", "service": "notion", "permissions": ["read"]},
        ])
        del_token_resp = _json_response({"access_token": "del-jwt"})

        mock_httpx.post.side_effect = [bootstrap_resp, del_token_resp, del_token_resp]
        mock_httpx.get.return_value = delegations_resp

        client = BootstrapClient(control_url="http://t:8000", gateway_url="http://t:8002")
        result = client.bootstrap("a", Platform.GCP)

        assert len(result.delegations) == 2
        assert result.delegations[0].service == "github"
        assert result.delegations[0].jwt == "del-jwt"

    @patch("deepsecure._core.bootstrap._gcp_fetch_identity_token", return_value="tok")
    def test_no_delegations_flag(self, mock_oidc, mock_httpx):
        mock_httpx.post.return_value = _json_response({"access_token": "jwt", "agent_id": "a"})

        client = BootstrapClient(control_url="http://t:8000", gateway_url="http://t:8002")
        result = client.bootstrap("a", Platform.GCP, fetch_delegations=False)

        assert result.delegations == []
        mock_httpx.get.assert_not_called()


# ---------------------------------------------------------------------------
# BootstrapResult output formats
# ---------------------------------------------------------------------------

class TestBootstrapResultFormats:

    def _make_result(self, **overrides):
        defaults = dict(
            agent_id="agent-1",
            jwt="jwt-tok",
            platform=Platform.GCP,
            control_url="http://ctrl",
            gateway_url="http://gw",
            delegations=[
                Delegation(delegation_id="d1", service="gh", permissions=["r"], jwt="del-jwt"),
            ],
            expires_in=3600,
        )
        defaults.update(overrides)
        return BootstrapResult(**defaults)

    def test_to_mcp_json_uses_delegation_jwt(self):
        result = self._make_result()
        mcp = result.to_mcp_json()

        assert "mcpServers" in mcp
        ds = mcp["mcpServers"]["deepsecure"]
        assert ds["url"] == "http://gw/mcp"
        assert ds["transport"] == "http"
        assert ds["headers"]["Authorization"] == "Bearer del-jwt"

    def test_to_mcp_json_falls_back_to_discovery_jwt(self):
        result = self._make_result(delegations=[])
        mcp = result.to_mcp_json()
        assert mcp["mcpServers"]["deepsecure"]["headers"]["Authorization"] == "Bearer jwt-tok"

    def test_to_mcp_json_no_double_mcp(self):
        result = self._make_result(gateway_url="https://app.deepsecure.one/mcp")
        mcp = result.to_mcp_json()
        assert mcp["mcpServers"]["deepsecure"]["url"] == "https://app.deepsecure.one/mcp"

    def test_to_mcp_json_appends_mcp_when_missing(self):
        result = self._make_result(gateway_url="https://app.deepsecure.one")
        mcp = result.to_mcp_json()
        assert mcp["mcpServers"]["deepsecure"]["url"] == "https://app.deepsecure.one/mcp"

    def test_to_env_format(self):
        result = self._make_result()
        env = result.to_env()

        assert 'export DEEPSECURE_AGENT_JWT="jwt-tok"' in env
        assert 'export DEEPSECURE_GATEWAY_URL="http://gw"' in env
        assert 'export DEEPSECURE_DELEGATION_JWT="del-jwt"' in env
        assert 'export DEEPSECURE_DELEGATION_ID="d1"' in env

    def test_to_env_no_delegations(self):
        result = self._make_result(delegations=[])
        env = result.to_env()
        assert "DELEGATION" not in env


# ---------------------------------------------------------------------------
# Signing helper
# ---------------------------------------------------------------------------

class TestSignChallenge:

    def test_sign_and_verify(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        priv = Ed25519PrivateKey.generate()
        priv_b64 = base64.b64encode(
            priv.private_bytes_raw()
        ).decode()

        sig_b64 = _sign_challenge(priv_b64, "test-challenge")

        sig_bytes = base64.b64decode(sig_b64)
        pub = priv.public_key()
        pub.verify(sig_bytes, b"test-challenge")


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

class TestBootstrapFunction:

    @patch("deepsecure._core.bootstrap._gcp_fetch_identity_token", return_value="tok")
    def test_convenience_wrapper(self, mock_oidc, mock_httpx):
        mock_httpx.post.return_value = _json_response({"access_token": "jwt", "agent_id": "a"})
        mock_httpx.get.return_value = _json_response([])

        result = bootstrap(
            "a",
            platform="gcp",
            control_url="http://t:8000",
            gateway_url="http://t:8002",
        )
        assert result.jwt == "jwt"
        assert result.platform == Platform.GCP
