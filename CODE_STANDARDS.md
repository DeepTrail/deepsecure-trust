# Code Standards & Self-Verification

> Extracted from CLAUDE.md. This is the reference for engineering preferences, code review process, and verification model.

## Engineering Preferences

- **DRY is important** — flag repetition aggressively
- **Well-tested code is non-negotiable** — too many tests > too few
- **"Engineered enough"** — not under-engineered (fragile, hacky) and not over-engineered (premature abstraction, unnecessary complexity)
- **Handle edge cases** — err on the side of more, not fewer; thoughtfulness > speed
- **Explicit over clever** — bias toward readable, obvious code

## 4-Stage Code Review Process

For significant changes, work through each stage:

### 1. Architecture Review
- Overall system design and component boundaries
- Dependency graph and coupling concerns
- Data flow patterns and potential bottlenecks
- Scaling characteristics and single points of failure
- Security architecture (auth, data access, API boundaries)

### 2. Code Quality Review
- Code organization and module structure
- DRY violations — be aggressive here
- Error handling patterns and missing edge cases (call these out explicitly)
- Technical debt hotspots
- Areas that are over-engineered or under-engineered

### 3. Test Review
- Test coverage gaps (unit, integration, e2e)
- Test quality and assertion strength
- Missing edge case coverage — be thorough
- Untested failure modes and error paths

### 4. Performance Review
- N+1 queries and database access patterns
- Memory-usage concerns
- Caching opportunities
- Slow or high-complexity code paths

### For Each Issue Found

1. **Describe the problem concretely** — with file and line references
2. **Present 2-3 options** — including "do nothing" where reasonable
3. **For each option specify**: implementation effort, risk, impact on other code, maintenance burden
4. **Give recommended option and why** — mapped to engineering preferences above
5. **Ask for direction** — explicitly ask whether to proceed or choose differently

### Workflow Rules

- Do not assume priorities on timeline or scale
- After each section, pause and ask for feedback before moving on
- NUMBER issues (1, 2, 3) and use LETTERS for options (A, B, C)
- Make the recommended option always the 1st option
- **BIG CHANGE**: Work through interactively, one section at a time with at most 4 top issues per section
- **SMALL CHANGE**: Work through interactively ONE question per review section

## Three-Tier Verification Model

| Tier | When | What | How |
|------|------|------|-----|
| **Micro** | After each file edit | Lint, format, type errors | `ReadLints` after edits |
| **Macro** | Before declaring "done" | Tests pass, requirements met | Run tests, verify acceptance criteria |
| **Meta** | Before task breakdown | Assumptions validated | `/explore-codebase` before `/breakdown-design` |

### Micro Verification: After Every Edit

1. **Run `ReadLints`** on edited files to catch errors immediately
2. **Fix any errors you introduced** (don't leave them for the user)
3. **Verify the change compiles/runs** if possible

### Macro Verification: Before Completion

1. **Re-read the acceptance criteria** from the task/ticket
2. **Verify each criterion is actually met** (don't assume)
3. **Run relevant tests** if specified
4. **Check that you didn't break existing functionality**

### Meta Verification: Validate Assumptions

1. **Verify design doc claims against codebase** (don't trust "Not Implemented" labels)
2. **Confirm file paths exist** before editing them
3. **Check that dependencies are in place** before building on them

## File Path Verification (MANDATORY)

Before documenting file paths in validation sections, test commands, BATCH_EXECUTION_PLAN.md, or MERGE_POINTS.md:

```bash
# Use glob to verify test file paths
ls [service]/tests/[module]/test_*.py

# Use find for fuzzy matching if unsure of exact name
find . -name "*vault*" -path "*/tests/*" -name "*.py"

# Check openapi.json for endpoint paths
curl -s http://localhost:8000/openapi.json | jq '.paths | keys'
```

Prefer glob patterns over specific file names when possible:
```bash
# Good - works even if file names change
pytest tests/backends/ -v

# Risky - fails if file is named differently
pytest tests/backends/test_notion_api.py -v
```

## Self-Check Questions

| Phase | Question | If "No" |
|-------|----------|---------|
| Planning | "Did I verify this component doesn't already exist?" | Run `/explore-codebase` |
| Implementation | "Did I run lints after my edits?" | Run `ReadLints` |
| Implementation | "Did I test this change?" | Run relevant tests |
| Completion | "Does my change actually meet the acceptance criteria?" | Re-read and verify |
| Completion | "Did I introduce any regressions?" | Run `make check-all` |

## Anti-Patterns

| Bad | Good |
|-----|------|
| Edit file → Move on | Edit file → ReadLints → Fix errors → Move on |
| "I implemented the feature" | "I implemented the feature and verified: [list of checks]" |
| Trust design doc claims | Verify claims against actual codebase |
| Assume tests will pass | Run tests before declaring done |
| "This should work" | "I verified this works by [specific test]" |

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
