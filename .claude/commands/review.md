# Review: Multi-Axis Code Review Before Merge

Conduct a structured code review across five axes: correctness, readability, architecture, security, and performance. Use before merging any change.

## Workflow Position

```
... → /execute-task → /complete-task → /run-checks → /review → /commit-push-pr
                                                        ↑
                                                   (YOU ARE HERE)
```

## When to Use

- Before merging any PR or change
- After completing a feature implementation (post `/execute-task`, pre `/commit-push-pr`)
- When another agent or subagent produced code you need to evaluate
- After any bug fix (review both the fix and the regression test)
- When refactoring existing code
- After a batch of tasks is complete and before batch verification

**When NOT to use:** Single-line typo fixes where the change is self-evidently correct.

---

## The Five-Axis Review

Every review evaluates code across these dimensions. **No axis can be skipped.**

### Axis 1: Correctness

Does the code do what it claims to do?

- Does it match the spec or task ticket requirements?
- Are edge cases handled (null, empty, boundary values)?
- Are error paths handled (not just the happy path)?
- Do tests actually test the right things (not just that they pass)?
- Are there off-by-one errors, race conditions, or state inconsistencies?
- **For API endpoints:** Do paths match the design doc exactly?

### Axis 2: Readability & Simplicity

Can another engineer (or agent) understand this without explanation?

