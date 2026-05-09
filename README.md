# Multi-Tenant AI Platform

Production-grade multi-tenant LLM platform with priority-based scheduling, token billing, and dynamic GPU resource allocation.

## Architecture

- **API Gateway:** FastAPI with API key auth and rate limiting
- **Queue:** Redis Streams with 3 priority tiers (Gold/Silver/Bronze)
- **Scheduler:** Python Worker Pool Manager with K8s autoscaling
- **Serving:** vLLM (TinyLlama-1.1B locally, Llama-3-8B in cloud)
- **Storage:** PostgreSQL for metadata and billing
- **Observability:** Prometheus + Grafana

## Local Development

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Minikube or Kind
- 4GB+ VRAM GPU (for local vLLM)

### Setup

```bash
# Install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start infrastructure
docker-compose up -d

# Run database migrations
alembic upgrade head

# Start API Gateway
python -m src.api_gateway.main

# Start Worker Manager (in another terminal)
python -m src.worker_manager.main
```

### Testing

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Load tests
locust -f tests/load/locustfile.py
```

## Cloud Deployment (GCP)

```bash
# Deploy to GKE
./scripts/deploy_gcp.sh

# Run cloud validation
pytest tests/integration/ --cloud
```

## Project Status

**Phase 1 (MVP):** In Progress
- [ ] API Gateway with auth and rate limiting
- [ ] Redis Streams priority queues
- [ ] Worker Pool Manager with scheduling
- [ ] PostgreSQL schema and migrations
- [ ] vLLM local deployment (TinyLlama)
- [ ] Token billing and usage tracking
- [ ] Prometheus metrics
- [ ] Integration tests

**Phase 2 (Advanced Features):** Not Started
- [ ] A/B testing framework
- [ ] Real-time cost dashboard
- [ ] Automated alerting
