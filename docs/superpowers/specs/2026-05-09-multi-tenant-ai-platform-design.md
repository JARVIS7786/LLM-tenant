---
name: Multi-Tenant AI Platform Design
description: SaaS LLM platform with priority-based scheduling, token billing, and dynamic resource allocation across 3 SLA tiers
type: design
---

# Multi-Tenant AI Platform - Design Specification

## Executive Summary

A production-grade multi-tenant LLM platform that serves API requests across three SLA tiers (Gold, Silver, Bronze) with priority-based scheduling, token-based billing, and dynamic GPU resource allocation. Built using vLLM for serving, Redis Streams for queue management, and Kubernetes for orchestration.

**Target Timeline:** 10-12 weeks (6 weeks MVP + 4-6 weeks advanced features)

**Target Audience:** SaaS customers (startups, SMBs) consuming LLM APIs

**Business Model:** Pay-per-token pricing with tiered SLAs

---

## Project Context

### Problem Statement

Multiple organizations need LLM capabilities but cannot afford dedicated GPU infrastructure. A multi-tenant platform must:

1. **Isolate tenants** - Prevent data leakage and resource interference
2. **Enforce SLAs** - Gold tier gets priority over Bronze
3. **Optimize costs** - Share GPU resources efficiently across tenants
4. **Track usage** - Accurate token-based billing per tenant
5. **Scale dynamically** - Handle traffic spikes without over-provisioning

### Success Criteria

**Phase 1 (MVP - Week 6):**
- ✅ Serve LLM requests across 3 SLA tiers with priority enforcement
- ✅ Token-based billing with <1% error rate
- ✅ Dynamic pod scaling based on queue depth
- ✅ P99 latency: Gold <2s, Silver <5s, Bronze <10s
- ✅ GPU utilization >60% (cost efficiency)

**Phase 2 (Week 10-12):**
- ✅ A/B testing framework for model versions
- ✅ Real-time cost attribution dashboard
- ✅ Automated alerting for SLA violations

---

## Architecture Overview

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENTS                                  │
│  (Developers making API calls with API keys)                    │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY                                 │
│  - Authentication (API key validation)                          │
│  - Rate limiting (by SLA tier)                                  │
│  - Request validation                                           │
│  - Enqueue to Redis Streams                                     │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                   REDIS STREAMS (Priority Queues)               │
│  ┌──────────────┬──────────────┬──────────────┐                │
│  │ gold_queue   │ silver_queue │ bronze_queue │                │
│  │ (Priority 1) │ (Priority 2) │ (Priority 3) │                │
│  └──────────────┴──────────────┴──────────────┘                │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│              WORKER POOL MANAGER (Scheduler)                    │
│  - Consumes from queues (Gold → Silver → Bronze)               │
│  - Routes requests to available vLLM pods                       │
│  - Monitors queue depth & scales pods via K8s API              │
│  - Tracks token usage for billing                              │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER                           │
│  ┌──────────────────────────────────────────────────┐          │
│  │  vLLM Pod Pool (Gold Tier)                       │          │
│  │  - Min replicas: 2, Max: 5                       │          │
│  │  - Each pod: 1 GPU, Llama-3-8B loaded           │          │
│  └──────────────────────────────────────────────────┘          │
│  ┌──────────────────────────────────────────────────┐          │
│  │  vLLM Pod Pool (Silver Tier)                     │          │
│  │  - Min replicas: 1, Max: 3                       │          │
│  └──────────────────────────────────────────────────┘          │
│  ┌──────────────────────────────────────────────────┐          │
│  │  vLLM Pod Pool (Bronze Tier)                     │          │
│  │  - Min replicas: 0, Max: 2                       │          │
│  └──────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                   OBSERVABILITY & STORAGE                       │
│  - PostgreSQL: Tenant metadata, API keys, usage logs           │
│  - Prometheus: Metrics (latency, throughput, GPU util)         │
│  - Grafana: Dashboards (per-tenant cost, SLA compliance)       │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Queue-based priority scheduling** - Simple, debuggable, scales well
2. **GPU-agnostic design** - Same code works with mocked or real GPUs
3. **Kubernetes-native** - Leverage K8s for pod lifecycle, not custom orchestration
4. **Observability-first** - Every request logged with full trace

---

## Component Design

### 1. API Gateway

**Technology:** FastAPI (Python 3.11+)

