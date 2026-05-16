---
name: code-review-and-quality
description: >-
  Conducts five-axis code review for the DeepSecure platform. Use before merging
  any change. Use when reviewing code written by yourself, another agent, or a human.
  Covers correctness, readability, architecture, security, and performance with
  DeepSecure-specific contract verification, token type checks, and service boundary
  validation.
---

# Code Review and Quality

## Overview

Multi-dimensional code review with quality gates, tailored for DeepSecure's dual-service architecture (Control Plane + Gateway), agent identity system, and MCP protocol. Every change gets reviewed before merge — no exceptions.

**The approval standard:** Approve a change when it definitely improves overall code health, even if it isn't perfect. Don't block a change because it isn't exactly how you would have written it. If it improves the codebase and follows project conventions, approve it.

## When to Use

- Before merging any PR or change
- After completing a feature implementation (`/execute-task`)
- When another agent or model produced code you need to evaluate
- When refactoring existing code
- After any bug fix (review both the fix and the regression test)

## Current Changes

```!
if [ -d .git ]; then
  echo "=== Changed files ==="
  git diff --name-only HEAD~1 2>/dev/null | head -30
  echo ""
  echo "=== Diff stats ==="
  git diff --stat HEAD~1 2>/dev/null | tail -5
fi
```

## The Five-Axis Review

### 1. Correctness

Does the code do what it claims to do?

- Does it match the spec or task requirements?
- Are edge cases handled (null, empty, boundary values)?
- Are error paths handled (not just the happy path)?
- Does it pass all tests? Are the tests actually testing the right things?
- Are there off-by-one errors, race conditions, or state inconsistencies?

**DeepSecure-specific:** Do API endpoints return the documented response schema? Does the challenge-response flow use proper Ed25519 signatures?

### 2. Readability & Simplicity

Can another engineer understand this code without the author explaining it?

