# Makefile for multi-tenant AI platform development

.PHONY: help up down restart logs clean test db-migrate db-reset

help: ## Show this help message
	@echo "Multi-Tenant AI Platform - Development Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Start all services
	docker-compose up -d
	@echo "✓ Services started. Access points:"
	@echo "  - API Gateway: http://localhost:8000"
	@echo "  - vLLM: http://localhost:8001"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Grafana: http://localhost:3000 (admin/admin)"
	@echo "  - PostgreSQL: localhost:5432"
	@echo "  - Redis: localhost:6379"

down: ## Stop all services
	docker-compose down

restart: ## Restart all services
	docker-compose restart

logs: ## Show logs from all services
	docker-compose logs -f

logs-api: ## Show API Gateway logs
	docker-compose logs -f api-gateway

logs-worker: ## Show Worker Manager logs
	docker-compose logs -f worker-manager

logs-vllm: ## Show vLLM logs
	docker-compose logs -f vllm

clean: ## Stop services and remove volumes
	docker-compose down -v
	@echo "✓ All services stopped and data volumes removed"

db-shell: ## Open PostgreSQL shell
	docker-compose exec postgres psql -U postgres -d mtai_platform

redis-cli: ## Open Redis CLI
	docker-compose exec redis redis-cli

test: ## Run all tests
	pytest tests/ -v

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-integration: ## Run integration tests only
	pytest tests/integration/ -v

install: ## Install Python dependencies
	pip install -r requirements.txt

dev-setup: install up ## Complete development setup
	@echo "✓ Development environment ready!"
	@echo "Run 'make db-migrate' to apply database migrations"

db-migrate: ## Run database migrations
	alembic upgrade head

db-rollback: ## Rollback last migration
	alembic downgrade -1

db-reset: ## Reset database (WARNING: deletes all data)
	docker-compose down postgres
	docker volume rm multi-tenant-ai-platform_postgres_data || true
	docker-compose up -d postgres
	@echo "⚠ Database reset complete. Run 'make db-migrate' to recreate schema"

check-health: ## Check health of all services
	@echo "Checking service health..."
	@curl -s http://localhost:8000/health || echo "❌ API Gateway not responding"
	@curl -s http://localhost:8001/health || echo "❌ vLLM not responding"
	@curl -s http://localhost:9090/-/healthy || echo "❌ Prometheus not responding"
	@docker-compose exec -T postgres pg_isready || echo "❌ PostgreSQL not ready"
	@docker-compose exec -T redis redis-cli ping || echo "❌ Redis not responding"
