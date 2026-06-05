"""Tests for the KMS client (Fernet fallback path).

GCP KMS is mocked; Fernet path tested with a real key.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from app.core.kms import KMSClient, get_kms_client, reset_kms_client


@pytest.fixture(autouse=True)
def _reset():
    reset_kms_client()
    yield
    reset_kms_client()


class TestFernetBackend:
    def test_encrypt_decrypt_roundtrip(self):
        key = Fernet.generate_key().decode()
        client = KMSClient(fernet_key=key)
        assert client.backend == "fernet"

        plaintext = "super-secret-api-key-12345"
        ciphertext = client.encrypt(plaintext)
        assert ciphertext != plaintext

        decrypted = client.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_decrypt_wrong_key_raises(self):
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()
        client1 = KMSClient(fernet_key=key1)
        client2 = KMSClient(fernet_key=key2)

        ciphertext = client1.encrypt("secret")
        with pytest.raises(ValueError, match="invalid token or wrong key"):
            client2.decrypt(ciphertext)

    def test_empty_string_encrypt_decrypt(self):
        key = Fernet.generate_key().decode()
        client = KMSClient(fernet_key=key)
        ciphertext = client.encrypt("")
        assert client.decrypt(ciphertext) == ""

    def test_unicode_encrypt_decrypt(self):
        key = Fernet.generate_key().decode()
        client = KMSClient(fernet_key=key)
        plaintext = "secret-with-unicode-\u2603-\U0001f600"
        assert client.decrypt(client.encrypt(plaintext)) == plaintext


class TestNoBackend:
    def test_encrypt_raises_when_no_backend(self):
        client = KMSClient()
        assert client.backend == "none"
        with pytest.raises(RuntimeError, match="No encryption backend"):
            client.encrypt("test")

    def test_decrypt_raises_when_no_backend(self):
        client = KMSClient()
        with pytest.raises(RuntimeError, match="No encryption backend"):
            client.decrypt("test")


class TestSingleton:
    def test_get_kms_client_returns_same_instance(self):
        os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
        try:
            c1 = get_kms_client()
            c2 = get_kms_client()
            assert c1 is c2
        finally:
            del os.environ["FERNET_KEY"]

    def test_reset_clears_singleton(self):
        os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
        try:
            c1 = get_kms_client()
            reset_kms_client()
            c2 = get_kms_client()
            assert c1 is not c2
        finally:
            del os.environ["FERNET_KEY"]


class TestGCPKMSBackend:
    @patch("app.core.kms._GCP_KMS_AVAILABLE", True)
    @patch("app.core.kms.kms", create=True)
    def test_gcp_backend_selected_when_project_set(self, mock_kms_module):
        mock_client = MagicMock()
        mock_kms_module.KeyManagementServiceClient.return_value = mock_client
        mock_client.crypto_key_path.return_value = "projects/p/locations/l/keyRings/kr/cryptoKeys/k"

        client = KMSClient(gcp_project="test-project")
        assert client.backend == "gcp-kms"

    @patch("app.core.kms._GCP_KMS_AVAILABLE", True)
    @patch("app.core.kms.kms", create=True)
    def test_gcp_encrypt_calls_kms(self, mock_kms_module):
        import base64
        mock_client = MagicMock()
        mock_kms_module.KeyManagementServiceClient.return_value = mock_client
        mock_client.crypto_key_path.return_value = "projects/p/locations/l/keyRings/kr/cryptoKeys/k"
        mock_client.encrypt.return_value = MagicMock(ciphertext=b"encrypted-bytes")

        client = KMSClient(gcp_project="test-project")
        result = client.encrypt("plaintext")

        mock_client.encrypt.assert_called_once()
        assert result == base64.b64encode(b"encrypted-bytes").decode("ascii")

    @patch("app.core.kms._GCP_KMS_AVAILABLE", True)
    @patch("app.core.kms.kms", create=True)
    def test_gcp_decrypt_calls_kms(self, mock_kms_module):
        import base64
        mock_client = MagicMock()
        mock_kms_module.KeyManagementServiceClient.return_value = mock_client
        mock_client.crypto_key_path.return_value = "projects/p/locations/l/keyRings/kr/cryptoKeys/k"
        mock_client.decrypt.return_value = MagicMock(plaintext=b"plaintext")

        client = KMSClient(gcp_project="test-project")
        ciphertext = base64.b64encode(b"encrypted-bytes").decode("ascii")
        result = client.decrypt(ciphertext)

        mock_client.decrypt.assert_called_once()
        assert result == "plaintext"
