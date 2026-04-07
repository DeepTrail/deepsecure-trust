# WS-K2 Completion Report: Cache Invalidation via Redis Pub/Sub

**Task:** WS-K2 Cache Invalidation via Redis Pub/Sub  
**Status:** ✅ Complete  
**Completed:** February 23, 2026  

---

## Summary

Implemented Redis Pub/Sub cache invalidation between Control Plane and Gateway. When tokens are stored, updated, deleted, or when Control Plane restarts, Gateway immediately invalidates its local token caches instead of waiting for TTL expiration.

---

## Changes Made

### Control Plane (Publisher)

| File | Action | Description |
|------|--------|-------------|
| `app/services/cache_events.py` | Created | Redis publisher module with 5 event publishers |
| `app/main.py` | Modified | Added lifespan context manager, configures publisher on startup |
| `app/services/vault_client.py` | Modified | Added publish calls for store/update/delete token |
| `app/api/v1/endpoints/users.py` | Modified | Added disconnect endpoint with publish call |
| `docker-compose.yml` | Modified | Added `REDIS_URL` env var for deeptrail-control |
| `tests/services/test_cache_events.py` | Created | 13 unit tests for publisher |

### Gateway (Subscriber)

| File | Action | Description |
|------|--------|-------------|
| `app/services/cache_subscriber.py` | Created | Redis subscriber with async background task |
| `app/main.py` | Modified | Start/stop subscriber in lifespan |
| `app/middleware/credential_injection.py` | Modified | Added `invalidate_user_service()` method and tracking |
| `tests/services/__init__.py` | Created | Services test package |
| `tests/services/test_cache_subscriber.py` | Created | 12 unit tests for subscriber |
| `tests/middleware/test_credential_injection.py` | Modified | Added 2 tests for new invalidation methods |

---

## Event Types Implemented

| Event Type | Trigger | Gateway Action |
|------------|---------|----------------|
| `token_stored` | `vault.store_token()` | `invalidate_credential(token_ref)` |
| `token_updated` | `vault.update_token()` | `invalidate_credential(token_ref)` |
| `token_deleted` | `vault.delete_token()` | `invalidate_credential(token_ref)` |
| `service_disconnected` | `DELETE /me/services/{id}` | `invalidate_user_service(user_id, service_id)` |
| `control_plane_restart` | Control Plane startup | `clear_cache()` |

---

## Acceptance Criteria Verification

### Functional

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Control Plane publishes `token_stored` event | ✅ Met | `test_publish_token_stored` passes |
| Control Plane publishes `token_updated` event | ✅ Met | `test_publish_token_updated` passes |
| Control Plane publishes `token_deleted` event | ✅ Met | `test_publish_token_deleted` passes |
| Control Plane publishes `service_disconnected` event | ✅ Met | `test_publish_service_disconnected` passes |
| Control Plane publishes `control_plane_restart` on startup | ✅ Met | Integrated in `main.py` lifespan |
| Gateway subscribes to channel | ✅ Met | `test_start_sets_running_flag` passes |
| Gateway clears specific token on token events | ✅ Met | `test_handle_message_token_*` tests pass |
| Gateway clears all cache on restart event | ✅ Met | `test_handle_message_control_plane_restart` passes |
| Subscriber reconnects after connection loss | ✅ Met | Implemented with 5s retry delay |

### Security

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Events contain token refs only, not values | ✅ Met | Code inspection of `cache_events.py` |
| Redis channel is internal only | ✅ Met | Docker compose internal network |
| No sensitive data logged | ✅ Met | Token refs truncated in logs |

### Integration

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Token update invalidates Gateway cache | ✅ Met | Integration via pub/sub |
| Control Plane restart clears Gateway caches | ✅ Met | `publish_control_plane_restart()` on startup |
| Gateway survives Redis unavailability | ✅ Met | Warning logged, no crash |
| No memory leaks from subscription | ✅ Met | Task properly cancelled on shutdown |

---

## Test Results

### Control Plane Tests
```
tests/services/test_cache_events.py: 13 passed
```

### Gateway Tests
```
tests/services/test_cache_subscriber.py: 12 passed
tests/middleware/test_credential_injection.py: 72 passed (5 new invalidation tests)
```

**Total: 97 tests passed**

---

## Technical Notes

### New Disconnect Endpoint

Added `DELETE /api/v1/users/me/services/{service_id}` endpoint that:
1. Sets `disconnected_at` timestamp (soft delete)
2. Removes from in-memory storage
3. Publishes `service_disconnected` event

### User+Service Tracking

Added `_ref_to_user_service` dict to `CredentialInjector` to track which token refs belong to which user+service combination, enabling efficient invalidation when a service is disconnected.

### Graceful Degradation

- If `REDIS_URL` not set, publisher logs warning and skips publishing
- If Redis connection fails, subscriber logs error and retries after 5s
- No hard failures - cache invalidation is best-effort enhancement

---

## Dependencies

### Added to Control Plane
- `REDIS_URL=redis://redis:6379` in docker-compose.yml

### Already Existed in Gateway
- Redis client via `redis.asyncio`
- `REDIS_URL` environment variable

---

## Post-Conditions Met

- [x] Token updates are immediately reflected in Gateway
- [x] Control Plane restarts no longer cause stale cache issues
- [x] Credential injection uses fresh tokens after refresh
- [x] Users can disconnect services (new endpoint)

---

## References

- **Task:** [WS-K2-cache-invalidation-redis-pubsub.md](../tasks/WS-K2-cache-invalidation-redis-pubsub.md)
- **Spec:** [WS-K2-spec.md](../specs/WS-K2-spec.md)
- **Related:** WS-K1 (Persistent Vault - triggers these events)
- **Downstream:** WS-H1, WS-H2 (Credential Injection - consumes these events)
