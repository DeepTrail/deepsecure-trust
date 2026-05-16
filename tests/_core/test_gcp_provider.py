"""
Unit tests for GCP environment detection and GcpIdentityProvider.

Covers:
  - EnvironmentDetector._detect_gcp() — env var signals and metadata server fallback
  - GcpIdentityProvider — bootstrap flow, error paths, and platform check
  - IdentityManager provider chain — GCP inclusion and recommendation
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from deepsecure._core.environment_detector import EnvironmentDetector, EnvironmentType
from deepsecure._core.identity_provider import GcpIdentityProvider, AgentIdentity
from deepsecure._core.identity_manager import IdentityManager


# ---------------------------------------------------------------------------
# Section 1: _detect_gcp() tests
# ---------------------------------------------------------------------------


class TestDetectGCP:
    """Tests for EnvironmentDetector._detect_gcp()."""

    def setup_method(self):
        self.detector = EnvironmentDetector()

    @patch.dict(os.environ, {"K_SERVICE": "my-service"}, clear=True)
    def test_detect_cloud_run(self):
        result = self.detector._detect_gcp()
        assert result is not None
        assert result.environment_type == EnvironmentType.GCP
        assert result.confidence >= 0.7
        assert result.metadata.get("service") == "cloud_run"
        assert result.metadata.get("k_service") == "my-service"

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "my-project"}, clear=True)
    def test_detect_gcp_project(self):
        result = self.detector._detect_gcp()
        assert result is not None
        assert result.environment_type == EnvironmentType.GCP
        assert result.confidence >= 0.4
        assert result.metadata.get("project_id") == "my-project"

    @patch.dict(os.environ, {"FUNCTION_TARGET": "my_handler"}, clear=True)
    def test_detect_cloud_functions(self):
        result = self.detector._detect_gcp()
        assert result is not None
        assert result.environment_type == EnvironmentType.GCP
        assert result.confidence >= 0.7
        assert result.metadata.get("service") == "cloud_functions"

    @patch.dict(os.environ, {}, clear=True)
    @patch("urllib.request.urlopen", side_effect=Exception("no metadata server"))
    def test_no_gcp_signals(self, _mock_urlopen):
        result = self.detector._detect_gcp()
        assert result is None

    @patch.dict(os.environ, {"K_SERVICE": "svc", "GOOGLE_CLOUD_PROJECT": "proj"}, clear=True)
    def test_multiple_signals_increase_confidence(self):
        result = self.detector._detect_gcp()
        assert result is not None
        # K_SERVICE (0.7) + GOOGLE_CLOUD_PROJECT (0.4) = 1.1 → capped at 1.0
        assert result.confidence == 1.0

    @patch.dict(os.environ, {}, clear=True)
    def test_metadata_server_fallback(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b"my-project-id"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = self.detector._detect_gcp()
            assert result is not None
            assert result.confidence == 0.8
            assert result.metadata.get("project_id") == "my-project-id"
            assert result.metadata.get("service") == "compute_engine"

    @patch.dict(os.environ, {"GCE_METADATA_HOST": "metadata.google.internal"}, clear=True)
    def test_gce_metadata_host(self):
        result = self.detector._detect_gcp()
        assert result is not None
        assert result.confidence >= 0.3
        assert result.metadata.get("service") == "compute_engine"


# ---------------------------------------------------------------------------
# Section 2: GcpIdentityProvider tests
# ---------------------------------------------------------------------------


class TestGcpIdentityProvider:
    """Tests for GcpIdentityProvider bootstrap flow."""

    def setup_method(self):
        self.mock_client = MagicMock()
        self.provider = GcpIdentityProvider(client=self.mock_client, silent_mode=True)

    def test_name(self):
        assert self.provider.name == "gcp"

    @patch.dict(os.environ, {}, clear=True)
    def test_not_on_gcp_returns_none(self):
        result = self.provider.get_identity("agent-test-123")
        assert result is None
        self.mock_client.bootstrap_gcp.assert_not_called()

    @patch.dict(os.environ, {"K_SERVICE": "my-svc"}, clear=True)
    def test_is_on_gcp(self):
        assert self.provider._is_on_gcp() is True

    @patch.dict(os.environ, {"K_SERVICE": "my-svc"}, clear=True)
    @patch("deepsecure._core.identity_provider.keyring")
    def test_successful_bootstrap(self, _mock_keyring):
        with patch.object(self.provider, "_fetch_identity_token", return_value="fake-gcp-jwt"):
            self.mock_client.bootstrap_gcp.return_value = {
                "access_token": "agent-jwt-token",
                "agent_id": "agent-resolved-123",
                "token_type": "bearer",
                "expires_in": 3600,
            }

            result = self.provider.get_identity("agent-test-123")

            assert result is not None
            assert isinstance(result, AgentIdentity)
            assert result.agent_id == "agent-resolved-123"
            assert result.private_key_b64 == "agent-jwt-token"
            assert result.public_key_b64 == ""
            assert result.provider_name == "gcp"
            self.mock_client.bootstrap_gcp.assert_called_once_with("fake-gcp-jwt")

    @patch.dict(os.environ, {"K_SERVICE": "my-svc"}, clear=True)
    def test_bootstrap_failure_returns_none(self):
        with patch.object(self.provider, "_fetch_identity_token", return_value="fake-jwt"):
            self.mock_client.bootstrap_gcp.side_effect = Exception("401 Unauthorized")
            result = self.provider.get_identity("agent-test-123")
            assert result is None

    @patch.dict(os.environ, {"K_SERVICE": "my-svc"}, clear=True)
    def test_no_token_returns_none(self):
        with patch.object(self.provider, "_fetch_identity_token", return_value=None):
            result = self.provider.get_identity("agent-test-123")
            assert result is None
            self.mock_client.bootstrap_gcp.assert_not_called()


# ---------------------------------------------------------------------------
# Section 3: Provider chain integration tests
# ---------------------------------------------------------------------------


class TestProviderChainIncludesGCP:
    """Tests for GCP inclusion in IdentityManager provider chain."""

    @patch("requests.get", side_effect=Exception("no network"))
    @patch("urllib.request.urlopen", side_effect=Exception("no metadata"))
    def test_gcp_in_provider_chain(self, _mock_urlopen, _mock_requests):
        mock_client = MagicMock()
        manager = IdentityManager(api_client=mock_client, silent_mode=True)
        provider_names = [p.name for p in manager.providers]
        assert "gcp" in provider_names

    @patch.dict(os.environ, {"K_SERVICE": "cloud-run-svc"}, clear=True)
    @patch("requests.get", side_effect=Exception("no network"))
    @patch("urllib.request.urlopen", side_effect=Exception("no metadata"))
    def test_gcp_recommended_when_detected(self, _mock_urlopen, _mock_requests):
        detector = EnvironmentDetector()
        method, info = detector.get_recommended_bootstrap_method()
        assert method == "gcp"
        assert info.environment_type == EnvironmentType.GCP
