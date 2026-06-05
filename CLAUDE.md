# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **⚠️ CHECK YOUR OWN WORK**: Before declaring any task complete, verify your changes actually work. Run lints after edits. Run tests before completion. Validate assumptions against the codebase, not design docs. See [Self-Verification](#self-verification-check-your-own-work) section.

## Project Overview

DeepSecure is a security platform that provides Identity-as-Code for AI agents, enabling them to fetch their own ephemeral credentials programmatically instead of using static API keys. The project consists of a Python CLI/SDK and backend services that implement a dual-service gateway architecture.

## Development Commands

### Environment Setup
```bash
# Install development dependencies
make install-dev
# or traditionally
make install-traditional

# Setup development environment
make setup
```

### Testing
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
```

### Code Quality
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

### Build and Package
```bash
# Build package
make build
./scripts/build_package.sh

# Clean build artifacts
make clean
```

## Architecture Overview

### Core Module Structure
- **`deepsecure/_core/`**: Internal implementation modules
  - `client.py`: High-level client services wrapping core functionalities
  - `base_client.py`: Base HTTP client with authentication
  - `vault_client.py`: Secret management operations
  - `agent_client.py`: Agent identity management
  - `identity_manager.py`: Agent identity and key management
  - `crypto/key_manager.py`: Cryptographic key operations
  - `config.py`: Configuration management

- **`deepsecure/`**: Public API layer
  - `client.py`: Main SDK client (uses _core modules)
  - `commands/`: CLI command implementations
  - `integrations/`: Framework integrations (LangChain, CrewAI)
  - `resources/`: Resource objects (Agent, Secret)

### Backend Services
- **`deeptrail-control/`**: Control plane (agent management, authentication, policies)
- **`deeptrail-gateway/`**: Data plane (API proxy with secret injection)

### Key Patterns
1. **Dual Client Architecture**: 
   - `deepsecure.Client` (public SDK) wraps `deepsecure._core.client` (internal)
   - Core modules handle low-level operations, public client provides clean API

2. **Identity Provider Pattern**:
   - Multiple identity providers (Keyring, Kubernetes, AWS)
   - Agents bootstrap identity from platform-native mechanisms

3. **Gateway Architecture**:
   - External API calls routed through gateway with automatic secret injection
   - JWT-based authentication between services

## Testing Strategy

### Test Organization
- **`tests/_core/`**: Core module unit tests (client, identity_manager, environment_detection)
- **`tests/commands/`**: CLI command tests (agent, auth, policy, vault)
- **`tests/sdk/`**: SDK-level tests (gateway requests, client properties, credentials)
- **`tests/test_examples.py`**: Example script validation
- **`tests/docs/`**: Documentation validation (README snippets)
- **End-to-end tests**: Marked with `@pytest.mark.e2e`, require live backend
- **Integration tests**: Marked with `@pytest.mark.integration`

### Running Specific Tests
```bash
# Run single test file
pytest tests/test_sdk_client.py

# Run tests by marker
pytest -m e2e -v          # End-to-end tests only
pytest -m integration -v  # Integration tests only

# Run tests with specific patterns
pytest -k "test_agent" -v  # All tests with 'agent' in name
```

### Backend Dependencies
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

## Development Workflow

### Making Changes
1. Core functionality changes go in `deepsecure/_core/`
2. Public API changes go in `deepsecure/client.py` or `deepsecure/`
3. CLI changes go in `deepsecure/commands/`
4. Always run `make check-all` before committing

### Adding New Features
1. Start with tests (TDD approach preferred)
2. Implement in appropriate core module
3. Expose through public client if needed
4. Add CLI commands if applicable
5. Update examples in `examples/` directory

### Pre-Completion Checklist (MANDATORY)

Before declaring ANY task complete, run through this checklist:

```
□ ReadLints on all edited files - fix any errors I introduced
□ Code compiles/imports without errors
□ Relevant tests pass (or new tests added)
□ Acceptance criteria explicitly verified (re-read and check each one)
□ No obvious regressions to existing functionality
□ Changes match the design doc/spec (if applicable)
```

**Do not skip this.** "I think it works" is not the same as "I verified it works."

### Security Considerations
- Never commit secrets or private keys
- All crypto operations use `ed25519` signatures
- Agent private keys stored in OS keyring by default
- JWT tokens used for service-to-service authentication
- Split-key architecture: client holds partial key, gateway holds partial key
- Redis used for gateway-side key storage in development

## Task Breakdown Workflow

When given a design document, follow this systematic approach:

### Step 1: Identify Architectural Boundaries
1. First identify the architectural boundaries (services, modules, APIs)
2. Map data dependencies and shared state
3. Group into parallel workstreams
4. Within each workstream, order sequentially by dependency
5. Output as actionable tasks with clear acceptance criteria

### Step 2: Classify Dependencies
- **PARALLEL**: Independent modules, separate services, isolated tests
- **SEQUENTIAL**: Schema changes → migrations → code, API contracts → implementations
- **BLOCKED**: Requires external input, design decision, or approval

### Parallelization Heuristics
- Different services/modules → Usually parallel
- Same database table → Usually sequential
- API producer/consumer → Producer first, then consumer
- Tests → Can parallel after implementation
- Documentation → Can parallel with implementation

### Task Template
Use this format for each task:

| Field | Value |
|-------|-------|
| **ID** | WS[workstream]-[number] (e.g., WS-A1) |
| **Description** | One sentence |
| **Dependencies** | List task IDs or "None" |
| **Complexity** | S (< 1hr), M (1-3hr), L (3+ hr) |
| **Acceptance** | How to verify completion |
| **Files** | Expected files to create/modify |

### Common Workstream Patterns

**SDK Feature Addition:**
```
WS-A: Core Implementation (deepsecure/_core/) [parallel with C, D]
WS-B: Public API (deepsecure/client.py) [depends on A]
WS-C: CLI Commands (deepsecure/commands/) [parallel with B]
WS-D: Tests [parallel with B and C]
WS-E: Examples & Docs [after B and C]
```

**Cross-Service Feature:**
```
WS-A: Shared Contracts (API specs, data models)
WS-B: Control Plane (deeptrail-control/) [after A]
WS-C: Gateway (deeptrail-gateway/) [after A, parallel with B]
WS-D: SDK Client Updates [after B and C]
WS-E: E2E Testing [after D]
```

### Reference Documents
- **Developer workflow (E2E):** `docs/DEVELOPER_WORKFLOW.md` ← Start here for full workflow
- Design template: `docs/design/DESIGN_TEMPLATE.md`
- Task breakdown framework: `docs/TASK_BREAKDOWN.md`
- Workflow guide: `docs/WORKFLOW_GUIDE.md`
- Parallel execution: `docs/PARALLEL_EXECUTION_GUIDE.md`
- Project rules: `.cursorrules`

## Task Ticket Structure Requirements

**CRITICAL:** All task tickets MUST include these mandatory sections in this order:

| # | Section | Purpose | Required Content |
|---|---------|---------|------------------|
| 1 | **Metadata** | Task identification | Task ID, Workstream, Phase, Dependencies, Complexity, Service, Validates |
| 2 | **Specification** | Contract reference | Link to spec file, Key Contracts summary |
| 3 | **API Contracts** | API details or "no API" note | **MANDATORY** - never omit this section |
| 4 | **Pre-Conditions** | Dependencies checklist | What must be complete before starting |
| 5 | **Task Description** | Full context | Objective + Background + What to Implement |
| 6 | **Files to Create/Modify** | File table | File path, Action, Description |
| 7 | **Acceptance Criteria** | Completion checklist | Functional + Security + Integration criteria |
| 8 | **Test Cases** | Test table | Test Case, Method, Endpoint/Module, Expected Status, Notes |
| 9 | **Post-Conditions** | Enables/unblocks | What this task unlocks |
| 10 | **Validation** | How to verify | Unit Tests + Manual Verification subsections |
| 11 | **References** | Links | Spec, Design doc, Upstream/Downstream, Related code |
| 12 | **Execution** | Commands | Copy-paste ready commands |

### API Contracts Section Format

**For tasks WITH API endpoints:**
```markdown
## API Contracts

