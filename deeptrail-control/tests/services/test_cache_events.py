"""Unit tests for cache_events.py (Redis Pub/Sub publisher).

Tests the cache invalidation event publishing functionality.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.services import cache_events


class TestCacheEventsPublisher:
    """Tests for cache event publishing functions."""

    def test_configure_publisher_no_redis_url(self):
        """Publisher should return False when REDIS_URL not set."""
        with patch.dict("os.environ", {}, clear=True):
            # Clear any existing client
            cache_events._redis_client = None
            
            result = cache_events.configure_cache_publisher(None)
            
            assert result is False
            assert cache_events._redis_client is None

    def test_configure_publisher_with_redis_url(self):
        """Publisher should configure when valid REDIS_URL provided."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        
        with patch("redis.from_url", return_value=mock_redis):
            result = cache_events.configure_cache_publisher("redis://localhost:6379")
            
            assert result is True
            assert cache_events._redis_client is mock_redis
            mock_redis.ping.assert_called_once()

    def test_configure_publisher_redis_connection_error(self):
        """Publisher should return False on Redis connection error."""
        with patch("redis.from_url", side_effect=Exception("Connection refused")):
            cache_events._redis_client = None
            
            result = cache_events.configure_cache_publisher("redis://invalid:6379")
            
            assert result is False
            assert cache_events._redis_client is None

    def test_is_publisher_configured(self):
        """is_publisher_configured should reflect client state."""
        cache_events._redis_client = None
        assert cache_events.is_publisher_configured() is False
        
        cache_events._redis_client = MagicMock()
        assert cache_events.is_publisher_configured() is True
        
        cache_events._redis_client = None

    def test_publish_event_not_configured(self):
        """Publishing should log warning when not configured."""
        cache_events._redis_client = None
        
        # Should not raise, just log
        cache_events.publish_token_stored("user1", "notion", "vault://test")
        cache_events.publish_token_updated("vault://test")
        cache_events.publish_token_deleted("vault://test")
        cache_events.publish_service_disconnected("user1", "notion")
        cache_events.publish_control_plane_restart()

    def test_publish_token_stored(self):
        """Should publish token_stored event with correct payload."""
        mock_client = MagicMock()
        cache_events._redis_client = mock_client
        
        cache_events.publish_token_stored("sarah@acme.com", "notion", "vault://sarah-notion-123")
        
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        channel = call_args[0][0]
        message = call_args[0][1]
        
        assert channel == "deepsecure:cache_invalidation"
        assert '"type": "token_stored"' in message
        assert '"user_id": "sarah@acme.com"' in message
        assert '"service_id": "notion"' in message
        assert '"token_ref": "vault://sarah-notion-123"' in message
        
        cache_events._redis_client = None

    def test_publish_token_updated(self):
        """Should publish token_updated event with correct payload."""
        mock_client = MagicMock()
        cache_events._redis_client = mock_client
        
        cache_events.publish_token_updated("vault://sarah-notion-123")
        
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        channel = call_args[0][0]
        message = call_args[0][1]
        
        assert channel == "deepsecure:cache_invalidation"
        assert '"type": "token_updated"' in message
        assert '"token_ref": "vault://sarah-notion-123"' in message
        
        cache_events._redis_client = None

    def test_publish_token_deleted(self):
        """Should publish token_deleted event with correct payload."""
        mock_client = MagicMock()
        cache_events._redis_client = mock_client
        
        cache_events.publish_token_deleted("vault://sarah-notion-123")
        
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        channel = call_args[0][0]
        message = call_args[0][1]
        
        assert channel == "deepsecure:cache_invalidation"
        assert '"type": "token_deleted"' in message
        assert '"token_ref": "vault://sarah-notion-123"' in message
        
        cache_events._redis_client = None

    def test_publish_service_disconnected(self):
        """Should publish service_disconnected event with correct payload."""
        mock_client = MagicMock()
        cache_events._redis_client = mock_client
        
        cache_events.publish_service_disconnected("sarah@acme.com", "notion")
        
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        channel = call_args[0][0]
        message = call_args[0][1]
        
        assert channel == "deepsecure:cache_invalidation"
        assert '"type": "service_disconnected"' in message
        assert '"user_id": "sarah@acme.com"' in message
        assert '"service_id": "notion"' in message
        
        cache_events._redis_client = None

    def test_publish_control_plane_restart(self):
        """Should publish control_plane_restart event."""
        mock_client = MagicMock()
        cache_events._redis_client = mock_client
        
        cache_events.publish_control_plane_restart()
        
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        channel = call_args[0][0]
        message = call_args[0][1]
        
        assert channel == "deepsecure:cache_invalidation"
        assert '"type": "control_plane_restart"' in message
        assert '"timestamp":' in message
        
        cache_events._redis_client = None

    def test_publish_event_redis_error(self):
        """Publishing should handle Redis errors gracefully."""
        mock_client = MagicMock()
        mock_client.publish.side_effect = Exception("Redis error")
        cache_events._redis_client = mock_client
        
        # Should not raise
        cache_events.publish_token_stored("user1", "notion", "vault://test")
        
        cache_events._redis_client = None

    def test_close_publisher(self):
        """close_publisher should close the client."""
        mock_client = MagicMock()
        cache_events._redis_client = mock_client
        
        cache_events.close_publisher()
        
        mock_client.close.assert_called_once()
        assert cache_events._redis_client is None

    def test_close_publisher_not_configured(self):
        """close_publisher should handle not configured case."""
        cache_events._redis_client = None
        
        # Should not raise
        cache_events.close_publisher()
        
        assert cache_events._redis_client is None