- Are names descriptive and consistent with project conventions?
- Is control flow straightforward (no deeply nested logic)?
- Could this be done with fewer lines without losing clarity?
- Are abstractions earning their complexity? (Don't generalize until the third use case)
- Are there dead code artifacts: unused imports, commented-out code, `# TODO` without tickets?
- Do comments explain *why*, not *what*?

### Axis 3: Architecture

Does the change fit the system's design?

- Does it follow existing patterns in `deepsecure/_core/`?
- Does it maintain clean module boundaries (SDK / Control / Gateway)?
- Is there code duplication that should be shared?
- Are dependencies flowing in the right direction (no circular imports)?
- Is the abstraction level appropriate (not over-engineered, not too coupled)?
- **DeepSecure-specific:** Does it respect the dual-service architecture?

### Axis 4: Security

Does the change introduce vulnerabilities?

- Is user input validated and sanitized at API boundaries?
- Are secrets kept out of code, logs, and version control?
- Is authentication/authorization checked where needed?
- Are SQL queries parameterized (no string concatenation)?
- Are JWT tokens validated (expiry, issuer, signature)?
- Is data from external sources treated as untrusted?
- **DeepSecure-specific:** Is the split-key architecture respected? Are agent private keys handled via keyring?
- **DeepSecure-specific:** Are the correct token types used? (User Token vs Agent JWT vs Internal Token)

### Axis 5: Performance

Does the change introduce performance problems?

- Any N+1 query patterns?
- Any unbounded loops or unconstrained data fetching?
- Any synchronous operations that should be async?
- Any missing pagination on list endpoints?
- Any large objects created in hot paths?
- **DeepSecure-specific:** Any Redis/database calls in the gateway request path that could be cached?

---

## Instructions

### Step 1: Gather Context

```bash
# See what changed
git diff --stat HEAD~1
git diff HEAD~1

# Or for staged changes
git diff --staged --stat
git diff --staged

# Or for a branch
git diff main...HEAD --stat
git diff main...HEAD
```

Understand intent before reviewing code:
- What spec/task does this implement?
- What is the expected behavior change?

### Step 2: Review Tests First

Tests reveal intent and coverage. Read them before the implementation:

```
- Do tests exist for every changed module?
- Do they test behavior (not implementation details)?
- Are edge cases covered (empty input, invalid auth, timeout)?
- Do tests have descriptive names?
- Would the tests catch a regression?
- Are async fixtures using @pytest_asyncio.fixture (not @pytest.fixture)?
```

### Step 3: Review Implementation (Five Axes)

Walk through each changed file with all five axes:

```
For each file changed:
  1. Correctness:  Does this match the spec?
  2. Readability:  Can I understand this without context?
  3. Architecture: Does this fit the system?
  4. Security:     Any vulnerabilities?
  5. Performance:  Any bottlenecks?
```

### Step 4: Categorize Findings

**Every finding MUST have a severity label:**

| Prefix | Meaning | Author Action |
|--------|---------|---------------|
| **Critical:** | Blocks merge | Security vulnerability, data loss, broken functionality |
| *(no prefix)* | Required change | Must address before merge |
| **Nit:** | Minor, optional | Author may ignore — formatting, naming preferences |
| **Consider:** | Suggestion | Worth thinking about but not required |
| **FYI** | Informational | No action needed — context for future reference |

### Step 5: Contract Verification (DeepSecure-Specific)

```bash
# Extract implemented endpoints
grep -r "@router\.\(get\|post\|put\|delete\)" [changed_files] | grep -o '"/api/v1[^"]*"'

# Compare with spec
# Check: docs/workstreams/[feature]/specs/[WS-ID]-spec.md

# Verify test endpoints match
grep -r '"/api/v1' [test_files] | grep -o '"/api/v1[^"]*"'
```

| Check | Command | Expected |
|-------|---------|----------|
| Async fixtures | `grep "@pytest.fixture" [test]` | Should be empty for async |
| HTTP client | `grep "httpx.AsyncClient" [test]` | Should have matches |
| File location | E2E tests at `tests/e2e/` root | Cross-service tests here |
| Service prefix | All FastAPI files under `app/` | Not directly under service root |

### Step 6: Generate Review Report

---

## Output Format

```markdown
## Code Review: [Feature/Change Name]

### Context
- **Spec/Ticket:** [link or ID]
- **Files Changed:** [count] files, +[additions]/-[deletions]
- **Change Size:** [Small (<100) / Medium (<300) / Large (>300)]

### Findings

#### Critical (blocks merge)
- [ ] **Critical:** [file:line] [description]

#### Required (must fix)
- [ ] [file:line] [description]

#### Suggestions
- **Consider:** [file:line] [description]
- **Nit:** [file:line] [description]
- **FYI:** [context for future reference]

### Five-Axis Summary

| Axis | Status | Notes |
|------|--------|-------|
| Correctness | ✅ / ⚠️ / ❌ | [brief note] |
| Readability | ✅ / ⚠️ / ❌ | [brief note] |
| Architecture | ✅ / ⚠️ / ❌ | [brief note] |
| Security | ✅ / ⚠️ / ❌ | [brief note] |
| Performance | ✅ / ⚠️ / ❌ | [brief note] |

### Contract Verification

| Check | Spec | Implemented | Match? |
|-------|------|-------------|--------|
| [endpoint] | `/api/v1/...` | `/api/v1/...` | ✅ / ❌ |

### Test Coverage

| Module | Tests Exist? | Edge Cases? | Regression Guard? |
|--------|-------------|-------------|-------------------|
| [module] | ✅ / ❌ | ✅ / ❌ | ✅ / ❌ |

### Dead Code Check
- [List any orphaned code, unused imports, commented-out blocks]

### Verdict

- [ ] **Approve** — Ready to merge. [Improves overall code health]
- [ ] **Approve with nits** — Merge after addressing required items
- [ ] **Request changes** — Critical/required issues must be addressed
- [ ] **Needs discussion** — Architectural concerns require human input
```

---

## Change Sizing

Target these sizes. If a change is too large, split it before reviewing:

```
~100 lines changed   → Good. Reviewable in one sitting.
~300 lines changed   → Acceptable if it's a single logical change.
~500+ lines changed  → Split it. Use these strategies:
```

| Strategy | How | When |
|----------|-----|------|
| **Stack** | Submit a small change, start the next one based on it | Sequential dependencies |
| **By service** | Separate changes for Control, Gateway, SDK | Cross-service work |
| **Horizontal** | Create shared models/schemas first, then consumers | Layered architecture |
| **Vertical** | Break into smaller full-stack slices | Feature work |

**Separate refactoring from feature work.** A change that refactors existing code AND adds new behavior is two changes — review them separately.

---

## Multi-Agent Review Pattern

For complex changes, use different review perspectives:

```
Agent A writes code (via /execute-task)
    │
    ▼
/review — General five-axis review
    │
    ▼
Subagent: code-reviewer — Deep correctness and architecture
Subagent: test-engineer — Test quality and coverage
Subagent: security-auditor — Security-focused review
    │
    ▼
Human makes the final call
```

To invoke subagent reviews:
```
Use Task tool with subagent_type="generalPurpose" and the agent definition
from .cursor/agents/code-reviewer.md (or test-engineer.md, security-auditor.md)
```

---

## Honesty in Review

- **Don't rubber-stamp.** "Looks good" without evidence of review helps no one.
- **Don't soften real issues.** "This might be a minor concern" when it's a bug is dishonest.
- **Quantify problems.** "This N+1 query adds ~50ms per item" beats "this could be slow."
- **Push back on bad approaches.** If the implementation has issues, say so directly and propose alternatives.
- **Accept override gracefully.** If the human has full context and disagrees, defer to their judgment.

---

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "It works, that's good enough" | Working code that's unreadable, insecure, or architecturally wrong creates debt that compounds. |
| "I wrote it, so I know it's correct" | Authors are blind to their own assumptions. Every change benefits from another set of eyes. |
| "We'll clean it up later" | Later never comes. The review is the quality gate — use it. Require cleanup before merge. |
| "AI-generated code is probably fine" | AI code needs *more* scrutiny, not less. It's confident and plausible, even when wrong. |
| "The tests pass, so it's good" | Tests are necessary but not sufficient. They don't catch architecture problems, security issues, or readability concerns. |
| "This change is too small to review" | Small changes cause large outages. Review everything. One-line auth bypass is one line. |
| "We're in a hurry" | Rushed code costs more in production. A 10-minute review saves hours of incident response. |
| "The subagent already reviewed it" | Subagent reviews are a first pass, not a replacement. Different perspectives catch different issues. |

## Red Flags

- Changes merged without any review
- Review that only checks if tests pass (ignoring other axes)
- "LGTM" without evidence of actual review
- Security-sensitive changes without security-focused review
- Large changes that are "too big to review properly" (split them first)
- No regression tests with bug fix changes
- Review comments without severity labels
- Accepting "I'll fix it later" — it never happens
- API endpoint paths that don't match the design doc
- Missing `@pytest_asyncio.fixture` on async test fixtures
- Cross-service tests placed inside a service directory instead of root `tests/e2e/`

## Verification

After review is complete:

- [ ] All five axes evaluated (no axis skipped)
- [ ] All Critical issues are resolved
- [ ] All Required issues are resolved or explicitly deferred with justification
- [ ] Contract verification passes (endpoints match spec)
- [ ] Tests pass (`pytest [relevant tests] -v`)
- [ ] Build succeeds (`ruff check .`)
- [ ] Correct token types used (User Token vs Agent JWT vs Internal Token)
- [ ] Files in correct locations (E2E at root, service tests under service)
- [ ] Review report generated with findings and verdict

---

## Reference

This command integrates with:
- `/run-checks` — Automated quality checks (run before review)
- `/commit-push-pr` — Ship after review approval
- `/complete-task` — Completion reports should reference review findings
- `.cursor/agents/code-reviewer.md` — Subagent for deep review
- `.cursor/agents/test-engineer.md` — Subagent for test review
- `.cursor/agents/security-auditor.md` — Subagent for security review

See also:
- `CLAUDE.md` — Self-Verification section (4-Stage Code Review Process)
- Osmani's `code-review-and-quality` — Upstream inspiration