### Endpoint: [Name]
| Field | Value |
|-------|-------|
| **Method** | `GET` / `POST` |
| **Path** | `/api/v1/path` |
| **Auth** | [Auth type] |
| **Purpose** | [Brief description] |

[Include path params, request body, success response, error responses]
```

**For tasks WITHOUT API endpoints:**
```markdown
## API Contracts

> **Note:** This task implements an internal module/service, not API endpoints.
> [Brief explanation of what the task creates.]
> See [WS-XX] for related API endpoints.
```

### Validation Section Format

```markdown
## Validation

### Unit Tests
\`\`\`bash
cd [service-directory]
pytest tests/[module]/test_[file].py -v
\`\`\`

### Manual Verification
\`\`\`bash
# 1. [Step description]
[command]
# Expected: [output]
\`\`\`
```

### Template and Command References
- Task Ticket Template: `docs/workstreams/TASK_TICKET_TEMPLATE.md`
- Task Spec Template: `docs/workstreams/TASK_SPEC_TEMPLATE.md`
- Create Task Ticket Command: `.cursor/commands/create-task-ticket.md`
- Create Task Spec Command: `.cursor/commands/create-task-spec.md`

## Workstream Prerequisites (MANDATORY)

**CRITICAL:** Never run `/run-batch` on a workstream that was not set up through the full PLAN phase. This is NOT optional.

### Required Files Before Any `/run-batch` Call

Before running `/run-batch N [feature-name]`, ALL six of the following files MUST exist:

| File | Proves | Created By |
|------|--------|------------|
| `docs/workstreams/[feature]/BREAKDOWN.md` | `/breakdown-design` was run | `/breakdown-design` |
| `docs/workstreams/[feature]/CODEBASE_ANALYSIS.md` | `/explore-codebase` was run (codebase was actually checked) | `/breakdown-design` internally |
| `docs/workstreams/[feature]/MERGE_POINTS.md` | `/create-workstream` fully completed | `/create-workstream` |
| `docs/workstreams/[feature]/BATCH_EXECUTION_PLAN.md` | Batches and waves were planned | `/create-batch-execution-plan` |
| `docs/workstreams/[feature]/WORKSTREAM.md` | Workstream overview exists | `/create-workstream` |
| `docs/workstreams/[feature]/STATUS.md` | Progress tracking initialized | `/create-workstream` |
| `docs/workstreams/[feature]/PIPELINE_STATE.md` | User reviewed and **approved** the plan at the `/run-plan` checkpoint | `/run-plan` (written only after user approval) |

**`/run-batch` enforces this at pre-flight** — it will STOP with `"Pre-Flight FAILED: PLAN Phase Incomplete"` if any of the first three files are missing.

### Verification Command (run before any `/run-batch`)

