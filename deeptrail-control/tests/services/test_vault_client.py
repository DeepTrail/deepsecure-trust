"""Unit tests for VaultClient.

Tests cover:
- Token storage and retrieval
- Encryption verification (data is not readable as plaintext)
- Token deletion
- Token existence checks
- Token update operations
- Reference format validation
- Error handling
- Key management
- Token expiration tracking
- Token refresh operations
- Usage tracking
- Expiring token identification
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet

from app.services.vault_client import (
    DecryptionError,
    StoredTokenData,
    TokenMetadata,
    VaultClient,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def vault() -> VaultClient:
    """Create a VaultClient with a test encryption key."""
    # Reset singleton for test isolation
    VaultClient._instance = None
    VaultClient._initialized = False
    test_key = Fernet.generate_key().decode()
    return VaultClient(encryption_key=test_key)


@pytest.fixture
def sample_token_data() -> dict:
    """Sample OAuth token data."""
    return {
        "access_token": "test_access_token_abc123",
        "refresh_token": "test_refresh_token_xyz789",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "read write",
    }


def unique_user_id() -> str:
    """Generate a unique user ID for test isolation."""
    return f"testuser_{uuid.uuid4().hex[:8]}@example.com"


# ============================================================================
# Token Storage and Retrieval Tests
# ============================================================================


class TestStoreAndRetrieveToken:
    """Tests for store_token and retrieve_token methods."""

    def test_store_token_returns_vault_reference(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """store_token should return a vault:// reference."""
        ref = vault.store_token("sarah@acme.com", "notion", sample_token_data)

        assert ref.startswith("vault://")

    def test_store_token_reference_contains_user_and_service(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Token reference should contain user and service identifiers."""
        ref = vault.store_token("sarah@acme.com", "notion", sample_token_data)

        assert "sarah" in ref
        assert "notion" in ref

    def test_store_token_sanitizes_email(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Token reference should only include username part of email."""
        ref = vault.store_token("sarah@acme.com", "notion", sample_token_data)

        assert "sarah" in ref
        assert "@acme.com" not in ref

    def test_retrieve_token_returns_original_data(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """retrieve_token should return the data that was stored, plus metadata."""
        ref = vault.store_token("user@example.com", "slack", sample_token_data)

        retrieved = vault.retrieve_token(ref)

        # Check original token fields are present
        for key, value in sample_token_data.items():
            assert retrieved[key] == value
        # Check metadata is included
        assert "metadata" in retrieved
        assert "created_at" in retrieved["metadata"]

    def test_retrieve_nonexistent_token_returns_none(self, vault: VaultClient):
        """retrieve_token should return None for unknown reference."""
        result = vault.retrieve_token("vault://nonexistent-ref-abc123")

        assert result is None

    def test_store_multiple_tokens_for_same_user(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """User can have tokens for multiple services."""
        user_id = unique_user_id()

        ref1 = vault.store_token(user_id, "notion", sample_token_data)
        ref2 = vault.store_token(user_id, "slack", sample_token_data)

        assert ref1 != ref2
        retrieved1 = vault.retrieve_token(ref1)
        retrieved2 = vault.retrieve_token(ref2)
        for key, value in sample_token_data.items():
            assert retrieved1[key] == value
            assert retrieved2[key] == value

    def test_store_tokens_for_different_users(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Different users can have tokens for the same service."""
        ref1 = vault.store_token(unique_user_id(), "notion", sample_token_data)
        ref2 = vault.store_token(unique_user_id(), "notion", sample_token_data)

        assert ref1 != ref2

    def test_store_duplicate_generates_new_reference(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Storing token again for same user/service generates new reference."""
        user_id = "same_user@example.com"
        ref1 = vault.store_token(user_id, "notion", sample_token_data)
        ref2 = vault.store_token(user_id, "notion", sample_token_data)

        # References should be different (both valid)
        assert ref1 != ref2
        # Both should be retrievable
        retrieved1 = vault.retrieve_token(ref1)
        retrieved2 = vault.retrieve_token(ref2)
        for key, value in sample_token_data.items():
            assert retrieved1[key] == value
            assert retrieved2[key] == value


# ============================================================================
# Encryption Verification Tests
# ============================================================================


class TestTokenEncryption:
    """Tests verifying tokens are actually encrypted."""

    def test_token_data_is_encrypted_at_rest(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Raw storage should contain encrypted data, not plaintext."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        raw = vault._storage[ref]

        # Raw data should be bytes (encrypted)
        assert isinstance(raw, bytes)
        # Sensitive values should not be readable
        assert b"test_access_token_abc123" not in raw
        assert b"test_refresh_token_xyz789" not in raw

    def test_encrypted_data_is_not_valid_json(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Encrypted data should not be parseable as JSON."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        raw = vault._storage[ref]

        with pytest.raises(json.JSONDecodeError):
            json.loads(raw.decode("utf-8", errors="replace"))

    def test_different_keys_cannot_decrypt(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Token encrypted with one key cannot be decrypted with another."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)
        encrypted_data = vault._storage[ref]

        # Reset singleton to create vault with different key
        VaultClient._instance = None
        VaultClient._initialized = False
        other_key = Fernet.generate_key().decode()
        other_vault = VaultClient(encryption_key=other_key)

        # Transfer the encrypted data (simulating storage access)
        other_vault._storage[ref] = encrypted_data

        # Attempting to retrieve should fail
        with pytest.raises(DecryptionError):
            other_vault.retrieve_token(ref)


# ============================================================================
# Token Deletion Tests
# ============================================================================


class TestDeleteToken:
    """Tests for delete_token method."""

    def test_delete_token_removes_from_storage(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """delete_token should remove token from storage."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        result = vault.delete_token(ref)

        assert result is True
        assert vault.retrieve_token(ref) is None

    def test_delete_nonexistent_token_returns_false(self, vault: VaultClient):
        """delete_token should return False for unknown reference."""
        result = vault.delete_token("vault://nonexistent-ref-abc123")

        assert result is False

    def test_delete_token_twice_returns_false_second_time(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Second delete of same token should return False."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        first = vault.delete_token(ref)
        second = vault.delete_token(ref)

        assert first is True
        assert second is False


# ============================================================================
# Token Existence Tests
# ============================================================================


class TestTokenExists:
    """Tests for token_exists method."""

    def test_token_exists_returns_true_for_stored_token(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """token_exists should return True for stored tokens."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        assert vault.token_exists(ref) is True

    def test_token_exists_returns_false_for_unknown(self, vault: VaultClient):
        """token_exists should return False for unknown references."""
        assert vault.token_exists("vault://unknown-ref-abc123") is False

    def test_token_exists_returns_false_after_deletion(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """token_exists should return False after token is deleted."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)
        vault.delete_token(ref)

        assert vault.token_exists(ref) is False


# ============================================================================
# Token Update Tests
# ============================================================================


class TestUpdateToken:
    """Tests for update_token method."""

    def test_update_token_changes_stored_data(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """update_token should change the stored token data."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        new_data = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 7200,
        }
        result = vault.update_token(ref, new_data)

        assert result is True
        retrieved = vault.retrieve_token(ref)
        for key, value in new_data.items():
            assert retrieved[key] == value

    def test_update_nonexistent_token_returns_false(self, vault: VaultClient):
        """update_token should return False for unknown reference."""
        result = vault.update_token(
            "vault://nonexistent-ref-abc123",
            {"access_token": "test"},
        )

        assert result is False

    def test_update_preserves_reference(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """update_token should not change the token reference."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        new_data = {"access_token": "updated"}
        vault.update_token(ref, new_data)

        # Same reference should still work
        retrieved = vault.retrieve_token(ref)
        assert retrieved["access_token"] == "updated"


# ============================================================================
# List Tokens Tests
# ============================================================================


class TestListTokensForUser:
    """Tests for list_tokens_for_user method."""

    def test_list_tokens_returns_user_refs(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """list_tokens_for_user should return all refs for a user."""
        user = "listtest@example.com"
        ref1 = vault.store_token(user, "notion", sample_token_data)
        ref2 = vault.store_token(user, "slack", sample_token_data)

        refs = vault.list_tokens_for_user(user)

        assert len(refs) >= 2
        assert ref1 in refs
        assert ref2 in refs

    def test_list_tokens_excludes_other_users(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """list_tokens_for_user should not include other users' tokens."""
        user1 = f"user1_{uuid.uuid4().hex[:4]}@example.com"
        user2 = f"user2_{uuid.uuid4().hex[:4]}@example.com"

        ref1 = vault.store_token(user1, "notion", sample_token_data)
        ref2 = vault.store_token(user2, "notion", sample_token_data)

        user1_refs = vault.list_tokens_for_user(user1)
        user2_refs = vault.list_tokens_for_user(user2)

        assert ref1 in user1_refs
        assert ref1 not in user2_refs
        assert ref2 in user2_refs
        assert ref2 not in user1_refs

    def test_list_tokens_empty_for_unknown_user(self, vault: VaultClient):
        """list_tokens_for_user should return empty list for unknown user."""
        refs = vault.list_tokens_for_user("unknown@example.com")

        assert refs == []


# ============================================================================
# Clear All Tests
# ============================================================================


class TestClearAll:
    """Tests for clear_all method."""

    def test_clear_all_removes_all_tokens(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """clear_all should remove all tokens from storage."""
        ref1 = vault.store_token("user1@example.com", "notion", sample_token_data)
        ref2 = vault.store_token("user2@example.com", "slack", sample_token_data)

        count = vault.clear_all()

        assert count >= 2
        assert vault.token_exists(ref1) is False
        assert vault.token_exists(ref2) is False

    def test_clear_all_returns_count(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """clear_all should return the number of deleted tokens."""
        vault.store_token("user@example.com", "s1", sample_token_data)
        vault.store_token("user@example.com", "s2", sample_token_data)
        vault.store_token("user@example.com", "s3", sample_token_data)

        count = vault.clear_all()

        assert count >= 3


# ============================================================================
# Key Management Tests
# ============================================================================


class TestKeyManagement:
    """Tests for encryption key handling."""

    def test_generate_encryption_key_returns_valid_key(self):
        """generate_encryption_key should return a usable Fernet key."""
        key = VaultClient.generate_encryption_key()

        # Should be valid for Fernet
        fernet = Fernet(key.encode())
        encrypted = fernet.encrypt(b"test")
        decrypted = fernet.decrypt(encrypted)
        assert decrypted == b"test"

    def test_vault_with_custom_key(self, sample_token_data: dict):
        """VaultClient should work with custom encryption key."""
        custom_key = VaultClient.generate_encryption_key()
        vault = VaultClient(encryption_key=custom_key)

        ref = vault.store_token("user@example.com", "service", sample_token_data)
        retrieved = vault.retrieve_token(ref)

        for key, value in sample_token_data.items():
            assert retrieved[key] == value

    def test_vault_loads_key_from_environment(
        self, sample_token_data: dict, monkeypatch
    ):
        """VaultClient should load key from VAULT_ENCRYPTION_KEY env var."""
        test_key = VaultClient.generate_encryption_key()
        monkeypatch.setenv("VAULT_ENCRYPTION_KEY", test_key)

        vault = VaultClient()  # No key argument

        ref = vault.store_token("user@example.com", "service", sample_token_data)
        retrieved = vault.retrieve_token(ref)
        for key, value in sample_token_data.items():
            assert retrieved[key] == value

    def test_vault_generates_ephemeral_key_if_none(self, sample_token_data: dict):
        """VaultClient should generate ephemeral key if none provided."""
        # Ensure env var is not set
        if "VAULT_ENCRYPTION_KEY" in os.environ:
            del os.environ["VAULT_ENCRYPTION_KEY"]

        vault = VaultClient()

        # Should still work (with ephemeral key)
        ref = vault.store_token("user@example.com", "service", sample_token_data)
        retrieved = vault.retrieve_token(ref)
        for key, value in sample_token_data.items():
            assert retrieved[key] == value


# ============================================================================
# Reference Format Tests
# ============================================================================


class TestReferenceFormat:
    """Tests for token reference format."""

    def test_reference_has_correct_prefix(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Token reference should start with vault://."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        assert ref.startswith("vault://")

    def test_reference_contains_unique_suffix(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Each reference should have a unique suffix."""
        user = "uniquetest@example.com"
        ref1 = vault.store_token(user, "notion", sample_token_data)
        ref2 = vault.store_token(user, "notion", sample_token_data)

        # Extract suffixes (last 8 chars before any trailing chars)
        suffix1 = ref1.split("-")[-1]
        suffix2 = ref2.split("-")[-1]

        assert suffix1 != suffix2

    def test_reference_is_url_safe(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Token reference should contain only URL-safe characters."""
        ref = vault.store_token("test.user+tag@example.com", "service", sample_token_data)

        # Only alphanumeric, hyphen, and some special chars
        import re
        # Allow vault://, alphanumeric, hyphens, periods, underscores
        pattern = r'^vault://[a-zA-Z0-9\-._+@]+$'
        assert re.match(pattern, ref) is not None


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_store_empty_token_data(self, vault: VaultClient):
        """Should handle empty token data."""
        ref = vault.store_token("user@example.com", "service", {})

        retrieved = vault.retrieve_token(ref)
        # Should have metadata but no token fields (except metadata)
        assert "metadata" in retrieved
        assert len([k for k in retrieved if k != "metadata"]) == 0

    def test_store_complex_token_data(self, vault: VaultClient):
        """Should handle complex nested token data."""
        complex_data = {
            "access_token": "abc",
            "token_metadata": {
                "scopes": ["read", "write"],
                "user": {"id": 123, "name": "Test"},
            },
            "numbers": [1, 2, 3],
            "boolean": True,
            "null_value": None,
        }

        ref = vault.store_token("user@example.com", "service", complex_data)
        retrieved = vault.retrieve_token(ref)

        # Check all original fields are present
        for key, value in complex_data.items():
            assert retrieved[key] == value
        # Also has metadata
        assert "metadata" in retrieved

    def test_user_id_without_at_sign(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Should handle user IDs without @ sign."""
        ref = vault.store_token("simple_user_id", "service", sample_token_data)

        assert "simple_user_id" in ref
        retrieved = vault.retrieve_token(ref)
        for key, value in sample_token_data.items():
            assert retrieved[key] == value

    def test_service_id_with_special_chars(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Should handle service IDs with special characters."""
        ref = vault.store_token("user@example.com", "my-service_v2", sample_token_data)

        assert "my-service_v2" in ref
        retrieved = vault.retrieve_token(ref)
        for key, value in sample_token_data.items():
            assert retrieved[key] == value


# ============================================================================
# Token Expiration Tests
# ============================================================================


class TestTokenExpiration:
    """Tests for token expiration tracking."""

    def test_store_with_expiration_sets_expires_at(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """store_token with expires_in should set expires_at."""
        ref = vault.store_token(
            "user@example.com", "service", sample_token_data, expires_in=3600
        )

        retrieved = vault.retrieve_token(ref)

        assert retrieved["metadata"]["expires_at"] is not None
        # Parse the ISO timestamp and verify it's ~1 hour from now
        expires_at = datetime.fromisoformat(retrieved["metadata"]["expires_at"])
        now = datetime.now(timezone.utc)
        # Should be between 59 and 61 minutes from now
        delta = expires_at - now
        assert 3500 < delta.total_seconds() < 3700

    def test_store_without_expiration_has_null_expires_at(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """store_token without expires_in should have expires_at=None."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        retrieved = vault.retrieve_token(ref)

        assert retrieved["metadata"]["expires_at"] is None

    def test_store_sets_created_at(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """store_token should set created_at timestamp."""
        before = datetime.now(timezone.utc)
        ref = vault.store_token("user@example.com", "service", sample_token_data)
        after = datetime.now(timezone.utc)

        retrieved = vault.retrieve_token(ref)

        created_at = datetime.fromisoformat(retrieved["metadata"]["created_at"])
        assert before <= created_at <= after

    def test_is_token_expired_returns_true_for_expired(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """is_token_expired should return True for expired tokens."""
        # Store with 0 second expiration (already expired)
        ref = vault.store_token(
            "user@example.com", "service", sample_token_data, expires_in=0
        )

        # Should be expired immediately
        assert vault.is_token_expired(ref) is True

    def test_is_token_expired_returns_false_for_valid(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """is_token_expired should return False for valid tokens."""
        ref = vault.store_token(
            "user@example.com", "service", sample_token_data, expires_in=3600
        )

        assert vault.is_token_expired(ref) is False

    def test_is_token_expired_returns_false_for_no_expiration(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """is_token_expired should return False for tokens with no expiration."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        assert vault.is_token_expired(ref) is False

    def test_is_token_expired_returns_false_for_nonexistent(
        self, vault: VaultClient
    ):
        """is_token_expired should return False for nonexistent tokens."""
        assert vault.is_token_expired("vault://nonexistent-abc123") is False


# ============================================================================
# Token Usage Tracking Tests
# ============================================================================


class TestUsageTracking:
    """Tests for token usage tracking."""

    def test_retrieve_updates_last_used_at(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """retrieve_token should update last_used_at when update_usage=True."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        # First retrieval
        retrieved = vault.retrieve_token(ref, update_usage=True)

        assert retrieved["metadata"]["last_used_at"] is not None

    def test_retrieve_without_update_does_not_change_last_used_at(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """retrieve_token should not update last_used_at when update_usage=False."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        # First retrieval with update
        vault.retrieve_token(ref, update_usage=True)
        first_used = vault.retrieve_token(ref, update_usage=False)["metadata"][
            "last_used_at"
        ]

        # Second retrieval without update
        import time

        time.sleep(0.01)  # Small delay
        second_used = vault.retrieve_token(ref, update_usage=False)["metadata"][
            "last_used_at"
        ]

        assert first_used == second_used

    def test_initial_last_used_at_is_none(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Newly stored tokens should have last_used_at=None."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        # Retrieve without updating usage
        retrieved = vault.retrieve_token(ref, update_usage=False)

        assert retrieved["metadata"]["last_used_at"] is None


# ============================================================================
# Token Refresh Tests
# ============================================================================


class TestRefreshToken:
    """Tests for refresh_token method."""

    def test_refresh_token_updates_access_token(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """refresh_token should update the access_token."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        result = vault.refresh_token(ref, new_access_token="new_access_token_xyz")

        assert result is True
        retrieved = vault.retrieve_token(ref)
        assert retrieved["access_token"] == "new_access_token_xyz"

    def test_refresh_token_updates_refresh_token(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """refresh_token should update refresh_token if provided."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        vault.refresh_token(
            ref,
            new_access_token="new_access",
            new_refresh_token="new_refresh_token_xyz",
        )

        retrieved = vault.retrieve_token(ref)
        assert retrieved["refresh_token"] == "new_refresh_token_xyz"

    def test_refresh_token_preserves_refresh_token_if_not_provided(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """refresh_token should keep existing refresh_token if not provided."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)
        original_refresh = sample_token_data["refresh_token"]

        vault.refresh_token(ref, new_access_token="new_access")

        retrieved = vault.retrieve_token(ref)
        assert retrieved["refresh_token"] == original_refresh

    def test_refresh_token_recalculates_expires_at(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """refresh_token should recalculate expires_at if new_expires_in provided."""
        ref = vault.store_token(
            "user@example.com", "service", sample_token_data, expires_in=60
        )
        original_expires = vault.retrieve_token(ref, update_usage=False)["metadata"][
            "expires_at"
        ]

        # Refresh with new expiration
        vault.refresh_token(ref, new_access_token="new", new_expires_in=7200)

        new_expires = vault.retrieve_token(ref, update_usage=False)["metadata"][
            "expires_at"
        ]
        assert new_expires != original_expires
        # New expiration should be ~2 hours from now
        expires_at = datetime.fromisoformat(new_expires)
        now = datetime.now(timezone.utc)
        delta = expires_at - now
        assert 7100 < delta.total_seconds() < 7300

    def test_refresh_token_increments_refresh_count(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """refresh_token should increment refresh_count."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        # First refresh
        vault.refresh_token(ref, new_access_token="access1")
        count1 = vault.retrieve_token(ref)["metadata"]["refresh_count"]

        # Second refresh
        vault.refresh_token(ref, new_access_token="access2")
        count2 = vault.retrieve_token(ref)["metadata"]["refresh_count"]

        assert count1 == 1
        assert count2 == 2

    def test_refresh_nonexistent_token_returns_false(self, vault: VaultClient):
        """refresh_token should return False for nonexistent tokens."""
        result = vault.refresh_token(
            "vault://nonexistent-abc123", new_access_token="test"
        )

        assert result is False


# ============================================================================
# Get Expiring Tokens Tests
# ============================================================================


class TestGetExpiringTokens:
    """Tests for get_expiring_tokens method."""

    def test_returns_expiring_tokens(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """get_expiring_tokens should return tokens expiring within threshold."""
        # Store token expiring in 5 minutes
        ref = vault.store_token(
            "user@example.com", "service", sample_token_data, expires_in=300
        )

        expiring = vault.get_expiring_tokens(threshold_minutes=15)

        assert ref in expiring

    def test_excludes_non_expiring_tokens(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """get_expiring_tokens should exclude tokens with longer expiration."""
        # Store token expiring in 2 hours
        ref = vault.store_token(
            "user@example.com", "service", sample_token_data, expires_in=7200
        )

        expiring = vault.get_expiring_tokens(threshold_minutes=15)

        assert ref not in expiring

    def test_excludes_no_expiration_tokens(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """get_expiring_tokens should exclude tokens with no expiration."""
        ref = vault.store_token("user@example.com", "service", sample_token_data)

        expiring = vault.get_expiring_tokens(threshold_minutes=15)

        assert ref not in expiring

    def test_returns_multiple_expiring_tokens(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """get_expiring_tokens should return all expiring tokens."""
        ref1 = vault.store_token("user1@example.com", "s1", sample_token_data, expires_in=60)
        ref2 = vault.store_token("user2@example.com", "s2", sample_token_data, expires_in=120)
        ref3 = vault.store_token("user3@example.com", "s3", sample_token_data, expires_in=7200)

        expiring = vault.get_expiring_tokens(threshold_minutes=15)

        assert ref1 in expiring
        assert ref2 in expiring
        assert ref3 not in expiring


# ============================================================================
# Token Metadata Data Classes Tests
# ============================================================================


class TestTokenMetadataDataClass:
    """Tests for TokenMetadata dataclass."""

    def test_to_dict_with_all_fields(self):
        """TokenMetadata.to_dict should serialize all fields."""
        now = datetime.now(timezone.utc)
        metadata = TokenMetadata(
            created_at=now,
            expires_at=now + timedelta(hours=1),
            last_used_at=now,
            refresh_count=5,
        )

        result = metadata.to_dict()

        assert result["created_at"] == now.isoformat()
        assert result["expires_at"] == (now + timedelta(hours=1)).isoformat()
        assert result["last_used_at"] == now.isoformat()
        assert result["refresh_count"] == 5

    def test_to_dict_with_none_fields(self):
        """TokenMetadata.to_dict should handle None fields."""
        now = datetime.now(timezone.utc)
        metadata = TokenMetadata(
            created_at=now,
            expires_at=None,
            last_used_at=None,
        )

        result = metadata.to_dict()

        assert result["created_at"] == now.isoformat()
        assert result["expires_at"] is None
        assert result["last_used_at"] is None

    def test_from_dict_roundtrip(self):
        """TokenMetadata should round-trip through to_dict/from_dict."""
        now = datetime.now(timezone.utc)
        original = TokenMetadata(
            created_at=now,
            expires_at=now + timedelta(hours=1),
            last_used_at=now,
            refresh_count=3,
        )

        restored = TokenMetadata.from_dict(original.to_dict())

        assert restored.created_at == original.created_at
        assert restored.expires_at == original.expires_at
        assert restored.last_used_at == original.last_used_at
        assert restored.refresh_count == original.refresh_count


class TestStoredTokenDataDataClass:
    """Tests for StoredTokenData dataclass."""

    def test_to_dict_serializes_correctly(self, sample_token_data: dict):
        """StoredTokenData.to_dict should serialize token and metadata."""
        now = datetime.now(timezone.utc)
        metadata = TokenMetadata(created_at=now)
        stored = StoredTokenData(token_data=sample_token_data, metadata=metadata)

        result = stored.to_dict()

        assert result["token_data"] == sample_token_data
        assert result["metadata"]["created_at"] == now.isoformat()

    def test_from_dict_handles_legacy_format(self, sample_token_data: dict):
        """StoredTokenData.from_dict should handle legacy format (no metadata wrapper)."""
        # Legacy format: just the token data, no metadata wrapper
        stored = StoredTokenData.from_dict(sample_token_data)

        assert stored.token_data == sample_token_data
        assert stored.metadata.created_at is not None
        assert stored.metadata.refresh_count == 0


# ============================================================================
# Database-Backed Tests (WS-K1: Persistent Vault)
# ============================================================================


class TestVaultClientWithDatabase:
    """Tests for VaultClient with PostgreSQL persistence.
    
    These tests verify the database-backed storage functionality added in WS-K1.
    """

    @pytest.fixture
    def vault_with_db(self) -> VaultClient:
        """Create a VaultClient with a test encryption key (for DB tests)."""
        # Reset singleton for fresh instance
        VaultClient._instance = None
        VaultClient._initialized = False
        test_key = Fernet.generate_key().decode()
        return VaultClient(encryption_key=test_key)

    @pytest.fixture
    def sample_token(self) -> dict:
        """Sample OAuth token data."""
        return {
            "access_token": "db_test_access_token",
            "refresh_token": "db_test_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

    def test_store_and_retrieve_with_db(
        self, vault_with_db: VaultClient, sample_token: dict, db
    ):
        """VaultClient should store and retrieve tokens using database."""
        ref = vault_with_db.store_token(
            "dbuser@example.com", "notion", sample_token, db=db
        )

        retrieved = vault_with_db.retrieve_token(ref, db=db)

        assert retrieved is not None
        assert retrieved["access_token"] == "db_test_access_token"
        assert retrieved["refresh_token"] == "db_test_refresh_token"
        assert "metadata" in retrieved

    def test_token_persisted_in_database(
        self, vault_with_db: VaultClient, sample_token: dict, db
    ):
        """Token should be stored in database, not just in memory."""
        from app.models.vault_token import VaultToken

        ref = vault_with_db.store_token(
            "persist@example.com", "slack", sample_token, db=db
        )

        # Verify record exists in database
        vault_token = db.query(VaultToken).filter(
            VaultToken.token_ref == ref
        ).first()

        assert vault_token is not None
        assert vault_token.user_id == "persist@example.com"
        assert vault_token.service_id == "slack"
        assert vault_token.encrypted_data is not None

    def test_delete_token_from_db(
        self, vault_with_db: VaultClient, sample_token: dict, db
    ):
        """delete_token should remove token from database."""
        ref = vault_with_db.store_token(
            "delete@example.com", "notion", sample_token, db=db
        )

        result = vault_with_db.delete_token(ref, db=db)

        assert result is True
        assert vault_with_db.retrieve_token(ref, db=db) is None

    def test_update_token_in_db(
        self, vault_with_db: VaultClient, sample_token: dict, db
    ):
        """update_token should update token data in database."""
        ref = vault_with_db.store_token(
            "update@example.com", "notion", sample_token, db=db
        )

        new_data = {"access_token": "updated_access_token"}
        result = vault_with_db.update_token(ref, new_data, db=db)

        assert result is True
        retrieved = vault_with_db.retrieve_token(ref, db=db)
        assert retrieved["access_token"] == "updated_access_token"

    def test_refresh_token_in_db(
        self, vault_with_db: VaultClient, sample_token: dict, db
    ):
        """refresh_token should update access token and increment count in DB."""
        ref = vault_with_db.store_token(
            "refresh@example.com", "notion", sample_token, db=db
        )

        result = vault_with_db.refresh_token(
            ref,
            new_access_token="refreshed_access_token",
            new_expires_in=7200,
            db=db,
        )

        assert result is True
        retrieved = vault_with_db.retrieve_token(ref, db=db)
        assert retrieved["access_token"] == "refreshed_access_token"
        assert retrieved["metadata"]["refresh_count"] == 1

    def test_token_exists_with_db(
        self, vault_with_db: VaultClient, sample_token: dict, db
    ):
        """token_exists should query database."""
        ref = vault_with_db.store_token(
            "exists@example.com", "notion", sample_token, db=db
        )

        assert vault_with_db.token_exists(ref, db=db) is True
        assert vault_with_db.token_exists("vault://nonexistent", db=db) is False

    def test_get_expiring_tokens_from_db(
        self, vault_with_db: VaultClient, sample_token: dict, db
    ):
        """get_expiring_tokens should query database for expiring tokens."""
        # Token expiring in 5 minutes
        ref1 = vault_with_db.store_token(
            "expiring1@example.com", "notion", sample_token, expires_in=300, db=db
        )
        # Token expiring in 2 hours (should not be included)
        ref2 = vault_with_db.store_token(
            "expiring2@example.com", "slack", sample_token, expires_in=7200, db=db
        )

        expiring = vault_with_db.get_expiring_tokens(threshold_minutes=15, db=db)

        assert ref1 in expiring
        assert ref2 not in expiring

    def test_is_token_expired_with_db(
        self, vault_with_db: VaultClient, sample_token: dict, db
    ):
        """is_token_expired should check expiration in database."""
        # Already expired
        ref = vault_with_db.store_token(
            "expired@example.com", "notion", sample_token, expires_in=0, db=db
        )

        assert vault_with_db.is_token_expired(ref, db=db) is True

    def test_list_tokens_for_user_with_db(
        self, vault_with_db: VaultClient, sample_token: dict, db
    ):
        """list_tokens_for_user should query database."""
        user = "listuser@example.com"
        ref1 = vault_with_db.store_token(user, "notion", sample_token, db=db)
        ref2 = vault_with_db.store_token(user, "slack", sample_token, db=db)

        refs = vault_with_db.list_tokens_for_user(user, db=db)

        assert ref1 in refs
        assert ref2 in refs

    def test_delete_user_tokens_from_db(
        self, vault_with_db: VaultClient, sample_token: dict, db
    ):
        """delete_user_tokens should delete all user tokens from database."""
        user = "deleteuser@example.com"
        vault_with_db.store_token(user, "notion", sample_token, db=db)
        vault_with_db.store_token(user, "slack", sample_token, db=db)

        count = vault_with_db.delete_user_tokens(user, db=db)

        assert count == 2
        assert vault_with_db.list_tokens_for_user(user, db=db) == []

    def test_delete_user_tokens_by_service_from_db(
        self, vault_with_db: VaultClient, sample_token: dict, db
    ):
        """delete_user_tokens should filter by service when provided."""
        user = "deletebyservice@example.com"
        ref_notion = vault_with_db.store_token(user, "notion", sample_token, db=db)
        ref_slack = vault_with_db.store_token(user, "slack", sample_token, db=db)

        count = vault_with_db.delete_user_tokens(user, service_id="notion", db=db)

        assert count == 1
        refs = vault_with_db.list_tokens_for_user(user, db=db)
        assert ref_slack in refs
        assert ref_notion not in refs

    def test_clear_all_from_db(
        self, vault_with_db: VaultClient, sample_token: dict, db
    ):
        """clear_all should delete all tokens from database."""
        vault_with_db.store_token("clear1@example.com", "notion", sample_token, db=db)
        vault_with_db.store_token("clear2@example.com", "slack", sample_token, db=db)

        count = vault_with_db.clear_all(db=db)

        assert count >= 2

    def test_usage_tracking_in_db(
        self, vault_with_db: VaultClient, sample_token: dict, db
    ):
        """retrieve_token should update last_used_at in database."""
        from app.models.vault_token import VaultToken

        ref = vault_with_db.store_token(
            "usage@example.com", "notion", sample_token, db=db
        )

        # Initial state
        vault_token = db.query(VaultToken).filter(VaultToken.token_ref == ref).first()
        assert vault_token.last_used_at is None

        # Retrieve with usage tracking
        vault_with_db.retrieve_token(ref, update_usage=True, db=db)

        # Refresh from DB
        db.refresh(vault_token)
        assert vault_token.last_used_at is not None

    def test_encryption_roundtrip_with_db(
        self, vault_with_db: VaultClient, db
    ):
        """Token data should be encrypted and decrypted correctly via DB."""
        from app.models.vault_token import VaultToken

        complex_data = {
            "access_token": "secret_token",
            "nested": {"key": "value"},
            "list": [1, 2, 3],
        }

        ref = vault_with_db.store_token(
            "encrypt@example.com", "notion", complex_data, db=db
        )

        # Verify encrypted data is not plaintext
        vault_token = db.query(VaultToken).filter(VaultToken.token_ref == ref).first()
        assert b"secret_token" not in vault_token.encrypted_data

        # Verify decryption works
        retrieved = vault_with_db.retrieve_token(ref, db=db)
        assert retrieved["access_token"] == "secret_token"
        assert retrieved["nested"]["key"] == "value"
        assert retrieved["list"] == [1, 2, 3]
