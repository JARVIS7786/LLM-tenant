# Quick Start Guide

## Prerequisites
- Docker Desktop installed and running
- Python 3.11+ with pip
- Git

## Setup (First Time)

1. **Clone and enter directory**
   ```bash
   cd multi-tenant-ai-platform
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env and set POSTGRES_PASSWORD to something secure
   ```

3. **Start infrastructure**
   ```bash
   docker-compose up -d
   ```

4. **Wait for services to be healthy** (30-60 seconds)
   ```bash
   docker-compose ps
   ```

5. **Install Python dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

## Daily Development

```bash
# Start services
docker-compose up -d

# Run API Gateway (once we build it)
python -m src.api_gateway.main

# Run Worker Manager (in another terminal)
python -m src.worker_manager.main

# Run tests
pytest tests/ -v

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| API Gateway | http://localhost:8000 | REST API endpoints |
| vLLM | http://localhost:8001 | LLM inference |
| Prometheus | http://localhost:9090 | Metrics |
| Grafana | http://localhost:3000 | Dashboards (admin/admin) |
| PostgreSQL | localhost:5432 | Database |
| Redis | localhost:6379 | Message queue |

## Troubleshooting

**vLLM fails to start?**
- Check if you have enough RAM (needs ~4GB)
- Try smaller model: `VLLM_MODEL_NAME=gpt2` in .env

**PostgreSQL connection refused?**
- Wait 10 seconds for health check to pass
- Check logs: `docker-compose logs postgres`

**Port already in use?**
- Change ports in .env file
- Or stop conflicting service

## What's Next?

See `docs/01-docker-setup.md` for detailed architecture explanation.

Next we'll build:
- Database models and migrations (Task #5)
- API Gateway with authentication (Task #2)
- Redis priority queues (Task #9)