```bash
FEATURE="[feature-name]"
echo "=== Workstream Prerequisite Check ==="
[ -f "docs/workstreams/${FEATURE}/BREAKDOWN.md" ] && echo "✅ BREAKDOWN.md" || echo "❌ MISSING — run /run-plan first"
[ -f "docs/workstreams/${FEATURE}/CODEBASE_ANALYSIS.md" ] && echo "✅ CODEBASE_ANALYSIS.md" || echo "❌ MISSING — run /run-plan first"
[ -f "docs/workstreams/${FEATURE}/MERGE_POINTS.md" ] && echo "✅ MERGE_POINTS.md" || echo "❌ MISSING — run /run-plan first"
[ -f "docs/workstreams/${FEATURE}/BATCH_EXECUTION_PLAN.md" ] && echo "✅ BATCH_EXECUTION_PLAN.md" || echo "❌ MISSING — run /run-plan first"
[ -f "docs/workstreams/${FEATURE}/WORKSTREAM.md" ] && echo "✅ WORKSTREAM.md" || echo "❌ MISSING — run /run-plan first"
[ -f "docs/workstreams/${FEATURE}/STATUS.md" ] && echo "✅ STATUS.md" || echo "❌ MISSING — run /run-plan first"
[ -f "docs/workstreams/${FEATURE}/PIPELINE_STATE.md" ] && echo "✅ PIPELINE_STATE.md (plan approved)" || echo "❌ MISSING — /run-plan not approved by user yet"
echo "=== If all ✅: ready for /run-batch ==="
```

### The Fix

If any prerequisite file is missing, do NOT manually create it to bypass the check. Run the full PLAN phase instead:

```
/run-plan [feature-name] [design-doc-path]
```

This is the lesson from the `mvp-foundation` workstream: files were created manually without running the pipeline, which meant codebase exploration was skipped, MERGE_POINTS.md was absent, and `/run-batch` had no way to detect the incomplete setup until execution failed mid-batch.

### Why This Matters

| Without full PLAN phase | With full PLAN phase |
|-------------------------|----------------------|
| Tasks may duplicate existing code (exploration not done) | Existing code inventoried — tasks correctly classified as Modify/Verify instead of Create |
| No merge points defined — parallel tracks diverge | Merge points defined upfront — convergence is planned |
| Batches may have incorrect wave ordering | Wave ordering is dependency-analyzed |
| `/run-batch` accepts the workstream as valid | `/run-batch` pre-flight enforces completeness |

---

## Status Verification Requirements (MANDATORY)

**CRITICAL:** Status files MUST be kept consistent with completion reports. This is NOT optional.

### After Task Completion

When completing a task (especially in a worktree), you MUST:

1. **Create completion report** in `reports/WS-{ID}-completion.md`
2. **Update main repo STATUS.md** using absolute path:
   ```bash
   MAIN_REPO=$(git worktree list | head -1 | awk '{print $1}')
   # Update: $MAIN_REPO/docs/workstreams/[feature]/STATUS.md
   ```
3. **Update main repo WORKSTREAM.md** - mark task complete, add report link
4. **Update main repo BATCH_EXECUTION_PLAN.md** - update task status
5. **Remind user to verify** if in worktree

### After Batch Completion (BLOCKING)

Before proceeding to the next batch, ALWAYS run:

```bash
/verify-batch-completion [batch-id] [feature-name]
```

**DO NOT proceed to the next batch if verification fails.**

### Files That Must Stay Consistent

| File | Source of Truth | Updated When |
|------|-----------------|--------------|
| `reports/WS-{ID}-completion.md` | **YES** - definitive proof | Task completed |
| `STATUS.md` | Derived from reports | After each task completion |
| `WORKSTREAM.md` | Derived from reports | After each task completion |
| `BATCH_EXECUTION_PLAN.md` | Derived from reports | After each task/batch completion |
| `MERGE_POINTS.md` | Derived from batch status | After batch that triggers MP |

### Verification Commands

| Command | Purpose | When to Run |
|---------|---------|-------------|
| `/verify-batch-completion` | Verify batch status consistency | After last task in batch, before starting next |
| `/sync-worktree-status` | Sync status from worktrees to main repo | After worktree tasks, before verification |

### Why This Matters

Without consistent status:
- Progress tracking becomes inaccurate
- Merge points can't be verified
- Dependencies may appear unmet when they're actually satisfied
- Next batch planning uses wrong information

### Quick Verification Check

Before proceeding to a new batch, run:

```bash
# Count completion reports
ls docs/workstreams/[feature]/reports/WS-*.md | wc -l

# Count "✅ Complete" in STATUS.md
grep -c "✅ Complete" docs/workstreams/[feature]/STATUS.md

# These numbers should match!
```

## Key File Locations

### Configuration Files
- `pyproject.toml`: Project metadata, dependencies, and tool configurations
- `docker-compose.yml`: Backend services orchestration (PostgreSQL, Redis, Control, Gateway)
- `pytest.ini`: Test configuration and markers
- `Makefile`: Development workflow automation

### Core Implementation
- `deepsecure/client.py`: Main public SDK client
- `deepsecure/_core/client.py`: Internal high-level client implementation
- `deepsecure/_core/base_client.py`: Base HTTP client with authentication
- `deepsecure/_core/identity_manager.py`: Agent identity and cryptographic operations
- `deepsecure/_core/crypto/key_manager.py`: Ed25519 key operations

### Service Ports (Development)
- **Control Plane**: http://localhost:8000 (mapped from container port 8001)
- **Gateway**: http://localhost:8002 (mapped from container port 8001)
- **PostgreSQL**: localhost:5434 (mapped from container port 5432)
- **Redis**: localhost:6380 (mapped from container port 6379)

### Common Debugging
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

## Self-Verification: Check Your Own Work

> **Principle**: Validation should be embedded in the work, not bolted on afterwards. Catch problems at the point of creation, not during review 20 minutes later.

### Engineering Preferences (Guide All Recommendations)
- **DRY is important** — flag repetition aggressively
- **Well-tested code is non-negotiable** — too many tests > too few
- **"Engineered enough"** — not under-engineered (fragile, hacky) and not over-engineered (premature abstraction, unnecessary complexity)
- **Handle edge cases** — err on the side of more, not fewer; thoughtfulness > speed
- **Explicit over clever** — bias toward readable, obvious code

