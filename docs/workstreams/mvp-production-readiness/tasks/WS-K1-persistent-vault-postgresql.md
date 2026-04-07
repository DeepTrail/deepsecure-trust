# Task: WS-K1 Persistent Vault - Store OAuth Tokens in PostgreSQL

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-K1 |
| **Task Name** | Persistent Vault - Store OAuth Tokens in PostgreSQL |
| **Workstream** | mvp-production-readiness |
| **Phase** | P1.5 (Integration Bug Fixes) |
| **Batch** | P1.5-B1 |
| **Status** | `ready` |
| **Dependencies** | None (standalone) |
| **Complexity** | L (3+ hrs) |
| **Service** | deeptrail-control |
| **Validates** | Token persistence across container restarts |

---

## Specification

| Field | Value |
|-------|-------|
| **Spec File** | [WS-K1-spec.md](../specs/WS-K1-spec.md) |
| **Source** | MVP_ARCHITECTURE_DEEP_DIVE.md, Issue #1 (In-Memory Vault is Ephemeral) |

### Key Contracts

| Component | Contract |
|-----------|----------|
| **Model** | `VaultToken` with `token_ref` (PK), `user_id`, `service_id`, `encrypted_data`, `expires_at` |
| **Service** | `VaultClient` refactored to use PostgreSQL instead of in-memory dict |
| **Encryption** | Fernet encryption (unchanged, already implemented) |
| **Migration** | Alembic migration to create `vault_tokens` table |

---

## API Contracts

> **Note:** This task modifies an internal service (`VaultClient`), not API endpoints.
> The existing vault API endpoints (E2, E3) remain unchanged.
> See [WS-E2](./WS-E2-vault-token-retrieval-endpoint.md) and [WS-E3](./WS-E3-vault-token-refresh-endpoint.md) for API contracts.

### Internal Service Changes

| Method | Current | After |
|--------|---------|-------|
| `store_token()` | Writes to `_storage` dict | Writes to `vault_tokens` table |
| `retrieve_token()` | Reads from `_storage` dict | Reads from `vault_tokens` table |
| `delete_token()` | Deletes from `_storage` dict | Deletes from `vault_tokens` table |
| `update_token()` | Updates `_storage` dict | Updates `vault_tokens` table |

---

## Pre-Conditions

- [ ] PostgreSQL database is running and accessible
- [ ] Alembic migrations are configured for deeptrail-control
- [ ] `VAULT_ENCRYPTION_KEY` environment variable is set (or defaults to ephemeral key)
- [ ] Existing `VaultClient` class exists in `deeptrail-control/app/services/vault_client.py`

---

## Task Description

### Objective

Replace the in-memory token storage in `VaultClient` with PostgreSQL persistence, ensuring OAuth tokens survive container restarts.

### Background

Currently, the `VaultClient` class stores encrypted OAuth tokens in an in-memory dictionary (`_storage: Dict[str, bytes]`). When the `deeptrail-control` container restarts:

1. The `_storage` dict is reset to `{}`
2. `ConnectedService` records still exist with `oauth_token_ref` pointing to the lost tokens
3. Token retrieval fails with "Service not connected" error
4. Users must re-authenticate with all connected services

This issue was identified during Integration Validation Guide testing (Step 17) after MP3 was reached.

### What to Implement

1. **Create `VaultToken` Model**
   - New SQLAlchemy model in `deeptrail-control/app/models/vault_token.py`
   - Fields: `token_ref` (PK), `user_id`, `service_id`, `encrypted_data`, `expires_at`, `last_used_at`, `refresh_count`
   - Appropriate indexes for common queries

2. **Create Alembic Migration**
   - Migration to create `vault_tokens` table
   - Indexes on `user_id`, `service_id`, and composite `user_id + service_id`

3. **Refactor `VaultClient`**
   - Add `db_session_factory` parameter to constructor
   - Change `store_token()` to insert/update database record
   - Change `retrieve_token()` to query database
   - Change `delete_token()` to delete from database
   - Change `update_token()` to update database record
   - Add `get_expiring_tokens()` method for proactive refresh
   - Add `delete_user_tokens()` method for user cleanup

