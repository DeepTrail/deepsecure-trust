"""Unit tests for cache_subscriber.py (Redis Pub/Sub subscriber).

Tests the cache invalidation event subscription functionality.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.services import cache_subscriber


class TestCacheSubscriber:
    """Tests for CacheSubscriber class."""

    def test_init(self):
        """Should initialize with callbacks."""
        on_token = MagicMock()
        on_user_service = MagicMock()
        on_clear = MagicMock()
        
        subscriber = cache_subscriber.CacheSubscriber(
            redis_url="redis://localhost:6379",
            on_token_invalidate=on_token,
            on_user_service_invalidate=on_user_service,
            on_clear_all=on_clear,
        )
        
        assert subscriber.redis_url == "redis://localhost:6379"
        assert subscriber.on_token_invalidate is on_token
        assert subscriber.on_user_service_invalidate is on_user_service
        assert subscriber.on_clear_all is on_clear
        assert not subscriber._running

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self):
        """start() should set running flag and create task."""
        on_token = MagicMock()
        on_user_service = MagicMock()
        on_clear = MagicMock()
        
        subscriber = cache_subscriber.CacheSubscriber(
            redis_url="redis://localhost:6379",
            on_token_invalidate=on_token,
            on_user_service_invalidate=on_user_service,
            on_clear_all=on_clear,
        )
        
        # Mock the subscribe loop to not actually connect
        with patch.object(subscriber, '_subscribe_loop', new_callable=AsyncMock):
            await subscriber.start()
            
            assert subscriber._running is True
            assert subscriber._task is not None
            
            # Clean up
            await subscriber.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        """stop() should cancel task and clear state."""
        on_token = MagicMock()
        on_user_service = MagicMock()
        on_clear = MagicMock()
        
        subscriber = cache_subscriber.CacheSubscriber(
            redis_url="redis://localhost:6379",
            on_token_invalidate=on_token,
            on_user_service_invalidate=on_user_service,
            on_clear_all=on_clear,
        )
        
        # Mock the subscribe loop
        with patch.object(subscriber, '_subscribe_loop', new_callable=AsyncMock):
            await subscriber.start()
            await subscriber.stop()
            
            assert subscriber._running is False

    @pytest.mark.asyncio
    async def test_handle_message_token_stored(self):
        """Should call on_token_invalidate for token_stored event."""
        on_token = MagicMock()
        on_user_service = MagicMock()
        on_clear = MagicMock()
        
        subscriber = cache_subscriber.CacheSubscriber(
            redis_url="redis://localhost:6379",
            on_token_invalidate=on_token,
            on_user_service_invalidate=on_user_service,
            on_clear_all=on_clear,
        )
        
        event = {
            "type": "token_stored",
            "token_ref": "vault://sarah-notion-123",
            "user_id": "sarah@acme.com",
            "service_id": "notion",
        }
        
        await subscriber._handle_message(json.dumps(event).encode())
        
        on_token.assert_called_once_with("vault://sarah-notion-123")
        on_user_service.assert_not_called()
        on_clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_token_updated(self):
        """Should call on_token_invalidate for token_updated event."""
        on_token = MagicMock()
        on_user_service = MagicMock()
        on_clear = MagicMock()
        
        subscriber = cache_subscriber.CacheSubscriber(
            redis_url="redis://localhost:6379",
            on_token_invalidate=on_token,
            on_user_service_invalidate=on_user_service,
            on_clear_all=on_clear,
        )
        
        event = {
            "type": "token_updated",
            "token_ref": "vault://sarah-notion-123",
        }
        
        await subscriber._handle_message(json.dumps(event).encode())
        
        on_token.assert_called_once_with("vault://sarah-notion-123")

    @pytest.mark.asyncio
    async def test_handle_message_token_deleted(self):
        """Should call on_token_invalidate for token_deleted event."""
        on_token = MagicMock()
        on_user_service = MagicMock()
        on_clear = MagicMock()
        
        subscriber = cache_subscriber.CacheSubscriber(
            redis_url="redis://localhost:6379",
            on_token_invalidate=on_token,
            on_user_service_invalidate=on_user_service,
            on_clear_all=on_clear,
        )
        
        event = {
            "type": "token_deleted",
            "token_ref": "vault://sarah-notion-123",
        }
        
        await subscriber._handle_message(json.dumps(event).encode())
        
        on_token.assert_called_once_with("vault://sarah-notion-123")

    @pytest.mark.asyncio
    async def test_handle_message_service_disconnected(self):
        """Should call on_user_service_invalidate for service_disconnected."""
        on_token = MagicMock()
        on_user_service = MagicMock()
        on_clear = MagicMock()
        
        subscriber = cache_subscriber.CacheSubscriber(
            redis_url="redis://localhost:6379",
            on_token_invalidate=on_token,
            on_user_service_invalidate=on_user_service,
            on_clear_all=on_clear,
        )
        
        event = {
            "type": "service_disconnected",
            "user_id": "sarah@acme.com",
            "service_id": "notion",
        }
        
        await subscriber._handle_message(json.dumps(event).encode())
        
        on_token.assert_not_called()
        on_user_service.assert_called_once_with("sarah@acme.com", "notion")
        on_clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_control_plane_restart(self):
        """Should call on_clear_all for control_plane_restart event."""
        on_token = MagicMock()
        on_user_service = MagicMock()
        on_clear = MagicMock()
        
        subscriber = cache_subscriber.CacheSubscriber(
            redis_url="redis://localhost:6379",
            on_token_invalidate=on_token,
            on_user_service_invalidate=on_user_service,
            on_clear_all=on_clear,
        )
        
        event = {
            "type": "control_plane_restart",
            "timestamp": "2026-02-22T12:00:00+00:00",
        }
        
        await subscriber._handle_message(json.dumps(event).encode())
        
        on_token.assert_not_called()
        on_user_service.assert_not_called()
        on_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_invalid_json(self):
        """Should handle invalid JSON gracefully."""
        on_token = MagicMock()
        on_user_service = MagicMock()
        on_clear = MagicMock()
        
        subscriber = cache_subscriber.CacheSubscriber(
            redis_url="redis://localhost:6379",
            on_token_invalidate=on_token,
            on_user_service_invalidate=on_user_service,
            on_clear_all=on_clear,
        )
        
        # Should not raise
        await subscriber._handle_message(b"invalid json")
        
        on_token.assert_not_called()
        on_user_service.assert_not_called()
        on_clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_unknown_event_type(self):
        """Should handle unknown event types gracefully."""
        on_token = MagicMock()
        on_user_service = MagicMock()
        on_clear = MagicMock()
        
        subscriber = cache_subscriber.CacheSubscriber(
            redis_url="redis://localhost:6379",
            on_token_invalidate=on_token,
            on_user_service_invalidate=on_user_service,
            on_clear_all=on_clear,
        )
        
        event = {"type": "unknown_event"}
        
        await subscriber._handle_message(json.dumps(event).encode())
        
        on_token.assert_not_called()
        on_user_service.assert_not_called()
        on_clear.assert_not_called()


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_start_and_stop_subscriber(self):
        """start_cache_subscriber and stop_cache_subscriber should work."""
        on_token = MagicMock()
        on_user_service = MagicMock()
        on_clear = MagicMock()
        
        # Clear any existing subscriber
        cache_subscriber._subscriber = None
        
        with patch.object(
            cache_subscriber.CacheSubscriber, 'start', new_callable=AsyncMock
        ), patch.object(
            cache_subscriber.CacheSubscriber, 'stop', new_callable=AsyncMock
        ):
            await cache_subscriber.start_cache_subscriber(
                redis_url="redis://localhost:6379",
                on_token_invalidate=on_token,
                on_user_service_invalidate=on_user_service,
                on_clear_all=on_clear,
            )
            
            assert cache_subscriber._subscriber is not None
            
            await cache_subscriber.stop_cache_subscriber()
            
            assert cache_subscriber._subscriber is None

    def test_is_subscriber_running(self):
        """is_subscriber_running should reflect subscriber state."""
        cache_subscriber._subscriber = None
        assert cache_subscriber.is_subscriber_running() is False
        
        mock_subscriber = MagicMock()
        mock_subscriber._running = True
        cache_subscriber._subscriber = mock_subscriber
        
        assert cache_subscriber.is_subscriber_running() is True
        
        mock_subscriber._running = False
        assert cache_subscriber.is_subscriber_running() is False
        
        cache_subscriber._subscriber = None