**Responsibilities:**
- Authenticate requests via API key (stored in PostgreSQL)
- Validate request payload (prompt, max_tokens, temperature, etc.)
- Rate limit by SLA tier (Gold: 1000 req/min, Silver: 100 req/min, Bronze: 10 req/min)
- Enqueue validated requests to Redis Streams
- Return request ID immediately (async processing)

**API Endpoints:**

```
POST /v1/completions
Headers:
  Authorization: Bearer <api_key>
Body:
  {
    "prompt": "string",
    "max_tokens": 100,
    "temperature": 0.7,
    "stream": false
  }
Response:
  {
    "request_id": "uuid",
    "status": "queued",
    "estimated_wait_seconds": 2
  }

GET /v1/completions/{request_id}
Response:
  {
    "request_id": "uuid",
    "status": "completed",
    "result": {
      "text": "generated text",
      "tokens_used": {"prompt": 10, "completion": 50}
    }
  }
```

**Rate Limiting Implementation:**
- Use Redis with sliding window algorithm
- Key: `ratelimit:{api_key}:{minute_bucket}`
- Increment on each request, expire after 60s
- Reject if count > tier limit

**Why FastAPI:**
- Async/await for high concurrency
- Built-in request validation (Pydantic)
- OpenAPI docs auto-generated

---

### 2. Redis Streams (Priority Queues)

**Technology:** Redis 7.0+ with Streams

**Queue Structure:**

```
gold_queue:   [request_1, request_2, ...]
silver_queue: [request_3, request_4, ...]
bronze_queue: [request_5, request_6, ...]
```

**Message Format:**

```json
{
  "request_id": "uuid",
  "tenant_id": "tenant_123",
  "api_key": "key_abc",
  "prompt": "string",
  "max_tokens": 100,
  "temperature": 0.7,
  "enqueued_at": "2026-05-09T14:00:00Z"
}
```

**Why Redis Streams:**
- Built-in consumer groups (multiple workers can consume)
- Persistent (survives Redis restart)
- Atomic operations (no race conditions)
- Low latency (<1ms enqueue/dequeue)

**Alternative Considered:** RabbitMQ
- **Rejected because:** Adds operational complexity (another service to manage), Redis already needed for rate limiting

---

### 3. Worker Pool Manager (Scheduler)

**Technology:** Python 3.11+ with asyncio

**Core Algorithm:**

```python
while True:
    # Priority-based consumption
    request = consume_from_queue(priority_order=["gold", "silver", "bronze"])
    
    if request:
        # Find available vLLM pod
        pod = find_available_pod(tier=request.tier)
        
        if pod:
            # Route request to pod
            response = await send_to_vllm(pod, request)
            
            # Track token usage
            log_usage(request.tenant_id, response.tokens)
        else:
            # No pod available, re-queue with backoff
            requeue(request, delay_seconds=1)
    
    # Check if scaling needed
    if queue_depth("gold") > 10:
        scale_up_pods(tier="gold")
    elif queue_depth("gold") < 2 and pod_count("gold") > min_replicas:
        scale_down_pods(tier="gold")
```

**Scaling Logic:**

| Condition | Action |
|-----------|--------|
| Queue depth > 10 requests | Scale up by 1 pod (max: tier limit) |
| Queue depth < 2 AND idle time > 5 min | Scale down by 1 pod (min: tier limit) |
| Pod startup time | ~60s (model loading) |

**Why Python:**
- Easy integration with K8s Python client
- Async/await for concurrent request handling
- Simple to test and debug

---

### 4. vLLM Serving Pods

**Technology:** vLLM 0.4.0+ with Llama-3-8B (4-bit quantized)

**Pod Specification:**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: vllm-gold-1
  labels:
    tier: gold
spec:
  containers:
  - name: vllm
    image: vllm/vllm-openai:latest
    resources:
      limits:
        nvidia.com/gpu: 1
        memory: 24Gi
      requests:
        nvidia.com/gpu: 1
        memory: 16Gi
    env:
    - name: MODEL_NAME
      value: "meta-llama/Llama-3-8B"
    - name: QUANTIZATION
      value: "awq"
    - name: MAX_MODEL_LEN
      value: "4096"
    ports:
    - containerPort: 8000
