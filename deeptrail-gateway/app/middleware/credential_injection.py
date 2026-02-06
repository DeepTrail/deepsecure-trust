"""
Credential Injection for Backend Tool Calls.

Retrieves OAuth tokens from the vault and injects them into backend requests.
This is the core security mechanism ensuring agents never see user credentials.

This implements:
- Demo 3: Delegation Execution
- Step 8 of Sarah's Journey

Security Principles:
- Just-in-time retrieval: Token fetched only when needed
- No token exposure: Agent never sees the OAuth token
- Fail-closed: Request denied if token unavailable
- No token logging: Token values never in logs

Usage:
    from app.middleware.credential_injection import CredentialInjector
    
    injector = CredentialInjector()
    
    # In tools/call handler, after permission validation
    result = await injector.inject_credentials(
        credential_ref="vault://sarah-notion-abc123",
        backend_id="notion",
    )
    
    if result.success:
        auth_headers = result.headers
        # Forward request with auth_headers
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class InjectionError(Enum):
    """
    Reasons for credential injection failure.
    
    Used for structured error reporting and handling.
    """
    NO_CREDENTIAL_REF = "no_credential_ref"
    TOKEN_NOT_FOUND = "token_not_found"
    TOKEN_EXPIRED = "token_expired"
    REFRESH_FAILED = "refresh_failed"
    VAULT_ERROR = "vault_error"
    INJECTION_ERROR = "injection_error"


@dataclass
class InjectionResult:
    """
    Result of credential injection.
    
    Provides structured information about whether credential injection
    succeeded and the authorization headers to use.
    
    Security Note:
        - Returns ONLY headers, not raw token values
        - Error messages are user-friendly, no token details
    
    Attributes:
        success: Whether injection succeeded
        headers: Authorization headers for the backend request
        error: Why injection failed (if not successful)
        error_message: Human-readable error message (if not successful)
    """
    success: bool
    headers: dict[str, str] | None = None
    error: InjectionError | None = None
    error_message: str | None = None
    
    @classmethod
    def ok(cls, headers: dict[str, str]) -> "InjectionResult":
        """
        Create a successful injection result.
        
        Args:
            headers: Authorization headers for the backend
            
        Returns:
            InjectionResult with success=True
        """
        return cls(success=True, headers=headers)
    
    @classmethod
    def fail(cls, error: InjectionError, message: str) -> "InjectionResult":
        """
        Create a failed injection result.
        
        Args:
            error: Why injection failed
            message: User-friendly error message
            
        Returns:
            InjectionResult with success=False
        """
        return cls(success=False, error=error, error_message=message)


# =============================================================================
# CredentialInjector Class
# =============================================================================


class CredentialInjector:
    """
    Injects OAuth credentials into backend requests.
    
    Responsibilities:
    1. Retrieve OAuth token from vault using credential_ref
    2. Format appropriate auth header for backend
    3. Handle token expiration and refresh
    4. NEVER expose token to agent or logs
    
    Security:
    - Fail-closed: No token = request denied
    - Just-in-time: Token retrieved only when needed
    - No logging of token values
    - Brief caching to reduce vault calls (configurable TTL)
    
    Example:
        >>> injector = CredentialInjector()
        >>> result = await injector.inject_credentials(
        ...     credential_ref="vault://sarah-notion-abc123",
        ...     backend_id="notion",
        ... )
        >>> if result.success:
        ...     # Use result.headers for backend request
        ...     pass
    """
    
    def __init__(
        self,
        control_plane_url: str | None = None,
        cache_ttl_seconds: int = 60,
    ):
        """
        Initialize the credential injector.
        
        Args:
            control_plane_url: URL to Control Plane for vault access
            cache_ttl_seconds: How long to cache tokens (short-lived for security)
        """
        self.control_plane_url = control_plane_url
        self.cache_ttl_seconds = cache_ttl_seconds
        # Brief cache: credential_ref -> (token_data, cached_at)
        self._token_cache: dict[str, tuple[dict[str, Any], float]] = {}
    
    async def inject_credentials(
        self,
        credential_ref: str | None,
        backend_id: str,
    ) -> InjectionResult:
        """
        Get authorization headers for a backend request.
        
        This is the main entry point for credential injection. It:
        1. Validates the credential reference exists
        2. Retrieves the token from the vault
        3. Handles token expiration/refresh
        4. Returns properly formatted authorization headers
        
        Args:
            credential_ref: Vault reference (e.g., "vault://sarah-notion-abc123")
            backend_id: Backend identifier for formatting headers
            
        Returns:
            InjectionResult with headers or error
            
        Security:
            - Returns ONLY headers, not raw token
            - Agent receives error message, not token details
            - Token values never appear in logs
        """
        # Step 1: Validate credential reference exists (fail-closed)
        if not credential_ref:
            logger.warning(
                "Credential injection failed: no credential_ref for backend %s",
                backend_id,
            )
            return InjectionResult.fail(
                InjectionError.NO_CREDENTIAL_REF,
                "No credential configured for this backend"
            )
        
        # Step 2: Retrieve token from vault
        token_data = await self._get_token(credential_ref)
        
        if token_data is None:
            # Log partial ref only for security
            ref_preview = credential_ref[:20] if len(credential_ref) > 20 else credential_ref
            logger.warning(
                "Token not found for credential_ref: %s... (backend: %s)",
                ref_preview,
                backend_id,
            )
            return InjectionResult.fail(
                InjectionError.TOKEN_NOT_FOUND,
                "Credential not found. User may need to re-authorize."
            )
        
        # Step 3: Check if token expired and needs refresh
        if self._is_token_expired(token_data):
            logger.info(
                "Token expired, attempting refresh for backend %s",
                backend_id,
            )
            refreshed = await self._refresh_token(credential_ref, token_data)
            
            if refreshed is None:
                return InjectionResult.fail(
                    InjectionError.REFRESH_FAILED,
                    "Session expired. User needs to re-authorize."
                )
            
            token_data = refreshed
        
        # Step 4: Format auth headers for this backend
        headers = self._format_auth_headers(token_data, backend_id)
        
        # Log success without exposing token
        ref_preview = credential_ref[:20] if len(credential_ref) > 20 else credential_ref
        logger.debug(
            "Credentials injected for backend %s (ref: %s...)",
            backend_id,
            ref_preview,
        )
        
        return InjectionResult.ok(headers)
    
    async def _get_token(
        self,
        credential_ref: str,
    ) -> dict[str, Any] | None:
        """
        Retrieve token from vault (with brief caching).
        
        Args:
            credential_ref: Vault reference
            
        Returns:
            Token data dict or None if not found
        """
        now = time.time()
        
        # Check cache first (brief TTL for security)
        if credential_ref in self._token_cache:
            token_data, cached_at = self._token_cache[credential_ref]
            if now - cached_at < self.cache_ttl_seconds:
                logger.debug("Token cache hit for credential_ref")
                return token_data
        
        # Fetch from vault
        token_data = await self._fetch_from_vault(credential_ref)
        
        if token_data:
            # Cache briefly
            self._token_cache[credential_ref] = (token_data, now)
        
        return token_data
    
    async def _fetch_from_vault(
        self,
        credential_ref: str,
    ) -> dict[str, Any] | None:
        """
        Fetch token from vault (Control Plane API or local vault).
        
        MVP: Uses mock token response
        Production: HashiCorp Vault, AWS Secrets Manager, etc.
        
        Args:
            credential_ref: Vault reference (e.g., "vault://sarah-notion-abc123")
            
        Returns:
            Token data or None
        """
        if not self.control_plane_url:
            # MVP: Return mock token for testing
            # SECURITY: This mock token simulates what production would return
            # but is never exposed to the agent
            logger.debug("MVP mode: returning mock token")
            return {
                "access_token": "mock_access_token_never_exposed_to_agent",
                "token_type": "Bearer",
                "expires_in": 3600,
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.control_plane_url}/api/v1/vault/tokens/{credential_ref}",
                    timeout=5.0,
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    return None
                else:
                    logger.error(
                        "Vault returned status %d for token fetch",
                        response.status_code,
                    )
                    return None
                    
        except httpx.TimeoutException:
            logger.error("Vault fetch timeout for credential")
            return None
        except Exception as e:
            # Log error without credential details
            logger.error("Vault fetch error: %s", type(e).__name__)
            return None
    
    def _is_token_expired(self, token_data: dict[str, Any]) -> bool:
        """
        Check if OAuth token is expired.
        
        Args:
            token_data: Token data with optional expires_at or expires_in
            
        Returns:
            True if token is expired or about to expire (within 5 min buffer)
        """
        expires_at = token_data.get("expires_at")
        
        if expires_at:
            # Buffer: consider expired if within 5 minutes of expiration
            buffer = 300  # 5 minutes
            return time.time() > (expires_at - buffer)
        
        # If no expiration info, assume valid
        return False
    
    async def _refresh_token(
        self,
        credential_ref: str,
        token_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Refresh an expired OAuth token.
        
        MVP: Returns None (refresh not implemented)
        Production: Calls OAuth refresh endpoint via Control Plane
        
        Args:
            credential_ref: Vault reference
            token_data: Current token data with refresh_token
            
        Returns:
            New token data or None if refresh failed
        """
        refresh_token = token_data.get("refresh_token")
        
        if not refresh_token:
            logger.warning("No refresh_token available for token refresh")
            return None
        
        if not self.control_plane_url:
            # MVP: Don't implement refresh
            logger.info("MVP mode: token refresh not implemented")
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.control_plane_url}/api/v1/vault/tokens/{credential_ref}/refresh",
                    timeout=10.0,
                )
                
                if response.status_code == 200:
                    new_token = response.json()
                    # Invalidate cache
                    self._token_cache.pop(credential_ref, None)
                    logger.info("Token refresh successful")
                    return new_token
                else:
                    logger.error(
                        "Token refresh failed with status %d",
                        response.status_code,
                    )
                    return None
                    
        except httpx.TimeoutException:
            logger.error("Token refresh timeout")
            return None
        except Exception as e:
            logger.error("Token refresh error: %s", type(e).__name__)
            return None
    
    def _format_auth_headers(
        self,
        token_data: dict[str, Any],
        backend_id: str,
    ) -> dict[str, str]:
        """
        Format authorization headers for the backend.
        
        Different backends may require different header formats:
        - Most: Authorization: Bearer <token>
        - Some: X-API-Key: <token>
        - Custom: Backend-specific headers
        
        Args:
            token_data: Token data with access_token
            backend_id: Backend identifier for format selection
            
        Returns:
            Headers dict ready to merge into request
            
        Security:
            - ONLY returns headers dict, not raw token
            - Headers are what get sent to backend, nothing more
        """
        access_token = token_data.get("access_token", "")
        token_type = token_data.get("token_type", "Bearer")
        
        # Backend-specific header formatting
        # Most OAuth APIs use Bearer token
        if backend_id in ("notion", "slack", "hubspot", "google"):
            return {
                "Authorization": f"{token_type} {access_token}"
            }
        
        # Some APIs use API key header
        if backend_id in ("sendgrid", "mailchimp"):
            return {
                "X-API-Key": access_token
            }
        
        # Default: Standard OAuth Bearer token format
        return {
            "Authorization": f"{token_type} {access_token}"
        }
    
    def clear_cache(self) -> None:
        """Clear the token cache."""
        self._token_cache.clear()
        logger.debug("Token cache cleared")
    
    def invalidate_credential(self, credential_ref: str) -> None:
        """
        Invalidate a cached credential.
        
        Call when a token is revoked or user disconnects.
        
        Args:
            credential_ref: Vault reference to invalidate
        """
        self._token_cache.pop(credential_ref, None)
        logger.debug("Credential invalidated from cache")
    
    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics for monitoring."""
        return {
            "cached_credentials": len(self._token_cache),
            "cache_ttl_seconds": self.cache_ttl_seconds,
        }


# =============================================================================
# Module-Level Configuration
# =============================================================================


# Singleton instance for handler use
_injector: CredentialInjector | None = None


def get_credential_injector() -> CredentialInjector:
    """
    Get the configured credential injector.
    
    Returns the singleton injector instance, creating it with
    defaults if not configured.
    
    Returns:
        CredentialInjector instance
    """
    global _injector
    if _injector is None:
        _injector = CredentialInjector()
    return _injector


def configure_credential_injector(
    control_plane_url: str | None = None,
    cache_ttl_seconds: int = 60,
) -> CredentialInjector:
    """
    Configure and return the credential injector.
    
    Args:
        control_plane_url: URL to Control Plane for vault access
        cache_ttl_seconds: Cache TTL for tokens
        
    Returns:
        Configured CredentialInjector instance
    """
    global _injector
    _injector = CredentialInjector(
        control_plane_url=control_plane_url,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    logger.info(
        "Credential injector configured: control_plane_url=%s",
        control_plane_url or "None (MVP mode)",
    )
    return _injector


def reset_credential_injector() -> None:
    """Reset the credential injector (for testing)."""
    global _injector
    _injector = None


# =============================================================================
# Convenience Functions
# =============================================================================


async def inject_credentials(
    credential_ref: str | None,
    backend_id: str,
) -> InjectionResult:
    """
    Convenience function to inject credentials.
    
    Uses the configured singleton injector.
    
    Args:
        credential_ref: Vault reference
        backend_id: Backend identifier
        
    Returns:
        InjectionResult
    """
    injector = get_credential_injector()
    return await injector.inject_credentials(credential_ref, backend_id)
