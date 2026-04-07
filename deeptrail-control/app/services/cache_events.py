"""Redis Pub/Sub cache invalidation publisher.

This module publishes cache invalidation events to Redis so that Gateway
services can immediately invalidate their local token caches when tokens
are stored, updated, deleted, or when the Control Plane restarts.

Security properties:
- Events contain only token references, never actual token values
- Redis channel is internal only (not exposed externally)
- No sensitive data is logged in event publishing

Event types:
- token_stored: New token added to vault
- token_updated: Existing token refreshed
- token_deleted: Token removed from vault
- service_disconnected: User disconnected a service
- control_plane_restart: Control Plane started/restarted
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_CHANNEL = "deepsecure:cache_invalidation"

# Singleton Redis client
_redis_client: Optional["redis.Redis"] = None  # type: ignore


def configure_cache_publisher(redis_url: Optional[str] = None) -> bool:
    """Configure the Redis publisher.

    Called during app startup if REDIS_URL is set.

    Args:
        redis_url: Redis connection URL. If None, reads from REDIS_URL env.

    Returns:
        True if publisher configured successfully, False otherwise.
    """
    global _redis_client

    url = redis_url or os.getenv("REDIS_URL")
    if not url:
        logger.info("REDIS_URL not set, cache invalidation publisher disabled")
        return False

    try:
        import redis

        _redis_client = redis.from_url(url)
        # Test connection
        _redis_client.ping()
        logger.info("Cache invalidation publisher configured successfully")
        return True
    except ImportError:
        logger.warning("redis package not installed, cache invalidation disabled")
        return False
    except Exception as e:
        logger.error(f"Failed to connect to Redis for cache invalidation: {e}")
        return False


def is_publisher_configured() -> bool:
    """Check if the publisher is configured."""
    return _redis_client is not None


def publish_token_stored(user_id: str, service_id: str, token_ref: str) -> None:
    """Publish event when a token is stored.

    Args:
        user_id: The user who owns the token.
        service_id: The service the token is for (e.g., "notion").
        token_ref: The vault reference for the token.
    """
    _publish_event(
        {
            "type": "token_stored",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "service_id": service_id,
            "token_ref": token_ref,
        }
    )


def publish_token_updated(token_ref: str) -> None:
    """Publish event when a token is updated (refreshed).

    Args:
        token_ref: The vault reference for the token.
    """
    _publish_event(
        {
            "type": "token_updated",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "token_ref": token_ref,
        }
    )


def publish_token_deleted(token_ref: str) -> None:
    """Publish event when a token is deleted.

    Args:
        token_ref: The vault reference for the token.
    """
    _publish_event(
        {
            "type": "token_deleted",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "token_ref": token_ref,
        }
    )


def publish_service_disconnected(user_id: str, service_id: str) -> None:
    """Publish event when a service is disconnected.

    Args:
        user_id: The user who disconnected the service.
        service_id: The service that was disconnected.
    """
    _publish_event(
        {
            "type": "service_disconnected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "service_id": service_id,
        }
    )


def publish_control_plane_restart() -> None:
    """Publish event when Control Plane restarts (signals clear all caches)."""
    _publish_event(
        {
            "type": "control_plane_restart",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


def _publish_event(event: dict) -> None:
    """Internal: Publish event to Redis channel.

    Args:
        event: Event dictionary to publish.
    """
    if _redis_client is None:
        logger.debug("Cache publisher not configured, skipping event: %s", event.get("type"))
        return

    try:
        message = json.dumps(event)
        _redis_client.publish(CACHE_CHANNEL, message)
        logger.debug("Published cache event: %s", event.get("type"))
    except Exception as e:
        # Log but don't fail - cache invalidation is best-effort
        logger.error(f"Failed to publish cache event: {e}")


def close_publisher() -> None:
    """Close the Redis publisher connection."""
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.close()
        except Exception:
            pass
        _redis_client = None
        logger.info("Cache invalidation publisher closed")
