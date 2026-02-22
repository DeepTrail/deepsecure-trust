# Task Specification: WS-K2 Cache Invalidation via Redis Pub/Sub

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** MVP_ARCHITECTURE_DEEP_DIVE.md, Issue #2 (Credential Cache Can Become Stale)

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-K2 |
| **Task Name** | Cache Invalidation via Redis Pub/Sub |
| **Type** | Infrastructure (Cross-Service) |
| **Services** | deeptrail-control (publisher), deeptrail-gateway (subscriber) |
| **Complexity** | M (1-3 hrs) |
| **Dependencies** | None (Redis already exists) |
| **Validates** | Token cache consistency across services |

---

## Problem Statement

### Current Architecture

```
Control Plane                                   Gateway
┌─────────────────────┐                        ┌─────────────────────┐
│ Token Update        │                        │ CredentialInjector  │
│ (connect/refresh/   │         ❌             │ ._token_cache       │
│  disconnect)        │   NO NOTIFICATION      │                     │
└─────────────────────┘   ─────────────────►   │ (60s TTL)           │
                                               └─────────────────────┘
```

**Issue:** When Control Plane updates a token:
1. Gateway's `_token_cache` still holds the old token
2. Cache has 60s TTL — stale data served for up to 60s
3. No way to force immediate invalidation
4. After Control Plane restart, Gateway may cache tokens that no longer exist

### Target Architecture

```
Control Plane                                   Gateway
┌─────────────────────┐                        ┌─────────────────────┐
│ Token Update        │                        │ CredentialInjector  │
│ (connect/refresh/   │──► Redis Pub/Sub ─────►│ ._token_cache       │
│  disconnect)        │    Channel:            │                     │
│                     │    deepsecure:cache    │ invalidate_cache()  │
│   publish(event)    │                        │   ↓                 │
└─────────────────────┘                        │ del _token_cache[ref]│
                                               └─────────────────────┘
```

---

## Infrastructure (Already Exists)

| Component | Status | Location |
|-----------|--------|----------|
| Redis server | ✅ Exists | `docker-compose.yml` (redis:7-alpine) |
| REDIS_URL env | ✅ Exists | Gateway env: `redis://redis:6379` |
| Redis client in Gateway | ✅ Exists | `ShareStorageManager` uses redis |
| Redis client in Control | ❌ **NEW** | Need to add |

---

## Event Specification

### Channel Name

```
deepsecure:cache_invalidation
```

### Event Types

| Event Type | Trigger | Payload |
|------------|---------|---------|
| `token_stored` | `vault.store_token()` | `{"type": "token_stored", "user_id": "...", "service_id": "...", "token_ref": "..."}` |
| `token_updated` | `vault.update_token()` | `{"type": "token_updated", "token_ref": "..."}` |
| `token_deleted` | `vault.delete_token()` | `{"type": "token_deleted", "token_ref": "..."}` |
| `service_disconnected` | `disconnect_service()` | `{"type": "service_disconnected", "user_id": "...", "service_id": "..."}` |
| `control_plane_restart` | Control Plane startup | `{"type": "control_plane_restart", "timestamp": "..."}` |

### Event Schema

```python
@dataclass
class CacheInvalidationEvent:
    """Event published when cache should be invalidated."""
    
    type: str  # Event type from table above
    timestamp: str  # ISO format timestamp
    
    # Optional fields depending on event type
    user_id: str | None = None
    service_id: str | None = None
    token_ref: str | None = None
    
    def to_json(self) -> str:
        """Serialize event to JSON for Redis publish."""
        return json.dumps({
            "type": self.type,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "service_id": self.service_id,
            "token_ref": self.token_ref,
        })
    
    @classmethod
    def from_json(cls, data: str) -> "CacheInvalidationEvent":
        """Deserialize event from Redis message."""
        parsed = json.loads(data)
        return cls(**parsed)
```

---

## Component Specification: Control Plane (Publisher)

### New Module: `cache_events.py`

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-control/app/services/cache_events.py` |
| **Type** | Module with singleton publisher |
| **Purpose** | Publish cache invalidation events to Redis |

### Interface Contract

```python
import redis
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_CHANNEL = "deepsecure:cache_invalidation"

# Singleton Redis client
_redis_client: Optional[redis.Redis] = None


