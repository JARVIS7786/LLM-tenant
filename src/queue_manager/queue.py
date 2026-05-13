"""Redis Streams queue manager for priority-based request scheduling."""
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import redis
from redis.exceptions import RedisError

from src.shared.config import settings
from src.shared.types import SLATier, QueueMessage

logger = logging.getLogger(__name__)


class QueueManager:
    """Manages Redis Streams for priority-based request queuing.

    Architecture:
    - 3 separate streams: gold_queue, silver_queue, bronze_queue
    - Workers poll in priority order: Gold → Silver → Bronze
    - Each stream uses consumer groups for load balancing
    """

    def __init__(self):
        """Initialize Redis connection and queue names."""
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,  # Auto-decode bytes to strings
            socket_connect_timeout=5,
            socket_keepalive=True,
        )

        # Queue names by tier
        self.queue_names = {
            SLATier.GOLD: settings.queue_gold,
            SLATier.SILVER: settings.queue_silver,
            SLATier.BRONZE: settings.queue_bronze,
        }

        # Consumer group name (shared by all workers)
        self.consumer_group = "workers"

        # Initialize consumer groups
        self._init_consumer_groups()

    def _init_consumer_groups(self) -> None:
        """Create consumer groups for each queue if they don't exist."""
        for tier, queue_name in self.queue_names.items():
            try:
                # Create consumer group starting from beginning of stream
                self.redis_client.xgroup_create(
                    name=queue_name,
                    groupname=self.consumer_group,
                    id="0",  # Start from beginning
                    mkstream=True  # Create stream if it doesn't exist
                )
                logger.info(f"Created consumer group for {queue_name}")
            except redis.ResponseError as e:
                if "BUSYGROUP" in str(e):
                    # Group already exists, that's fine
                    logger.debug(f"Consumer group already exists for {queue_name}")
                else:
                    raise

    def enqueue(
        self,
        tier: SLATier,
        request_id: str,
        tenant_id: str,
        api_key: str,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        """Add a request to the appropriate priority queue.

        Args:
            tier: SLA tier (determines which queue)
            request_id: Unique request identifier
            tenant_id: Tenant UUID
            api_key: API key (for authentication)
            prompt: User's prompt text
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Message ID in Redis Stream (e.g., "1234567890123-0")
        """
        queue_name = self.queue_names[tier]

        # Create message payload
        message: QueueMessage = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "api_key": api_key,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "enqueued_at": datetime.utcnow().isoformat(),
        }

        # Add to Redis Stream
        # XADD returns message ID like "1234567890123-0"
        message_id = self.redis_client.xadd(
            name=queue_name,
            fields=message,  # type: ignore
            maxlen=10000,  # Keep last 10k messages (prevents unbounded growth)
            approximate=True  # Faster trimming
        )

        logger.info(
            f"Enqueued request {request_id} to {tier.value} queue "
            f"(message_id={message_id})"
        )

        return message_id

    def dequeue(
        self,
        consumer_name: str,
        block_ms: int = 5000,
        count: int = 1,
    ) -> List[tuple[SLATier, str, Dict[str, Any]]]:
        """Dequeue requests from priority queues (Gold → Silver → Bronze).

        Args:
            consumer_name: Unique name for this worker (e.g., "worker-1")
            block_ms: How long to wait for messages (milliseconds)
            count: Maximum number of messages to fetch

        Returns:
            List of (tier, message_id, message_data) tuples
        """
        results = []

        # Poll queues in priority order
        for tier in [SLATier.GOLD, SLATier.SILVER, SLATier.BRONZE]:
            queue_name = self.queue_names[tier]

            try:
                # XREADGROUP: Read from consumer group
                # ">" means "only new messages not yet delivered"
                messages = self.redis_client.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=consumer_name,
                    streams={queue_name: ">"},
                    count=count,
                    block=block_ms if not results else 0,  # Only block on first queue
                )

                # Parse response: [('queue_name', [('msg_id', {'field': 'value'})])]
                if messages:
                    for stream_name, stream_messages in messages:
                        for message_id, message_data in stream_messages:
                            results.append((tier, message_id, message_data))
                            logger.debug(
                                f"Dequeued {message_data['request_id']} from {tier.value}"
                            )

                # If we got messages from higher priority queue, stop checking lower ones
                if results:
                    break

            except RedisError as e:
                logger.error(f"Error reading from {queue_name}: {e}")
                continue

        return results

    def acknowledge(self, tier: SLATier, message_id: str) -> None:
        """Acknowledge successful processing of a message.

        This removes the message from the pending list.
        """
        queue_name = self.queue_names[tier]

        try:
            self.redis_client.xack(
                name=queue_name,
                groupname=self.consumer_group,
                id=message_id
            )
            logger.debug(f"Acknowledged message {message_id} from {tier.value}")
        except RedisError as e:
            logger.error(f"Error acknowledging message {message_id}: {e}")

    def get_queue_depth(self, tier: SLATier) -> int:
        """Get number of pending messages in a queue.

        Returns:
            Number of messages waiting to be processed
        """
        queue_name = self.queue_names[tier]

        try:
            # XLEN returns total messages in stream
            return self.redis_client.xlen(queue_name)
        except RedisError as e:
            logger.error(f"Error getting queue depth for {tier.value}: {e}")
            return 0

    def get_all_queue_depths(self) -> Dict[str, int]:
        """Get queue depths for all tiers.

        Returns:
            Dict mapping tier name to queue depth
        """
        return {
            tier.value: self.get_queue_depth(tier)
            for tier in [SLATier.GOLD, SLATier.SILVER, SLATier.BRONZE]
        }

    def health_check(self) -> bool:
        """Check if Redis connection is healthy.

        Returns:
            True if Redis is reachable, False otherwise
        """
        try:
            self.redis_client.ping()
            return True
        except RedisError:
            return False

    def clear_queue(self, tier: SLATier) -> None:
        """Clear all messages from a queue (for testing/debugging).

        WARNING: This deletes all pending requests!
        """
        queue_name = self.queue_names[tier]

        try:
            # Delete the stream entirely
            self.redis_client.delete(queue_name)
            # Recreate consumer group
            self._init_consumer_groups()
            logger.warning(f"Cleared all messages from {tier.value} queue")
        except RedisError as e:
            logger.error(f"Error clearing queue {tier.value}: {e}")


# Global queue manager instance
queue_manager = QueueManager()
