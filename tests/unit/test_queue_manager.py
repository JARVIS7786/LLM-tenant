"""Unit tests for Redis queue manager."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.queue_manager.queue import QueueManager
from src.shared.types import SLATier


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    with patch('src.queue_manager.queue.redis.Redis') as mock:
        redis_instance = MagicMock()
        mock.return_value = redis_instance
        yield redis_instance


@pytest.fixture
def queue_manager(mock_redis):
    """Create QueueManager with mocked Redis."""
    return QueueManager()


class TestQueueManager:
    """Test suite for QueueManager."""

    def test_init_creates_consumer_groups(self, mock_redis):
        """Test that consumer groups are created on initialization."""
        manager = QueueManager()

        # Should create consumer group for each queue
        assert mock_redis.xgroup_create.call_count == 3

        # Verify calls for each tier
        calls = mock_redis.xgroup_create.call_args_list
        queue_names = [call[1]['name'] for call in calls]
        assert 'gold_queue' in queue_names
        assert 'silver_queue' in queue_names
        assert 'bronze_queue' in queue_names

    def test_enqueue_adds_message_to_correct_queue(self, queue_manager, mock_redis):
        """Test that messages are added to the correct priority queue."""
        mock_redis.xadd.return_value = "1234567890-0"

        message_id = queue_manager.enqueue(
            tier=SLATier.GOLD,
            request_id="req_123",
            tenant_id="tenant_456",
            api_key="sk_test_abc",
            prompt="Hello, world!",
            max_tokens=100,
            temperature=0.8
        )

        # Verify XADD was called with correct queue
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[1]['name'] == 'gold_queue'
        assert call_args[1]['fields']['request_id'] == 'req_123'
        assert call_args[1]['fields']['prompt'] == 'Hello, world!'
        assert message_id == "1234567890-0"

    def test_enqueue_different_tiers(self, queue_manager, mock_redis):
        """Test enqueuing to different tier queues."""
        mock_redis.xadd.return_value = "msg_id"

        # Enqueue to each tier
        queue_manager.enqueue(SLATier.GOLD, "req_1", "t1", "key1", "prompt1")
        queue_manager.enqueue(SLATier.SILVER, "req_2", "t2", "key2", "prompt2")
        queue_manager.enqueue(SLATier.BRONZE, "req_3", "t3", "key3", "prompt3")

        # Verify correct queues were used
        calls = mock_redis.xadd.call_args_list
        assert calls[0][1]['name'] == 'gold_queue'
        assert calls[1][1]['name'] == 'silver_queue'
        assert calls[2][1]['name'] == 'bronze_queue'

    def test_dequeue_prioritizes_gold_queue(self, queue_manager, mock_redis):
        """Test that dequeue checks Gold queue first."""
        # Mock Gold queue has messages
        mock_redis.xreadgroup.return_value = [
            ('gold_queue', [
                ('msg_1', {'request_id': 'req_1', 'prompt': 'test'})
            ])
        ]

        results = queue_manager.dequeue(consumer_name="worker-1", count=1)

        # Should only call xreadgroup once (found message in Gold)
        assert mock_redis.xreadgroup.call_count == 1

        # Should return Gold tier message
        assert len(results) == 1
        tier, msg_id, msg_data = results[0]
        assert tier == SLATier.GOLD
        assert msg_id == 'msg_1'
        assert msg_data['request_id'] == 'req_1'

    def test_dequeue_falls_back_to_lower_priority(self, queue_manager, mock_redis):
        """Test that dequeue falls back to Silver/Bronze if Gold is empty."""
        # Mock: Gold empty, Silver has message
        def mock_xreadgroup(*args, **kwargs):
            stream_name = list(kwargs['streams'].keys())[0]
            if stream_name == 'gold_queue':
                return []  # Empty
            elif stream_name == 'silver_queue':
                return [('silver_queue', [('msg_2', {'request_id': 'req_2'})])]
            return []

        mock_redis.xreadgroup.side_effect = mock_xreadgroup

        results = queue_manager.dequeue(consumer_name="worker-1", count=1)

        # Should check Gold, then Silver
        assert mock_redis.xreadgroup.call_count == 2

        # Should return Silver tier message
        assert len(results) == 1
        tier, msg_id, msg_data = results[0]
        assert tier == SLATier.SILVER

    def test_acknowledge_removes_message(self, queue_manager, mock_redis):
        """Test that acknowledge calls XACK."""
        queue_manager.acknowledge(SLATier.GOLD, "msg_123")

        mock_redis.xack.assert_called_once_with(
            name='gold_queue',
            groupname='workers',
            id='msg_123'
        )

    def test_get_queue_depth(self, queue_manager, mock_redis):
        """Test getting queue depth."""
        mock_redis.xlen.return_value = 42

        depth = queue_manager.get_queue_depth(SLATier.GOLD)

        assert depth == 42
        mock_redis.xlen.assert_called_once_with('gold_queue')

    def test_get_all_queue_depths(self, queue_manager, mock_redis):
        """Test getting depths for all queues."""
        mock_redis.xlen.side_effect = [10, 20, 30]  # Gold, Silver, Bronze

        depths = queue_manager.get_all_queue_depths()

        assert depths == {
            'gold': 10,
            'silver': 20,
            'bronze': 30
        }

    def test_health_check_success(self, queue_manager, mock_redis):
        """Test health check when Redis is healthy."""
        mock_redis.ping.return_value = True

        assert queue_manager.health_check() is True

    def test_health_check_failure(self, queue_manager, mock_redis):
        """Test health check when Redis is down."""
        from redis.exceptions import RedisError
        mock_redis.ping.side_effect = RedisError("Connection refused")

        assert queue_manager.health_check() is False

    def test_clear_queue(self, queue_manager, mock_redis):
        """Test clearing a queue."""
        queue_manager.clear_queue(SLATier.GOLD)

        # Should delete the stream
        mock_redis.delete.assert_called_once_with('gold_queue')

        # Should recreate consumer groups
        assert mock_redis.xgroup_create.call_count > 3  # Initial + after clear
