"""Unit tests for IdPSessionService.

Tests cover:
- store() with/without refresh_token, UUID generation, id_token_claims
- get_by_session() found/not-found/revoked filtering
- get_decrypted_tokens() round-trip, not found, wrong key
- refresh() token update + refreshed_at, not found raises ValueError
- revoke() success/not-found/idempotent
- revoke_all_for_user() multiple sessions, none
- cleanup_expired() expired + revoked deletion, nothing to clean
- Security: no plaintext tokens in logs, ephemeral key warning
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.models.idp_session import IdPSession
from app.services.idp_service import OIDCTokens
from app.services.idp_session_service import IdPSessionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fernet_key() -> str:
    return Fernet.generate_key().decode()


def _tokens(
    access: str = "ya29.access-token",
    refresh: str | None = "1//refresh-token",
    id_tok: str = "eyJ.id-token",
) -> OIDCTokens:
    return OIDCTokens(
        id_token=id_tok,
        access_token=access,
        refresh_token=refresh,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def key() -> str:
    return _fernet_key()


@pytest.fixture
def svc(db: Session, key: str) -> IdPSessionService:
    return IdPSessionService(db=db, encryption_key=key)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class TestStore:
    def test_stores_with_refresh_token(self, svc: IdPSessionService):
        result = svc.store("sess-1", "user@acme.com", "google", _tokens())
        assert isinstance(result, IdPSession)
        assert result.session_id == "sess-1"
        assert result.user_id == "user@acme.com"
        assert result.idp == "google"
        assert result.encrypted_access_token is not None
        assert result.encrypted_refresh_token is not None
        assert result.encrypted_access_token != "ya29.access-token"
        assert result.encrypted_refresh_token != "1//refresh-token"

    def test_stores_without_refresh_token(self, svc: IdPSessionService):
        result = svc.store("sess-2", "user@acme.com", "google", _tokens(refresh=None))
        assert result.encrypted_refresh_token is None
        assert result.encrypted_access_token is not None

    def test_generates_uuid(self, svc: IdPSessionService):
        result = svc.store("sess-3", "user@acme.com", "google", _tokens())
        uuid.UUID(result.id)

    def test_stores_id_token_claims(self, svc: IdPSessionService):
        claims = {"sub": "1234", "email": "user@acme.com", "hd": "acme.com"}
        result = svc.store(
            "sess-4", "user@acme.com", "google", _tokens(),
            id_token_claims=claims,
        )
        assert result.id_token_claims == claims

    def test_stores_none_claims(self, svc: IdPSessionService):
        result = svc.store("sess-5", "user@acme.com", "google", _tokens())
        assert result.id_token_claims is None

    def test_revoked_defaults_false(self, svc: IdPSessionService):
        result = svc.store("sess-6", "user@acme.com", "google", _tokens())
        assert result.revoked is False


# ---------------------------------------------------------------------------
# Get by session
# ---------------------------------------------------------------------------


class TestGetBySession:
    def test_found(self, svc: IdPSessionService):
        svc.store("sess-get-1", "user@acme.com", "google", _tokens())
        result = svc.get_by_session("sess-get-1")
        assert result is not None
        assert result.session_id == "sess-get-1"

    def test_not_found(self, svc: IdPSessionService):
        result = svc.get_by_session("nonexistent-session")
        assert result is None

    def test_revoked_filtered(self, svc: IdPSessionService):
        stored = svc.store("sess-get-rev", "user@acme.com", "google", _tokens())
        stored.revoked = True
        svc.db.commit()
        result = svc.get_by_session("sess-get-rev")
        assert result is None


# ---------------------------------------------------------------------------
# Decrypt tokens
# ---------------------------------------------------------------------------


class TestGetDecryptedTokens:
    def test_round_trip(self, svc: IdPSessionService):
        svc.store(
            "sess-dec-1", "user@acme.com", "google",
            _tokens(access="my-access", refresh="my-refresh"),
        )
        result = svc.get_decrypted_tokens("sess-dec-1")
        assert result is not None
        assert result["access_token"] == "my-access"
        assert result["refresh_token"] == "my-refresh"

    def test_round_trip_no_refresh(self, svc: IdPSessionService):
        svc.store(
            "sess-dec-2", "user@acme.com", "google",
            _tokens(access="my-access", refresh=None),
        )
        result = svc.get_decrypted_tokens("sess-dec-2")
        assert result is not None
        assert result["access_token"] == "my-access"
        assert result["refresh_token"] is None

    def test_not_found(self, svc: IdPSessionService):
        result = svc.get_decrypted_tokens("no-such-session")
        assert result is None

    def test_wrong_key(self, db: Session, key: str):
        svc1 = IdPSessionService(db=db, encryption_key=key)
        svc1.store("sess-dec-wk", "user@acme.com", "google", _tokens())

        other_key = _fernet_key()
        svc2 = IdPSessionService(db=db, encryption_key=other_key)
        result = svc2.get_decrypted_tokens("sess-dec-wk")
        assert result is None


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    def test_updates_tokens(self, svc: IdPSessionService):
        svc.store(
            "sess-ref-1", "user@acme.com", "google",
            _tokens(access="old-access", refresh="old-refresh"),
        )
        new = _tokens(access="new-access", refresh="new-refresh")
        updated = svc.refresh("sess-ref-1", new)
        assert updated.refreshed_at is not None

        decrypted = svc.get_decrypted_tokens("sess-ref-1")
        assert decrypted["access_token"] == "new-access"
        assert decrypted["refresh_token"] == "new-refresh"

    def test_updates_only_access_when_no_new_refresh(self, svc: IdPSessionService):
        svc.store(
            "sess-ref-2", "user@acme.com", "google",
            _tokens(access="old-access", refresh="orig-refresh"),
        )
        new = _tokens(access="new-access", refresh=None)
        svc.refresh("sess-ref-2", new)

        decrypted = svc.get_decrypted_tokens("sess-ref-2")
        assert decrypted["access_token"] == "new-access"
        assert decrypted["refresh_token"] == "orig-refresh"

    def test_not_found_raises_value_error(self, svc: IdPSessionService):
        with pytest.raises(ValueError, match="not found or revoked"):
            svc.refresh("nonexistent", _tokens())

    def test_revoked_raises_value_error(self, svc: IdPSessionService):
        svc.store("sess-ref-rev", "user@acme.com", "google", _tokens())
        svc.revoke("sess-ref-rev")
        with pytest.raises(ValueError, match="not found or revoked"):
            svc.refresh("sess-ref-rev", _tokens())


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------


class TestRevoke:
    def test_success(self, svc: IdPSessionService):
        svc.store("sess-revoke-1", "user@acme.com", "google", _tokens())
        assert svc.revoke("sess-revoke-1") is True

        result = svc.get_by_session("sess-revoke-1")
        assert result is None

    def test_not_found(self, svc: IdPSessionService):
        assert svc.revoke("nonexistent") is False

    def test_idempotent(self, svc: IdPSessionService):
        svc.store("sess-revoke-idem", "user@acme.com", "google", _tokens())
        assert svc.revoke("sess-revoke-idem") is True
        assert svc.revoke("sess-revoke-idem") is True


# ---------------------------------------------------------------------------
# Revoke all for user
# ---------------------------------------------------------------------------


class TestRevokeAllForUser:
    def test_revokes_multiple(self, svc: IdPSessionService):
        svc.store("sess-rall-1", "alice@acme.com", "google", _tokens())
        svc.store("sess-rall-2", "alice@acme.com", "google", _tokens())
        svc.store("sess-rall-3", "bob@acme.com", "google", _tokens())

        count = svc.revoke_all_for_user("alice@acme.com")
        assert count == 2

        assert svc.get_by_session("sess-rall-1") is None
        assert svc.get_by_session("sess-rall-2") is None
        assert svc.get_by_session("sess-rall-3") is not None

    def test_no_sessions(self, svc: IdPSessionService):
        count = svc.revoke_all_for_user("nobody@acme.com")
        assert count == 0

    def test_skips_already_revoked(self, svc: IdPSessionService):
        svc.store("sess-rall-skip-1", "charlie@acme.com", "google", _tokens())
        svc.store("sess-rall-skip-2", "charlie@acme.com", "google", _tokens())
        svc.revoke("sess-rall-skip-1")

        count = svc.revoke_all_for_user("charlie@acme.com")
        assert count == 1


# ---------------------------------------------------------------------------
# Cleanup expired
# ---------------------------------------------------------------------------


class TestCleanupExpired:

    @pytest.fixture(autouse=True)
    def _clean_table(self, svc: IdPSessionService):
        """Purge all IdP sessions before each cleanup test for count accuracy."""
        from sqlalchemy import select as sa_select
        all_rows = list(svc.db.execute(sa_select(IdPSession)).scalars().all())
        for row in all_rows:
            svc.db.delete(row)
        svc.db.commit()

    def test_deletes_revoked(self, svc: IdPSessionService):
        svc.store("sess-clean-rev", "user@acme.com", "google", _tokens())
        svc.revoke("sess-clean-rev")

        count = svc.cleanup_expired()
        assert count == 1

        from sqlalchemy import select as sa_select
        found = svc.db.execute(
            sa_select(IdPSession).where(
                IdPSession.session_id == "sess-clean-rev"
            )
        ).scalar_one_or_none()
        assert found is None

    def test_deletes_expired(self, svc: IdPSessionService):
        stored = svc.store("sess-clean-exp", "user@acme.com", "google", _tokens())
        stored.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        svc.db.commit()

        count = svc.cleanup_expired()
        assert count == 1

    def test_nothing_to_clean(self, svc: IdPSessionService):
        svc.store("sess-clean-ok", "user@acme.com", "google", _tokens())
        count = svc.cleanup_expired()
        assert count == 0

    def test_preserves_active(self, svc: IdPSessionService):
        svc.store("sess-clean-active", "user@acme.com", "google", _tokens())
        stored_revoked = svc.store("sess-clean-del", "user@acme.com", "google", _tokens())
        stored_revoked.revoked = True
        svc.db.commit()

        svc.cleanup_expired()

        active = svc.get_by_session("sess-clean-active")
        assert active is not None


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


class TestSecurity:
    def test_no_plaintext_in_store_logs(self, svc: IdPSessionService, caplog):
        import logging
        with caplog.at_level(logging.DEBUG, logger="app.services.idp_session_service"):
            svc.store(
                "sess-sec-1", "user@acme.com", "google",
                _tokens(access="SUPER_SECRET_TOKEN", refresh="SUPER_SECRET_REFRESH"),
            )

        for record in caplog.records:
            assert "SUPER_SECRET_TOKEN" not in record.message
            assert "SUPER_SECRET_REFRESH" not in record.message

    def test_ephemeral_key_warning(self, db: Session, caplog):
        import logging
        import os
        env_backup = os.environ.pop("VAULT_ENCRYPTION_KEY", None)
        try:
            with caplog.at_level(logging.WARNING, logger="app.services.idp_session_service"):
                IdPSessionService(db=db)
            assert any("ephemeral key" in r.message for r in caplog.records)
        finally:
            if env_backup is not None:
                os.environ["VAULT_ENCRYPTION_KEY"] = env_backup


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_accepts_explicit_key(self, db: Session):
        key = _fernet_key()
        svc = IdPSessionService(db=db, encryption_key=key)
        assert svc._fernet is not None

    def test_loads_from_env(self, db: Session, monkeypatch):
        key = _fernet_key()
        monkeypatch.setenv("VAULT_ENCRYPTION_KEY", key)
        svc = IdPSessionService(db=db)
        assert svc._fernet is not None
