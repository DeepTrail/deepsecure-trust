"""Tests for Redis-backed agent session revocation (WS-D5)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.services import token_revocation as svc


class TestTokenRevocationService:
    def setup_method(self):
        svc.reset_revocation_client()

    def teardown_method(self):
        svc.reset_revocation_client()

    def test_revoke_and_check_session(self):
        mock_client = MagicMock()
        mock_client.exists.return_value = 1

        with patch("app.services.token_revocation._get_redis", return_value=mock_client):
            assert svc.revoke_agent_session("asess-abc", 3600) is True
            mock_client.setex.assert_called_once_with(
                "revoked_agent_session:asess-abc", 3600, "1"
            )
            assert svc.is_agent_session_revoked("asess-abc") is True

    def test_ttl_seconds_until_uses_remaining_time(self):
        expires = datetime.now(timezone.utc) + timedelta(hours=2)
        ttl = svc.ttl_seconds_until(expires)
        assert 7000 < ttl <= 7200

    def test_ttl_seconds_until_minimum_sixty(self):
        expires = datetime.now(timezone.utc) - timedelta(minutes=5)
        assert svc.ttl_seconds_until(expires) == 60

    def test_revoke_without_redis_returns_false(self):
        with patch("app.services.token_revocation._get_redis", return_value=None):
            assert svc.revoke_agent_session("asess-x", 60) is False