```

**vLLM Configuration:**
- **PagedAttention:** Enabled (reduces KV-cache memory by 60%)
- **Continuous batching:** Enabled (dynamic request batching)
- **Quantization:** AWQ 4-bit (16GB model → 4GB)
- **Max batch size:** 32 requests
- **Max sequence length:** 4096 tokens

**Why vLLM:**
- Industry standard (used by Anthropic, Perplexity)
- 2-4x throughput vs naive PyTorch serving
- OpenAI-compatible API (easy integration)

---

### 5. PostgreSQL (Metadata Store)

**Schema:**

```sql
-- Tenants table
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sla_tier VARCHAR(10) CHECK (sla_tier IN ('gold', 'silver', 'bronze')),
    created_at TIMESTAMP DEFAULT NOW()
);

-- API Keys table
CREATE TABLE api_keys (
    key VARCHAR(64) PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    rate_limit_per_minute INT,
    created_at TIMESTAMP DEFAULT NOW(),
    revoked_at TIMESTAMP NULL
);

-- Usage logs table (for billing)
CREATE TABLE usage_logs (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID NOT NULL,
    tenant_id UUID REFERENCES tenants(id),
    prompt_tokens INT NOT NULL,
    completion_tokens INT NOT NULL,
    total_tokens INT NOT NULL,
    latency_ms INT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX idx_usage_tenant_time ON usage_logs(tenant_id, created_at);
CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id);
```

**Why PostgreSQL:**
- ACID guarantees for billing data
- Rich query capabilities (aggregations for cost reports)
- Well-understood operational model

---

### 6. Observability Stack

**Prometheus Metrics:**

```
# Request metrics
llm_requests_total{tier="gold", status="success"}
llm_request_duration_seconds{tier="gold", quantile="0.99"}
llm_tokens_generated_total{tier="gold"}

# Queue metrics
redis_queue_depth{queue="gold_queue"}
redis_queue_wait_time_seconds{queue="gold_queue"}

# Resource metrics
vllm_pod_count{tier="gold"}
vllm_gpu_utilization_percent{pod="vllm-gold-1"}
vllm_requests_per_second{pod="vllm-gold-1"}
```

**Grafana Dashboards:**

1. **Tenant Cost Dashboard**
   - Total tokens used (last 30 days)
   - Estimated cost ($0.01 per 1K tokens)
   - Request volume by hour

2. **SLA Compliance Dashboard**
   - P50/P99 latency by tier
   - Request success rate
   - Queue wait time

3. **Resource Utilization Dashboard**
   - GPU utilization per pod
   - Pod count by tier
   - Cost per GPU hour

---

## Data Flow

### Request Lifecycle

```
1. Client sends POST /v1/completions with API key
   ↓
2. API Gateway validates API key → looks up tenant + SLA tier
   ↓
3. Rate limiter checks: has tenant exceeded tier limit?
   - If yes: return 429 Too Many Requests
   - If no: continue
   ↓
4. Request enqueued to Redis Stream (gold/silver/bronze queue)
   ↓
5. API Gateway returns 202 Accepted with request_id
   ↓
6. Worker Pool Manager consumes from queue (priority: gold → silver → bronze)
   ↓
7. Manager finds available vLLM pod for that tier
   ↓
8. Manager sends request to vLLM pod via HTTP
   ↓
9. vLLM generates tokens (streaming or batch)
   ↓
10. vLLM returns response with token counts
   ↓
11. Manager logs usage to PostgreSQL (tenant_id, tokens, latency)
   ↓
12. Manager stores result in Redis (key: request_id, TTL: 1 hour)
   ↓
