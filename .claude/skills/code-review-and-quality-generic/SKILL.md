---
name: code-review-and-quality
description: >-
  Conducts five-axis code review: correctness, readability, architecture,
  security, performance. Use before merging any change. Use when reviewing
  code written by yourself, another agent, or a human.
---

# Code Review and Quality

Five-axis code review with quality gates. Every change gets reviewed before merge — no exceptions.

**Approval standard:** Approve when the change definitely improves overall code health, even if it isn't perfect. Don't block because it isn't how you would have written it.

## When to Use

- Before merging any PR or change
- After completing a feature implementation
- When another agent or model produced code
- After any bug fix (review fix + regression test)

## Current Changes

```!
if [ -d .git ]; then
  echo "=== Changed files ==="
  git diff --name-only HEAD~1 2>/dev/null | head -30
  echo ""
  echo "=== Stats ==="
  git diff --stat HEAD~1 2>/dev/null | tail -5
fi
```

## The Five-Axis Review

### 1. Correctness

- Does it match the spec or task requirements?
- Are edge cases handled (null, empty, boundary values)?
- Are error paths handled (not just the happy path)?
- Do tests exist and actually test the right things?
- Off-by-one errors, race conditions, state inconsistencies?

### 2. Readability

- Names descriptive and consistent with project conventions?
- Control flow straightforward (no deep nesting, nested ternaries)?
- Could this be done in fewer lines? (1000 lines where 100 suffice = failure)
- Are abstractions earning their complexity?
- Dead code: no-op variables, backwards-compat shims, `// removed` comments?

### 3. Architecture

- Follows existing patterns or introduces a justified new one?
- Clean module boundaries, no circular dependencies?
- Dependencies flowing in the right direction?
- Appropriate abstraction level (not over-engineered, not too coupled)?
- Code duplication that should be shared?

### 4. Security

- User input validated and sanitized?
- Secrets out of code, logs, and version control?
- Auth/authz checked where needed?
- SQL queries parameterized (no string concatenation)?
- Outputs encoded to prevent XSS?
- External data treated as untrusted at boundaries?

### 5. Performance

- N+1 query patterns?
- Unbounded loops or unconstrained data fetching?
- Synchronous operations that should be async?
- Missing pagination on list endpoints?
- Large objects created in hot paths?

## Change Sizing

```
~100 lines   → Good. Reviewable in one sitting.
~300 lines   → Acceptable if single logical change.
~1000 lines  → Too large. Split it.
```

| Split Strategy | When |
|----------------|------|
| **Stack** | Sequential dependencies |
| **By file group** | Cross-cutting concerns |
| **Horizontal** | Shared code first, then consumers |
| **Vertical** | Smaller full-stack slices |

Separate refactoring from feature work. Both in one PR = two PRs.

## Review Process

### Step 1: Understand Context

What is this change trying to accomplish? What spec does it implement?

### Step 2: Review Tests First

Tests exist? Test behavior not implementation? Edge cases covered? Descriptive names? Would they catch a regression?

### Step 3: Review Implementation

Walk each file with all five axes.

### Step 4: Label Findings

| Label | Meaning | Author Action |
|-------|---------|---------------|
| *(none)* | Required | Must fix before merge |
| **Critical:** | Blocks merge | Security, data loss, broken functionality |
| **Nit:** | Minor | Author may ignore |
| **Optional:** | Suggestion | Worth considering |
| **FYI** | Info | No action needed |

### Step 5: Verify the Verification

Tests pass? Build succeeds? Lint clean? Manual verification (if applicable)?

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "It works, good enough" | Working + unreadable + insecure = tech debt that compounds |
| "I wrote it, so it's correct" | Authors are blind to their own assumptions |
| "We'll clean it up later" | Later never comes. Cleanup before merge. |
| "AI-generated code is fine" | AI code needs more scrutiny, not less |
| "Tests pass, so it's good" | Tests don't catch architecture, security, or readability issues |

## Red Flags

- PRs merged without review
- Review that only checks test results
- "LGTM" without evidence of actual review
- Security changes without security-focused review
- PRs over 300 lines that aren't split
- No regression test with bug fixes
- Findings without severity labels
- Accepting "I'll fix it later"

## Verification

- [ ] All Critical issues resolved
- [ ] All required issues resolved or deferred with justification
- [ ] Tests pass
- [ ] Lint clean
- [ ] Review checklist completed
