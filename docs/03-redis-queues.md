# Redis Streams Priority Queues - Learning Guide

## What We Just Built

We implemented a priority-based message queue system using Redis Streams. This is the **core scheduling mechanism** that ensures Gold tier customers get faster responses than Bronze tier customers.

---

## 1. Why Redis Streams?

### Traditional Queue Options

| Technology | Pros | Cons |
|------------|------|------|
| **RabbitMQ** | Feature-rich, reliable | Complex setup, separate service |
| **Kafka** | High throughput, durable | Overkill for our scale, complex |
| **AWS SQS** | Managed, scalable | Cloud-locked, costs add up |
| **Redis Streams** | ✓ Fast, ✓ Simple, ✓ Already using Redis | Limited features vs Kafka |

**Our choice: Redis Streams** because:
- Sub-millisecond latency (in-memory)
- We already need Redis for caching
- Simple API (just 5 commands)
- Consumer groups for load balancing
- Persistent (AOF mode)

---

## 2. Architecture: 3 Separate Streams

```
┌─────────────┐
│ API Gateway │
└──────┬──────┘
       │ Enqueue based on tenant tier
       ├──────────────┬──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  Gold    │   │  Silver  │   │  Bronze  │   │  Worker  │
│  Queue   │   │  Queue   │   │  Queue   │   │  Pool    │
└──────────┘   └──────────┘   └──────────┘   └────┬─────┘
                                                    │
                                    Dequeue: Gold → Silver → Bronze
```

**Key Design Decision:**
- **3 separate streams** (not 1 stream with priority field)
- Workers poll Gold first, then Silver, then Bronze
- If Gold has messages, Silver/Bronze wait
- Simple priority enforcement through polling order

---

## 3. Redis Streams Concepts

### What is a Stream?

Think of it like a **log file** that multiple consumers can read:

```
Stream: gold_queue
┌─────────────────────────────────────────────────┐
│ 1234567890-0: {request_id: "req_1", prompt: ...}│
│ 1234567891-0: {request_id: "req_2", prompt: ...}│
│ 1234567892-0: {request_id: "req_3", prompt: ...}│
└─────────────────────────────────────────────────┘
         ↑
    Message ID (timestamp-sequence)
```

**Properties:**
- Messages are **append-only** (like a log)
- Each message has a unique ID: `timestamp-sequence`
- Messages stay in stream until explicitly deleted
- Multiple consumers can read the same stream

### Consumer Groups

**Problem:** How do multiple workers share the load?

**Solution:** Consumer groups distribute messages across workers:

```
Stream: gold_queue
       │
       ├─── Consumer Group: "workers"
       │         │
       │         ├─── Worker-1 (gets msg 1, 3, 5...)
       │         ├─── Worker-2 (gets msg 2, 4, 6...)
       │         └─── Worker-3 (gets msg 7, 9, 11...)
```

**How it works:**
1. Each message is delivered to **only one** worker in the group
2. Worker must **acknowledge** (ACK) when done
3. If worker crashes, message goes to another worker (after timeout)

---

## 4. Core Operations

### Enqueue (Producer Side)

```python
queue_manager.enqueue(
    tier=SLATier.GOLD,
    request_id="req_123",
    tenant_id="tenant_456",
    api_key="sk_test_abc",
    prompt="Explain quantum computing",
    max_tokens=512,
    temperature=0.7
)
```

**What happens:**
1. Determines queue name: `gold_queue`
2. Creates message with metadata
3. Calls `XADD gold_queue * request_id req_123 prompt "Explain..." ...`
4. Returns message ID: `1715445309123-0`

**Redis Command:**
```redis
XADD gold_queue MAXLEN ~ 10000 * \
  request_id req_123 \
  tenant_id tenant_456 \
  prompt "Explain quantum computing" \
  enqueued_at 2026-05-11T14:15:09Z
```

### Dequeue (Consumer Side)

```python
messages = queue_manager.dequeue(
    consumer_name="worker-1",
    block_ms=5000,  # Wait up to 5 seconds
    count=1         # Fetch 1 message
)

# Returns: [(SLATier.GOLD, "1715445309123-0", {...message data...})]
```

