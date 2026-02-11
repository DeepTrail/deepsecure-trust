# Commit, Push, and Create PR

Commit current changes, push to remote, and create a pull request.

## Instructions

1. **Check current state:**
   ```bash
   git status
   git diff --staged
   git diff
   ```

2. **Run quality checks first:**
   - Run `make lint` or `ruff check .`
   - Run `mypy deepsecure/`
   - Run relevant tests
   - If any fail, fix before proceeding

3. **Stage changes:**
   - Review unstaged changes
   - Stage appropriate files (not secrets, not generated files)
   - Confirm with user what to include

4. **Create commit:**
   - Generate descriptive commit message
   - Follow conventional commits format if applicable:
     - `feat:` new feature
     - `fix:` bug fix
     - `refactor:` code refactoring
     - `test:` adding tests
     - `docs:` documentation
     - `chore:` maintenance

5. **Push to remote:**
   ```bash
   git push -u origin HEAD
   ```

6. **Create PR:**
   ```bash
   gh pr create --title "..." --body "..."
   ```
   
   PR body should include:
   - Summary of changes (bullet points)
   - Related issues/tickets
   - Test plan
   - Any breaking changes

## Output Format

```markdown
## Changes Committed and PR Created

### Commit
- **Hash:** abc1234
- **Message:** feat: add token validation to gateway

### Files Changed
- `deepsecure/_core/token.py` (+120/-30)
- `tests/test_token.py` (+85/-0)

### Pull Request
- **PR #123:** [feat: add token validation to gateway](link)
- **Branch:** feature/token-validation → main

### PR Summary
- Added TokenValidator class for JWT validation
- Integrated with gateway middleware
- Added comprehensive test coverage

---

PR is ready for review.
```

## Safety Checks

Before committing, verify:
- [ ] No secrets or credentials in diff
- [ ] No `.env` files staged
- [ ] No large binary files
- [ ] Tests pass
- [ ] Lint passes

## Example Commit Messages

```
feat: add MCP protocol handler for gateway

- Implement message parsing for MCP format
- Add request routing based on message type
- Include validation for required fields

Closes #45
```

```
fix: resolve token expiration edge case

The token validator was not handling timezone-aware
datetimes correctly, causing false expiration errors.

Fixes #67
```
