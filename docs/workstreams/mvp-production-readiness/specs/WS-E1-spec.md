# Task Specification: WS-E1 Enhance Vault Client for Token Storage

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** plans/mvp_production_readiness.plan.md - P1-1: Real Credential Storage

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-E1 |
| **Task Name** | Enhance vault client for token storage |
| **Type** | Service Enhancement |
| **Service** | deeptrail-control |
| **Complexity** | M (1-3 hours) |
| **Validates** | Real Notion/Slack/HubSpot API calls (E2E Steps 9) |

---

## Current State Analysis

**Existing Implementation:** `deeptrail-control/app/services/vault_client.py` (283 lines)

The VaultClient already implements:
- Fernet encryption (AES-128-CBC + HMAC) for OAuth tokens
- In-memory storage with database-ready interface
- Methods: `store_token()`, `retrieve_token()`, `delete_token()`, `update_token()`, `token_exists()`
- Opaque token references: `vault://{user}-{service}-{unique_id}`
- Exception types: `VaultError`, `TokenNotFoundError`, `DecryptionError`

**Supporting Files:**
- `app/models/connected_service.py` - SQLAlchemy model with `oauth_token_ref` field
- `app/services/connected_service_service.py` - Business logic using VaultClient

---

## Enhancement Requirements

### 1. Token Expiration Tracking

Add expiration metadata to stored tokens:

```python
@dataclass
class StoredToken:
    """Enhanced token storage with metadata."""
    access_token: str
    token_type: str
    refresh_token: str | None
    expires_at: datetime | None  # NEW: Absolute expiration time
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None  # NEW: Track usage
    service_id: str
    user_id: str
```

### 2. Token Refresh Scheduling

Add method to identify tokens needing refresh:

```python
async def get_expiring_tokens(
    self,
    threshold_minutes: int = 15
) -> list[str]:
    """
    Returns token references expiring within threshold.

    Args:
        threshold_minutes: Minutes before expiration to flag

    Returns:
        List of token references needing refresh
    """
```

### 3. Token Refresh Support

Add method to update token after refresh:

```python
async def refresh_token(
    self,
    token_ref: str,
    new_access_token: str,
    new_expires_in: int | None = None,
    new_refresh_token: str | None = None
) -> bool:
    """
    Update stored token with refreshed values.

    Args:
        token_ref: Opaque vault reference
        new_access_token: Fresh access token
        new_expires_in: Optional new TTL in seconds
        new_refresh_token: Optional rotated refresh token

    Returns:
        True if successful

    Raises:
        TokenNotFoundError: Token ref doesn't exist
        VaultError: Update failed
    """
```

### 4. Usage Tracking

Update `last_used_at` on token retrieval:

```python
async def retrieve_token(
    self,
    token_ref: str,
    update_usage: bool = True  # NEW parameter
) -> dict:
    """Retrieve and optionally mark token as used."""
```

---

## Component Specification

### Class: `VaultClient` (Enhanced)

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-control/app/services/vault_client.py` |
| **Type** | Class (modify existing) |
| **Purpose** | Encrypted OAuth token storage with expiration tracking |

### New/Modified Methods

| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `store_token` | `user_id, service_id, token_data, expires_in` | `str` (token_ref) | Store with expiration metadata |
| `retrieve_token` | `token_ref, update_usage=True` | `dict` | Get token, optionally track usage |
| `refresh_token` | `token_ref, new_access_token, new_expires_in, new_refresh_token` | `bool` | Update after OAuth refresh |
| `get_expiring_tokens` | `threshold_minutes=15` | `list[str]` | Find tokens needing refresh |
| `is_token_expired` | `token_ref` | `bool` | Check if token past expiration |

### Data Classes (New)

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TokenMetadata:
    """Metadata for stored OAuth tokens."""
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    refresh_count: int = 0

@dataclass
class StoredTokenData:
    """Complete stored token with metadata."""
    access_token: str
    token_type: str
    refresh_token: str | None
    scopes: list[str]
    service_id: str
    user_id: str
    metadata: TokenMetadata
```

---

## Technical Requirements

### Framework-Specific

| Requirement | Pattern | Why |
|-------------|---------|-----|
| Encryption | Fernet (existing) | Already implemented, maintain consistency |
| Storage | In-memory dict (MVP) | Production: swap for HashiCorp Vault or AWS Secrets Manager |
| Timestamps | UTC datetime | Consistent timezone handling |
| Async | `async def` methods | Gateway calls are async |

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `cryptography` | existing | Fernet encryption |
| `python-dateutil` | existing | Timestamp handling |

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `VAULT_ENCRYPTION_KEY` | Fernet key for encryption | Generated if not set |
| `VAULT_TOKEN_REFRESH_THRESHOLD_MINUTES` | Minutes before expiry to flag | `15` |

---

## File Location Rules

| Artifact | Correct Location | Notes |
|----------|------------------|-------|
| Implementation | `deeptrail-control/app/services/vault_client.py` | Modify existing |
| Unit tests | `deeptrail-control/tests/services/test_vault_client.py` | Add/modify |
| Integration tests | `tests/e2e/` (ROOT) | Cross-service |

---

## Test Cases

| Test Case | Method | Expected | Notes |
|-----------|--------|----------|-------|
| Store with expiration | `store_token()` | Token stored with `expires_at` calculated | expires_in → expires_at |
| Retrieve updates usage | `retrieve_token()` | `last_used_at` updated | Only if `update_usage=True` |
| Get expiring tokens | `get_expiring_tokens()` | Returns tokens expiring within threshold | Threshold configurable |
| Refresh token | `refresh_token()` | Token updated, `refresh_count` incremented | Preserves original metadata |
| Check expired | `is_token_expired()` | Returns True if past `expires_at` | Handles None (never expires) |
| Store without expiration | `store_token()` | Token stored with `expires_at=None` | Valid for tokens without TTL |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `store_token()` accepts `expires_in` parameter
- [ ] `store_token()` calculates and stores `expires_at` timestamp
- [ ] `retrieve_token()` updates `last_used_at` when `update_usage=True`
- [ ] `refresh_token()` updates access token and optionally refresh token
- [ ] `refresh_token()` recalculates `expires_at` if new `expires_in` provided
- [ ] `get_expiring_tokens()` returns refs for tokens within threshold
- [ ] `is_token_expired()` correctly compares against current time
- [ ] All methods handle `None` expiration (tokens that don't expire)
- [ ] Encryption/decryption still works with new metadata fields
- [ ] Existing tests still pass
- [ ] New tests cover all new functionality

---

## References

- **Design Doc Section:** P1-1: Real Credential Storage (Vault Integration)
- **Related Specs:** WS-E2-spec.md (vault retrieval endpoint), WS-E3-spec.md (refresh endpoint)
- **Upstream Dependencies:** MP1 (P0 complete)
- **Downstream Dependents:** WS-E2, WS-E3, WS-H1 (CredentialInjector)