**What happens:**
1. Tries Gold queue: `XREADGROUP GROUP workers worker-1 COUNT 1 BLOCK 5000 STREAMS gold_queue >`
2. If empty, tries Silver queue (no blocking)
3. If empty, tries Bronze queue
4. Returns first available message

**The `>` symbol** means "only new messages I haven't seen yet"

### Acknowledge (After Processing)

```python
queue_manager.acknowledge(SLATier.GOLD, "1715445309123-0")
```

**What happens:**
- Calls `XACK gold_queue workers 1715445309123-0`
- Removes message from "pending" list
- If you don't ACK, message stays pending and can be reclaimed

---

## 5. Priority Enforcement

### How Priority Works

```python
# Worker polling loop
for tier in [SLATier.GOLD, SLATier.SILVER, SLATier.BRONZE]:
    messages = read_from_queue(tier)
    if messages:
        process(messages)
        break  # Stop checking lower priority queues
```

**Example Scenario:**

```
Time  | Gold Queue | Silver Queue | Bronze Queue | Worker Action
------|------------|--------------|--------------|---------------
T0    | [req_1]    | [req_2]      | [req_3]      | Process req_1 (Gold)
T1    | []         | [req_2]      | [req_3]      | Process req_2 (Silver)
T2    | [req_4]    | []           | [req_3]      | Process req_4 (Gold)
T3    | []         | []           | [req_3]      | Process req_3 (Bronze)
```

**Bronze request waits** until Gold and Silver are empty!

### Starvation Prevention

**Problem:** What if Gold queue is always full? Bronze never gets processed!

**Solutions (not yet implemented, but you should consider):**
1. **Time-based fairness**: Process 10 Gold, then 1 Silver, then 1 Bronze
2. **Age-based priority**: Boost priority of old messages
3. **Quota limits**: Max N requests per tenant per minute

---

## 6. Key Implementation Details

### Message Structure

```python
QueueMessage = {
    "request_id": "req_123",      # Unique ID for tracking
    "tenant_id": "uuid",          # For billing
    "api_key": "sk_...",          # For auth (if needed)
    "prompt": "User's text",      # LLM input
    "max_tokens": 512,            # Generation limit
    "temperature": 0.7,           # Sampling param
    "enqueued_at": "2026-05-11T14:15:09Z"  # For latency tracking
}
```

### Stream Trimming

```python
self.redis_client.xadd(
    name=queue_name,
    fields=message,
    maxlen=10000,      # Keep only last 10k messages
    approximate=True   # Faster, allows ~10k-10.1k
)
```

