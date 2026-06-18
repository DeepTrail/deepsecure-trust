# Development Commands

> Extracted from CLAUDE.md. This is the reference for all development commands.

## Environment Setup

```bash
# Install development dependencies
make install-dev
# or traditionally
make install-traditional

# Setup development environment
make setup
```

## Testing

```bash
# Run all tests
make test
pytest

# Run tests with coverage
make test-cov
pytest --cov=deepsecure --cov-report=html --cov-report=term

# Run specific test markers
pytest -m e2e          # End-to-end tests (require live backend)
pytest -m integration  # Integration tests

# Run single test file
pytest tests/test_sdk_client.py

# Run tests by marker
pytest -m e2e -v          # End-to-end tests only
pytest -m integration -v  # Integration tests only

# Run tests with specific patterns
pytest -k "test_agent" -v  # All tests with 'agent' in name
```

## Code Quality

```bash
# Run linting
make lint
ruff check .
mypy deepsecure/

# Format code
make format
black .
isort .

# Security scanning
make security
bandit -r deepsecure/
safety check

# Run all quality checks
make check-all
```

## Build and Package

```bash
# Build package
make build
./scripts/build_package.sh

# Clean build artifacts
make clean
```

## Backend Services

```bash
# Start backend services (includes PostgreSQL and Redis dependencies)
docker compose up deeptrail-control deeptrail-gateway -d

# Start with dependencies (full stack)
docker compose up db redis deeptrail-control deeptrail-gateway -d

# Verify services
curl http://localhost:8000/health  # Control plane
curl http://localhost:8002/health  # Gateway

# View service logs
docker compose logs deeptrail-control  # Control plane logs
docker compose logs deeptrail-gateway  # Gateway logs
```

## Configuration

### Environment Variables

```bash
export DEEPSECURE_DEEPTRAIL_CONTROL_URL=http://localhost:8000
export DEEPSECURE_GATEWAY_URL=http://localhost:8002
export DEEPSECURE_DEBUG=true  # Enable verbose logging
```

### CLI Configuration

```bash
deepsecure configure set-url http://127.0.0.1:8001
deepsecure configure set-gateway-url http://localhost:8002
deepsecure configure set-token  # Prompts for token
```

## Common Debugging

```bash
# Check service status
docker compose ps

# Restart services if needed
docker compose restart deeptrail-control deeptrail-gateway

# Clean restart (removes volumes)
docker compose down -v && docker compose up -d

# Database access for debugging
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb

# Redis access for debugging
docker compose exec redis redis-cli
```

## Service Ports (Development)

| Service | URL | Container Port |
|---------|-----|---------------|
| Control Plane | http://localhost:8000 | 8001 |
| Gateway | http://localhost:8002 | 8001 |
| PostgreSQL | localhost:5434 | 5432 |
| Redis | localhost:6380 | 6379 |

## Post-Implementation Verification

```bash
# After modifying Python files
ruff check [modified_file.py]
python -c "import [module]"  # Verify imports work

# After modifying tests
pytest [test_file.py] -v

# After modifying demos/scripts
python [script.py] --help  # Verify it runs
echo "Exit code: $?"  # Must be 0

# Full quality check before completion
make check-all
```
