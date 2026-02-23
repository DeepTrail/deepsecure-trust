"""Unit tests for VaultToken model.

Tests cover:
- Model field definitions and constraints
- Token expiration checking
- Usage tracking
- Refresh count tracking
- String representation
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.vault_token import VaultToken


class TestVaultTokenModel:
    """Tests for VaultToken SQLAlchemy model."""

    def test_create_vault_token(self, db: Session):
        """VaultToken can be created with required fields."""
        token = VaultToken(
            token_ref="vault://test-user-service-abc123",
            user_id="test@example.com",
            service_id="notion",
            encrypted_data=b"encrypted_data_here",
        )
        db.add(token)
        db.commit()

        retrieved = db.query(VaultToken).filter(
            VaultToken.token_ref == "vault://test-user-service-abc123"
        ).first()

        assert retrieved is not None
        assert retrieved.user_id == "test@example.com"
        assert retrieved.service_id == "notion"
        assert retrieved.encrypted_data == b"encrypted_data_here"
        assert retrieved.refresh_count == 0

    def test_vault_token_with_expiration(self, db: Session):
        """VaultToken can store expiration timestamp."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        token = VaultToken(
            token_ref="vault://test-expires-abc123",
            user_id="test@example.com",
            service_id="slack",
            encrypted_data=b"encrypted",
            expires_at=expires_at,
        )
        db.add(token)
        db.commit()

        retrieved = db.query(VaultToken).filter(
            VaultToken.token_ref == "vault://test-expires-abc123"
        ).first()

        assert retrieved.expires_at is not None
        # Compare timestamps (allowing for timezone differences)
        assert abs((retrieved.expires_at.replace(tzinfo=timezone.utc) - expires_at).total_seconds()) < 1

    def test_vault_token_null_expiration(self, db: Session):
        """VaultToken can have no expiration (NULL expires_at)."""
        token = VaultToken(
            token_ref="vault://test-noexpire-abc123",
            user_id="test@example.com",
            service_id="hubspot",
            encrypted_data=b"encrypted",
            expires_at=None,
        )
        db.add(token)
        db.commit()

        retrieved = db.query(VaultToken).filter(
            VaultToken.token_ref == "vault://test-noexpire-abc123"
        ).first()

        assert retrieved.expires_at is None

    def test_vault_token_last_used_at(self, db: Session):
        """VaultToken tracks last_used_at timestamp."""
        token = VaultToken(
            token_ref="vault://test-usage-abc123",
            user_id="test@example.com",
            service_id="notion",
            encrypted_data=b"encrypted",
        )
        db.add(token)
        db.commit()

        # Initially None
        assert token.last_used_at is None

        # Update usage
        token.record_usage()
        db.commit()

        retrieved = db.query(VaultToken).filter(
            VaultToken.token_ref == "vault://test-usage-abc123"
        ).first()

        assert retrieved.last_used_at is not None

    def test_vault_token_refresh_count(self, db: Session):
        """VaultToken tracks refresh count."""
        token = VaultToken(
            token_ref="vault://test-refresh-abc123",
            user_id="test@example.com",
            service_id="notion",
            encrypted_data=b"encrypted",
        )
        db.add(token)
        db.commit()

        # Initially 0
        assert token.refresh_count == 0

        # Increment
        token.increment_refresh_count()
        token.increment_refresh_count()
        db.commit()

        retrieved = db.query(VaultToken).filter(
            VaultToken.token_ref == "vault://test-refresh-abc123"
        ).first()

        assert retrieved.refresh_count == 2


