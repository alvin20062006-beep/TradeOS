# Developer Setup Guide

This guide walks you through setting up the TradeOS development environment.

## Prerequisites

- Python 3.10+
- Git
- Docker (optional, for PostgreSQL)

## Step 1: Clone Repository

```bash
cd ~/projects
git clone <repository-url> TradeOS
cd TradeOS
```

## Step 2: Create Virtual Environment

```bash
# Create venv
python -m venv venv

# Activate
# macOS/Linux:
source venv/bin/activate
# Windows:
.\venv\Scripts\activate
```

## Step 3: Install Dependencies

```bash
# Product runtime + local test stack
pip install -r requirements-local.txt
pip install -e ".[dev,test]"

# Optional research extras
pip install -e ".[research]"

# Optional execution extras
pip install -e ".[execution]"
```

## Step 4: Configure Environment

```bash
# Copy environment template
cp config/env/development.example.yaml config/env/development.yaml

# Edit configuration
nano config/env/development.yaml
```

### Development Configuration

```yaml
environment: development
debug: true

database:
  type: sqlite
  sqlite_path: "audit.db"

execution:
  mode: backtest

logging:
  level: DEBUG
  format: text
```

## Step 5: Setup Database

```bash
# Run migrations
make db-migrate

# Or with Alembic directly
alembic upgrade head
```

## Step 6: Verify Installation

```bash
# Check schemas
make schema-check

# Check config
make config-check

# Run all tests
python -m pytest -q

# Run release gate
python -m pytest -m release -q
```

## Step 7: Install Pre-commit Hooks (Optional)

```bash
make pre-commit-install
```

## IDE Setup

### VS Code

Create `.vscode/settings.json`:

```json
{
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "editor.formatOnSave": true,
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true
  }
}
```

### PyCharm

1. Open Settings → Project → Python Interpreter
2. Select your venv
3. Set test runner to pytest
4. Enable Black formatter

## Running the Application

### CLI

```bash
# Check CLI help
tradeos --help

# Status
tradeos status
```

### API Server

```bash
# Start API server
python run.py api

# API will be available at http://localhost:8000
```

### Product Shell / Console

```bash
# Start desktop shell
python run.py start

# Open console in browser for development fallback
python run.py console
```

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError`:

```bash
# Reinstall package
pip install -e .
```

### Database Errors

```bash
# Reset database
make db-reset
```

### Test Failures

```bash
# Run with verbose output
pytest tests/ -vv --tb=long

# Run specific test
pytest tests/unit/test_schemas.py -vv
```

## Common Issues

### TA-Lib Installation (Windows)

TA-Lib requires manual installation on Windows:

1. Download TA-Lib from https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
2. Install: `pip install TA-Lib‑0.4.28‑cp310‑cp310‑win_amd64.whl`

### Optional Research Dependencies

Research extras such as Qlib are optional. The default full pytest run must stay green even when these packages are absent, and research-only tests must skip cleanly.

Qlib may require additional setup:

```bash
# Initialize Qlib data
python -m qlib.tests.data_tests.dump_all_data
```

## Next Steps

- Read [System Overview](../architecture/system_overview.md)
- Review [Module Boundaries](../architecture/module_boundaries.md)
- Check [ROADMAP.md](../../ROADMAP.md)
