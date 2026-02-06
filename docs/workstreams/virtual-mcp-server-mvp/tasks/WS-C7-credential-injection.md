# Task: WS-C7 Implement Credential Injection

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-C: Auth & Permissions |
| **Dependencies** | C6 (Delegation validator) ✅*, A4 (OAuth token vault storage) ✅ |
| **Blocked By** | C6 (must complete first for permission validation) |
| **Assigned** | - |
| **Created** | February 5, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 6 |
| **Target Worktree** | `vmcp-gateway` |

*Note: C6 is in `ready` status but should be completed before C7 to ensure proper permission validation flow.

---

## Validation Mapping

| Validates | Reference |
|-----------|-----------|
| **Demo 3** | Delegation Execution - Agent uses Sarah's credentials but never sees tokens |
| **User Journey Step** | Step 8: Agent executes tool → OAuth token injected invisibly |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] A4 (OAuth token vault storage) is complete - provides `VaultClient.retrieve_token(ref)`
- [ ] C6 (Delegation validator) is complete - validates permission before injection
- [x] B7 (tools/call handler) is complete - calls credential injection
- [x] B3 (MCP session tracking) is complete - provides `credential_ref` per backend session
- [x] D1-D6 (Backend connectors) are complete - receive injected credentials

---

## Task Description

Implement **credential injection** that retrieves OAuth tokens from the vault and injects them into backend requests, ensuring the agent never sees the actual credentials.

### Context

This is **Step 8 of Sarah's journey** and the core of **Demo 3 (Delegation Execution)**:
- Sarah delegated `notion:pages:search` permission to her agent
- The agent calls `tools/call("notion.search_pages", {...})`
- Gateway validates permission (C6) ✓
- Gateway retrieves Sarah's Notion OAuth token from vault (C7 - THIS TASK)
- Gateway forwards request to Notion with OAuth token
- Agent receives result, never seeing the token

### Key Security Requirements

