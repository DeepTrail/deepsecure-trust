# Task: WS-E1 Enhance Vault Client for Token Storage

> **Status:** `completed`
> **Batch:** P1-B1
> **Worktree:** mvp-prod-control

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-E1 |
| **Workstream** | E (Vault & Credential Storage) |
| **Phase** | P1 (Real Backend Integration) |
| **Dependencies** | MP1 (P0 complete) ✅ |
| **Complexity** | M (1-3 hours) |
| **Service** | deeptrail-control |
| **Validates** | E2E Step 9 (Agent Executes Tools with real API calls) |

---

## Specification

> See full specification: [../specs/WS-E1-spec.md](../specs/WS-E1-spec.md)

### Key Contracts

**New/Modified Methods:**

| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `store_token` | `user_id, service_id, token_data, expires_in` | `str` (token_ref) | Store with expiration metadata |
| `retrieve_token` | `token_ref, update_usage=True` | `dict` | Get token, optionally track usage |
| `refresh_token` | `token_ref, new_access_token, new_expires_in, new_refresh_token` | `bool` | Update after OAuth refresh |
| `get_expiring_tokens` | `threshold_minutes=15` | `list[str]` | Find tokens needing refresh |
| `is_token_expired` | `token_ref` | `bool` | Check if token past expiration |

**New Data Classes:**
- `TokenMetadata` - `created_at`, `expires_at`, `last_used_at`, `refresh_count`
- `StoredTokenData` - Complete token with metadata

---

## API Contracts

> **Note:** This task enhances an internal service module, not API endpoints.
> The VaultClient is used by other services but does not expose any DeepSecure API endpoints directly.
> See WS-E2 for the vault token retrieval endpoint or WS-E3 for the token refresh endpoint.

---

## Pre-Conditions

- [x] MP1 reached (P0 complete, E2E demo verified)
- [x] `deeptrail-control/app/services/vault_client.py` exists (283 lines)
- [x] VaultClient has basic CRUD methods working
- [x] Fernet encryption implemented

---

## Task Description

### Objective

Enhance the existing VaultClient to support OAuth token lifecycle management including:
1. Token expiration tracking
2. Token refresh support
3. Usage tracking
4. Expiring token identification

### Background

The VaultClient currently stores encrypted OAuth tokens but lacks:
- Expiration metadata (`expires_at` timestamp)
- Usage tracking (`last_used_at`)
- Token refresh capability
- Query for expiring tokens

These enhancements enable the gateway's CredentialInjector to:
- Know when tokens need refresh before API calls fail
- Track token usage for auditing
- Update tokens after OAuth refresh flow

### What to Implement

1. **Add data classes** for token metadata:
   ```python
   @dataclass
   class TokenMetadata:
       created_at: datetime
       expires_at: datetime | None
       last_used_at: datetime | None
       refresh_count: int = 0
   ```

2. **Modify `store_token()`** to accept `expires_in` and calculate `expires_at`:
   ```python
   async def store_token(
       self,
       user_id: str,
       service_id: str,
       token_data: dict,
       expires_in: int | None = None  # NEW: seconds until expiration
   ) -> str:
   ```

3. **Modify `retrieve_token()`** to update usage timestamp:
   ```python
   async def retrieve_token(
       self,
       token_ref: str,
       update_usage: bool = True  # NEW: track usage
   ) -> dict:
   ```

4. **Add `refresh_token()` method**:
   ```python
   async def refresh_token(
       self,
       token_ref: str,
       new_access_token: str,
       new_expires_in: int | None = None,
       new_refresh_token: str | None = None
   ) -> bool:
   ```

5. **Add `get_expiring_tokens()` method**:
   ```python
   async def get_expiring_tokens(
       self,
       threshold_minutes: int = 15
   ) -> list[str]:
   ```

6. **Add `is_token_expired()` method**:
   ```python
   async def is_token_expired(self, token_ref: str) -> bool:
   ```