13. Client polls GET /v1/completions/{request_id} to retrieve result
```

**Why async (202 Accepted) instead of sync?**
- LLM generation takes 500ms-2s (too slow for HTTP timeout)
- Allows client to poll or use webhooks
- Decouples API Gateway from vLLM availability

---

## Deployment Strategy

### Local Development Environment

**Hardware Constraint:** 4GB VRAM GPU (insufficient for Llama-3-8B)

**Solution:** Use lightweight proxy model for local testing

**Local Model:** TinyLlama-1.1B or Qwen-0.5B
- Model size: ~600MB (fits in 4GB VRAM)
- Inference speed: ~50 tokens/sec on 4GB GPU
- Purpose: Test routing, scaling, and queue logic

**Local Stack:**
- Docker Compose for services (API Gateway, Worker Manager, Redis, PostgreSQL)
- Minikube or Kind for local Kubernetes
- vLLM with TinyLlama-1.1B (mocked GPU scheduling)

**Local Development Flow:**
1. Start Docker Compose: `docker-compose up`
2. Start Minikube: `minikube start --driver=docker`
3. Deploy vLLM pods: `kubectl apply -f k8s/vllm-local.yaml`
4. Run integration tests with TinyLlama
5. Validate queue logic, scaling, and billing

---

### Cloud Validation Environment (GCP)

**Frequency:** Weekly (every Friday)

**Infrastructure:**
- GKE cluster with 1-2 T4 GPU nodes
- Cloud SQL (PostgreSQL)
- Cloud Monitoring (Prometheus-compatible)

**Cloud Model:** Llama-3-8B (4-bit quantized via AWQ)
- Model size: ~4GB
- Inference speed: ~20 tokens/sec on T4
- Purpose: Validate real GPU performance and scaling

**Cloud Validation Checklist:**
1. Deploy full stack to GKE
2. Run load tests (100 concurrent requests)
3. Measure P99 latency by tier
4. Validate GPU utilization >60%
5. Check token billing accuracy
6. Tear down cluster (minimize costs)

**Cost Estimate:**
- T4 GPU: $0.35/hour
- Testing duration: 4 hours/week
- Total: ~$1.40/week × 8 weeks = $11.20

**Why this approach:**
- Fast local iteration (no cloud deploy delays)
- Real GPU validation when needed
- Minimal cloud costs (<$80 total)

---

## Error Handling

### Failure Scenarios

| Failure | Detection | Recovery |
|---------|-----------|----------|
| vLLM pod crashes | K8s liveness probe fails | K8s restarts pod automatically |
| Redis goes down | Connection timeout | API Gateway returns 503, requests buffered in memory |
| PostgreSQL unavailable | Connection timeout | Log to local file, sync when DB recovers |
| GPU OOM (out of memory) | vLLM returns 500 | Worker Manager retries with smaller batch size |
| Queue depth > 1000 | Prometheus alert | Auto-scale pods to max, notify ops team |

### Retry Logic

**Client-side:**
- Exponential backoff: 1s, 2s, 4s, 8s (max 4 retries)
- Retry on: 429 (rate limit), 503 (service unavailable)
- Do NOT retry on: 400 (bad request), 401 (unauthorized)

**Server-side (Worker Manager):**
- Retry failed vLLM requests up to 3 times
- If all retries fail: move request to dead-letter queue
- Alert ops team if dead-letter queue depth > 10

---

## Security

### Tenant Isolation

1. **API Key-based authentication**
   - Each tenant gets unique API key (64-char random string)
   - Keys stored hashed in PostgreSQL (bcrypt)
   - Keys rotatable via admin API

2. **Network isolation**
   - vLLM pods in separate K8s namespace per tier
   - Network policies prevent cross-tier communication

3. **Data isolation**
   - No shared state between tenants
   - Usage logs partitioned by tenant_id
   - Prompts NOT logged (privacy)

### Rate Limiting

**Purpose:** Prevent abuse and ensure fair resource allocation

**Implementation:**
- Sliding window algorithm (Redis)
- Limits by tier:
  - Gold: 1000 req/min
  - Silver: 100 req/min
  - Bronze: 10 req/min

**Burst handling:**
- Allow 2x burst for 10 seconds (e.g., Gold can do 2000 req/min for 10s)
- After burst: throttle to normal rate

---

## Testing Strategy

### Unit Tests

**Coverage target:** >80%

**Key test cases:**
- API Gateway: rate limiting logic, API key validation
- Worker Manager: queue consumption order, scaling decisions
- Token counting: verify input/output token accuracy

**Tools:** pytest, pytest-asyncio

---

### Integration Tests

**Scenarios:**
1. **End-to-end request flow**
   - Send request → verify queued → verify processed → verify billed
2. **Priority enforcement**
   - Enqueue 10 Bronze + 10 Gold requests
   - Verify Gold requests processed first
3. **Scaling behavior**
   - Enqueue 50 requests → verify pods scale up
   - Wait 5 min → verify pods scale down

**Tools:** pytest, Docker Compose (local stack)

---

### Load Tests

**Tool:** Locust (Python-based load testing)

**Scenarios:**
1. **Sustained load**
   - 100 req/sec for 10 minutes
   - Verify P99 latency < 5s
2. **Spike load**
   - 0 → 500 req/sec in 10 seconds
   - Verify queue absorbs spike, no dropped requests
3. **Mixed tier load**
   - 50% Gold, 30% Silver, 20% Bronze
   - Verify Gold gets priority

**Success criteria:**
- No request failures (<0.1% error rate)
- P99 latency within SLA targets
- GPU utilization >60%

---

## Monitoring & Alerting

### Key Metrics

| Metric | Threshold | Alert |
|--------|-----------|-------|
| P99 latency (Gold) | >3s | Page on-call |
| Queue depth | >100 | Scale up pods |
| GPU utilization | <40% | Scale down pods |
| Request error rate | >1% | Page on-call |
| Dead-letter queue depth | >10 | Page on-call |

### Dashboards

1. **Real-time Operations Dashboard**
   - Current queue depth by tier
   - Active pod count by tier
   - Requests per second
   - P50/P99 latency

2. **Business Metrics Dashboard**
   - Total tokens generated (last 24h)
   - Revenue estimate ($0.01 per 1K tokens)
   - Top 10 tenants by usage
   - New tenant signups

---

## Cost Model

### Pricing Tiers

| Tier | Rate Limit | Price per 1K tokens | Min Monthly |
|------|------------|---------------------|-------------|
| Free (Bronze) | 10 req/min | $0.02 | $0 |
| Pro (Silver) | 100 req/min | $0.015 | $50 |
| Enterprise (Gold) | 1000 req/min | $0.01 | $500 |

### Cost Attribution

**Per-request tracking:**
```python
cost = (prompt_tokens + completion_tokens) / 1000 * price_per_1k_tokens
```

**Monthly billing:**
- Aggregate usage_logs by tenant_id
- Generate invoice on 1st of month
- Send via email + store in PostgreSQL

**Why token-based pricing:**
- Industry standard (OpenAI, Anthropic use this)
- Fair: customers pay for what they use
- Predictable: customers can estimate costs

---

## Phase 2 Features (Weeks 7-10)

### 1. A/B Testing Framework

**Use case:** Test new model versions before full rollout

**Design:**
- Each tenant can have multiple model versions (e.g., v1, v2)
- Traffic split: 90% v1, 10% v2
- Track metrics per version (latency, token usage, error rate)
- Promote v2 to 100% if metrics improve

**Implementation:**
- Add `model_version` field to requests
- Worker Manager routes to appropriate vLLM pod
- Grafana dashboard compares versions side-by-side

---

### 2. Real-Time Cost Dashboard

**Use case:** Tenants see live usage and costs

**Design:**
- WebSocket connection to stream usage updates
- Chart: tokens used per hour (last 24h)
- Projected monthly cost based on current usage

**Implementation:**
- FastAPI WebSocket endpoint
- Prometheus metrics → WebSocket stream
- React frontend with Chart.js

---

### 3. Automated Alerting

**Use case:** Notify tenants when approaching rate limits or budget

**Alerts:**
- "You've used 80% of your monthly budget"
- "You're being rate-limited (upgrade to Pro?)"
- "Your API key expires in 7 days"

**Implementation:**
- Background job checks usage every hour
- Send email via SendGrid API
- Store alert history in PostgreSQL

---

## Open Questions

None - all requirements clarified during brainstorming.

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| vLLM pod startup time (60s) | Slow scaling response | Pre-warm 1 pod per tier (min replicas) |
| Redis single point of failure | All requests blocked | Redis Sentinel (HA mode) in Phase 2 |
| Token counting inaccuracy | Billing disputes | Use vLLM's built-in tokenizer (same as model) |
| GPU costs exceed budget | Project blocked | Use GCP free credits + spot instances |

---

## Success Metrics (Phase 1)

**Technical:**
- ✅ P99 latency: Gold <2s, Silver <5s, Bronze <10s
- ✅ GPU utilization >60%
- ✅ Request success rate >99.9%
- ✅ Token billing accuracy >99%

**Learning:**
- ✅ Understand PagedAttention internals (vLLM)
- ✅ Implement priority-based queue scheduling
- ✅ Build K8s autoscaling logic
- ✅ Design token-based billing system

**Portfolio:**
- ✅ Working demo with 3 SLA tiers
- ✅ Grafana dashboards showing real metrics
- ✅ GitHub repo with clean code + docs
- ✅ Blog post explaining architecture

---

## Timeline

**Week 1-2:** Math foundations + local setup
- Queuing theory (M/M/c queues, Little's Law)
- Redis Streams deep-dive
- Set up Docker Compose + Minikube
- Deploy TinyLlama locally

**Week 3-4:** Core platform
- API Gateway (FastAPI)
- Worker Pool Manager (queue consumption + routing)
- PostgreSQL schema + migrations
- Integration tests

**Week 5-6:** Scaling + observability
- K8s autoscaling logic
- Prometheus metrics
- Grafana dashboards
- Load testing

**Week 7-8:** Cloud validation
- Deploy to GKE with Llama-3-8B
- Run load tests on real GPUs
- Measure P99 latency
- Validate billing accuracy

**Week 9-10:** Phase 2 features (pick 1-2)
- A/B testing framework
- Real-time cost dashboard
- Automated alerting

---

## Appendix: Mathematical Foundations

### Queuing Theory

**Why it matters:** Predict queue wait times and optimal pod count

**M/M/c Queue Model:**
- M/M/c = Poisson arrivals, exponential service time, c servers (GPUs)
- λ = arrival rate (requests/sec)
- μ = service rate (requests/sec per GPU)
- c = number of GPUs

**Little's Law:**
```
L = λ × W
```
- L = average queue length
- λ = arrival rate
- W = average wait time

**Example:**
- λ = 10 req/sec
- μ = 2 req/sec per GPU (500ms per request)
- c = 6 GPUs

**Queue length:** L = λ / (c × μ - λ) = 10 / (6 × 2 - 10) = 5 requests

**Wait time:** W = L / λ = 5 / 10 = 0.5 seconds

**Interview question:** "How many GPUs do you need to keep P99 latency under 2 seconds?"

**Answer:** Use M/M/c formula to calculate wait time distribution, then solve for c where P99 < 2s.

---

### Token Counting

**Why it matters:** Accurate billing depends on correct token counts

**Tokenization:**
- LLMs use subword tokenization (BPE, WordPiece)
- "Hello world" → ["Hello", " world"] = 2 tokens
- "Antidisestablishmentarianism" → ["Anti", "dis", "establish", "ment", "arian", "ism"] = 6 tokens

**Counting:**
```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3-8B")

