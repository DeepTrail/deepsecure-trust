"""Tests for CIMD (Client ID Metadata Document) service."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.cimd_service import (
    AuthorizationRequest,
    CIMDError,
    CIMDService,
    CIMDSSRFError,
    ClientMetadata,
)


class TestCIMDURLDetection:
    def test_url_client_id(self):
        assert CIMDService.is_url_client_id(
            "https://myapp.example.com/.well-known/oauth-client"
        )

    def test_non_url_client_id(self):
        assert not CIMDService.is_url_client_id("my-client-id")
        assert not CIMDService.is_url_client_id("http://insecure.example.com/client")


class TestSSRFProtection:
    def test_rejects_http(self):
        svc = CIMDService()
        with pytest.raises(CIMDSSRFError, match="HTTPS"):
            svc.validate_url_safe("http://example.com/client")

    def test_rejects_private_ip_literal(self):
        svc = CIMDService()
        with pytest.raises(CIMDSSRFError):
            svc.validate_url_safe("https://127.0.0.1/client")

    def test_rejects_blocked_domain(self):
        svc = CIMDService(blocked_domains=["evil.example.com"])
        with pytest.raises(CIMDSSRFError, match="blocked"):
            svc.validate_url_safe("https://evil.example.com/client")

    @patch("socket.getaddrinfo")
    def test_rejects_private_dns_resolution(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("10.0.0.5", 0)),
        ]
        svc = CIMDService()
        with pytest.raises(CIMDSSRFError, match="non-public"):
            svc.validate_url_safe("https://metadata.example.com/client")


class TestFetchClientMetadata:
    @pytest.mark.asyncio
    async def test_fetch_success(self):
        svc = CIMDService()
        url = "https://myapp.example.com/.well-known/oauth-client"
        payload = {
            "client_id": url,
            "redirect_uris": ["https://myapp.example.com/callback"],
            "client_name": "My App",
        }

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = payload

        with patch.object(svc, "validate_url_safe"), patch(
            "httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            metadata = await svc.fetch_client_metadata(url)

        assert metadata.client_name == "My App"
        assert metadata.client_id == url

    @pytest.mark.asyncio
    async def test_rejects_client_id_mismatch(self):
        svc = CIMDService()
        url = "https://myapp.example.com/.well-known/oauth-client"
        payload = {
            "client_id": "https://other.example.com/client",
            "redirect_uris": [],
        }

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = payload

        with patch.object(svc, "validate_url_safe"), patch(
            "httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(CIMDError, match="exactly match"):
                await svc.fetch_client_metadata(url)


class TestValidateClientMetadata:
    def test_valid_redirect_uri(self):
        svc = CIMDService()
        url = "https://myapp.example.com/.well-known/oauth-client"
        metadata = ClientMetadata(
            client_id=url,
            redirect_uris=["https://myapp.example.com/callback"],
            client_name="My App",
        )
        result = svc.validate_client_metadata(
            metadata,
            AuthorizationRequest(
                client_id=url,
                redirect_uri="https://myapp.example.com/callback",
            ),
        )
        assert result.valid
        assert result.consent_display["client_name"] == "My App"

    def test_invalid_redirect_uri(self):
        svc = CIMDService()
        url = "https://myapp.example.com/.well-known/oauth-client"
        metadata = ClientMetadata(
            client_id=url,
            redirect_uris=["https://myapp.example.com/callback"],
        )
        result = svc.validate_client_metadata(
            metadata,
            AuthorizationRequest(
                client_id=url,
                redirect_uri="https://evil.example.com/callback",
            ),
        )
        assert not result.valid
        assert any("redirect_uri" in e for e in result.errors)

    def test_localhost_redirect_warning(self):
        svc = CIMDService()
        url = "https://myapp.example.com/.well-known/oauth-client"
        metadata = ClientMetadata(
            client_id=url,
            redirect_uris=["http://localhost:3000/callback"],
        )
        result = svc.validate_client_metadata(
            metadata,
            AuthorizationRequest(
                client_id=url,
                redirect_uri="http://localhost:3000/callback",
            ),
        )
        assert result.valid
        assert any("loopback" in w for w in result.warnings)