**Why trim?**
- Streams grow unbounded without trimming
- Old messages (already processed) waste memory
- `approximate=True` is faster (doesn't scan entire stream)

### Blocking vs Non-Blocking

```python
# First queue: Block for 5 seconds
messages = xreadgroup(..., block=5000)

# Subsequent queues: Don't block (immediate return)
messages = xreadgroup(..., block=0)
```

**Why?**
- Block on Gold queue: Wait for new high-priority work
- Don't block on Silver/Bronze: Check quickly and move on

---

## 7. Error Handling

### Connection Failures

```python
try:
    messages = queue_manager.dequeue(...)
except RedisError as e:
    logger.error(f"Redis connection failed: {e}")
    # Retry with exponential backoff
    time.sleep(2 ** retry_count)
```

### Message Processing Failures

```python
tier, msg_id, msg_data = queue_manager.dequeue(...)

try:
    result = process_llm_request(msg_data)
    queue_manager.acknowledge(tier, msg_id)  # Success!
except Exception as e:
    # Don't acknowledge - message stays pending
    # Another worker will retry it after timeout
    logger.error(f"Failed to process {msg_id}: {e}")
```

**Automatic Retry:**
- If worker crashes before ACK, message stays in "pending" list
- After timeout (configurable), another worker can claim it
- Use `XPENDING` and `XCLAIM` for manual retry logic

---

## 8. Monitoring & Observability

### Queue Depth

```python
depths = queue_manager.get_all_queue_depths()
# {'gold': 5, 'silver': 23, 'bronze': 142}
```

**Use cases:**
- **Alerting**: If Bronze queue > 1000, scale up workers
- **Dashboards**: Visualize queue backlog in Grafana
- **Auto-scaling**: Trigger K8s HPA based on queue depth

### Latency Tracking

```python
enqueued_at = datetime.fromisoformat(msg_data['enqueued_at'])
queue_latency = datetime.utcnow() - enqueued_at

# Log to Prometheus
queue_latency_histogram.observe(queue_latency.total_seconds())
```

---

## 9. Testing Strategy

### Unit Tests (Mocked Redis)

```python
def test_enqueue_adds_to_correct_queue(mock_redis):
    queue_manager.enqueue(SLATier.GOLD, ...)
    mock_redis.xadd.assert_called_once()
    assert call_args['name'] == 'gold_queue'
```

**Benefits:**
- Fast (no real Redis needed)
- Isolated (tests don't interfere)
- Deterministic (no timing issues)

### Integration Tests (Real Redis)

```python
def test_priority_ordering(redis_container):
    # Enqueue to all tiers
    queue_manager.enqueue(SLATier.BRONZE, "req_1", ...)
    queue_manager.enqueue(SLATier.GOLD, "req_2", ...)
    queue_manager.enqueue(SLATier.SILVER, "req_3", ...)

    # Dequeue should return Gold first
    messages = queue_manager.dequeue("worker-1")
    assert messages[0][2]['request_id'] == "req_2"  # Gold
```

---

## 10. Production Considerations

### Redis Configuration

```redis
# redis.conf
appendonly yes              # Enable AOF persistence
appendfsync everysec        # Fsync every second (balance speed/durability)
maxmemory 2gb              # Limit memory usage
maxmemory-policy allkeys-lru  # Evict least recently used keys
```

### Consumer Group Management

```bash
# View consumer group info
redis-cli XINFO GROUPS gold_queue

# View pending messages
redis-cli XPENDING gold_queue workers

# Claim abandoned messages (worker crashed)
redis-cli XCLAIM gold_queue workers worker-2 3600000 <message-id>
```

### Scaling Workers

**Horizontal scaling:**
- Add more workers with unique `consumer_name`
- Redis automatically distributes messages
- No coordination needed!

**Vertical scaling:**
- Increase `count` parameter (fetch multiple messages)
- Process in parallel (thread pool)

---

## 11. Next Steps

Now that we have the queue system, we'll build:

1. **API Gateway** (Task #2): Receives requests, enqueues them
2. **Worker Pool Manager** (Task #7): Dequeues and processes requests
3. **vLLM Integration** (Task #6): Actual LLM inference

---

## Try It Out (Once Redis is Running)

```python
from src.queue_manager import queue_manager
from src.shared.types import SLATier

# Enqueue some requests
queue_manager.enqueue(
    tier=SLATier.GOLD,
    request_id="req_1",
    tenant_id="tenant_123",
    api_key="sk_test_abc",
    prompt="Hello, world!"
)

# Check queue depth
print(queue_manager.get_all_queue_depths())
# {'gold': 1, 'silver': 0, 'bronze': 0}

# Dequeue (as a worker)
messages = queue_manager.dequeue(consumer_name="worker-1")
tier, msg_id, msg_data = messages[0]
print(f"Processing: {msg_data['prompt']}")

# Acknowledge when done
queue_manager.acknowledge(tier, msg_id)
```

---

## Redis Streams Cheat Sheet

| Command | Purpose | Example |
|---------|---------|---------|
| `XADD` | Add message | `XADD mystream * field1 value1` |
| `XREADGROUP` | Read as consumer | `XREADGROUP GROUP mygroup consumer1 STREAMS mystream >` |
| `XACK` | Acknowledge message | `XACK mystream mygroup 1234567890-0` |
| `XLEN` | Get stream length | `XLEN mystream` |
| `XPENDING` | View pending messages | `XPENDING mystream mygroup` |
| `XGROUP CREATE` | Create consumer group | `XGROUP CREATE mystream mygroup 0 MKSTREAM` |

---

## Summary

We built a **priority-based message queue** that:
- ✓ Separates requests by SLA tier (Gold/Silver/Bronze)
- ✓ Ensures high-priority customers get faster service
- ✓ Distributes load across multiple workers
- ✓ Handles failures gracefully (automatic retry)
- ✓ Provides observability (queue depth, latency)
- ✓ Scales horizontally (add more workers)

This is the **scheduling backbone** of our multi-tenant platform!
