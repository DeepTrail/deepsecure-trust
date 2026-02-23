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
        internal_api_token: str | None = None,
    ):
        """
        Initialize the credential injector.

        Args:
            control_plane_url: URL to Control Plane for vault access
            cache_ttl_seconds: How long to cache tokens (short-lived for security)
            internal_api_token: Internal API token for Gateway-to-Control calls (E3 refresh)
        """
        self.control_plane_url = control_plane_url
        self.cache_ttl_seconds = cache_ttl_seconds
        self.internal_api_token = internal_api_token
        # Brief cache: credential_ref -> (token_data, cached_at)
        self._token_cache: dict[str, tuple[dict[str, Any], float]] = {}
        # Track token_ref -> (user_id, service_id) for user+service invalidation
        self._ref_to_user_service: dict[str, tuple[str, str]] = {}
    
    async def inject_credentials(
        self,
        credential_ref: str | None,
        backend_id: str,
        agent_jwt_token: str | None = None,
        user_id: str | None = None,
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
            agent_jwt_token: Raw Agent JWT for E2 vault API auth
            user_id: User ID (owner) for E3 token refresh

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
        token_data = await self._get_token(
            credential_ref, backend_id, agent_jwt_token, user_id
        )

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
            refreshed = await self._refresh_token(
                credential_ref, token_data, backend_id, user_id
            )
            
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
        backend_id: str = "",
        agent_jwt_token: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Retrieve token from vault (with brief caching).

        Args:
            credential_ref: Vault reference
            backend_id: Service identifier (e.g., "notion") for E2 URL
            agent_jwt_token: Raw Agent JWT for E2 auth
            user_id: User ID for tracking (enables user+service cache invalidation)

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
        token_data = await self._fetch_from_vault(
            credential_ref, backend_id, agent_jwt_token
        )
        
        if token_data:
            # Cache briefly
            self._token_cache[credential_ref] = (token_data, now)
            # Track for user+service invalidation
            if user_id and backend_id:
                self._ref_to_user_service[credential_ref] = (user_id, backend_id)
        
        return token_data
    
    async def _fetch_from_vault(
        self,
        credential_ref: str,
        backend_id: str = "",
        agent_jwt_token: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Fetch token from Control Plane vault API (E2 endpoint).

        MVP: Uses mock token response when control_plane_url is None.
        Production: Calls GET /api/v1/vault/tokens/{service_id} with Agent JWT.

        Args:
            credential_ref: Vault reference (e.g., "vault://sarah-notion-abc123")
            backend_id: Service identifier (e.g., "notion") for E2 URL path
            agent_jwt_token: Raw Agent JWT for Authorization header

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

        # Production: Call Control Plane E2 endpoint
        if not agent_jwt_token:
            logger.error(
                "No agent JWT available for vault fetch (service: %s)", backend_id
            )
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.control_plane_url}/api/v1/vault/tokens/{backend_id}",
                    headers={"Authorization": f"Bearer {agent_jwt_token}"},
                    timeout=5.0,
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 403:
                    logger.warning(
                        "Vault 403: service %s not delegated", backend_id
                    )
                    return None
                elif response.status_code == 404:
                    logger.warning(
                        "Vault 404: service %s not connected", backend_id
                    )
                    return None
                else:
                    logger.error(
                        "Vault status %d for service %s",
                        response.status_code,
                        backend_id,
                    )
                    return None

        except httpx.TimeoutException:
            logger.error("Vault fetch timeout for service %s", backend_id)
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
        backend_id: str = "",
        user_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Refresh an expired OAuth token via Control Plane E3 endpoint.

        MVP: Returns None (refresh not implemented) when control_plane_url is None.
        Production: Calls POST /api/v1/vault/tokens/{service_id}/refresh with
                    internal API token and X-User-ID header.

        Args:
            credential_ref: Vault reference
            token_data: Current token data with refresh_token
            backend_id: Service identifier (e.g., "notion") for E3 URL path
            user_id: User email for X-User-ID header

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

        # Production: Call Control Plane E3 endpoint
        if not self.internal_api_token:
            logger.error("No internal API token configured for token refresh")
            return None

        if not user_id:
            logger.error("No user_id available for token refresh")
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.control_plane_url}/api/v1/vault/tokens/{backend_id}/refresh",
                    headers={
                        "Authorization": f"Bearer {self.internal_api_token}",
                        "X-User-ID": user_id,
                    },
                    json={"force": False},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    new_token = response.json()
                    # Invalidate cache
                    self._token_cache.pop(credential_ref, None)
                    logger.info("Token refresh successful for service %s", backend_id)
                    return new_token
                elif response.status_code == 400:
                    logger.warning(
                        "Token refresh 400: no refresh token for %s", backend_id
                    )
                    return None
                elif response.status_code == 404:
                    logger.warning(
                        "Token refresh 404: service %s not connected", backend_id
                    )
                    return None
                elif response.status_code == 502:
                    logger.error(
                        "Token refresh 502: provider error for %s", backend_id
                    )
                    return None
                else:
                    logger.error(
                        "Token refresh status %d for %s",
                        response.status_code,
                        backend_id,
                    )
                    return None

        except httpx.TimeoutException:
            logger.error("Token refresh timeout for service %s", backend_id)
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
        
        # Normalize token_type to title case (Bearer, not bearer)
        # Most OAuth APIs expect "Bearer" with capital B
        if token_type.lower() == "bearer":
            token_type = "Bearer"
        
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
        """Clear the entire token cache (e.g., on Control Plane restart)."""
        count = len(self._token_cache)
        self._token_cache.clear()
        self._ref_to_user_service.clear()
        logger.info(f"Cleared credential cache: {count} entries")
    
    def invalidate_credential(self, credential_ref: str) -> None:
        """
        Invalidate a cached credential.
        
        Call when a token is revoked or user disconnects.
        
        Args:
            credential_ref: Vault reference to invalidate
        """
        if credential_ref in self._token_cache:
            self._token_cache.pop(credential_ref, None)
            self._ref_to_user_service.pop(credential_ref, None)
            logger.debug("Credential invalidated from cache")
    
    def invalidate_user_service(self, user_id: str, service_id: str) -> None:
        """
        Invalidate all cached tokens for a user+service combination.
        
        Called when a user disconnects a service. All tokens for that
        user+service pair are removed from cache.
        
        Args:
            user_id: User identifier
            service_id: Service identifier (e.g., "notion")
        """
        refs_to_remove = [
            ref for ref, (uid, sid) in self._ref_to_user_service.items()
            if uid == user_id and sid == service_id
        ]
        for ref in refs_to_remove:
            self._token_cache.pop(ref, None)
            self._ref_to_user_service.pop(ref, None)
        
        if refs_to_remove:
            logger.info(
                f"Invalidated {len(refs_to_remove)} cached tokens for "
                f"user={user_id} service={service_id}"
            )
    
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
    internal_api_token: str | None = None,
) -> CredentialInjector:
    """
    Configure and return the credential injector.

    Args:
        control_plane_url: URL to Control Plane for vault access
        cache_ttl_seconds: Cache TTL for tokens
        internal_api_token: Internal API token for Gateway-to-Control calls

    Returns:
        Configured CredentialInjector instance
    """
    global _injector
    _injector = CredentialInjector(
        control_plane_url=control_plane_url,
        cache_ttl_seconds=cache_ttl_seconds,
        internal_api_token=internal_api_token,
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
    agent_jwt_token: str | None = None,
    user_id: str | None = None,
) -> InjectionResult:
    """
    Convenience function to inject credentials.

    Uses the configured singleton injector.

    Args:
        credential_ref: Vault reference
        backend_id: Backend identifier
        agent_jwt_token: Raw Agent JWT for E2 vault API auth
        user_id: User ID (owner) for E3 token refresh

    Returns:
        InjectionResult
    """
    injector = get_credential_injector()
    return await injector.inject_credentials(
        credential_ref, backend_id, agent_jwt_token, user_id
    )