prompt = "Explain quantum computing"
prompt_tokens = len(tokenizer.encode(prompt))  # e.g., 4 tokens

completion = "Quantum computing uses qubits..."
completion_tokens = len(tokenizer.encode(completion))  # e.g., 50 tokens

total_tokens = prompt_tokens + completion_tokens  # 54 tokens
cost = (total_tokens / 1000) * 0.01  # $0.00054
```

**Interview question:** "Why can't you just count words for billing?"

**Answer:** Tokenization is subword-based. "Hello" = 1 token, but "Antidisestablishmentarianism" = 6 tokens. Word count would undercharge for long words.

---

## Appendix: vLLM PagedAttention

**Why it matters:** Key interview topic for LLM infrastructure roles

**Problem:** KV-cache memory fragmentation

**Traditional approach:**
- Allocate contiguous memory for each request's KV-cache
- If request generates 100 tokens, allocate 100 × hidden_dim × 2 (K + V)
- Problem: Fragmentation wastes 60-80% of GPU memory

**PagedAttention solution:**
- Divide KV-cache into fixed-size "pages" (e.g., 16 tokens per page)
- Store pages non-contiguously (like OS virtual memory)
- Share pages across requests (prefix caching)

**Example:**
- Request 1: "Explain quantum" → KV-cache pages [A, B]
- Request 2: "Explain quantum computing" → Shares pages [A, B], adds page [C]
- Memory saved: 2 pages (50% reduction)

**Interview question:** "How does PagedAttention reduce memory usage?"

**Answer:** By dividing KV-cache into fixed-size pages and allowing non-contiguous storage, PagedAttention eliminates fragmentation and enables prefix sharing across requests.

---

## Conclusion

This design balances production-readiness with achievability. The hybrid queue + K8s approach demonstrates both distributed systems knowledge (queues, priority scheduling) and cloud-native skills (K8s, autoscaling). The local-first development strategy with weekly cloud validation keeps costs under $80 while ensuring the platform works on real GPUs.

**Next steps:** Review this spec, then create implementation plan.
