# Docker Compose Setup - Learning Guide

## What We Just Built

We created a complete local development infrastructure using Docker Compose. Here's what each service does:

### 1. **PostgreSQL** (Port 5432)
- **Purpose**: Stores tenant data, API keys, and billing records
- **Why**: Relational database perfect for structured data with relationships (tenants → API keys → usage records)
- **Key Features**:
  - Auto-runs `init_db.sql` on first startup to create tables
  - Persistent volume so data survives container restarts
  - Health checks to ensure it's ready before other services connect

### 2. **Redis** (Port 6379)
- **Purpose**: Message queue for priority-based request scheduling
- **Why**: In-memory data store with Redis Streams - perfect for high-throughput queuing
- **Key Features**:
  - Append-only file (AOF) persistence for durability
  - Sub-millisecond latency for queue operations
  - Supports priority queues (Gold/Silver/Bronze)

### 3. **vLLM** (Port 8001)
- **Purpose**: LLM inference server (runs the actual AI model)
- **Why**: Optimized for high-throughput LLM serving with continuous batching
- **Key Features**:
  - Uses TinyLlama (1.1B params) for local development
  - OpenAI-compatible API
  - Can be switched to GPU mode by uncommenting deploy section

### 4. **Prometheus** (Port 9090)
- **Purpose**: Metrics collection and time-series database
- **Why**: Industry standard for monitoring microservices
- **Collects**: Request rates, latency, queue depth, token usage

### 5. **Grafana** (Port 3000)
- **Purpose**: Visualization dashboard for metrics
- **Why**: Beautiful, interactive dashboards to monitor system health
- **Default Login**: admin/admin

## Architecture Flow

```
User Request → API Gateway → Redis Queue (Priority) → Worker Pool → vLLM → Response
                    ↓              ↓                      ↓           ↓
                PostgreSQL     Prometheus ← ← ← ← ← ← ← ← ← ← ← Grafana
              (billing data)    (metrics)                      (dashboards)
```

## Key Concepts Explained

### Docker Compose vs Kubernetes
- **Docker Compose**: Local development, single machine, simple YAML
- **Kubernetes**: Production, multi-machine clusters, complex orchestration
- We use Compose locally, will deploy to K8s in production

### Health Checks
Every service has a health check that Docker monitors:
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U postgres"]
  interval: 5s  # Check every 5 seconds
  retries: 5    # Try 5 times before marking unhealthy
```
This prevents services from trying to connect before dependencies are ready.

### Volumes (Data Persistence)
```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data
```
Without volumes, all data is lost when containers stop. Named volumes persist data on your host machine.

### Networks
All services are on `mtai-network` so they can communicate using service names:
- API Gateway connects to `postgres:5432` (not `localhost:5432`)
- Worker connects to `redis:6379`

## Next Steps

Now that infrastructure is ready, we'll build:
1. **Database Models** (SQLAlchemy ORM)
2. **API Gateway** (FastAPI with auth)
3. **Redis Queue Manager** (Priority scheduling)
4. **Worker Pool** (Consumes from queue, calls vLLM)

## Try It Out

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f

# Access services
curl http://localhost:9090  # Prometheus
curl http://localhost:8001/health  # vLLM

# Stop everything
docker-compose down
```