### 4-Stage Code Review Process (For Significant Changes)

#### 1. Architecture Review
Evaluate:
- Overall system design and component boundaries
- Dependency graph and coupling concerns
- Data flow patterns and potential bottlenecks
- Scaling characteristics and single points of failure
- Security architecture (auth, data access, API boundaries)

#### 2. Code Quality Review
Evaluate:
- Code organization and module structure
- DRY violations — be aggressive here
- Error handling patterns and missing edge cases (call these out explicitly)
- Technical debt hotspots
- Areas that are over-engineered or under-engineered

#### 3. Test Review
Evaluate:
- Test coverage gaps (unit, integration, e2e)
- Test quality and assertion strength
- Missing edge case coverage — be thorough
- Untested failure modes and error paths

#### 4. Performance Review
Evaluate:
- N+1 queries and database access patterns
- Memory-usage concerns
- Caching opportunities
- Slow or high-complexity code paths

### File Path Verification (MANDATORY)

**Before documenting any file paths in:**
- Validation sections
- Test commands
- BATCH_EXECUTION_PLAN.md
- MERGE_POINTS.md
- Any documentation with executable commands

**You MUST verify the paths actually exist:**

```bash
# Use glob to verify test file paths
ls [service]/tests/[module]/test_*.py

# Use find for fuzzy matching if unsure of exact name
find . -name "*vault*" -path "*/tests/*" -name "*.py"

# Check openapi.json for endpoint paths
curl -s http://localhost:8000/openapi.json | jq '.paths | keys'
```

**Why this matters:**
- Documenting non-existent paths causes confusion and wasted debugging time
- Task completion reports may incorrectly claim tests pass when tests don't exist
- Validation sections become untestable

**Pattern: Prefer glob patterns over specific file names when possible:**
```bash
# Good - works even if file names change
pytest tests/backends/ -v

# Risky - fails if file is named differently
pytest tests/backends/test_notion_api.py -v  # What if it's test_notion_client.py?
```

### For Each Issue Found
For every specific issue (bug, smell, design concern, or risk):
1. **Describe the problem concretely** — with file and line references
2. **Present 2-3 options** — including "do nothing" where reasonable
3. **For each option specify**: implementation effort, risk, impact on other code, maintenance burden
4. **Give recommended option and why** — mapped to engineering preferences above
5. **Ask for direction** — explicitly ask whether to proceed or choose differently

### Workflow Rules
- Do not assume priorities on timeline or scale
- After each section, pause and ask for feedback before moving on
- When presenting options, NUMBER issues (1, 2, 3) and use LETTERS for options (A, B, C)
- Make the recommended option always the 1st option

### Before Starting Significant Work
Ask user preference:
- **BIG CHANGE**: Work through interactively, one section at a time (Architecture → Code Quality → Tests → Performance) with at most 4 top issues per section
- **SMALL CHANGE**: Work through interactively ONE question per review section

### Three-Tier Verification Model

| Tier | When | What | How |
|------|------|------|-----|
| **Micro** | After each file edit | Lint, format, type errors | `ReadLints` after edits |
| **Macro** | Before declaring "done" | Tests pass, requirements met | Run tests, verify acceptance criteria |
| **Meta** | Before task breakdown | Assumptions validated | `/explore-codebase` before `/breakdown-design` |

### Micro Verification: After Every Edit

After making substantive code changes:

