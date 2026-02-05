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
"""

import json
import os
import uuid

import pytest
from cryptography.fernet import Fernet

from app.services.vault_client import (
    DecryptionError,
    VaultClient,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def vault() -> VaultClient:
    """Create a VaultClient with a test encryption key."""
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
        """retrieve_token should return the exact data that was stored."""
        ref = vault.store_token("user@example.com", "slack", sample_token_data)

        retrieved = vault.retrieve_token(ref)

        assert retrieved == sample_token_data

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
        assert vault.retrieve_token(ref1) == sample_token_data
        assert vault.retrieve_token(ref2) == sample_token_data

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
        assert vault.retrieve_token(ref1) == sample_token_data
        assert vault.retrieve_token(ref2) == sample_token_data


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

        # Create a new vault with different key
        other_key = Fernet.generate_key().decode()
        other_vault = VaultClient(encryption_key=other_key)

        # Transfer the encrypted data (simulating storage access)
        other_vault._storage[ref] = vault._storage[ref]

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
        assert vault.retrieve_token(ref) == new_data

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
        assert vault.retrieve_token(ref) == new_data


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

        assert retrieved == sample_token_data

    def test_vault_loads_key_from_environment(
        self, sample_token_data: dict, monkeypatch
    ):
        """VaultClient should load key from VAULT_ENCRYPTION_KEY env var."""
        test_key = VaultClient.generate_encryption_key()
        monkeypatch.setenv("VAULT_ENCRYPTION_KEY", test_key)

        vault = VaultClient()  # No key argument

        ref = vault.store_token("user@example.com", "service", sample_token_data)
        assert vault.retrieve_token(ref) == sample_token_data

    def test_vault_generates_ephemeral_key_if_none(self, sample_token_data: dict):
        """VaultClient should generate ephemeral key if none provided."""
        # Ensure env var is not set
        if "VAULT_ENCRYPTION_KEY" in os.environ:
            del os.environ["VAULT_ENCRYPTION_KEY"]

        vault = VaultClient()

        # Should still work (with ephemeral key)
        ref = vault.store_token("user@example.com", "service", sample_token_data)
        assert vault.retrieve_token(ref) == sample_token_data


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

        assert vault.retrieve_token(ref) == {}

    def test_store_complex_token_data(self, vault: VaultClient):
        """Should handle complex nested token data."""
        complex_data = {
            "access_token": "abc",
            "metadata": {
                "scopes": ["read", "write"],
                "user": {"id": 123, "name": "Test"},
            },
            "numbers": [1, 2, 3],
            "boolean": True,
            "null_value": None,
        }

        ref = vault.store_token("user@example.com", "service", complex_data)
        retrieved = vault.retrieve_token(ref)

        assert retrieved == complex_data

    def test_user_id_without_at_sign(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Should handle user IDs without @ sign."""
        ref = vault.store_token("simple_user_id", "service", sample_token_data)

        assert "simple_user_id" in ref
        assert vault.retrieve_token(ref) == sample_token_data

    def test_service_id_with_special_chars(
        self, vault: VaultClient, sample_token_data: dict
    ):
        """Should handle service IDs with special characters."""
        ref = vault.store_token("user@example.com", "my-service_v2", sample_token_data)

        assert "my-service_v2" in ref
        assert vault.retrieve_token(ref) == sample_token_data