- Are names descriptive and consistent with project conventions?
- Is the control flow straightforward (no deep nesting)?
- Could this be done in fewer lines? (1000 lines where 100 suffice is a failure)
- Are abstractions earning their complexity? (Don't generalize until the third use case)
- Are there dead code artifacts: no-op variables, backwards-compat shims?

### 3. Architecture

Does the change fit DeepSecure's service architecture?

- Does it follow existing patterns or introduce a new one? If new, is it justified?
- Does it maintain clean service boundaries (Control Plane vs Gateway vs SDK)?
- Are dependencies flowing in the right direction?
- Does it follow the file path conventions?

**DeepSecure file conventions:**

| Pattern | Convention |
|---------|-----------|
| API endpoints | `[service]/app/api/v1/endpoints/` |
| Business logic | `[service]/app/services/*_service.py` |
| Models | `[service]/app/models/` |
| Security | `[service]/app/security/` |

For the full path convention table, see [reference/deepsecure-conventions.md](reference/deepsecure-conventions.md).

### 4. Security

Does the change introduce vulnerabilities?

- Is user input validated and sanitized?
- Are secrets kept out of code, logs, and version control?
- Is authentication/authorization checked on every endpoint?
- Are SQL queries parameterized (no string concatenation)?
- Are the correct token types used per endpoint?

**DeepSecure token verification** (check every endpoint):

| Endpoint Pattern | Required Token |
|-----------------|---------------|
| `/api/v1/auth/*` (public) | None or User Token |
| `/api/v1/agents/*` | User Token |
| `/api/v1/vault/*` | Agent JWT (has `owner` claim) |
| `/api/v1/auth/agent/*` | None (challenge) or Agent JWT (verify) |
| Internal (`/internal/*`) | Internal API Token + `X-User-ID` |
| Gateway MCP (`/mcp`) | Agent JWT, `initialize` before `tools/call` |

For the full token flow reference, see [reference/auth-patterns.md](reference/auth-patterns.md).

### 5. Performance

Does the change introduce performance problems?

- Any N+1 query patterns?
- Any unbounded loops or unconstrained data fetching?
- Any synchronous operations that should be async?
- Any missing pagination on list endpoints?
- Any large objects created in hot paths?

## Change Sizing

Target these sizes:

```
~100 lines changed   → Good. Reviewable in one sitting.
~300 lines changed   → Acceptable if it's a single logical change.
~1000 lines changed  → Too large. Split it.
```

**Splitting strategies:**

| Strategy | When |
|----------|------|
| **Stack** | Sequential dependencies |
| **By service** | Changes span Control + Gateway |
| **Horizontal** | Shared models/contracts first, then consumers |
| **Vertical** | Smaller full-stack slices |

**Separate refactoring from feature work.** A change that refactors existing code AND adds new behavior is two changes — submit them separately.

## Review Process

### Step 1: Understand the Context

```
- What is this change trying to accomplish?
- What spec or task ticket does it implement?
- What is the expected behavior change?
```

### Step 2: Review the Tests First

Tests reveal intent and coverage:

```
- Do tests exist for the change?
- Do they test behavior (not implementation details)?
- Are edge cases covered?
- Does every auth-gated endpoint have correct/wrong/expired/missing token tests?
- Would the tests catch a regression?
```

### Step 3: Review the Implementation

Walk through each file with the five axes in mind.

### Step 4: Categorize Findings

Label every comment with severity:

| Prefix | Meaning | Author Action |
|--------|---------|---------------|
| *(no prefix)* | Required change | Must address before merge |
| **Critical:** | Blocks merge | Security vulnerability, data loss, broken functionality |
| **Nit:** | Minor, optional | Author may ignore |
| **Optional:** / **Consider:** | Suggestion | Worth considering but not required |
| **FYI** | Informational | No action needed |

### Step 5: Verify the Verification

```
- Tests pass?
- Build succeeds?
- ruff check / mypy clean?
- Manual verification done (if applicable)?
```

## Multi-Agent Review Pattern

For complex changes, invoke specialist agents:

```
code-reviewer    → Correctness + Architecture
test-engineer    → Test quality + Coverage gaps
security-auditor → OWASP + Token verification (for auth changes)
```

See `.claude/agents/` for agent definitions.

## Honesty in Review

- **Don't rubber-stamp.** "LGTM" without evidence is not a review.
- **Don't soften real issues.** A bug that will hit production is not "a minor concern."
- **Quantify when possible.** "This N+1 adds ~50ms per item" beats "this could be slow."
- **Push back on bad approaches.** Sycophancy is a failure mode.

## The Review Checklist

```markdown
## Review: [PR/Change title]

### Context
- [ ] I understand what this change does and why

### Correctness
- [ ] Matches spec/task requirements
- [ ] Edge cases handled
- [ ] Error paths handled
- [ ] Tests adequate

### Readability
- [ ] Names clear and consistent
- [ ] Logic straightforward
- [ ] No unnecessary complexity

### Architecture
- [ ] Follows existing DeepSecure patterns
- [ ] Correct file locations (app/api/v1/endpoints/, app/services/, etc.)
- [ ] Clean service boundaries (Control vs Gateway vs SDK)

### Security
- [ ] No secrets in code/logs/errors
- [ ] Correct token types per endpoint
- [ ] Input validated at boundaries
- [ ] Auth dependencies (Depends()) on every endpoint

### Performance
- [ ] No N+1 patterns
- [ ] No unbounded operations
- [ ] Pagination on list endpoints

### Verification
- [ ] pytest passes
- [ ] ruff check clean
- [ ] mypy clean (or no new errors)

### Verdict
- [ ] **Approve** — Ready to merge
- [ ] **Request changes** — Issues must be addressed
```

## See Also

- For detailed security review, see `security-and-hardening` skill or `/security-audit`
- For DeepSecure conventions, see [reference/deepsecure-conventions.md](reference/deepsecure-conventions.md)
- For auth flow details, see [reference/auth-patterns.md](reference/auth-patterns.md)

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "It works, that's good enough" | Working code that's unreadable, insecure, or architecturally wrong creates debt that compounds. |
| "I wrote it, so I know it's correct" | Authors are blind to their own assumptions. Every change benefits from another set of eyes. |
| "We'll clean it up later" | Later never comes. Require cleanup before merge, not after. |
| "AI-generated code is probably fine" | AI code needs more scrutiny, not less. It's confident and plausible, even when wrong. |
| "The tests pass, so it's good" | Tests don't catch architecture problems, security issues, or readability concerns. |
| "This is just an internal API" | Internal APIs get compromised via SSRF, supply chain attacks, or lateral movement. |

## Red Flags

- PRs merged without any review
- Review that only checks if tests pass (ignoring other axes)
- "LGTM" without evidence of actual review
- Security-sensitive changes without token type verification
- Large PRs (>300 lines) that aren't split
- No regression tests with bug fix PRs
- Review comments without severity labels
- Accepting "I'll fix it later"
- `Depends()` missing on auth-gated endpoints
- User Token used where Agent JWT is required (or vice versa)

## Verification

After review is complete:

- [ ] All Critical issues resolved
- [ ] All required issues resolved or explicitly deferred with justification
- [ ] `pytest` passes
- [ ] `ruff check .` clean
- [ ] `mypy deepsecure/` clean (or no new errors)
- [ ] Review checklist completed and documented
