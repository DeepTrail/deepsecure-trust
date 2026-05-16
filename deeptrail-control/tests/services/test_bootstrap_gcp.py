"""Unit tests for GCP Workload Identity bootstrap flow.

Covers:
- validate_gcp_identity_token(): OIDC token verification via google-auth mock
- bootstrap_gcp_agent(): 1:1 selector lookup, policy check, JWT issuance
"""

import os
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app import crud, schemas
from app.core.exceptions import (
    BootstrapError,
    TokenValidationError,
)
from app.models.attestation_policy import PlatformType
from app.services.bootstrap_service import BootstrapService, GCPClaims


FAKE_SA_EMAIL = "my-agent@my-project.iam.gserviceaccount.com"

VALID_GCP_ID_INFO = {
    "email": FAKE_SA_EMAIL,
    "email_verified": True,
    "iss": "https://accounts.google.com",
    "azp": "my-project",
    "sub": "1234567890",
    "iat": 1700000000,
    "exp": 1700003600,
}


def _make_service() -> BootstrapService:
    return BootstrapService()


def _unique_email() -> str:
    return f"sa-{uuid.uuid4().hex[:8]}@proj.iam.gserviceaccount.com"


def _id_info_for(email: str) -> dict:
    return {**VALID_GCP_ID_INFO, "email": email}


def _seed_gcp_agent(db: Session, selector: str) -> str:
    agent_in = schemas.AgentCreate(
        name=f"gcp-agent-{uuid.uuid4().hex[:6]}",
        platform="gcp_workload_identity",
        selector=selector,
    )
    agent = crud.agent.create(db, obj_in=agent_in)
    return agent.agent_id


def _seed_gcp_policy(db: Session, selector: str) -> None:
    policy_in = schemas.AttestationPolicyCreate(
        agent_name_to_bootstrap=f"gcp-agent-{uuid.uuid4().hex[:6]}",
        platform=PlatformType.GCP_WORKLOAD_IDENTITY,
        selector=selector,
    )
    crud.attestation_policy.create(db, obj_in=policy_in)


# ── validate_gcp_identity_token ─────────────────────────────────────────


class TestValidateGCPIdentityToken:

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_valid_token_returns_claims(self, mock_verify):
        mock_verify.return_value = VALID_GCP_ID_INFO

        claims = _make_service().validate_gcp_identity_token("fake-jwt-token")

        assert isinstance(claims, GCPClaims)
        assert claims.service_account_email == FAKE_SA_EMAIL
        assert claims.project_id == "my-project"
        assert claims.instance_id == "1234567890"

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_valid_token_uses_aud_fallback(self, mock_verify):
        """When 'azp' is absent, project_id should fall back to 'aud'."""
        id_info = {**VALID_GCP_ID_INFO}
        del id_info["azp"]
        id_info["aud"] = "audience-project"
        mock_verify.return_value = id_info

        claims = _make_service().validate_gcp_identity_token("t")
        assert claims.project_id == "audience-project"

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_invalid_token_raises(self, mock_verify):
        mock_verify.side_effect = ValueError("Token expired")

        with pytest.raises(TokenValidationError, match="Invalid GCP identity token"):
            _make_service().validate_gcp_identity_token("bad-token")

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_expired_token_raises(self, mock_verify):
        mock_verify.side_effect = ValueError("Token expired or invalid")

        with pytest.raises(TokenValidationError, match="Invalid GCP identity token"):
            _make_service().validate_gcp_identity_token("expired-token")

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_missing_email_raises(self, mock_verify):
        id_info = {**VALID_GCP_ID_INFO}
        del id_info["email"]
        mock_verify.return_value = id_info

        with pytest.raises(TokenValidationError, match="missing verified email"):
            _make_service().validate_gcp_identity_token("t")

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_email_not_verified_raises(self, mock_verify):
        id_info = {**VALID_GCP_ID_INFO, "email_verified": False}
        mock_verify.return_value = id_info

        with pytest.raises(TokenValidationError, match="missing verified email"):
            _make_service().validate_gcp_identity_token("t")

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_bad_issuer_raises(self, mock_verify):
        id_info = {**VALID_GCP_ID_INFO, "iss": "https://evil.example.com"}
        mock_verify.return_value = id_info

        with pytest.raises(TokenValidationError, match="Invalid issuer"):
            _make_service().validate_gcp_identity_token("t")

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_custom_audience_env_var(self, mock_verify):
        mock_verify.return_value = VALID_GCP_ID_INFO

        with patch.dict(os.environ, {"GCP_BOOTSTRAP_AUDIENCE": "custom-aud"}):
            _make_service().validate_gcp_identity_token("t")

        _, kwargs = mock_verify.call_args
        assert kwargs.get("audience") == "custom-aud"

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_accounts_google_com_issuer_accepted(self, mock_verify):
        """Short-form issuer 'accounts.google.com' should also be accepted."""
        id_info = {**VALID_GCP_ID_INFO, "iss": "accounts.google.com"}
        mock_verify.return_value = id_info

        claims = _make_service().validate_gcp_identity_token("t")
        assert claims.service_account_email == FAKE_SA_EMAIL


# ── bootstrap_gcp_agent ─────────────────────────────────────────────────


class TestBootstrapGCPAgent:

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_happy_path(self, mock_verify, db: Session):
        email = _unique_email()
        mock_verify.return_value = _id_info_for(email)
        agent_id = _seed_gcp_agent(db, email)
        _seed_gcp_policy(db, email)

        result = _make_service().bootstrap_gcp_agent(db, identity_token="tok")

        assert result["agent_id"] == agent_id
        assert result["token_type"] == "bearer"
        assert result["expires_in"] == 3600
        assert isinstance(result["access_token"], str) and len(result["access_token"]) > 0

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_agent_not_found(self, mock_verify, db: Session):
        email = _unique_email()
        mock_verify.return_value = _id_info_for(email)
        _seed_gcp_policy(db, email)

        with pytest.raises(BootstrapError) as exc_info:
            _make_service().bootstrap_gcp_agent(db, identity_token="tok")

        assert exc_info.value.error_code == "AGENT_NOT_FOUND"

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_policy_not_found(self, mock_verify, db: Session):
        email = _unique_email()
        mock_verify.return_value = _id_info_for(email)
        _seed_gcp_agent(db, email)

        with pytest.raises(BootstrapError) as exc_info:
            _make_service().bootstrap_gcp_agent(db, identity_token="tok")

        assert exc_info.value.error_code == "POLICY_NOT_FOUND"

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_token_validation_fails(self, mock_verify, db: Session):
        mock_verify.side_effect = ValueError("bad token")

        with pytest.raises(TokenValidationError):
            _make_service().bootstrap_gcp_agent(db, identity_token="tok")

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_client_ip_logged(self, mock_verify, db: Session):
        """Smoke test: client_ip is accepted without error."""
        email = _unique_email()
        mock_verify.return_value = _id_info_for(email)
        _seed_gcp_agent(db, email)
        _seed_gcp_policy(db, email)

        result = _make_service().bootstrap_gcp_agent(
            db, identity_token="tok", client_ip="10.0.0.1",
        )
        assert result["agent_id"]