def configure_cache_publisher(redis_url: str) -> None:
    """Configure the Redis publisher.
    
    Called during app startup if REDIS_URL is set.
    """
    global _redis_client
    _redis_client = redis.from_url(redis_url)
    logger.info("Cache invalidation publisher configured")


def publish_token_stored(user_id: str, service_id: str, token_ref: str) -> None:
    """Publish event when a token is stored."""
    _publish_event({
        "type": "token_stored",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "service_id": service_id,
        "token_ref": token_ref,
    })


def publish_token_updated(token_ref: str) -> None:
    """Publish event when a token is updated (refreshed)."""
    _publish_event({
        "type": "token_updated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "token_ref": token_ref,
    })


def publish_token_deleted(token_ref: str) -> None:
    """Publish event when a token is deleted."""
    _publish_event({
        "type": "token_deleted",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "token_ref": token_ref,
    })


def publish_service_disconnected(user_id: str, service_id: str) -> None:
    """Publish event when a service is disconnected."""
    _publish_event({
        "type": "service_disconnected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "service_id": service_id,
    })


def publish_control_plane_restart() -> None:
    """Publish event when Control Plane restarts (clear all caches)."""
    _publish_event({
        "type": "control_plane_restart",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def _publish_event(event: dict) -> None:
    """Internal: Publish event to Redis channel."""
    if _redis_client is None:
        logger.warning("Cache publisher not configured, skipping event")
        return
    
    try:
        _redis_client.publish(CACHE_CHANNEL, json.dumps(event))
        logger.debug(f"Published cache event: {event['type']}")
    except Exception as e:
        logger.error(f"Failed to publish cache event: {e}")
```

### Integration Points (Control Plane)

| File | Function | Add Call |
|------|----------|----------|
| `app/main.py` | `lifespan()` startup | `configure_cache_publisher(redis_url)` + `publish_control_plane_restart()` |
| `app/services/vault_client.py` | `store_token()` | `publish_token_stored(user_id, service_id, token_ref)` |
| `app/services/vault_client.py` | `update_token()` | `publish_token_updated(token_ref)` |
| `app/services/vault_client.py` | `delete_token()` | `publish_token_deleted(token_ref)` |
| `app/api/v1/endpoints/users.py` | `disconnect_service()` | `publish_service_disconnected(user_id, service_id)` |

---

## Component Specification: Gateway (Subscriber)

### New Module: `cache_subscriber.py`

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-gateway/app/services/cache_subscriber.py` |
| **Type** | Background task module |
| **Purpose** | Subscribe to cache invalidation events and clear caches |

### Interface Contract

```python
import asyncio
import json
import logging
import redis.asyncio as redis
from typing import Callable, Dict, Any

logger = logging.getLogger(__name__)

CACHE_CHANNEL = "deepsecure:cache_invalidation"


class CacheSubscriber:
    """Subscribe to cache invalidation events from Control Plane."""
    
    def __init__(
        self,
        redis_url: str,
        on_token_invalidate: Callable[[str], None],  # token_ref
        on_user_service_invalidate: Callable[[str, str], None],  # user_id, service_id
        on_clear_all: Callable[[], None],  # Clear all caches
    ):
        """
        Initialize cache subscriber.
        
        Args:
            redis_url: Redis connection URL
            on_token_invalidate: Callback when specific token should be invalidated
            on_user_service_invalidate: Callback when user+service cache should be cleared
            on_clear_all: Callback when all caches should be cleared
        """
        self.redis_url = redis_url
        self.on_token_invalidate = on_token_invalidate
        self.on_user_service_invalidate = on_user_service_invalidate
        self.on_clear_all = on_clear_all
        self._task: asyncio.Task | None = None
        self._running = False
    
    async def start(self) -> None:
        """Start the subscription background task."""
        self._running = True
        self._task = asyncio.create_task(self._subscribe_loop())
        logger.info("Cache subscriber started")
    
    async def stop(self) -> None:
        """Stop the subscription background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Cache subscriber stopped")
    
    async def _subscribe_loop(self) -> None:
        """Main subscription loop."""
        while self._running:
            try:
                client = redis.from_url(self.redis_url)
                pubsub = client.pubsub()
                await pubsub.subscribe(CACHE_CHANNEL)
                
                logger.info(f"Subscribed to {CACHE_CHANNEL}")
                
                async for message in pubsub.listen():
                    if not self._running:
                        break
                    
                    if message["type"] == "message":
                        await self._handle_message(message["data"])
                
            except Exception as e:
                logger.error(f"Cache subscriber error: {e}")
                if self._running:
                    await asyncio.sleep(5)  # Reconnect delay
    
    async def _handle_message(self, data: bytes) -> None:
        """Handle a cache invalidation message."""
        try:
            event = json.loads(data.decode())
            event_type = event.get("type")
            
            logger.debug(f"Received cache event: {event_type}")
            
            if event_type == "control_plane_restart":
                self.on_clear_all()
                
            elif event_type in ("token_stored", "token_updated", "token_deleted"):
                token_ref = event.get("token_ref")
                if token_ref:
                    self.on_token_invalidate(token_ref)
                    
            elif event_type == "service_disconnected":
                user_id = event.get("user_id")
                service_id = event.get("service_id")
                if user_id and service_id:
                    self.on_user_service_invalidate(user_id, service_id)
                    
        except Exception as e:
            logger.error(f"Failed to handle cache event: {e}")


# Module-level instance
_subscriber: CacheSubscriber | None = None


async def start_cache_subscriber(
    redis_url: str,
    credential_injector: "CredentialInjector",
) -> None:
    """Start the cache subscriber with credential injector callbacks."""
    global _subscriber
    
    _subscriber = CacheSubscriber(
        redis_url=redis_url,
        on_token_invalidate=credential_injector.invalidate_token,
        on_user_service_invalidate=credential_injector.invalidate_user_service,
        on_clear_all=credential_injector.clear_cache,
    )
    
    await _subscriber.start()


async def stop_cache_subscriber() -> None:
    """Stop the cache subscriber."""
    global _subscriber
    if _subscriber:
        await _subscriber.stop()
        _subscriber = None
```

### CredentialInjector Changes

```python
class CredentialInjector:
    """Updated with cache invalidation methods."""
    
    def __init__(self, ...):
        # Existing fields...
        self._token_cache: dict[str, tuple[dict[str, Any], float]] = {}
        
        # NEW: Track token_ref -> (user_id, service_id) for invalidation
        self._ref_to_user_service: dict[str, tuple[str, str]] = {}
    
    # NEW METHODS
    
    def invalidate_token(self, token_ref: str) -> None:
        """Invalidate a specific token from cache."""
        if token_ref in self._token_cache:
            del self._token_cache[token_ref]
            logger.debug(f"Invalidated cache for token_ref: {token_ref[:20]}...")
    
    def invalidate_user_service(self, user_id: str, service_id: str) -> None:
        """Invalidate all cached tokens for a user+service combination."""
        to_remove = [
            ref for ref, (uid, sid) in self._ref_to_user_service.items()
            if uid == user_id and sid == service_id
        ]
        for ref in to_remove:
            self.invalidate_token(ref)
            del self._ref_to_user_service[ref]
    
    def clear_cache(self) -> None:
        """Clear entire token cache (e.g., on Control Plane restart)."""
        count = len(self._token_cache)
        self._token_cache.clear()
        self._ref_to_user_service.clear()
        logger.info(f"Cleared credential cache: {count} entries")
    
    # MODIFIED: Track user_id/service_id when caching
    async def _get_token(
        self,
        credential_ref: str,
        backend_id: str,
        agent_jwt_token: str | None = None,
        user_id: str | None = None,  # NEW: For tracking
    ) -> dict[str, Any] | None:
        # ... existing cache check ...
        
        token_data = await self._fetch_from_vault(...)
        
        if token_data:
            self._token_cache[credential_ref] = (token_data, now)
            # NEW: Track for invalidation
            if user_id:
                self._ref_to_user_service[credential_ref] = (user_id, backend_id)
        
        return token_data
```

### Integration Points (Gateway)

| File | Location | Add |
|------|----------|-----|
| `app/main.py` | `lifespan()` startup | `await start_cache_subscriber(redis_url, credential_injector)` |
| `app/main.py` | `lifespan()` shutdown | `await stop_cache_subscriber()` |
| `app/core/proxy_config.py` | Config | Add `redis_url` field (already exists via env) |

---

## Environment Variables

### Control Plane (NEW)

```bash
# Add to docker-compose.yml for deeptrail-control
REDIS_URL=redis://redis:6379
```

### Gateway (Already Exists)

```bash
REDIS_URL=redis://redis:6379  # Already configured
```

---

## Sequence Diagram

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│    User      │      │Control Plane │      │    Redis     │      │   Gateway    │
└──────┬───────┘      └──────┬───────┘      └──────┬───────┘      └──────┬───────┘
       │                     │                     │                     │
       │  POST /connect      │                     │                     │
       │────────────────────>│                     │                     │
       │                     │                     │                     │
       │                     │  store_token()      │                     │
       │                     │─────────────────────│                     │
       │                     │                     │                     │
       │                     │  PUBLISH            │                     │
       │                     │  token_stored       │                     │
       │                     │────────────────────>│                     │
       │                     │                     │                     │
       │                     │                     │  MESSAGE            │
       │                     │                     │  token_stored       │
       │                     │                     │────────────────────>│
       │                     │                     │                     │
       │                     │                     │    invalidate_token()
       │                     │                     │                     │
       │  201 Created        │                     │                     │
       │<────────────────────│                     │                     │
       │                     │                     │                     │
```

---

## File Location Rules

| Artifact | Location |
|----------|----------|
| Publisher module | `deeptrail-control/app/services/cache_events.py` |
| Publisher tests | `deeptrail-control/tests/services/test_cache_events.py` |
| Subscriber module | `deeptrail-gateway/app/services/cache_subscriber.py` |
| Subscriber tests | `deeptrail-gateway/tests/services/test_cache_subscriber.py` |
| Integration tests | `tests/e2e/test_cache_invalidation.py` |

---

## Test Cases

| Test Case | Input | Expected Outcome |
|-----------|-------|------------------|
| Publisher configured | Valid REDIS_URL | No errors, client connected |
| Publisher not configured | No REDIS_URL | Log warning, skip publish |
| Publish token_stored | store_token() called | Event published to channel |
| Subscriber receives event | token_stored event | `invalidate_token()` called |
| Clear all on restart | control_plane_restart event | `clear_cache()` called |
| Reconnect on disconnect | Redis connection lost | Reconnect after 5s |
| Subscriber shutdown | `stop()` called | Task cancelled, no leak |
| Token invalidated | Event received | Token removed from `_token_cache` |

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| Event spoofing | Redis is internal only (no external exposure) |
| Sensitive data in events | Events contain refs only, not actual tokens |
| DoS via flood | Rate limit not needed (internal service) |
| Message integrity | Redis handles message delivery |

---

## Technical Requirements

### Framework-Specific

| Requirement | Pattern | Why |
|-------------|---------|-----|
| Async Redis | `redis.asyncio` | Non-blocking subscription |
| Background tasks | `asyncio.create_task()` | Pub/sub runs alongside FastAPI |
| Graceful shutdown | Cancel + await task | No zombie tasks |

### Dependencies

| Dependency | Version | Purpose | Status |
|------------|---------|---------|--------|
| `redis` | Existing | Sync client (Control Plane) | ✅ Installed |
| `redis.asyncio` | Existing | Async client (Gateway) | ✅ Imported in main.py |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] Control Plane has `cache_events.py` module
- [ ] `REDIS_URL` added to Control Plane docker-compose env
- [ ] `publish_*` functions called at correct points
- [ ] Gateway has `cache_subscriber.py` module
- [ ] Subscriber started in Gateway lifespan
- [ ] `CredentialInjector` has invalidation methods
- [ ] Token cache cleared on `control_plane_restart` event
- [ ] Integration test passes: store → invalidate → miss

---

## References

- **Architecture Doc:** [MVP_ARCHITECTURE_DEEP_DIVE.md](../../architecture/MVP_ARCHITECTURE_DEEP_DIVE.md)
- **Existing Redis Usage:** [share_storage.py](../../../deeptrail-gateway/app/core/share_storage.py)
- **Credential Injector:** [credential_injection.py](../../../deeptrail-gateway/app/middleware/credential_injection.py)
- **Related Specs:** WS-K1 (Persistent Vault)
- **Upstream Dependencies:** Redis service (docker-compose)
- **Downstream Dependents:** WS-H1, WS-H2 (Credential Injection)
