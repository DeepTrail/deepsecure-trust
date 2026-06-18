# Verify App: End-to-End Application Verification

Full-stack verification: start services, run health checks, execute tests, report results. Designed for both interactive use and as a step in the `/go` pipeline.

## Invocation

```
/verify-app [--skip-docker] [--test-only] [--health-check-only]
```

**Parameters:**
- `--skip-docker` — Skip docker compose up/down (services already running)
- `--test-only` — Run tests only, no health checks or docker management
- `--health-check-only` — Only verify services are healthy, no tests

---

## Instructions

### Step 1: Environment Detection

```bash
if [ -n "$AFK_CLOUD_ENV" ]; then
    echo "Cloud environment detected — skipping Docker, running unit/integration tests only"
    # Skip to Step 3 with --skip-docker behavior
fi
```

### Step 2: Start Services (unless `--skip-docker` or `--test-only`)

```bash
echo "Starting services..."
docker compose up -d db redis deeptrail-control deeptrail-gateway

# Wait for healthy
echo "Waiting for services to be healthy..."
RETRIES=0
MAX_RETRIES=30
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do
    RETRIES=$((RETRIES + 1))
    [ "$RETRIES" -ge "$MAX_RETRIES" ] && { echo "❌ Control plane failed to start"; break; }
    sleep 2
done

curl -sf http://localhost:8000/health && echo "✅ Control plane healthy" || echo "❌ Control plane unhealthy"
curl -sf http://localhost:8002/health && echo "✅ Gateway healthy" || echo "❌ Gateway unhealthy"
```

If health checks fail, report and exit:

    ## Verification FAILED: Services Not Healthy

    | Service | Status | URL |
    |---------|--------|-----|
    | Control Plane | ❌ Unhealthy | http://localhost:8000/health |
    | Gateway | ✅ Healthy | http://localhost:8002/health |

    Check logs: docker compose logs deeptrail-control

### Step 3: Run Tests (unless `--health-check-only`)

Run tests in order of speed (fast failures first):

```bash
# 3a. Unit tests (fast)
echo "=== Unit Tests ==="
python -m pytest tests/ --ignore=tests/e2e/ -q --tb=short 2>&1
UNIT_EXIT=$?

# 3b. Service-specific tests
echo "=== Control Plane Tests ==="
cd deeptrail-control && python -m pytest tests/ -q --tb=short 2>&1
CONTROL_EXIT=$?
cd ..

echo "=== Gateway Tests ==="
cd deeptrail-gateway && python -m pytest tests/ -q --tb=short 2>&1
GATEWAY_EXIT=$?
cd ..

# 3c. E2E tests (slow, require services)
if [ -z "$AFK_CLOUD_ENV" ]; then
    echo "=== E2E Tests ==="
    python -m pytest tests/e2e/ -v --tb=short 2>&1
    E2E_EXIT=$?
fi
```

### Step 4: Lint & Type Check

```bash
echo "=== Lint ==="
ruff check deepsecure/ --quiet && echo "✅ Lint clean" || echo "❌ Lint issues"

echo "=== Type Check ==="
mypy deepsecure/ --ignore-missing-imports --quiet && echo "✅ Types clean" || echo "❌ Type issues"
```

### Step 5: Report Results

```markdown
## Verification Report

| Check | Status | Details |
|-------|--------|---------|
| Services healthy | ✅ / ❌ | [which services] |
| Unit tests | ✅ [N] passed / ❌ [N] failed | [failure summary if any] |
| Control plane tests | ✅ / ❌ | [details] |
| Gateway tests | ✅ / ❌ | [details] |
| E2E tests | ✅ / ❌ / ⏭️ skipped | [details] |
| Lint | ✅ / ❌ | [issue count] |
| Type check | ✅ / ❌ | [issue count] |

**Verdict:** [ALL PASSING / FAILURES DETECTED]
```

Save detailed output to `reports/verify-[YYYY-MM-DD-HHMMSS].log`.

### Step 6: Cleanup (unless `--skip-docker`)

```bash
# Only tear down if we started the services
docker compose down 2>/dev/null
```

**Exit behavior:**
- All checks pass → exit 0, print "Verification passed"
- Any check fails → exit 1, print summary of failures

---

## When to Use

- Before shipping code (part of `/go` pipeline)
- After completing a batch of tasks
- When debugging "works on my machine" issues
- As a smoke test after pulling changes

**When NOT to use:**
- Quick documentation-only changes
- When you only need to run a single test file (use `pytest` directly)

## Related Skills

- `/go` — Invokes this as Step 1 of the ship pipeline
- `/run-checks` — Lighter-weight lint and type checking only
