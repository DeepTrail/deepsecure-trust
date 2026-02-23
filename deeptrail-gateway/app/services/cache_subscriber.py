"""Redis Pub/Sub cache invalidation subscriber.

This module subscribes to cache invalidation events from the Control Plane
so that the Gateway can immediately invalidate its local token caches when
tokens are stored, updated, deleted, or when the Control Plane restarts.

Event types handled:
- token_stored: Invalidate specific token reference
- token_updated: Invalidate specific token reference
- token_deleted: Invalidate specific token reference
- service_disconnected: Invalidate all tokens for user+service
- control_plane_restart: Clear entire cache
"""

import asyncio
import json
import logging
from typing import Callable, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

CACHE_CHANNEL = "deepsecure:cache_invalidation"


class CacheSubscriber:
    """Subscribe to cache invalidation events from Control Plane."""

    def __init__(
        self,
        redis_url: str,
        on_token_invalidate: Callable[[str], None],
        on_user_service_invalidate: Callable[[str, str], None],
        on_clear_all: Callable[[], None],
    ):
        """Initialize cache subscriber.

        Args:
            redis_url: Redis connection URL
            on_token_invalidate: Callback when specific token should be invalidated.
                                 Receives token_ref.
            on_user_service_invalidate: Callback when user+service cache should be
                                        cleared. Receives (user_id, service_id).
            on_clear_all: Callback when all caches should be cleared.
        """
        self.redis_url = redis_url
        self.on_token_invalidate = on_token_invalidate
        self.on_user_service_invalidate = on_user_service_invalidate
        self.on_clear_all = on_clear_all
        self._task: Optional[asyncio.Task] = None
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
        """Main subscription loop with auto-reconnect."""
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

                await pubsub.close()
                await client.aclose()

            except asyncio.CancelledError:
                # Normal shutdown
                break
            except Exception as e:
                logger.error(f"Cache subscriber error: {e}")
                if self._running:
                    # Reconnect with exponential backoff (capped at 30s)
                    await asyncio.sleep(5)

    async def _handle_message(self, data: bytes) -> None:
        """Handle a cache invalidation message.

        Args:
            data: Raw message bytes from Redis.
        """
        try:
            event = json.loads(data.decode())
            event_type = event.get("type")

            logger.debug(f"Received cache event: {event_type}")

            if event_type == "control_plane_restart":
                self.on_clear_all()
                logger.info("Cleared cache due to control_plane_restart event")

            elif event_type in ("token_stored", "token_updated", "token_deleted"):
                token_ref = event.get("token_ref")
                if token_ref:
                    self.on_token_invalidate(token_ref)
                    logger.debug(f"Invalidated token cache: {token_ref[:30]}...")

            elif event_type == "service_disconnected":
                user_id = event.get("user_id")
                service_id = event.get("service_id")
                if user_id and service_id:
                    self.on_user_service_invalidate(user_id, service_id)
                    logger.info(f"Invalidated cache for user={user_id} service={service_id}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse cache event: {e}")
        except Exception as e:
            logger.error(f"Failed to handle cache event: {e}")


# Module-level instance for singleton pattern
_subscriber: Optional[CacheSubscriber] = None


async def start_cache_subscriber(
    redis_url: str,
    on_token_invalidate: Callable[[str], None],
    on_user_service_invalidate: Callable[[str, str], None],
    on_clear_all: Callable[[], None],
) -> None:
    """Start the cache subscriber with callbacks.

    Args:
        redis_url: Redis connection URL.
        on_token_invalidate: Called with token_ref when token should be invalidated.
        on_user_service_invalidate: Called with (user_id, service_id) when all
                                    tokens for that combination should be invalidated.
        on_clear_all: Called when entire cache should be cleared.
    """
    global _subscriber

    if _subscriber is not None:
        logger.warning("Cache subscriber already running")
        return

    _subscriber = CacheSubscriber(
        redis_url=redis_url,
        on_token_invalidate=on_token_invalidate,
        on_user_service_invalidate=on_user_service_invalidate,
        on_clear_all=on_clear_all,
    )

    await _subscriber.start()


async def stop_cache_subscriber() -> None:
    """Stop the cache subscriber."""
    global _subscriber
    if _subscriber:
        await _subscriber.stop()
        _subscriber = None


def is_subscriber_running() -> bool:
    """Check if the subscriber is running."""
    return _subscriber is not None and _subscriber._running
