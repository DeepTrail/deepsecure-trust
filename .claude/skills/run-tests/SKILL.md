---
name: run-tests
description: >-
  Run and analyze tests for the DeepSecure project. Knows test locations,
  markers, fixture patterns, and coverage requirements. Use when the user
  asks to run tests, check coverage, fix failing tests, or add missing tests.
argument-hint: "[scope: all | changed | file-path]"
arguments: [scope]
allowed-tools: Bash(pytest *) Bash(python -m pytest *) Bash(git diff *)
---

## Project context

!`python -c "import sys; print(f'Python {sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "Python not detected"`

```!
# Detect what changed (skip if scope is explicit)
if [ -d .git ]; then
  echo "=== Recently modified Python files ==="
  git diff --name-only HEAD~1 2>/dev/null | grep '\.py$' | head -20
  echo ""
  echo "=== Recently modified test files ==="
  git diff --name-only HEAD~1 2>/dev/null | grep 'test_' | head -20
fi
```

## Test organization

| Type | Location | Marker | When to run |
|------|----------|--------|-------------|
| Core unit tests | `tests/_core/` | (none) | Always |
| Command tests | `tests/commands/` | (none) | After CLI changes |
| SDK tests | `tests/sdk/` | (none) | After client/SDK changes |
| Integration | `tests/` | `@pytest.mark.integration` | After service changes |
| End-to-end | `tests/e2e/` | `@pytest.mark.e2e` | Requires live backend |
| Demo validation | `tests/demos/` | (none) | After demo scripts change |

## How to run

Based on `$scope`:

- **`all`** (or no argument): `pytest -v`
- **`changed`**: Run tests matching changed files only:
  ```bash
  # Find test files for changed source files
  git diff --name-only HEAD~1 | grep '\.py$' | sed 's|deepsecure/|tests/|;s|\.py$||' | while read f; do
    find tests -name "test_$(basename $f).py" 2>/dev/null
  done | sort -u | xargs pytest -v
  ```
- **A file path**: `pytest $scope -v`

Always add `-v` for verbose output. Add `--tb=short` for concise tracebacks.

### Useful pytest flags

```
pytest -v                          # verbose
pytest -x                          # stop on first failure
pytest -k "test_agent"             # filter by name pattern
pytest -m e2e                      # run only e2e-marked tests
pytest -m "not e2e"                # skip e2e tests
pytest --cov=deepsecure --cov-report=term   # with coverage
pytest --tb=short                  # short tracebacks
pytest --lf                        # rerun last failures only
```

## Critical patterns

**Async fixtures** — MUST use `@pytest_asyncio.fixture`, not `@pytest.fixture`:

```python
import pytest_asyncio

@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as c:
        yield c
```

**Auth token tests** — every auth-gated endpoint needs these 4 cases:

| Test | Token | Expected |
|------|-------|----------|
| Correct token type | User Token / Agent JWT (per endpoint) | 200 |
| Wrong token type | Agent JWT where User Token expected (or vice versa) | 401 |
| Expired token | Valid structure, past expiry | 401 |
| Missing token | No Authorization header | 401 or 403 |

## After running

1. If all pass: report summary and any coverage gaps
2. If failures: for each failure, identify root cause category:
   - **Code bug** → fix the source code
   - **Test bug** → fix the test (stale mock, wrong assertion)
   - **Missing fixture** → check for `@pytest_asyncio.fixture`
   - **Backend required** → mark with `@pytest.mark.e2e` and skip
3. For detailed debugging patterns, see [reference/debug-test-failures.md](reference/debug-test-failures.md)
