"""Client ID Metadata Document (CIMD) service.

Fetches and validates OAuth client metadata from URL-format client_id values
per draft-ietf-oauth-client-id-metadata-document.

SSRF protections: HTTPS-only, private IP blocking, public DNS resolution,
per-domain rate limiting, aggressive timeouts.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 5.0
RATE_LIMIT_PER_DOMAIN = 10
RATE_LIMIT_WINDOW_SECONDS = 60.0

PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)

LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


class CIMDError(Exception):
    """Base error for CIMD operations."""

    def __init__(self, message: str, error_code: str = "cimd_error"):
        super().__init__(message)
        self.error_code = error_code


class CIMDSSRFError(CIMDError):
    """URL rejected by SSRF protections."""

    def __init__(self, message: str):
        super().__init__(message, error_code="cimd_ssrf_blocked")


class CIMDRateLimitError(CIMDError):
    """Domain exceeded metadata fetch rate limit."""

    def __init__(self, domain: str):
        super().__init__(
            f"Rate limit exceeded for domain: {domain}",
            error_code="cimd_rate_limited",
        )


@dataclass
class ClientMetadata:
    """Parsed CIMD document."""

    client_id: str
    redirect_uris: list[str] = field(default_factory=list)
    client_name: str | None = None
    logo_uri: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClientMetadata":
        redirect_uris = data.get("redirect_uris") or []
        if isinstance(redirect_uris, str):
            redirect_uris = [redirect_uris]
        return cls(
            client_id=data.get("client_id", ""),
            redirect_uris=list(redirect_uris),
            client_name=data.get("client_name"),
            logo_uri=data.get("logo_uri"),
            raw=data,
        )


@dataclass
class AuthorizationRequest:
    """Subset of OAuth authorization request fields for CIMD validation."""

    client_id: str
    redirect_uri: str | None = None


@dataclass
class CIMDValidationResult:
    """Result of CIMD metadata validation."""

    valid: bool
    metadata: ClientMetadata | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    consent_display: dict[str, str | None] = field(default_factory=dict)


class _DomainRateLimiter:
    """In-memory sliding-window rate limiter per domain."""

    def __init__(self, max_requests: int, window_seconds: float):
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, list[float]] = {}

    def check(self, domain: str) -> None:
        now = time.monotonic()
        hits = self._hits.setdefault(domain, [])
        hits[:] = [t for t in hits if now - t < self._window]
        if len(hits) >= self._max:
            raise CIMDRateLimitError(domain)
        hits.append(now)


class CIMDService:
    """Fetch and validate Client ID Metadata Documents."""

    def __init__(
        self,
        *,
        trusted_domains: list[str] | None = None,
        blocked_domains: list[str] | None = None,
        require_trusted_domain: bool = False,
        rate_limiter: _DomainRateLimiter | None = None,
    ):
        self._trusted = {d.lower() for d in (trusted_domains or [])}
        self._blocked = {d.lower() for d in (blocked_domains or [])}
        self._require_trusted = require_trusted_domain
        self._rate_limiter = rate_limiter or _DomainRateLimiter(
            RATE_LIMIT_PER_DOMAIN, RATE_LIMIT_WINDOW_SECONDS
        )

    @staticmethod
    def is_url_client_id(client_id: str) -> bool:
        """Return True when client_id is an HTTPS metadata URL."""
        if not client_id:
            return False
        parsed = urlparse(client_id)
        return parsed.scheme == "https" and bool(parsed.netloc)

    def validate_url_safe(self, url: str) -> None:
        """Reject URLs that could target internal networks (SSRF)."""
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise CIMDSSRFError("client_id URL must use HTTPS")

        host = parsed.hostname
        if not host:
            raise CIMDSSRFError("client_id URL has no hostname")

        host_lower = host.lower()
        if host_lower in self._blocked:
            raise CIMDSSRFError(f"Domain blocked: {host}")

        if self._require_trusted and host_lower not in self._trusted:
            raise CIMDSSRFError(f"Domain not in trusted allowlist: {host}")

        # Literal IP check
        try:
            addr = ipaddress.ip_address(host)
            for network in PRIVATE_NETWORKS:
                if addr in network:
                    raise CIMDSSRFError("client_id URL resolves to private/reserved IP")
        except ValueError:
            pass  # hostname — resolve below

        # DNS resolution must yield public IPs only
        try:
            infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        except socket.gaierror as e:
            raise CIMDSSRFError(f"DNS resolution failed for {host}") from e

        for info in infos:
            ip_str = info[4][0]
            try:
                addr = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            for network in PRIVATE_NETWORKS:
                if addr in network:
                    raise CIMDSSRFError(
                        f"DNS for {host} resolved to non-public IP: {ip_str}"
                    )

        domain = host_lower
        self._rate_limiter.check(domain)

    async def fetch_client_metadata(self, client_id_url: str) -> ClientMetadata:
        """HTTP GET the CIMD document at client_id_url."""
        if not self.is_url_client_id(client_id_url):
            raise CIMDError(
                "client_id must be an HTTPS URL for CIMD",
                error_code="invalid_client_id_format",
            )

        self.validate_url_safe(client_id_url)

        try:
            async with httpx.AsyncClient(
                timeout=FETCH_TIMEOUT_SECONDS,
                follow_redirects=False,
            ) as client:
                response = await client.get(client_id_url)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            raise CIMDError(
                f"Metadata fetch failed: HTTP {e.response.status_code}",
                error_code="metadata_fetch_failed",
            ) from e
        except httpx.RequestError as e:
            raise CIMDError(
                f"Metadata fetch failed: {e}",
                error_code="metadata_fetch_failed",
            ) from e
        except ValueError as e:
            raise CIMDError(
                "Metadata response is not valid JSON",
                error_code="invalid_metadata_json",
            ) from e

        if not isinstance(data, dict):
            raise CIMDError(
                "Metadata document must be a JSON object",
                error_code="invalid_metadata_format",
            )

        metadata = ClientMetadata.from_dict(data)
        if metadata.client_id != client_id_url:
            raise CIMDError(
                "client_id in metadata must exactly match the fetch URL",
                error_code="client_id_mismatch",
            )

        return metadata

    def validate_client_metadata(
        self,
        metadata: ClientMetadata,
        request: AuthorizationRequest,
    ) -> CIMDValidationResult:
        """Validate fetched metadata against an authorization request."""
        errors: list[str] = []
        warnings: list[str] = []

        if metadata.client_id != request.client_id:
            errors.append("client_id mismatch between metadata and request")

        if request.redirect_uri:
            if request.redirect_uri not in metadata.redirect_uris:
                errors.append(
                    f"redirect_uri not in metadata allowlist: {request.redirect_uri}"
                )
            redirect_host = urlparse(request.redirect_uri).hostname or ""
            if redirect_host.lower() in LOOPBACK_HOSTS or redirect_host.startswith(
                "127."
            ):
                warnings.append(
                    f"redirect_uri uses loopback host ({redirect_host}) — development client"
                )

        for uri in metadata.redirect_uris:
            host = (urlparse(uri).hostname or "").lower()
            if host in LOOPBACK_HOSTS or host.startswith("127."):
                warnings.append(
                    f"metadata redirect_uri uses loopback host ({host})"
                )

        consent_display = {
            "client_name": metadata.client_name,
            "logo_uri": metadata.logo_uri,
            "client_id": metadata.client_id,
        }

        return CIMDValidationResult(
            valid=len(errors) == 0,
            metadata=metadata,
            errors=errors,
            warnings=warnings,
            consent_display=consent_display,
        )

    async def resolve_and_validate(
        self,
        request: AuthorizationRequest,
    ) -> CIMDValidationResult:
        """Fetch CIMD (when URL client_id) and validate against the request."""
        if not self.is_url_client_id(request.client_id):
            return CIMDValidationResult(
                valid=False,
                errors=["client_id is not a URL — CIMD not applicable"],
            )

        try:
            metadata = await self.fetch_client_metadata(request.client_id)
        except CIMDError as e:
            return CIMDValidationResult(valid=False, errors=[str(e)])

        return self.validate_client_metadata(metadata, request)
