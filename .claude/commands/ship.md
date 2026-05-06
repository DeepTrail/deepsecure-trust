# Ship: Production Launch Checklist and Rollback Plan

Pre-deployment verification, production launch checklist, smoke tests, and rollback plan. Goes beyond `/commit-push-pr` (which handles git/PR) — this covers everything needed to safely put code into production.

## Workflow Position

```
... → /review → /security-audit → /commit-push-pr → /ship
                                                       ↑
                                                  (YOU ARE HERE — final gate)
```

## When to Use

- Before deploying a merged feature to production/staging
- When releasing a new version of the SDK or backend services
- After a batch of PRs merge and a deployment is planned
- For any change that affects running services (Control Plane, Gateway)
- When the user says "ship it", "deploy", "release", "go live"

**When NOT to use:**
- Documentation-only changes (no deployment needed)
- SDK-only changes that don't affect backend services
- Changes still in PR review (use `/review` and `/commit-push-pr` first)
- Hotfixes with their own emergency deployment process

---

## Instructions

### Phase 1: PRE-FLIGHT — Verify Merge Readiness

Before any deployment, confirm everything is in order:

```bash
# Verify branch is up to date
git checkout dev
git pull origin dev

# Verify all PRs are merged
gh pr list --state open --base dev

# Verify tests pass on latest
pytest -v
ruff check .
mypy deepsecure/
```

**Pre-flight checklist:**

| # | Check | Command | Expected |
|---|-------|---------|----------|
| 1 | Branch up to date | `git status` | Clean, up to date |
| 2 | No open PRs blocking | `gh pr list --state open` | None blocking deployment |
| 3 | Tests pass | `pytest -v` | All green |
| 4 | Lint clean | `ruff check .` | Zero errors |
| 5 | Type check clean | `mypy deepsecure/` | No new errors |
| 6 | Security audit passed | `/security-audit` completed | No Critical/High findings |
| 7 | DB migrations ready | `alembic heads` | Single head, no conflicts |

### Phase 2: CHANGELOG — Document What's Shipping

Generate a changelog from commits since last deployment:

```bash
# Commits since last tag/deployment
git log --oneline $(git describe --tags --abbrev=0 2>/dev/null || echo HEAD~20)..HEAD

# Or since a specific date
git log --oneline --since="2026-04-01"
```

**Organize into changelog:**

```markdown
## Release: [version or date]

### Features
- [feat commits summarized]

### Bug Fixes
- [fix commits summarized]

### Security
- [security commits summarized]

### Breaking Changes
- [any API contract changes, schema migrations, env var changes]

### Migration Steps Required
- [ ] [step 1 — e.g., "Run alembic upgrade head"]
- [ ] [step 2 — e.g., "Add new env var DEEPSECURE_X"]
```

### Phase 3: ROLLBACK PLAN — Define Before Deploying

**CRITICAL: Write the rollback plan BEFORE deploying, not after something breaks.**

```markdown
## Rollback Plan

### Trigger Conditions
Deploy rollback if ANY of these occur within 30 minutes of deployment:
- [ ] Health checks fail on any service
- [ ] Error rate exceeds 5% (vs pre-deployment baseline)
- [ ] Auth flow broken (agents can't authenticate)
- [ ] MCP Gateway returns session errors
- [ ] Database connection failures

### Rollback Steps

#### Option A: Git Revert (preferred for code-only changes)
```bash
# Revert to previous known-good commit
git revert --no-commit HEAD~[N]..HEAD
git commit -m "revert: rollback deployment [date]"
git push origin dev

# Redeploy
docker compose pull
docker compose up -d
```

#### Option B: Docker Image Rollback (faster for containerized services)
```bash
# Roll back to previous image tag
docker compose down deeptrail-control deeptrail-gateway
docker compose up -d --no-build deeptrail-control deeptrail-gateway
# Uses previous cached images
```

#### Option C: Database Rollback (if migration was applied)
```bash
# Identify current and target migration
cd deeptrail-control
alembic current
alembic history

# Downgrade to specific revision
alembic downgrade [target_revision]
```

### Point of No Return
- [List any irreversible changes — e.g., "data migration that drops old columns"]
- If past this point, forward-fix is required instead of rollback
```

### Phase 4: DEPLOY — Execute the Deployment

**For Docker Compose (development/staging):**

```bash
# Pull latest images / rebuild
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose build deeptrail-control deeptrail-gateway
docker compose up -d deeptrail-control deeptrail-gateway

# Wait for services to start
sleep 10

# Run database migrations (if any)
docker compose exec deeptrail-control alembic upgrade head
```

**For SDK releases:**

```bash
# Build package
make build
# or: ./scripts/build_package.sh

# Test the built package
pip install dist/deepsecure-*.whl
python -c "import deepsecure; print(deepsecure.__version__)"

# Publish (if authorized)
# twine upload dist/*
```

### Phase 5: SMOKE TEST — Verify the Deployment

**Run these immediately after deployment. Use the Shell tool.**