1. **Run `ReadLints`** on edited files to catch errors immediately
2. **Fix any errors you introduced** (don't leave them for the user)
3. **Verify the change compiles/runs** if possible

```
# After editing Python files:
- ReadLints on edited file
- Fix any new errors
- Verify imports are correct
```

### Macro Verification: Before Completion

Before declaring a task complete:

1. **Re-read the acceptance criteria** from the task/ticket
2. **Verify each criterion is actually met** (don't assume)
3. **Run relevant tests** if specified
4. **Check that you didn't break existing functionality**

```
# Before saying "done":
- [ ] Re-read original request
- [ ] Verify each requirement is met (not just "I think I did it")
- [ ] Run `make check-all` or equivalent
- [ ] Check for regressions
```

### Meta Verification: Validate Assumptions

Before starting significant work:

1. **Verify design doc claims against codebase** (don't trust "Not Implemented" labels)
2. **Confirm file paths exist** before editing them
3. **Check that dependencies are in place** before building on them

```
# Before breakdown/implementation:
- [ ] Explore codebase to verify what exists
- [ ] Grep for components claimed to be "missing"
- [ ] Verify API contracts match actual endpoints
```

### Self-Check Questions

Ask yourself these questions before completing tasks:

| Phase | Question | If "No" |
|-------|----------|---------|
| Planning | "Did I verify this component doesn't already exist?" | Run `/explore-codebase` |
| Implementation | "Did I run lints after my edits?" | Run `ReadLints` |
| Implementation | "Did I test this change?" | Run relevant tests |
| Completion | "Does my change actually meet the acceptance criteria?" | Re-read and verify |
| Completion | "Did I introduce any regressions?" | Run `make check-all` |

### Anti-Patterns: Not Checking Your Work

| Bad | Good |
|-----|------|
| Edit file → Move on | Edit file → ReadLints → Fix errors → Move on |
| "I implemented the feature" | "I implemented the feature and verified: [list of checks]" |
| Trust design doc claims | Verify claims against actual codebase |
| Assume tests will pass | Run tests before declaring done |
| "This should work" | "I verified this works by [specific test]" |

### Post-Implementation Verification Commands
```bash
# After modifying Python files
ruff check [modified_file.py]
python -c "import [module]"  # Verify imports work

# After modifying tests
pytest [test_file.py] -v

# After modifying demos/scripts
python [script.py] --help  # Verify it runs
python [script.py] --auto --skip-api  # Dry run if applicable
echo "Exit code: $?"  # Must be 0

# Full quality check before completion
make check-all
```

---

## Common Pitfalls and Learnings

### Token Types for API Validation (CRITICAL)

Different endpoints require different authentication tokens. Using the wrong token type causes 401 errors.

| Token Type | How to Obtain | Used For | Header Format |
|------------|---------------|----------|---------------|
| **User Token** | `POST /api/v1/auth/login` → `.token` | User-facing endpoints, service connection | `Authorization: Bearer $USER_TOKEN` |
| **Agent JWT** | Ed25519 challenge-response flow (see below) | Agent-to-Control APIs, vault token retrieval | `Authorization: Bearer $AGENT_JWT` |
| **Internal API Token** | From `docker-compose.yml` env var | Gateway-to-Control internal APIs | `Authorization: Bearer gateway-internal-secret-token` |

**Common Mistakes:**

| Mistake | Error | Fix |
|---------|-------|-----|
| Using User Token for vault token retrieval | `401 "missing user identity"` | Use Agent JWT (has `owner` claim) |
| Using User Token for vault token refresh | `401 "Invalid internal token"` | Use Internal API Token + `X-User-ID` header |
| Using `.access_token` for login response | Returns `null` | Use `.token` - login returns `token` field |

**Login API Response Field:**
```bash
# WRONG - returns null
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login ... | jq -r '.access_token')

# CORRECT - login returns "token" not "access_token"
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login ... | jq -r '.token')
```

### Agent JWT Creation Flow (For Validation Commands)

When validation commands need an Agent JWT, use this full flow:

```bash
# 1. Generate Ed25519 keypair
python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey.generate()
public_key = private_key.verify_key
print(f'PRIVATE_KEY_HEX={private_key.encode().hex()}')
print(f'PUBLIC_KEY_B64={base64.b64encode(public_key.encode()).decode()}')
" > /tmp/agent_keys.env
source /tmp/agent_keys.env

# 2. Register agent with public key
curl -s -X POST http://localhost:8000/api/v1/agents/ \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"test-agent\", \"name\": \"Test\", \"public_key\": \"$PUBLIC_KEY_B64\"}"

# 3. Create delegation
curl -s -X POST http://localhost:8000/api/v1/auth/delegate \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent", "permissions": ["service:scope:action"]}'

# 4. Request challenge
CHALLENGE=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/challenge \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent"}' | jq -r '.challenge')

# 5. Sign challenge
SIGNATURE=$(python3 -c "
from nacl.signing import SigningKey
import base64
private_key = SigningKey(bytes.fromhex('$PRIVATE_KEY_HEX'))
signed = private_key.sign('$CHALLENGE'.encode())
print(base64.urlsafe_b64encode(signed.signature).decode())
")

# 6. Get Agent JWT
AGENT_JWT=$(curl -s -X POST http://localhost:8000/api/v1/auth/agent/verify \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"test-agent\", \"challenge\": \"$CHALLENGE\", \"signature\": \"$SIGNATURE\"}" \
  | jq -r '.access_token')
```

### MCP Gateway Protocol Flow (CRITICAL)

**CRITICAL**: The Gateway requires an `initialize` call before any `tools/call` requests. Calling `tools/call` without initialization returns:
```json
{"jsonrpc":"2.0","id":1,"error":{"code":-32002,"message":"Session not found. Call initialize first.","data":null}}
```

**Required MCP Call Sequence:**
1. `initialize` - Establishes session, returns server info
2. `tools/list` (optional) - Lists available tools based on agent permissions
3. `tools/call` - Actually executes a tool (requires active session)

**Initialize Example:**
```bash
# Step 1: Initialize MCP session
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test-agent", "version": "1.0.0"}
    }
  }'
# Expected: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","serverInfo":{...}}}

# Step 2: Now tools/call will work
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 2,
    "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
  }'
```

**Common Mistakes:**
| Mistake | Fix |
|---------|-----|
| Calling `tools/call` without `initialize` | Always call `initialize` first |
| Using static `AGENT_JWT` placeholder | Create real Agent JWT via challenge-response flow |
| Reusing session after timeout | Re-initialize if session expired |

**Reference Implementation:** See `demos/demo_sarah_journey_e2e.py` → `step_06_mcp_initialize()` for correct flow.

### API Contract Verification

**CRITICAL**: Always verify that implementation endpoints match design doc specifications exactly.

| Common Mistake | Correct Approach |
|----------------|------------------|
| Test uses `/api/v1/agents/challenge` | Check design doc - might be `/api/v1/auth/agent/challenge` |
| Implementing without reading spec | Copy endpoint path from design doc's "API Contracts" section |
| Tests diverge from implementation | Both must match the canonical spec in design doc |

**Verification command:**
```bash
# Check implemented endpoints
grep -r "@router\.\(get\|post\|put\|delete\)" [file] | grep -o '"/api/v1[^"]*"'

# Check test endpoints
grep -r '"/api/v1' [test_file] | grep -o '"/api/v1[^"]*"'
```

### Async Test Fixtures

**CRITICAL**: Use `@pytest_asyncio.fixture` for async fixtures, not `@pytest.fixture`.

```python
# WRONG - causes "AttributeError: 'async_generator' object has no attribute 'post'"
@pytest.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c

# CORRECT
import pytest_asyncio

@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c
```

### File Organization Rules

| Artifact Type | Correct Location | Wrong Location |
|---------------|------------------|----------------|
| MVP E2E tests (cross-service) | `tests/e2e/` (root) | `deeptrail-gateway/tests/e2e/` |
| MVP demos (cross-service) | `demos/` (root) | `deeptrail-gateway/demos/` |
| Demo tests | `tests/demos/` (root) | `deeptrail-gateway/tests/demos/` |
| Service-specific unit tests | `[service]/tests/` | Root level |

**Rule of thumb**: If it tests/demonstrates functionality spanning multiple services, it belongs at the root level.

### Design → Implementation Workflow

1. **Design doc defines canonical API contracts** - This is the source of truth
2. **Task tickets copy spec from design doc** - Don't modify without updating design doc
3. **Implementation must match spec exactly** - Endpoint paths, schemas, error codes
4. **Tests must match implementation** - Which must match spec
5. **Contract verification before completion** - Check all three match

### Codebase Exploration Before Breakdown (CRITICAL)

**LESSON LEARNED (Feb 2026):** A breakdown was created based on design docs claiming endpoints were "missing." After codebase exploration, ~60% already existed. Design docs describe **intent**, not **current state**.

**Rule:** ALWAYS explore the codebase BEFORE creating task breakdowns.

| Bad Pattern | Good Pattern |
|-------------|--------------|
| Read design doc → Create tasks for "missing" items | Read design doc → Explore codebase → Identify TRUE gaps → Create tasks |
| Assume coverage matrix is current | Verify coverage matrix against codebase |
| Trust "Not Implemented" labels | Grep codebase for actual implementations |

**Task Classification by Codebase State:**

| Codebase State | Task Type | Example |
|----------------|-----------|---------|
| Component doesn't exist | `Create` | "Create OAuth service" |
| Component exists, format wrong | `Modify` | "Update response format" |
| Component exists, needs validation | `Verify` | "Verify endpoint matches E2E" |
| Component exists, fully correct | `Skip` | Remove from task list |

**Commands:**
- `/explore-codebase [design-doc]` - Run BEFORE `/breakdown-design`
- Creates `CODEBASE_ANALYSIS.md` documenting actual state

### MERGE_POINTS.md Required Sections (CRITICAL)

**LESSON LEARNED (Feb 2026):** A MERGE_POINTS.md was created with basic structure but was missing critical sections that made it unusable for validation. Always use the full template.

**Required sections for every MERGE_POINTS.md:**

| Section | Purpose |
|---------|---------|
| Code Dependencies vs Runtime Dependencies | ASCII diagram explaining difference |
| Task Lifecycle with Dependencies | ASCII diagram: blocked → ready → dev → complete |
| Development Mode vs Integration Mode | Fallback behaviors when services down |
| Runtime Dependencies by Merge Point | Service availability table by MP |
| **Per-MP: Merge Actions** | Git workflow (push, PR, merge, rebase) |
| **Per-MP: Container Deployment** | Docker commands |
| **Per-MP: Container Test Scenarios** | curl examples with expected outputs |
| **Per-MP: Cleanup** | Cleanup commands |
| **Per-MP: Success Criteria** | Checklist |
| **Per-MP: Post-Merge Status Update** | Status update commands |
| Testing Strategy by Phase | P0, P1, P2 validation commands |
| Troubleshooting | Issue/Cause/Fix tables |
| Container Deployment Schedule | When to deploy |
| Quick Reference Commands | Copy-paste ready |
| Merge Point Status | Status table with Progress Summary |
| History | Event log |

**Template:** `docs/workstreams/MERGE_POINT_GUIDE.md`

### Merge Point Tag Naming Convention (MANDATORY)

**LESSON LEARNED (May 2026):** Bare merge point tags like `mp1-foundation-complete` collide across workstreams. When multiple workstreams have an MP1, the tag name is ambiguous and can't be traced to a specific feature.

**Convention:** Tags MUST include the feature branch name as a suffix:

```
{base-tag}-{feature-branch}
```

| Component | Source | Example |
|-----------|--------|---------|
| `{base-tag}` | From `BATCH_EXECUTION_PLAN.md` Quick Reference table | `mp1-foundation-complete` |
| `{feature-branch}` | From `git branch --show-current` | `feature/ui-improvements-audit-activity` |
| **Full tag** | Concatenated with `-` | `mp1-foundation-complete-feature/ui-improvements-audit-activity` |

**Tag creation command (used in `/run-batch` Step 7d):**
```bash
BASE_TAG="mp1-foundation-complete"
FULL_TAG="${BASE_TAG}-$(git branch --show-current)"
git tag "$FULL_TAG"
git push origin "$FULL_TAG"
```

**Where enforced:**
- `/run-batch` Step 7d (tag creation) — appends branch automatically
- `/create-batch-execution-plan` Section 1 — documents base tag in Quick Reference
- `/create-workstream` — MERGE_POINTS.md Merge Actions use dynamic construction

### Merge Point Protocol (MANDATORY)

**LESSON LEARNED (May 2026):** During the P5.2 workstream, Merge Actions (commit, tag, push) were executed immediately after code implementation and local SQLite tests passed — skipping Container Deployment, Container Test Scenarios, and the Success Criteria checklist from MERGE_POINTS.md. The Alembic migration had never been run against PostgreSQL before MP1 was tagged. All steps passed when run retroactively, but this was luck, not process.

**Rule:** Merge Point completion is a **sequential pre-merge gate**. You MUST complete all steps in this exact order before running Merge Actions:

| Step | Source | What |
|------|--------|------|
| 1. **Batch Validation** | `BATCH_EXECUTION_PLAN.md` → Validation section | Run every `pytest` and verification command listed for the batch |
| 2. **Container Deployment** | `MERGE_POINTS.md` → Container Deployment | `docker compose build`, `up -d`, `alembic upgrade head`, table verification |
| 3. **Container Test Scenarios** | `MERGE_POINTS.md` → Container Test Scenarios | Live `curl` tests against running containers (health, endpoints, auth) |
| 4. **Success Criteria** | `MERGE_POINTS.md` → Success Criteria | Check every `[ ]` box — if any fail, fix before proceeding |
| 5. **Merge Actions** | `MERGE_POINTS.md` → Merge Actions | Only now: `git commit`, `git push`, `git tag` |

**Anti-pattern (what went wrong):**
```
Code → Local tests pass → Commit → Tag → Push → [Container tests skipped]
```

**Correct pattern:**
```
Code → Local tests pass → Container build → Container deploy → Container tests → Success criteria → Commit → Tag → Push
```

**Why this matters:**
- SQLite tests don't catch PostgreSQL-specific issues (UUID types, JSONB, NOT NULL constraints)
- Container deployment verifies the service actually starts with new code
- Container test scenarios verify endpoints work with real auth, real DB, real service-to-service communication
- A tagged merge point that fails container tests creates confusion about what "complete" means

**Where enforced:**
- `/run-batch` Step 7 — must run Container Deployment + Test Scenarios before Merge Actions
- Agent self-check — before any `git tag` for a merge point, verify Container Test Scenarios were executed in this session

### Test Suite Health (MANDATORY)

**LESSON LEARNED (May 2026):** During P5.2 batch execution, 151 pre-existing test failures (19 FAILED + 83 ERRORs in `deeptrail-control`, 132 FAILED + 5 ERRORs in `deeptrail-gateway`) were encountered and skipped with the rationale "not from this workstream." This is wrong — test failures compound, root causes become harder to diagnose over time, and new code may silently break old tests.

**Rule: ALL tests must pass before a batch is declared complete.**

| Scenario | Action |
|----------|--------|
| Test fails and was broken by your changes | Fix immediately — this is a regression |
| Test was already failing before your changes | Fix it anyway — you encountered it, you own it |
| Test requires live services (Redis, PostgreSQL) | Mark with `@pytest.mark.e2e` or `@pytest.mark.integration`, but do NOT skip silently |
| Test references non-existent code (design spec drift) | Rewrite to test actual implementation |
| Test is flaky (passes alone, fails in suite) | Fix the root cause (usually fixture cleanup, DB state pollution, or `dependency_overrides.clear()`) |

**Common root causes of pre-existing failures:**
- Tests written against design specs, not actual implementation (wrong imports, non-existent classes)
- `app.dependency_overrides.clear()` in one test fixture destroying overrides set by conftest (use `pop()` instead)
- Hardcoded expected values that drifted (version numbers, backend counts, response field names)
- Missing fixture cleanup causing `UNIQUE constraint` violations across tests
- Pydantic V2 migration: aliases in error messages, `ConfigDict` vs `class Config`

**Verification command (run before declaring any batch complete):**
```bash
cd deeptrail-control && python -m pytest tests/ --ignore=tests/test_jwt_tokens.py -q --tb=short
cd deeptrail-gateway && python -m pytest tests/ -q --tb=short
```

**Where enforced:**
- `/run-batch` Step 6 (after task execution) — full test suite must pass
- `/execute-task` completion gate — tests in the modified service must pass
- Agent self-check — never dismiss a failing test as "not mine"

### Documentation Consistency (MANDATORY)

**LESSON LEARNED (Feb 2026):** Status files drifted out of sync with completion reports, causing confusion about batch completion and blocking next batch unnecessarily.

**Files that MUST stay consistent:**

| File | Updated When | By Whom |
|------|--------------|---------|
| `reports/WS-{ID}-completion.md` | Task completed | Agent completing task |
| `STATUS.md` | After each task | Agent, sync to main repo |
| `WORKSTREAM.md` | After each task | Agent, sync to main repo |
| `BATCH_EXECUTION_PLAN.md` | After each batch | Agent, after `/verify-batch-completion` |
| `MERGE_POINTS.md` | After batch triggers MP | Agent, update MP status |

**Verification command (run after every batch):**
```bash
/verify-batch-completion [batch-id] [feature-name]
```

**DO NOT proceed to next batch if verification fails.**

### Backend Service File Path Conventions

**IMPORTANT**: When creating files in backend services, follow these actual conventions (not design doc paths):

| Design Doc Pattern | Actual Pattern | Convention |
|--------------------|----------------|------------|
| `[service]/models/` | `[service]/app/models/` | FastAPI `app/` prefix |
| `[service]/services/` | `[service]/app/services/` | FastAPI `app/` prefix |
| `[service]/api/[domain]/` | `[service]/app/api/v1/endpoints/` | Versioned, flat |
| `[service]/gateway/` | `[service]/app/` | Use `app/` not domain name |
| `middleware/[security].py` | `security/[security].py` | Security separation |

**Naming Conventions:**
- Services: Always use `*_service.py` suffix (e.g., `[domain]_service.py`)
- Validation: Use descriptive names (e.g., `[x]_validation.py` not `[x]_auth.py`)
- Constraints: Use active verbs (e.g., `[x]_checker.py` not `[x]s.py`)
- Related endpoints: Consolidate into single files by domain

**Directory Structure:**
```
[service-name]/
├── app/
│   ├── api/v1/endpoints/    ← Flat, versioned API endpoints
│   ├── models/              ← SQLAlchemy/Pydantic models
│   ├── services/            ← Business logic (*_service.py)
│   ├── middleware/          ← Request/response handling
│   ├── security/            ← Security concerns (fail-closed, constraints)
│   └── [domain]/            ← Domain modules
├── tests/
└── migrations/
```

**Service directories in this project:**
- `deeptrail-control/` - Control Plane service
- `deeptrail-gateway/` - Gateway service

---

## Lessons Learned Changelog

| Date | Lesson | Impact | Section Updated |
|------|--------|--------|-----------------|
| Feb 2026 | Design docs describe intent, not current state | Reduced over-scoping by 60% | Codebase Exploration Before Breakdown |
| Feb 2026 | Async fixtures need `@pytest_asyncio.fixture` | Prevents AttributeError in tests | Async Test Fixtures |
| Feb 2026 | File paths must be verified before documenting | Prevents untestable validation sections | File Path Verification |
| Feb 2026 | Status files drift without enforcement | Added mandatory `/verify-batch-completion` | Status Verification Requirements |
| Feb 2026 | Login API returns `token` not `access_token` | Fixed `null` token issues in validation | Token Types for API Validation |
| Feb 2026 | Vault endpoints need Agent JWT not User Token | Fixed 401 "missing user identity" errors | Token Types for API Validation |
| Feb 2026 | Vault refresh needs Internal Token + X-User-ID | Fixed 401 "Invalid internal token" errors | Token Types for API Validation |
| Feb 2026 | MERGE_POINTS.md missing critical sections | Added 18-section template requirement | MERGE_POINTS.md Required Sections |
| Feb 2026 | Task tickets must have mandatory sections | Standardized across workstreams | Task Ticket Structure Requirements |
| Feb 2026 | MCP Gateway requires `initialize` before `tools/call` | Fixed "Session not found" errors in validation | MCP Gateway Protocol Flow |
| May 2026 | Workstream created manually without full pipeline — `/run-batch` accepted it because it only checked 3 files | Added 3 new pre-flight checks to `/run-batch` (BREAKDOWN.md, CODEBASE_ANALYSIS.md, MERGE_POINTS.md); added "Workstream Prerequisites (MANDATORY)" section | Workstream Prerequisites |
| May 2026 | MERGE_POINTS.md verification only checked section headers, not content — p3-gcp merge actions had no git commit/push/tag commands | Added content-level grep for `git commit\|git push\|git tag` in `/create-workstream` verification | MERGE_POINTS.md Required Sections |
| May 2026 | MERGE_POINTS.md verification checked only 6 of 18 required sections — p3-gcp file passed with 10 sections missing entirely | Expanded `/create-workstream` verification from 6 to 18+2 section checks; added N/A-block pattern for inapplicable sections | MERGE_POINTS.md Required Sections |
| May 2026 | Deploy batch in BATCH_EXECUTION_PLAN.md used inline `docker build`/`docker push` instead of existing `infra/build-and-push.sh`; `migrate.sh` used wrong gcloud flag (`--add-cloudsql-instances` vs `--set-cloudsql-instances`) hidden by `2>/dev/null` | Added deploy-script prerequisite check to `/create-batch-execution-plan`; fixed `migrate.sh` flag and error handling; added verification check for inline docker commands | Deploy Commands |
| May 2026 | Workstream fully deployed and verified on live site but all status files still showed "in progress" — closure was manual and forgotten | Added auto-closure to `/verify-batch-completion`: detects final batch, auto-updates STATUS.md, BATCH_EXECUTION_PLAN.md, MERGE_POINTS.md, and workstreams/README.md | Verify Batch Completion |
| May 2026 | Merge point tags like `mp1-foundation-complete` collided across workstreams — no way to tell which workstream a tag belonged to | Tags now include feature branch suffix: `{base-tag}-{feature-branch}` (e.g., `mp1-foundation-complete-feature/ui-improvements-audit-activity`). Updated `/run-batch`, `/create-batch-execution-plan`, `/create-workstream` | Merge Point Tag Naming Convention |
| May 2026 | mp_config files were created manually per workstream/merge-point — easy to forget, inconsistent | Added Step 3.5 to `/run-plan`: auto-generates `scripts/mp_configs/[feature]-mp[N].conf` from MERGE_POINTS.md after batch plan is created | mp_config Auto-Generation |
| May 2026 | `execute_merge_point.sh` Phase 4 had hardcoded agent-lifecycle API smoke tests; Phase 5 had hardcoded commit-message grep | Replaced with config-driven `SMOKE_ENDPOINTS[]` array and `COMMIT_PATTERN` variable; added single-branch mode support (empty `WORKTREE_PATH`) | Execute Merge Point Generalization |
| May 2026 | `/run-batch` did not call `execute_merge_point.sh` or `validate_integration.sh`; no batch chaining | Added Steps 7e (execute_merge_point.sh), 7f (validate_integration.sh for backend batches), and 8a (`--continue` flag for auto-chaining batches) | Batch Automation Generalization |
| May 2026 | Merge Actions (commit, tag, push) were run before BATCH_EXECUTION_PLAN Validation scripts, Container Deployment, and Container Test Scenarios — migration had never been tested on PostgreSQL before MP1 was tagged | Added "Merge Point Protocol" section: Validation → Container Deployment → Container Test Scenarios → Success Criteria → Merge Actions. This is a sequential pre-merge gate, not an optional post-merge check | Merge Point Protocol |
| May 2026 | P0-B1/B2 execution skipped 151 pre-existing test failures (19F+83E control, 132F+5E gateway) — tests were dismissed as "not from this workstream" but many were broken by new code or drifted from implementation | Added mandatory rule: ALL tests must pass before batch completion, not just workstream-generated tests. Pre-existing failures must be fixed if encountered. Added "Test Suite Health (MANDATORY)" section | Test Suite Health |

### How to Add New Lessons

When you discover a pattern that caused issues:

1. **Document the symptom** - What error/problem occurred?
2. **Document the root cause** - What was actually wrong?
3. **Document the fix** - How to avoid it in the future?
4. **Add to this table** with date
5. **Update relevant section** in CLAUDE.md with the learning