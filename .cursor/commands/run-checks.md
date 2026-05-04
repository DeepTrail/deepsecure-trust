# Run Checks: Quality Gate Before Review and Merge

Run linting, type checking, formatting, and tests as a mandatory quality gate. This is the automated verification step that must pass before any code review or merge.

## Workflow Position

```
... → /execute-task → /complete-task → /run-checks → /review → /commit-push-pr
                                           ↑
                                      (YOU ARE HERE)
```

## When to Use

- After completing task implementation (post `/execute-task`)
- Before requesting code review (`/review`)
- Before committing and creating a PR (`/commit-push-pr`)
- After fixing review feedback (re-run before re-review)
- After any refactoring or debugging session

**When NOT to use:**
- Documentation-only changes (no Python code) — skip to `/review`
- Changes exclusively in markdown/config files with no code impact

---

## Instructions

### Phase 1: SCOPE — Determine What to Check

Identify which files changed and which checks apply:

```bash
# What changed?
git diff --name-only HEAD~1
# Or for staged changes:
git diff --staged --name-only

# Categorize changes
PYTHON_CHANGED=$(git diff --name-only HEAD~1 | grep '\.py$')
TEST_CHANGED=$(git diff --name-only HEAD~1 | grep 'test_')
```

| Files Changed | Checks to Run |
|---------------|---------------|
| Python source files | Format + Lint + Type check + Tests |
| Test files only | Tests only (format + lint still recommended) |
| Config/YAML/TOML | Syntax validation only |
| Markdown/docs only | Skip quality checks entirely |
| Mixed | Full check sequence |

### Phase 2: FORMAT — Auto-Fix Style Issues

```bash
# Format with black
black .
# or target specific files:
black [changed_files]

# Sort imports
isort .
# or target specific files:
isort [changed_files]

# Combined
make format
```

**Use the Shell tool** to run these commands. If formatting changes files, note which files were modified — they need to be staged before commit.

### Phase 3: LINT — Static Analysis

```bash
# Run ruff linter
ruff check .
# or target specific files:
ruff check [changed_files]

# Auto-fix safe issues
ruff check --fix [changed_files]
```

**Use the ReadLints tool** on edited files as a complementary check — it catches IDE-level diagnostics that ruff may not cover.

**Common ruff issues and fixes:**

| Rule | Issue | Fix |
|------|-------|-----|
| `F401` | Unused import | Remove the import |
| `E501` | Line too long | Break line or adjust string |
| `E302` | Missing blank lines | Add blank lines before function/class |
| `F841` | Unused variable | Remove or prefix with `_` |
| `E711` | Comparison to None | Use `is None` instead of `== None` |

### Phase 4: TYPE — Type Checking

```bash
# Type check SDK
mypy deepsecure/

# Type check specific service
mypy deeptrail-control/app/
mypy deeptrail-gateway/app/

# Type check specific files
mypy [changed_files]
```

**Common mypy issues:**

| Error | Fix |
|-------|-----|
| `Missing return type` | Add `-> ReturnType` to function signature |
| `Incompatible types` | Fix type annotation or add cast |
| `Module has no attribute` | Check import path, add stub if needed |
| `Missing type stubs` | `pip install types-[package]` or add to `mypy.ini` ignore |

### Phase 5: TEST — Run Relevant Tests

**Run tests in the correct working directory:**

```bash
# SDK tests (from repo root)
cd /Users/imaxxs/repositories/deepsecure-mvp
pytest tests/ -v

# Control Plane tests
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-control
pytest tests/ -v

# Gateway tests
cd /Users/imaxxs/repositories/deepsecure-mvp/deeptrail-gateway
pytest tests/ -v

# Specific test file
pytest tests/path/to/test_file.py -v

# Tests matching a pattern
pytest -k "test_agent" -v

# With coverage
pytest --cov=deepsecure --cov-report=term -v
```

**If tests fail, use `/debug` to investigate — do not proceed past failing tests.**

### Phase 6: REPORT — Summarize Results

Generate the quality report (see Output Format below).

---

## Output Format

```markdown
## Quality Check Results

### Scope
- **Files changed:** [N] files
- **Python files:** [N]
- **Test files:** [N]

### Results

| # | Check | Status | Details |
|---|-------|--------|---------|
| 1 | Format (black/isort) | ✅ Pass / ⚠️ Fixed [N] files | [details] |
| 2 | Lint (ruff) | ✅ Pass / ❌ [N] errors | [details] |
| 3 | Type Check (mypy) | ✅ Pass / ⚠️ [N] warnings | [details] |
| 4 | Tests (pytest) | ✅ [N] passed / ❌ [N] failed | [details] |

### Errors (if any)

[Specific errors with file:line references and suggested fixes]

### Verdict

- [ ] **All checks pass** — Ready for `/review`
- [ ] **Checks pass with warnings** — Proceed but note warnings in review
- [ ] **Checks fail** — Fix issues before proceeding (use `/debug` if needed)
```

---

## Quick Check Mode

For faster iteration during development (not a substitute for full checks):

```bash
# Just lint the file you're editing
ruff check path/to/file.py

# Just run one test
pytest tests/path/to/test_file.py::test_name -v

# Just typecheck one module
mypy path/to/module.py
```

## Full Validation Mode

Before a PR, run everything:

```bash
make check-all
# or manually:
black . && isort . && ruff check . && mypy deepsecure/ && pytest -v
```

---

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "Tests pass, so linting doesn't matter" | Lint catches bugs that tests don't: unused imports hiding dependency issues, type comparison errors, unreachable code. |
| "I'll fix the lint warnings later" | Later never comes. Fix now — it takes 2 minutes. Leaving warnings normalizes ignoring them. |
| "Type checking is too strict / noisy" | Run `mypy` on changed files only. Type errors in new code are real bugs worth catching now. |
| "The formatter changed too many files" | That means those files were already inconsistent. Stage only your changes if needed, but the formatting is correct. |
| "These tests are flaky, ignore them" | Flaky tests mask real bugs. If a test is genuinely flaky, fix the flakiness. If it's a real failure, stop and debug. |
| "I only changed one line, no need to run checks" | One-line changes cause production outages. Run checks. Always. |
| "make check-all takes too long" | Use targeted checks on changed files for speed. Run full checks before the final PR. |

## Red Flags

- Proceeding to `/review` without running checks
- Commenting out failing tests instead of fixing them
- Running `ruff check --fix` without reviewing what it changed
- Ignoring mypy errors with `# type: ignore` without justification
- Tests passing but with `pytest` warnings about deprecated fixtures
- Format check "passing" because formatter was never run (no changes doesn't mean no issues)
- Skipping tests for "documentation-only" changes when Python files were actually touched

## Verification

Before proceeding to `/review`:

- [ ] `black` and `isort` run — no unformatted files
- [ ] `ruff check` passes — zero errors (warnings acceptable with justification)
- [ ] `mypy` passes on changed modules — no new type errors introduced
- [ ] `pytest` passes for relevant test suite — zero failures
- [ ] Any auto-fixed files are staged for commit
- [ ] If checks fail, issues are fixed (not suppressed)

---

## Reference

This command integrates with:
- `/execute-task` → Run checks after implementation
- `/debug` → Use when checks reveal failures
- `/review` → Next step after checks pass
- `/commit-push-pr` → Checks must pass before committing
- Hooks (`afterFileEdit`) → Micro-level lint runs automatically on each edit

See also:
- `CLAUDE.md` → "Self-Verification: Check Your Own Work" (Three-Tier Model)
- `Makefile` → `make check-all`, `make lint`, `make format`, `make test`
