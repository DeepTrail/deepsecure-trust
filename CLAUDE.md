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