1. **Agent never sees tokens**: OAuth token is injected server-side
2. **Tokens retrieved just-in-time**: Not cached in memory longer than needed
3. **Tokens never logged**: Token values must not appear in logs
4. **Fail-closed**: If token unavailable, deny the request (don't proceed without auth)
5. **Token refresh support**: Handle expired tokens with refresh flow

### Integration Flow

```
tools/call handler (B7)
         │
         ├── DelegationValidator (C6) → permission validated ✓
         │
         └── CredentialInjector (C7) → THIS TASK
                  │
                  ├── Get credential_ref from backend session (B3)
                  │
                  ├── Retrieve token from VaultClient (A4)
                  │
                  └── Inject into backend request
                           │
                           └── Backend Connector (D3-D6)
                                    │
                                    └── Backend MCP Server (Notion, Slack, etc.)
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/middleware/credential_injection.py` | **CREATE** | Credential injector class |
| `deeptrail-gateway/app/mcp/handlers/tools_call.py` | **MODIFY** | Use CredentialInjector |
| `deeptrail-gateway/tests/middleware/test_credential_injection.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. CredentialInjector Class

```python
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
    
    injector = CredentialInjector(vault_client=vault)
    
    # In tools/call handler, after permission validation
    injected_request = await injector.inject_credentials(
        credential_ref="vault://sarah-notion-abc123",
        backend_request={...}
    )
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class InjectionError(Enum):
    """Reasons for credential injection failure."""
    NO_CREDENTIAL_REF = "no_credential_ref"
    TOKEN_NOT_FOUND = "token_not_found"
    TOKEN_EXPIRED = "token_expired"
    REFRESH_FAILED = "refresh_failed"
    VAULT_ERROR = "vault_error"
    INJECTION_ERROR = "injection_error"


@dataclass
class InjectionResult:
    """Result of credential injection."""
    success: bool
    headers: dict[str, str] | None = None
    error: InjectionError | None = None
    error_message: str | None = None
    
    @classmethod
    def ok(cls, headers: dict[str, str]) -> "InjectionResult":
        return cls(success=True, headers=headers)
    
    @classmethod
    def fail(cls, error: InjectionError, message: str) -> "InjectionResult":
        return cls(success=False, error=error, error_message=message)


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
    """
    
    def __init__(
        self,
        control_plane_url: str | None = None,
        cache_ttl_seconds: int = 60,  # Brief cache to reduce vault calls
    ):
        """
        Initialize the credential injector.
        
        Args:
            control_plane_url: URL to Control Plane for vault access
            cache_ttl_seconds: How long to cache tokens (short-lived for security)
        """
        self.control_plane_url = control_plane_url
        self.cache_ttl_seconds = cache_ttl_seconds
        # Brief cache: credential_ref -> (token, cached_at)
        self._token_cache: dict[str, tuple[dict, float]] = {}
    
    async def inject_credentials(
        self,
        credential_ref: str | None,
        backend_id: str,
    ) -> InjectionResult:
        """
        Get authorization headers for a backend request.
        
        Args:
            credential_ref: Vault reference (e.g., "vault://sarah-notion-abc123")
            backend_id: Backend identifier for formatting headers
            
        Returns:
            InjectionResult with headers or error
            
        Security:
            - Returns ONLY headers, not raw token
            - Agent receives error message, not token details
        """
        # Step 1: Validate credential reference exists
        if not credential_ref:
            logger.warning("No credential_ref provided for %s", backend_id)
            return InjectionResult.fail(
                InjectionError.NO_CREDENTIAL_REF,
                "No credential configured for this backend"
            )
        
        # Step 2: Retrieve token from vault
        token_data = await self._get_token(credential_ref)
        
        if token_data is None:
            logger.warning(
                "Token not found for credential_ref: %s... (backend: %s)",
                credential_ref[:20], backend_id  # Log partial ref only
            )
            return InjectionResult.fail(
                InjectionError.TOKEN_NOT_FOUND,
                "Credential not found. User may need to re-authorize."
            )
        
        # Step 3: Check if token expired and needs refresh
        if self._is_token_expired(token_data):
            logger.info("Token expired, attempting refresh for %s", backend_id)
            refreshed = await self._refresh_token(credential_ref, token_data)
            
            if refreshed is None:
                return InjectionResult.fail(
                    InjectionError.REFRESH_FAILED,
                    "Session expired. User needs to re-authorize."
                )
            
            token_data = refreshed
        
        # Step 4: Format auth headers for this backend
        headers = self._format_auth_headers(token_data, backend_id)
        
        logger.debug(
            "Credentials injected for %s (ref: %s...)",
            backend_id, credential_ref[:20]
        )
        
        return InjectionResult.ok(headers)
    
    async def _get_token(
        self,
        credential_ref: str,
    ) -> dict | None:
        """
        Retrieve token from vault (with brief caching).
        
        Args:
            credential_ref: Vault reference
            
        Returns:
            Token data dict or None if not found
        """
        import time
        
        # Check cache first (brief TTL for security)
        now = time.time()
        if credential_ref in self._token_cache:
            token_data, cached_at = self._token_cache[credential_ref]
            if now - cached_at < self.cache_ttl_seconds:
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
    ) -> dict | None:
        """
        Fetch token from vault (Control Plane API or local vault).
        
        MVP: Uses in-memory vault or Control Plane API
        Production: HashiCorp Vault, AWS Secrets Manager, etc.
        
        Args:
            credential_ref: Vault reference (e.g., "vault://sarah-notion-abc123")
            
        Returns:
            Token data or None
        """
        if not self.control_plane_url:
            # MVP: Return mock token for testing
            logger.debug("MVP mode: returning mock token for %s...", credential_ref[:20])
            return {
                "access_token": "mock_access_token_never_exposed",
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
                        "Vault returned %d for token fetch",
                        response.status_code
                    )
                    return None
                    
        except Exception as e:
            logger.error("Vault fetch error: %s", str(e))
            return None
    
    def _is_token_expired(self, token_data: dict) -> bool:
        """
        Check if OAuth token is expired.
        
        Args:
            token_data: Token data with optional expires_at or expires_in
            
        Returns:
            True if token is expired or about to expire (within 5 min buffer)
        """
        import time
        
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
        token_data: dict,
    ) -> dict | None:
        """
        Refresh an expired OAuth token.
        
        MVP: Returns None (refresh not implemented)
        Production: Calls OAuth refresh endpoint
        
        Args:
            credential_ref: Vault reference
            token_data: Current token data with refresh_token
            
        Returns:
            New token data or None if refresh failed
        """
        refresh_token = token_data.get("refresh_token")
        
        if not refresh_token:
            logger.warning("No refresh_token available for refresh")
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
                    return new_token
                else:
                    logger.error("Token refresh failed: %d", response.status_code)
                    return None
                    
        except Exception as e:
            logger.error("Token refresh error: %s", str(e))
            return None
    
    def _format_auth_headers(
        self,
        token_data: dict,
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
        
        # Standard OAuth Bearer token format
        # Backend connectors (D3-D6) receive these headers
        return {
            "Authorization": f"{token_type} {access_token}"
        }
    
    def clear_cache(self) -> None:
        """Clear the token cache."""
        self._token_cache.clear()
    
    def invalidate_credential(self, credential_ref: str) -> None:
        """
        Invalidate a cached credential.
        
        Call when a token is revoked or user disconnects.
        
        Args:
            credential_ref: Vault reference to invalidate
        """
        self._token_cache.pop(credential_ref, None)


# Singleton instance
_injector: CredentialInjector | None = None


def get_credential_injector() -> CredentialInjector:
    """Get the configured credential injector."""
    global _injector
    if _injector is None:
        _injector = CredentialInjector()
    return _injector


def configure_credential_injector(
    control_plane_url: str | None = None,
) -> CredentialInjector:
    """Configure and return the credential injector."""
    global _injector
    _injector = CredentialInjector(control_plane_url=control_plane_url)
    return _injector
```

### 2. Integration with tools_call Handler

Modify `_forward_to_backend()` in `tools_call.py`:

```python
from app.middleware.credential_injection import (
    CredentialInjector,
    get_credential_injector,
    InjectionResult,
)

async def _forward_to_backend(
    backend_id: str,
    backend_session: BackendMCPSession,
    tool_name: str,
    arguments: dict[str, Any]
) -> dict[str, Any]:
    """
    Forward tool call to backend with credential injection.
    """
    # Get credential reference from session
    cred_ref = None
    if backend_session.credential_ref:
        cred_ref = backend_session.credential_ref.ref
    
    # Inject credentials (C7)
    injector = get_credential_injector()
    injection_result = await injector.inject_credentials(
        credential_ref=cred_ref,
        backend_id=backend_id,
    )
    
    if not injection_result.success:
        raise MCPError(
            ToolsCallErrorCode.CREDENTIAL_ERROR,
            injection_result.error_message
        )
    
    # Forward to backend with injected headers
    auth_headers = injection_result.headers
    
    # ... call backend with auth_headers ...
```

### 3. Key Behaviors

| Scenario | Behavior |
|----------|----------|
| No credential_ref | Fail with `NO_CREDENTIAL_REF` |
| Token not in vault | Fail with `TOKEN_NOT_FOUND` |
| Token expired, no refresh | Fail with `REFRESH_FAILED` |
| Token expired, refresh works | Continue with new token |
| Token valid | Inject headers, proceed |

---

## Acceptance Criteria

### Protocol Criteria
- [ ] Backend requests include proper `Authorization` header
- [ ] Response to agent contains NO token information
- [ ] Error messages give actionable info without exposing credentials

### Security Criteria
- [ ] **Agent never sees token**: Token values never returned to agent
- [ ] **No token logging**: Token values never appear in logs
- [ ] **Fail-closed**: No token = request denied, not anonymous request
- [ ] **Just-in-time**: Tokens retrieved when needed, brief cache only
- [ ] **Cache invalidation**: Can invalidate on disconnect/revoke

### Integration Criteria
- [ ] Uses `VaultClient` from A4 (via Control Plane API)
- [ ] Works after `DelegationValidator` (C6) validates permission
- [ ] Integrates with B7 tools/call handler
- [ ] Backend connectors (D3-D6) receive proper auth headers

### Demo 3 Metric
- [ ] Can demonstrate: Agent executes tool successfully
- [ ] Can demonstrate: If we inspect network, agent never sees OAuth token
- [ ] Can demonstrate: Backend receives valid `Authorization: Bearer <token>` header

---

## Test Cases

### Unit Tests (`test_credential_injection.py`)

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.middleware.credential_injection import (
    CredentialInjector,
    InjectionResult,
    InjectionError,
)


class TestCredentialInjector:
    """Tests for C7: Credential Injection"""
    
    @pytest.fixture
    def injector(self):
        return CredentialInjector()
    
    @pytest.mark.asyncio
    async def test_inject_returns_headers_not_token(self, injector):
        """C7 Security: Should return headers, not raw token"""
        # Mock vault response
        injector._fetch_from_vault = AsyncMock(return_value={
            "access_token": "secret_token_value",
            "token_type": "Bearer",
        })
        
        result = await injector.inject_credentials(
            credential_ref="vault://test-notion-abc123",
            backend_id="notion",
        )
        
        assert result.success is True
        assert result.headers is not None
        assert "Authorization" in result.headers
        # Headers should contain token but result shouldn't expose raw token
        assert result.headers["Authorization"] == "Bearer secret_token_value"
    
    @pytest.mark.asyncio
    async def test_fails_without_credential_ref(self, injector):
        """C7 Fail-closed: Should fail if no credential_ref"""
        result = await injector.inject_credentials(
            credential_ref=None,
            backend_id="notion",
        )
        
        assert result.success is False
        assert result.error == InjectionError.NO_CREDENTIAL_REF
    
    @pytest.mark.asyncio
    async def test_fails_if_token_not_found(self, injector):
        """C7 Fail-closed: Should fail if token not in vault"""
        injector._fetch_from_vault = AsyncMock(return_value=None)
        
        result = await injector.inject_credentials(
            credential_ref="vault://nonexistent-ref",
            backend_id="notion",
        )
        
        assert result.success is False
        assert result.error == InjectionError.TOKEN_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_no_token_in_error_message(self, injector):
        """C7 Security: Error messages should not contain token"""
        injector._fetch_from_vault = AsyncMock(return_value=None)
        
        result = await injector.inject_credentials(
            credential_ref="vault://sarah-notion-abc123",
            backend_id="notion",
        )
        
        assert result.success is False
        # Error message should be user-friendly, not contain tokens
        assert "token" not in result.error_message.lower() or "not found" in result.error_message.lower()
        assert "secret" not in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self, injector):
        """C7: Should be able to invalidate cached credentials"""
        # Populate cache
        injector._token_cache["vault://test-ref"] = (
            {"access_token": "cached_token"},
            0  # Old timestamp
        )
        
        injector.invalidate_credential("vault://test-ref")
        
        assert "vault://test-ref" not in injector._token_cache
    
    def test_expired_token_detection(self, injector):
        """C7: Should detect expired tokens"""
        import time
        
        expired_token = {
            "access_token": "old_token",
            "expires_at": time.time() - 100,  # Expired
        }
        
        assert injector._is_token_expired(expired_token) is True
        
        valid_token = {
            "access_token": "new_token",
            "expires_at": time.time() + 3600,  # Valid for 1 hour
        }
        
        assert injector._is_token_expired(valid_token) is False


class TestCredentialInjectorLogging:
    """Tests to ensure tokens are never logged"""
    
    @pytest.mark.asyncio
    async def test_no_token_in_logs(self, caplog):
        """C7 Security: Token values should never appear in logs"""
        injector = CredentialInjector()
        injector._fetch_from_vault = AsyncMock(return_value={
            "access_token": "SUPER_SECRET_TOKEN_12345",
            "token_type": "Bearer",
        })
        
        with caplog.at_level("DEBUG"):
            await injector.inject_credentials(
                credential_ref="vault://sarah-notion-abc123",
                backend_id="notion",
            )
        
        # Check logs don't contain the actual token
        log_text = caplog.text
        assert "SUPER_SECRET_TOKEN_12345" not in log_text
```

### Integration Tests

```python
@pytest.mark.integration
async def test_tools_call_with_credential_injection(
    gateway_client, agent_jwt_with_notion_access
):
    """C7 Demo 3: tools/call should inject credentials"""
    response = await gateway_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "notion.search_pages",
                "arguments": {"query": "test"}
            }
        },
        headers={"Authorization": f"Bearer {agent_jwt_with_notion_access}"},
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Success - tool executed
    assert "result" in result
    assert "content" in result["result"]
    
    # Agent response should NOT contain token
    response_text = str(result)
    assert "access_token" not in response_text.lower()
    assert "bearer" not in response_text.lower()


@pytest.mark.integration
async def test_tools_call_fails_without_valid_credential(
    gateway_client, agent_jwt_no_credentials
):
    """C7 Fail-closed: Should fail if no credential available"""
    response = await gateway_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "notion.search_pages",
                "arguments": {"query": "test"}
            }
        },
        headers={"Authorization": f"Bearer {agent_jwt_no_credentials}"},
    )
    
    assert response.status_code == 200
    result = response.json()
    assert "error" in result
    assert result["error"]["code"] == -32003  # CREDENTIAL_ERROR
```

---

## Post-Conditions

After completing this task:

1. Backend requests include valid `Authorization` headers
2. Agent responses never contain OAuth tokens
3. Token refresh is attempted for expired tokens
4. C7 completes the Batch 6 permission/auth pipeline

---

## Unblocks

| Task | Name | Notes |
|------|------|-------|
| **E3** | Audit Middleware | Can now audit full tool execution with credential usage |
| **F4** | Demo 3: Delegation Execution | Can demonstrate agent using credentials invisibly |

---

## References

- **Design Doc**: Section "Step 8: Agent executes a delegated tool"
- **A4 Implementation**: `deeptrail-control/app/services/vault_client.py`
- **B7 Handler**: `deeptrail-gateway/app/mcp/handlers/tools_call.py`
- **C6 Validator**: `deeptrail-gateway/app/middleware/delegation_validator.py`
- **Backend Connectors**: `deeptrail-gateway/app/backends/` (D3-D6)

---

## Notes

- MVP uses mock token responses; production connects to Control Plane vault API
- Token cache has short TTL (60s) for security - brief enough to limit exposure if token revoked
- Backend-specific header formats can be extended in `_format_auth_headers()`
- Token refresh requires Control Plane endpoint (future work beyond MVP)
