# Task: WS-K2 Cache Invalidation via Redis Pub/Sub

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-K2 |
| **Task Name** | Cache Invalidation via Redis Pub/Sub |
| **Workstream** | mvp-production-readiness |
| **Phase** | P1.5 (Integration Bug Fixes) |
| **Batch** | P1.5-B1 |
| **Status** | `ready` |
| **Dependencies** | None (Redis already exists) |
| **Complexity** | M (1-3 hrs) |
| **Services** | deeptrail-control (publisher), deeptrail-gateway (subscriber) |
| **Validates** | Token cache consistency across services |

---

## Specification

| Field | Value |
|-------|-------|
| **Spec File** | [WS-K2-spec.md](../specs/WS-K2-spec.md) |
| **Source** | MVP_ARCHITECTURE_DEEP_DIVE.md, Issue #2 (Credential Cache Can Become Stale) |

### Key Contracts

| Component | Contract |
|-----------|----------|
| **Channel** | `deepsecure:cache_invalidation` |
| **Publisher** | `deeptrail-control/app/services/cache_events.py` |
| **Subscriber** | `deeptrail-gateway/app/services/cache_subscriber.py` |
| **Event Types** | `token_stored`, `token_updated`, `token_deleted`, `service_disconnected`, `control_plane_restart` |

---

## API Contracts

> **Note:** This task implements infrastructure (Redis Pub/Sub), not API endpoints.
> The cache invalidation happens via Redis messages between services.
> No new HTTP endpoints are created by this task.

### Redis Pub/Sub Channel

| Field | Value |
|-------|-------|
| **Channel** | `deepsecure:cache_invalidation` |
| **Publisher** | Control Plane |
| **Subscriber** | Gateway |
| **Message Format** | JSON |

### Event Payload Examples

**token_stored:**
```json
{
  "type": "token_stored",
  "timestamp": "2026-02-22T12:00:00+00:00",
  "user_id": "sarah@acme.com",
  "service_id": "notion",
  "token_ref": "vault://sarah-notion-abc123"
}
```

**control_plane_restart:**
```json
{
  "type": "control_plane_restart",
  "timestamp": "2026-02-22T12:00:00+00:00"
}
```

---

## Pre-Conditions

- [ ] Redis server is running (docker-compose: `redis:7-alpine`)
- [ ] Gateway already has REDIS_URL env configured
- [ ] `CredentialInjector` class exists with `_token_cache` dict
- [ ] Control Plane and Gateway can both connect to Redis

---

## Task Description

### Objective

Implement Redis Pub/Sub between Control Plane and Gateway so that token cache invalidation happens immediately when tokens are stored, updated, deleted, or when Control Plane restarts.

### Background

Currently, when the Control Plane updates a token:
1. Gateway's `_token_cache` still holds the old token
2. Cache has 60s TTL — stale data served for up to 60 seconds
3. No way to force immediate invalidation
4. After Control Plane restart, Gateway may cache tokens that no longer exist

This causes issues during Integration Validation Guide testing (Step 17) when tokens are updated but Gateway continues to use cached values.

### What to Implement

#### Control Plane (Publisher)

1. **Create `cache_events.py` module**
   - `configure_cache_publisher(redis_url)` - Initialize Redis connection
   - `publish_token_stored(user_id, service_id, token_ref)`
   - `publish_token_updated(token_ref)`
   - `publish_token_deleted(token_ref)`
   - `publish_service_disconnected(user_id, service_id)`
   - `publish_control_plane_restart()`

2. **Integrate into existing code**
   - Call `configure_cache_publisher()` on startup
   - Call `publish_control_plane_restart()` on startup
   - Call `publish_token_stored()` in `vault_client.store_token()`
   - Call `publish_token_updated()` in `vault_client.update_token()`
   - Call `publish_token_deleted()` in `vault_client.delete_token()`
   - Call `publish_service_disconnected()` in `disconnect_service()`

3. **Add REDIS_URL to docker-compose**

#### Gateway (Subscriber)

1. **Create `cache_subscriber.py` module**
   - `CacheSubscriber` class with async subscription loop
   - Callbacks for token invalidation, user+service invalidation, clear all
   - `start_cache_subscriber()` and `stop_cache_subscriber()` functions

2. **Update `CredentialInjector`**
   - Add `invalidate_token(token_ref)` method
   - Add `invalidate_user_service(user_id, service_id)` method
   - Add `clear_cache()` method
   - Track `token_ref -> (user_id, service_id)` for invalidation