4. **Update Tests**
   - Modify existing tests to use database
   - Add container restart persistence test
   - Add model-level unit tests

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/models/vault_token.py` | Create | `VaultToken` SQLAlchemy model |
| `deeptrail-control/app/models/__init__.py` | Modify | Export `VaultToken` |
| `deeptrail-control/alembic/versions/xxx_add_vault_tokens_table.py` | Create | Migration for `vault_tokens` table |
| `deeptrail-control/app/services/vault_client.py` | Modify | Refactor to use PostgreSQL |
| `deeptrail-control/tests/models/test_vault_token.py` | Create | Model unit tests |
| `deeptrail-control/tests/services/test_vault_client.py` | Modify | Update service tests for DB |

---

## Acceptance Criteria

### Functional

- [ ] `VaultToken` model created with all required fields
- [ ] Alembic migration creates `vault_tokens` table successfully
- [ ] `VaultClient.store_token()` persists token to PostgreSQL
- [ ] `VaultClient.retrieve_token()` retrieves token from PostgreSQL
- [ ] `VaultClient.delete_token()` removes token from PostgreSQL
- [ ] `VaultClient.update_token()` updates token in PostgreSQL
- [ ] Encryption/decryption roundtrip works correctly
- [ ] `get_expiring_tokens()` returns tokens expiring within timeframe
- [ ] `delete_user_tokens()` removes all tokens for a user

### Security

- [ ] Token data is Fernet-encrypted before storage
- [ ] Encryption key never stored in database
- [ ] No plaintext token values appear in logs
- [ ] SQL injection prevented (using ORM)

### Integration

- [ ] Token survives container restart (store → restart → retrieve)
- [ ] `ConnectedService` records work correctly with persistent vault
- [ ] Vault endpoints (E2, E3) continue to work unchanged
- [ ] Gateway credential injection (H1) continues to work

---

## Test Cases

| Test Case | Method | Module | Expected | Notes |
|-----------|--------|--------|----------|-------|
| Store token | `test_store_token_success` | `test_vault_client.py` | Token stored in DB, ref returned | |
| Retrieve token | `test_retrieve_token_success` | `test_vault_client.py` | Token data returned with metadata | |
| Retrieve missing | `test_retrieve_missing_token` | `test_vault_client.py` | Returns `None` | |
| Delete token | `test_delete_token_success` | `test_vault_client.py` | Token removed from DB | |
| Update token | `test_update_token_success` | `test_vault_client.py` | Token updated, metadata preserved | |
| Encryption roundtrip | `test_encryption_roundtrip` | `test_vault_client.py` | Decrypted matches original | |
| Get expiring tokens | `test_get_expiring_tokens` | `test_vault_client.py` | Returns tokens expiring in window | |
| Delete user tokens | `test_delete_user_tokens` | `test_vault_client.py` | All user tokens deleted | |
| Model creation | `test_vault_token_model` | `test_vault_token.py` | Model fields correct | |
| Model indexes | `test_vault_token_indexes` | `test_vault_token.py` | Indexes created | |

---

## Post-Conditions

After this task is complete:

- [ ] WS-K2 (Cache Invalidation) can be implemented (depends on persistent storage)
- [ ] Integration Validation Guide Step 17 will pass after container restart
- [ ] OAuth tokens persist across deployments
- [ ] Proactive token refresh can use `get_expiring_tokens()`

---

## Validation

### Unit Tests

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control

# Run model tests
pytest tests/models/test_vault_token.py -v

# Run service tests
pytest tests/services/test_vault_client.py -v

# Run all related tests
pytest tests/models/test_vault_token.py tests/services/test_vault_client.py -v
```

### Manual Verification

```bash
# 1. Apply migration
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
alembic upgrade head

# 2. Verify table created
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb -c "\d vault_tokens"
# Expected: Table with columns token_ref, user_id, service_id, encrypted_data, etc.

# 3. Start services
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d deeptrail-control deeptrail-gateway

# 4. Connect a service and store token
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "test_token_for_persistence",
      "token_type": "Bearer",
      "scope": "read_pages search_content",
      "expires_at": "2027-02-22T00:00:00+00:00"
    }
  }' | jq .

# 5. Verify token in database
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb \
  -c "SELECT token_ref, user_id, service_id, created_at FROM vault_tokens"
# Expected: Row with token_ref starting with "vault://sarah-notion-"

# 6. Restart container
docker compose restart deeptrail-control
sleep 15

# 7. Verify token still retrievable
# (Create agent JWT and retrieve token - abbreviated)
# The key test: GET /api/v1/vault/tokens/notion should return the token, not 404

# 8. Clean up
docker compose down
```

### Container Restart Test (Critical)

```bash
#!/bin/bash
# Container restart persistence test

set -e

echo "=== WS-K1 Persistence Test ==="

# Start fresh
docker compose down -v
docker compose up -d
sleep 20

# Store token
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

CONNECT_RESULT=$(curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "persistence_test_token",
      "token_type": "Bearer",
      "scope": "read_pages",
      "expires_at": "2027-12-31T00:00:00+00:00"
    }
  }')
echo "Connect result: $CONNECT_RESULT"

# Restart ONLY control plane (not database)
echo "Restarting control plane..."
docker compose restart deeptrail-control
sleep 15

# Try to retrieve token
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

# List connected services
SERVICES=$(curl -s -X GET http://localhost:8000/api/v1/users/me/services \
  -H "Authorization: Bearer $USER_TOKEN")

if echo "$SERVICES" | jq -e '.services[] | select(.service_id=="notion")' > /dev/null; then
  echo "✅ PASS: Token persisted across container restart"
else
  echo "❌ FAIL: Token not found after restart"
  exit 1
fi

echo "=== WS-K1 Persistence Test Complete ==="
```

---

## References

- **Spec:** [WS-K1-spec.md](../specs/WS-K1-spec.md)
- **Architecture:** [MVP_ARCHITECTURE_DEEP_DIVE.md](../../architecture/MVP_ARCHITECTURE_DEEP_DIVE.md)
- **Existing Model Pattern:** [connected_service.py](../../../deeptrail-control/app/models/connected_service.py)
- **Existing Service:** [vault_client.py](../../../deeptrail-control/app/services/vault_client.py)
- **Upstream Dependencies:** None
- **Downstream Dependents:** WS-K2 (Cache Invalidation), WS-H1/H2 (Credential Injection)

---

## Execution

```bash
# Run in mvp-prod-control worktree:
cd /Users/imaxxs/repositories/mvp-prod-control

# Execute the task
/execute-task WS-K1 mvp-production-readiness

# After completion
/complete-task WS-K1 mvp-production-readiness
```
