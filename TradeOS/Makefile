# AI Trading Tool - Makefile

.PHONY: help install install-dev test test-unit test-integration test-contract lint format clean docs db-migrate db-reset

# ─────────────────────────────────────────────────────────────
# HELP
# ─────────────────────────────────────────────────────────────

help:
	@echo "AI Trading Tool - Available Commands"
	@echo ""
	@echo "  make install          Install package with dependencies"
	@echo "  make install-dev      Install with development dependencies"
	@echo "  make test             Run all tests"
	@echo "  make test-unit        Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make test-contract    Run contract tests only"
	@echo "  make lint             Run linting (ruff)"
	@echo "  make format           Format code (black, ruff)"
	@echo "  make clean            Clean build artifacts"
	@echo "  make docs             Build documentation"
	@echo "  make docs-serve       Serve documentation locally"
	@echo "  make db-migrate       Run database migrations"
	@echo "  make db-reset        Reset database (development only)"
	@echo "  make check            Run all checks (lint + test)"

# ─────────────────────────────────────────────────────────────
# INSTALLATION
# ─────────────────────────────────────────────────────────────

install:
	pip install -e .

install-dev:
	pip install -e ".[dev,test,docs]"

install-full:
	pip install -e ".[full]"

# ─────────────────────────────────────────────────────────────
# TESTING
# ─────────────────────────────────────────────────────────────

test:
	pytest tests/ -v --tb=short

test-unit:
	pytest tests/unit/ -v --tb=short

test-integration:
	pytest tests/integration/ -v --tb=short

test-contract:
	pytest tests/contracts/ -v --tb=short

test-coverage:
	pytest tests/ --cov=ai_trading_tool --cov-report=html --cov-report=term

test-fast:
	pytest tests/ -v --tb=short -m "not slow"

# ─────────────────────────────────────────────────────────────
# LINTING & FORMATTING
# ─────────────────────────────────────────────────────────────

lint:
	ruff check ai_trading_tool tests

format:
	black ai_trading_tool tests
	ruff check --fix ai_trading_tool tests

type-check:
	mypy ai_trading_tool

# ─────────────────────────────────────────────────────────────
# CLEANING
# ─────────────────────────────────────────────────────────────

clean:
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .coverage htmlcov
	rm -rf **/__pycache__ **/*.pyc **/*.pyo
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .ruff_cache .mypy_cache

# ─────────────────────────────────────────────────────────────
# DOCUMENTATION
# ─────────────────────────────────────────────────────────────

docs:
	mkdocs build

docs-serve:
	mkdocs serve -a localhost:8000

docs-deploy:
	mkdocs gh-deploy

# ─────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────

db-migrate:
	alembic upgrade head

db-rollback:
	alembic downgrade -1

db-reset:
	rm -f audit.db
	alembic upgrade head

db-seed:
	python -m ai_trading_tool.infra.db.seeds.run

# ─────────────────────────────────────────────────────────────
# DEVELOPMENT
# ─────────────────────────────────────────────────────────────

dev-setup: install-dev db-migrate
	@echo "Development environment ready!"

pre-commit-install:
	pre-commit install

# ─────────────────────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────────────────────

check: lint test

schema-check:
	python -c "from ai_trading_tool.core.schemas import *; print('All schemas import OK')"

config-check:
	python -c "from ai_trading_tool.core.shared.config import get_config; c = get_config(); print(f'Config loaded: {c.env.environment}')"

# ─────────────────────────────────────────────────────────────
# DOCKER
# ─────────────────────────────────────────────────────────────

docker-build:
	docker build -t ai-trading-tool:latest -f infra/docker/Dockerfile .

docker-run:
	docker run -p 8000:8000 ai-trading-tool:latest

docker-compose-up:
	docker-compose -f infra/docker/docker-compose.yml up -d

docker-compose-down:
	docker-compose -f infra/docker/docker-compose.yml down