class TestVaultTokenExpiration:
    """Tests for VaultToken expiration checking."""

    def test_is_expired_returns_false_for_future_expiration(self, db: Session):
        """is_expired returns False when expires_at is in the future."""
        token = VaultToken(
            token_ref="vault://test-future-abc123",
            user_id="test@example.com",
            service_id="notion",
            encrypted_data=b"encrypted",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(token)
        db.commit()

        assert token.is_expired is False

    def test_is_expired_returns_true_for_past_expiration(self, db: Session):
        """is_expired returns True when expires_at is in the past."""
        token = VaultToken(
            token_ref="vault://test-past-abc123",
            user_id="test@example.com",
            service_id="notion",
            encrypted_data=b"encrypted",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.add(token)
        db.commit()

        assert token.is_expired is True

    def test_is_expired_returns_false_for_null_expiration(self, db: Session):
        """is_expired returns False when expires_at is None."""
        token = VaultToken(
            token_ref="vault://test-null-abc123",
            user_id="test@example.com",
            service_id="notion",
            encrypted_data=b"encrypted",
            expires_at=None,
        )
        db.add(token)
        db.commit()

        assert token.is_expired is False


class TestVaultTokenIndexes:
    """Tests verifying indexes work correctly for queries."""

    def test_query_by_user_id(self, db: Session):
        """Can efficiently query tokens by user_id (indexed)."""
        # Create tokens for two users
        token1 = VaultToken(
            token_ref="vault://user1-notion-abc123",
            user_id="user1@example.com",
            service_id="notion",
            encrypted_data=b"encrypted1",
        )
        token2 = VaultToken(
            token_ref="vault://user2-notion-def456",
            user_id="user2@example.com",
            service_id="notion",
            encrypted_data=b"encrypted2",
        )
        db.add_all([token1, token2])
        db.commit()

        # Query by user_id
        results = db.query(VaultToken).filter(
            VaultToken.user_id == "user1@example.com"
        ).all()

        assert len(results) == 1
        assert results[0].token_ref == "vault://user1-notion-abc123"

    def test_query_by_service_id(self, db: Session):
        """Can efficiently query tokens by service_id (indexed)."""
        import uuid
        unique = uuid.uuid4().hex[:8]
        
        token1 = VaultToken(
            token_ref=f"vault://idx-user-notion-{unique}",
            user_id="idx_user@example.com",
            service_id=f"notion_{unique}",
            encrypted_data=b"encrypted1",
        )
        token2 = VaultToken(
            token_ref=f"vault://idx-user-slack-{unique}",
            user_id="idx_user@example.com",
            service_id=f"slack_{unique}",
            encrypted_data=b"encrypted2",
        )
        db.add_all([token1, token2])
        db.commit()

        # Query by service_id
        results = db.query(VaultToken).filter(
            VaultToken.service_id == f"slack_{unique}"
        ).all()

        assert len(results) == 1
        assert results[0].token_ref == f"vault://idx-user-slack-{unique}"

    def test_query_by_user_and_service(self, db: Session):
        """Can efficiently query tokens by user_id and service_id (composite index)."""
        token = VaultToken(
            token_ref="vault://composite-user-notion-abc123",
            user_id="composite@example.com",
            service_id="notion",
            encrypted_data=b"encrypted",
        )
        db.add(token)
        db.commit()

        results = db.query(VaultToken).filter(
            VaultToken.user_id == "composite@example.com",
            VaultToken.service_id == "notion",
        ).all()

        assert len(results) == 1

    def test_query_expiring_tokens(self, db: Session):
        """Can query tokens by expires_at (indexed)."""
        import uuid
        unique = uuid.uuid4().hex[:8]
        
        now = datetime.now(timezone.utc)
        token1 = VaultToken(
            token_ref=f"vault://expiring-soon-{unique}",
            user_id=f"expiry_{unique}@example.com",
            service_id=f"notion_{unique}",
            encrypted_data=b"encrypted1",
            expires_at=now + timedelta(minutes=5),
        )
        token2 = VaultToken(
            token_ref=f"vault://expiring-later-{unique}",
            user_id=f"expiry_{unique}@example.com",
            service_id=f"slack_{unique}",
            encrypted_data=b"encrypted2",
            expires_at=now + timedelta(hours=2),
        )
        db.add_all([token1, token2])
        db.commit()

        # Query tokens expiring within 15 minutes for this specific user
        threshold = now + timedelta(minutes=15)
        results = db.query(VaultToken).filter(
            VaultToken.user_id == f"expiry_{unique}@example.com",
            VaultToken.expires_at.isnot(None),
            VaultToken.expires_at <= threshold,
        ).all()

        assert len(results) == 1
        assert results[0].token_ref == f"vault://expiring-soon-{unique}"


class TestVaultTokenRepr:
    """Tests for VaultToken string representation."""

    def test_repr_active_token(self, db: Session):
        """__repr__ shows 'active' for non-expired tokens."""
        token = VaultToken(
            token_ref="vault://repr-active-abc123",
            user_id="repr@example.com",
            service_id="notion",
            encrypted_data=b"encrypted",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        repr_str = repr(token)

        assert "vault://repr-active-abc123" in repr_str
        assert "repr@example.com" in repr_str
        assert "notion" in repr_str
        assert "active" in repr_str

    def test_repr_expired_token(self, db: Session):
        """__repr__ shows 'expired' for expired tokens."""
        token = VaultToken(
            token_ref="vault://repr-expired-abc123",
            user_id="repr@example.com",
            service_id="notion",
            encrypted_data=b"encrypted",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        repr_str = repr(token)

        assert "expired" in repr_str