3. **Integrate into main.py**
   - Start subscriber in `lifespan()` startup
   - Stop subscriber in `lifespan()` shutdown

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/services/cache_events.py` | Create | Redis publisher module |
| `deeptrail-control/app/main.py` | Modify | Configure publisher on startup |
| `deeptrail-control/app/services/vault_client.py` | Modify | Publish events on token operations |
| `deeptrail-control/app/api/v1/endpoints/users.py` | Modify | Publish on service disconnect |
| `deeptrail-control/docker-compose.yml` (or parent) | Modify | Add REDIS_URL env var |
| `deeptrail-gateway/app/services/cache_subscriber.py` | Create | Redis subscriber module |
| `deeptrail-gateway/app/main.py` | Modify | Start/stop subscriber |
| `deeptrail-gateway/app/middleware/credential_injection.py` | Modify | Add invalidation methods |
| `deeptrail-control/tests/services/test_cache_events.py` | Create | Publisher unit tests |
| `deeptrail-gateway/tests/services/test_cache_subscriber.py` | Create | Subscriber unit tests |

---

## Acceptance Criteria

### Functional

- [ ] Control Plane publishes `token_stored` event on `store_token()`
- [ ] Control Plane publishes `token_updated` event on `update_token()`
- [ ] Control Plane publishes `token_deleted` event on `delete_token()`
- [ ] Control Plane publishes `service_disconnected` event on disconnect
- [ ] Control Plane publishes `control_plane_restart` on startup
- [ ] Gateway subscribes to `deepsecure:cache_invalidation` channel
- [ ] Gateway clears specific token from cache on `token_*` events
- [ ] Gateway clears all cache on `control_plane_restart` event
- [ ] Subscriber reconnects after Redis connection loss

### Security

- [ ] Events contain token references only, not actual token values
- [ ] Redis channel is internal only (not exposed externally)
- [ ] No sensitive data logged in event handling

### Integration

- [ ] Token update in Control Plane immediately invalidates Gateway cache
- [ ] Control Plane restart clears all Gateway caches
- [ ] Gateway survives Redis temporary unavailability
- [ ] No memory leaks from subscription task

---

## Test Cases

| Test Case | Method | Module | Expected | Notes |
|-----------|--------|--------|----------|-------|
| Publisher configured | `test_configure_publisher` | `test_cache_events.py` | Redis client connected | |
| Publisher not configured | `test_publisher_not_configured` | `test_cache_events.py` | Log warning, no error | |
| Publish token_stored | `test_publish_token_stored` | `test_cache_events.py` | Event sent to channel | |
| Subscriber receives event | `test_subscriber_receives` | `test_cache_subscriber.py` | Callback invoked | |
| Clear all on restart | `test_clear_all_on_restart` | `test_cache_subscriber.py` | `clear_cache()` called | |
| Reconnect on disconnect | `test_reconnect` | `test_cache_subscriber.py` | Reconnect after 5s | |
| Subscriber shutdown | `test_subscriber_shutdown` | `test_cache_subscriber.py` | Task cancelled cleanly | |
| Token invalidated | `test_token_invalidated` | `test_credential_injection.py` | Token removed from cache | |
| User service invalidated | `test_user_service_invalidated` | `test_credential_injection.py` | All user+service tokens removed | |

---

## Post-Conditions

After this task is complete:

- [ ] Token updates are immediately reflected in Gateway
- [ ] Control Plane restarts no longer cause stale cache issues
- [ ] Integration Validation Guide Step 17 passes consistently
- [ ] Credential injection uses fresh tokens after refresh

---

## Validation

### Unit Tests

```bash
# Control Plane tests
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
pytest tests/services/test_cache_events.py -v

# Gateway tests
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-gateway
pytest tests/services/test_cache_subscriber.py -v
pytest tests/middleware/test_credential_injection.py -v -k "invalidat"
```

### Manual Verification

```bash
# 1. Start services
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d

# 2. Monitor Redis channel (in another terminal)
docker compose exec redis redis-cli SUBSCRIBE deepsecure:cache_invalidation
# Leave this running...

# 3. Login and connect a service
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "test_token_123",
      "token_type": "Bearer",
      "scope": "read_pages",
      "expires_at": "2027-02-22T00:00:00+00:00"
    }
  }' | jq .
# Expected in Redis monitor: token_stored event

# 4. Verify Gateway received the event
docker compose logs deeptrail-gateway --tail=20 | grep -i "cache\|invalidat"
# Expected: "Received cache event: token_stored"

# 5. Restart Control Plane
docker compose restart deeptrail-control
sleep 15

# Expected in Redis monitor: control_plane_restart event
# Expected in Gateway logs: "Cleared credential cache"

# 6. Clean up
docker compose down
```

### Integration Test (E2E)

```bash
#!/bin/bash
# Cache invalidation E2E test

set -e

echo "=== WS-K2 Cache Invalidation Test ==="

# Start services
docker compose up -d
sleep 20

# 1. Login
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

# 2. Connect service
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "original_token",
      "token_type": "Bearer",
      "scope": "read_pages",
      "expires_at": "2027-02-22T00:00:00+00:00"
    }
  }' > /dev/null

# 3. Make a request to cache the token in Gateway
# (This requires an agent JWT and MCP call - simplified here)

# 4. Update the token
curl -s -X POST http://localhost:8000/api/v1/users/me/services/connect \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "notion",
    "oauth_token": {
      "access_token": "updated_token",
      "token_type": "Bearer",
      "scope": "read_pages",
      "expires_at": "2027-02-22T00:00:00+00:00"
    }
  }' > /dev/null

# 5. Check Gateway logs for invalidation
INVALIDATED=$(docker compose logs deeptrail-gateway --tail=50 | grep -c "Invalidated cache" || true)

if [ "$INVALIDATED" -gt 0 ]; then
  echo "✅ PASS: Cache invalidation event received"
else
  echo "❌ FAIL: No cache invalidation detected"
  exit 1
fi

echo "=== WS-K2 Cache Invalidation Test Complete ==="
```

---

## References

- **Spec:** [WS-K2-spec.md](../specs/WS-K2-spec.md)
- **Architecture:** [MVP_ARCHITECTURE_DEEP_DIVE.md](../../architecture/MVP_ARCHITECTURE_DEEP_DIVE.md)
- **Existing Redis Usage:** [share_storage.py](../../../deeptrail-gateway/app/core/share_storage.py)
- **Credential Injector:** [credential_injection.py](../../../deeptrail-gateway/app/middleware/credential_injection.py)
- **Related:** WS-K1 (Persistent Vault - triggers these events)
- **Upstream Dependencies:** Redis service (docker-compose)
- **Downstream Dependents:** WS-H1, WS-H2 (Credential Injection)

---

## Execution

```bash
# This task spans BOTH services, so execute in both worktrees:

# Control Plane (publisher):
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-K2 mvp-production-readiness

# Gateway (subscriber):
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-K2 mvp-production-readiness

# After completion
/complete-task WS-K2 mvp-production-readiness
```
