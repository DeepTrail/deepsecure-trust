# Testing Guide

> Extracted from CLAUDE.md. This is the reference for test organization, markers, and backend dependencies.

## Test Organization

- **`tests/_core/`**: Core module unit tests (client, identity_manager, environment_detection)
- **`tests/commands/`**: CLI command tests (agent, auth, policy, vault)
- **`tests/sdk/`**: SDK-level tests (gateway requests, client properties, credentials)
- **`tests/test_examples.py`**: Example script validation
- **`tests/docs/`**: Documentation validation (README snippets)
- **End-to-end tests**: Marked with `@pytest.mark.e2e`, require live backend
- **Integration tests**: Marked with `@pytest.mark.integration`

## Running Tests

```bash
# Run all tests
make test
pytest

# Run tests with coverage
make test-cov
pytest --cov=deepsecure --cov-report=html --cov-report=term

# Run single test file
pytest tests/test_sdk_client.py

# Run tests by marker
pytest -m e2e -v          # End-to-end tests only
pytest -m integration -v  # Integration tests only

# Run tests with specific patterns
pytest -k "test_agent" -v  # All tests with 'agent' in name
```

## Backend Dependencies

Many tests require the backend services running:

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

## File Organization Rules

| Artifact Type | Correct Location | Wrong Location |
|---------------|------------------|----------------|
| MVP E2E tests (cross-service) | `tests/e2e/` (root) | `deeptrail-gateway/tests/e2e/` |
| MVP demos (cross-service) | `demos/` (root) | `deeptrail-gateway/demos/` |
| Demo tests | `tests/demos/` (root) | `deeptrail-gateway/tests/demos/` |
| Service-specific unit tests | `[service]/tests/` | Root level |

**Rule of thumb**: If it tests/demonstrates functionality spanning multiple services, it belongs at the root level.

## Test Suite Health (MANDATORY)

ALL tests must pass before a batch is declared complete.

| Scenario | Action |
|----------|--------|
| Test fails and was broken by your changes | Fix immediately — this is a regression |
| Test was already failing before your changes | Fix it anyway — you encountered it, you own it |
| Test requires live services (Redis, PostgreSQL) | Mark with `@pytest.mark.e2e` or `@pytest.mark.integration`, but do NOT skip silently |
| Test references non-existent code (design spec drift) | Rewrite to test actual implementation |
| Test is flaky (passes alone, fails in suite) | Fix the root cause (usually fixture cleanup, DB state pollution, or `dependency_overrides.clear()`) |

### Common Root Causes of Pre-Existing Failures

- Tests written against design specs, not actual implementation (wrong imports, non-existent classes)
- `app.dependency_overrides.clear()` in one test fixture destroying overrides set by conftest (use `pop()` instead)
- Hardcoded expected values that drifted (version numbers, backend counts, response field names)
- Missing fixture cleanup causing `UNIQUE constraint` violations across tests
- Pydantic V2 migration: aliases in error messages, `ConfigDict` vs `class Config`

### Verification

```bash
cd deeptrail-control && python -m pytest tests/ --ignore=tests/test_jwt_tokens.py -q --tb=short
cd deeptrail-gateway && python -m pytest tests/ -q --tb=short
```

## Technical Requirements

| Requirement | Correct Pattern | Common Mistake |
|-------------|-----------------|----------------|
| Async fixtures | `@pytest_asyncio.fixture` | `@pytest.fixture` (breaks async) |
| HTTP client | `httpx.AsyncClient` | `requests` (sync) |
| Mock external APIs | `respx` or `httpx` mock | Calling live APIs in tests |