---

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/services/vault_client.py` | Modify | Add expiration/refresh support |
| `deeptrail-control/tests/services/test_vault_client.py` | Modify | Add tests for new functionality |

---

## Acceptance Criteria

### Functional Criteria

- [ ] `store_token()` accepts `expires_in` parameter (seconds)
- [ ] `store_token()` calculates `expires_at` from current time + expires_in
- [ ] `store_token()` stores `created_at` timestamp
- [ ] `retrieve_token()` updates `last_used_at` when `update_usage=True`
- [ ] `retrieve_token()` does NOT update `last_used_at` when `update_usage=False`
- [ ] `refresh_token()` updates `access_token` in stored data
- [ ] `refresh_token()` updates `refresh_token` if provided
- [ ] `refresh_token()` recalculates `expires_at` if `new_expires_in` provided
- [ ] `refresh_token()` increments `refresh_count`
- [ ] `get_expiring_tokens()` returns refs for tokens expiring within threshold
- [ ] `is_token_expired()` returns True for tokens past `expires_at`
- [ ] `is_token_expired()` returns False for tokens with `expires_at=None`

### Security Criteria

- [ ] Encrypted storage maintained (Fernet encryption unchanged)
- [ ] All timestamps in UTC
- [ ] No sensitive data in error messages
- [ ] Token references remain opaque

### Integration Criteria

- [ ] Existing tests continue to pass
- [ ] Backward compatible with current token storage format
- [ ] ConnectedServiceService continues to work

---

## Test Cases

| Test Case | Method | Input | Expected Output |
|-----------|--------|-------|-----------------|
| Store with expiration | `store_token()` | `expires_in=3600` | Token stored, `expires_at` = now + 1hr |
| Store without expiration | `store_token()` | `expires_in=None` | Token stored, `expires_at=None` |
| Retrieve updates usage | `retrieve_token()` | `update_usage=True` | `last_used_at` updated |
| Retrieve no update | `retrieve_token()` | `update_usage=False` | `last_used_at` unchanged |
| Get expiring tokens | `get_expiring_tokens()` | threshold=15 | Returns tokens expiring in 15 min |
| Refresh token | `refresh_token()` | new token values | Token updated, count incremented |
| Check expired token | `is_token_expired()` | expired token ref | Returns `True` |
| Check valid token | `is_token_expired()` | valid token ref | Returns `False` |
| Check no-expiry token | `is_token_expired()` | `expires_at=None` | Returns `False` |

---

## Post-Conditions

After this task is complete:
- [ ] VaultClient supports token expiration tracking
- [ ] VaultClient supports token refresh operations
- [ ] VaultClient supports usage tracking
- [ ] All unit tests pass
- [ ] No regressions in existing functionality

---

## Validation

### Unit Tests
```bash
cd deeptrail-control
pytest tests/services/test_vault_client.py -v
```

### Manual Verification
```python
# In Python REPL or test
from app.services.vault_client import VaultClient, get_vault_client

vault = get_vault_client()

# Test store with expiration
ref = await vault.store_token(
    user_id="user-123",
    service_id="notion",
    token_data={"access_token": "test", "token_type": "bearer"},
    expires_in=3600
)

# Test retrieve
token = await vault.retrieve_token(ref)
assert token["metadata"]["last_used_at"] is not None

# Test expiring tokens
expiring = await vault.get_expiring_tokens(threshold_minutes=60)
assert ref in expiring  # Should be expiring within 60 min

# Test refresh
await vault.refresh_token(ref, new_access_token="refreshed", new_expires_in=3600)
token2 = await vault.retrieve_token(ref)
assert token2["access_token"] == "refreshed"
```

---

## References

- **Specification:** [../specs/WS-E1-spec.md](../specs/WS-E1-spec.md)
- **Design Doc:** `plans/mvp_production_readiness.plan.md` - P1-1
- **Related Files:**
  - `deeptrail-control/app/services/vault_client.py` (existing)
  - `deeptrail-control/app/services/connected_service_service.py` (uses VaultClient)
  - `deeptrail-control/app/models/connected_service.py` (has `oauth_token_ref`)
- **Downstream Tasks:** WS-E2, WS-E3, WS-H1

---

## Execution

```bash
# Run in mvp-prod-control worktree:
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-E1 mvp-production-readiness
```
---

## Execution Log

### Progress Updates

| Date | Update |
|------|--------|
| Feb 16, 2026 | Task started |
| Feb 16, 2026 | Added `TokenMetadata` and `StoredTokenData` dataclasses |
| Feb 16, 2026 | Enhanced `store_token()` with `expires_in` parameter |
| Feb 16, 2026 | Enhanced `retrieve_token()` with `update_usage` parameter |
| Feb 16, 2026 | Added `refresh_token()` method |
| Feb 16, 2026 | Added `get_expiring_tokens()` method |
| Feb 16, 2026 | Added `is_token_expired()` method |
| Feb 16, 2026 | Updated existing tests for new return format |
| Feb 16, 2026 | Added 25 new tests for new functionality |
| Feb 16, 2026 | All 61 tests pass, lint passes |
| Feb 16, 2026 | ✅ Task complete |

### Files Modified

| File | Changes |
|------|---------|
| `deeptrail-control/app/services/vault_client.py` | Added TokenMetadata, StoredTokenData dataclasses; enhanced store_token, retrieve_token; added refresh_token, get_expiring_tokens, is_token_expired |
| `deeptrail-control/tests/services/test_vault_client.py` | Added 25 new tests for expiration, usage tracking, refresh, and data classes |

### Test Results

```
61 passed, 6 warnings in 0.08s
```