```bash
# 1. Health checks
echo "=== Health Checks ==="
curl -sf http://localhost:8000/health && echo " ✅ Control Plane" || echo " ❌ Control Plane"
curl -sf http://localhost:8002/health && echo " ✅ Gateway" || echo " ❌ Gateway"

# 2. Auth flow
echo ""
echo "=== Auth Flow ==="
USER_TOKEN=$(curl -sf -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('token','FAILED'))")
[ "$USER_TOKEN" != "FAILED" ] && echo "✅ Login" || echo "❌ Login"

# 3. API responsiveness
echo ""
echo "=== API Responsiveness ==="
curl -sf -o /dev/null -w "%{http_code} %{time_total}s" http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer $USER_TOKEN" && echo " ✅ Agents API" || echo " ❌ Agents API"

# 4. Database connectivity
echo ""
echo "=== Database ==="
docker compose exec db psql -U deepsecure_user -d deeptrail_controldb -c "SELECT 1" > /dev/null 2>&1 \
  && echo "✅ PostgreSQL" || echo "❌ PostgreSQL"

# 5. Redis connectivity
echo ""
echo "=== Redis ==="
docker compose exec redis redis-cli PING > /dev/null 2>&1 \
  && echo "✅ Redis" || echo "❌ Redis"
```

**If any smoke test fails: execute rollback plan immediately.**

### Phase 6: MONITOR — Post-Deploy Observation

After smoke tests pass, monitor for 15-30 minutes:

```bash
# Watch service logs for errors
docker compose logs -f deeptrail-control deeptrail-gateway --since 5m

# Check error rates
docker compose logs deeptrail-control --since 5m | grep -c "ERROR" || echo "0 errors"
docker compose logs deeptrail-gateway --since 5m | grep -c "ERROR" || echo "0 errors"
```

**Post-deploy checklist:**
- [ ] No new errors in logs for 15 minutes
- [ ] Response times normal (< 500ms for API calls)
- [ ] All smoke tests passing
- [ ] No user-reported issues

---

## Output Format

```markdown
## Ship Report: [Feature/Version]

### Pre-Flight
| Check | Status |
|-------|--------|
| Branch up to date | ✅ |
| Tests pass | ✅ |
| Lint clean | ✅ |
| Security audit | ✅ |
| DB migrations | ✅ N/A |

### Changelog
- feat: [summary]
- fix: [summary]

### Rollback Plan
- **Trigger:** [conditions]
- **Method:** [A/B/C]
- **Point of no return:** [yes/no, what]

### Deployment
- **Method:** [docker compose / pip release / manual]
- **Timestamp:** [when deployed]
- **Services:** [which services restarted]

### Smoke Tests
| Test | Status | Response Time |
|------|--------|---------------|
| Control health | ✅ | [Xms] |
| Gateway health | ✅ | [Xms] |
| Auth flow | ✅ | [Xms] |
| Agents API | ✅ | [Xms] |
| Database | ✅ | — |
| Redis | ✅ | — |

### Post-Deploy Monitoring
- **Duration:** [X minutes]
- **Error count:** [N]
- **Status:** ✅ Stable / ⚠️ Degraded / ❌ Rollback triggered

### Verdict
- [ ] **Successful** — Deployment complete and stable
- [ ] **Degraded** — Deployed but monitoring issues (create follow-up tickets)
- [ ] **Rolled Back** — Deployment reverted (document root cause)
```

---

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "It works in dev, it'll work in prod" | Dev has different data, different load, different config. Smoke test every deployment. |
| "We don't need a rollback plan, it's a small change" | Small changes cause the biggest outages because they're under-scrutinized. Always have a rollback plan. |
| "I'll write the changelog later" | Write it now. Later you won't remember what shipped or why. |
| "Smoke tests are overkill for this" | Smoke tests take 30 seconds. A broken deployment takes hours. |
| "We can fix forward if something breaks" | Fix-forward is valid AFTER you've written the rollback plan. It's a choice, not an excuse for no plan. |
| "Nobody uses this service right now" | Services in deployment pipelines get depended on before you realize it. Ship safely always. |

## Red Flags

- Deploying without running smoke tests
- No rollback plan written before deployment
- Deploying on Friday afternoon
- Deploying with unrun database migrations
- Skipping the monitoring period
- Multiple features deployed simultaneously without clear changelog
- Force-pushing to production branch
- "Quick deploy" that bypasses all checks
- No health check endpoints on services

## Verification

Before declaring the deployment successful:

- [ ] Pre-flight checklist complete (all checks pass)
- [ ] Changelog written with breaking changes noted
- [ ] Rollback plan written with trigger conditions
- [ ] Deployment executed
- [ ] All smoke tests passing
- [ ] 15+ minutes of monitoring with no new errors
- [ ] Ship report generated

---

## Reference

This command integrates with:
- `/commit-push-pr` → Creates the PR; this command handles post-merge deployment
- `/security-audit` → Must pass before deployment
- `/run-checks` → Must pass before deployment
- Hooks (`stop`) → Notification when deployment scripts complete

See also:
- `CLAUDE.md` → Service Ports (Development)
- `CLAUDE.md` → Common Debugging (docker compose commands)
- `docker-compose.yml` → Service definitions and ports
