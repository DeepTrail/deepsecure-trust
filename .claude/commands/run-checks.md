# Run Quality Checks

Run linting, type checking, and tests before committing.

## Instructions

1. **Run the standard check sequence:**

   ```bash
   # Step 1: Format code
   make format
   # or: black . && isort .
   
   # Step 2: Run linter
   make lint
   # or: ruff check .
   
   # Step 3: Run type checker
   mypy deepsecure/
   
   # Step 4: Run tests (if specified)
   pytest [specific tests or all]
   ```

2. **Report results:**
   - Show pass/fail for each step
   - For failures, show the specific errors
   - Suggest fixes for common issues

3. **If all pass:**
   - Confirm ready to commit
   - Optionally run `make check-all` for full validation

## Output Format

```markdown
## Quality Check Results

| Check | Status | Details |
|-------|--------|---------|
| Format (black/isort) | ✅ Pass | No changes needed |
| Lint (ruff) | ✅ Pass | 0 issues |
| Type Check (mypy) | ⚠️ Warning | 2 notes (non-blocking) |
| Tests (pytest) | ✅ Pass | 45 passed in 12.3s |

### Summary
All checks passed. Ready to commit.

---

Run `make check-all` for comprehensive validation including security scans.
```

## On Failure

If any check fails:

```markdown
## Quality Check Results

| Check | Status | Details |
|-------|--------|---------|
| Format | ✅ Pass | |
| Lint | ❌ Fail | 3 errors |
| Type Check | - | Skipped (lint failed) |
| Tests | - | Skipped |

### Lint Errors

```
deepsecure/client.py:45:1: E501 Line too long (120 > 100 characters)
deepsecure/client.py:67:5: F401 'os' imported but unused
deepsecure/_core/utils.py:12:1: E302 Expected 2 blank lines, found 1
```

### Suggested Fixes
1. Line 45: Break the long line or adjust string
2. Line 67: Remove unused import `os`
3. utils.py line 12: Add blank line before function

Would you like me to fix these issues?
```

## Quick Checks (Subset)

For faster iteration, can run subset:

```bash
# Just lint current file
ruff check path/to/file.py

# Just typecheck
mypy deepsecure/

# Just run related tests
pytest -k "test_pattern" -v
```
