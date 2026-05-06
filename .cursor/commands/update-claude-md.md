# Update CLAUDE.md: Capture Learnings as Permanent Rules

Add a new rule, pattern, or pitfall to CLAUDE.md so every future session benefits from what you just learned. This is the "compounding engineering" step — every mistake becomes a rule that prevents future mistakes.

## Workflow Position

```
... → /complete-task → /run-checks → /review → /commit-push-pr
                           │
                           └── /update-claude-md ← Triggered by any learning
                                    ↑
                               (YOU ARE HERE)
```

This command can be triggered at any point in the pipeline when a generalizable learning is discovered — during execution, debugging, review, or completion.

## When to Use

- You discovered a new pitfall that cost time (wrong token type, wrong file path, etc.)
- A debugging session revealed a non-obvious pattern
- A `/complete-task` report recommends a CLAUDE.md update
- A `/review` found a recurring issue worth codifying
- You found a new "common mistake" that should be documented
- An API contract or behavior was different from what documentation suggested

**When NOT to use:**
- The learning is project-specific to a single feature (put it in the feature's completion report instead)
- The learning is already documented in CLAUDE.md (check first with grep)
- The learning is obvious to any engineer (e.g., "run tests before committing")
- The change would contradict an existing rule without justification

---

## Instructions

### Phase 1: VALIDATE — Confirm the Learning is Worth Adding

Before modifying CLAUDE.md, verify:

1. **Is it generalizable?** Would this help with future tasks beyond the current one?
2. **Is it already documented?** Search CLAUDE.md first:
   ```bash
   grep -i "[keyword]" CLAUDE.md
   ```
3. **Is it a root cause?** Don't document symptoms — document the underlying pattern.

| Type of Learning | Add to CLAUDE.md? | Where Instead? |
|------------------|-------------------|----------------|
| "Login API returns `.token` not `.access_token`" | ✅ Yes — affects all validation | Token Types section |
| "WS-A3 took longer than estimated" | ❌ No — single task | Completion report |
| "Async fixtures need `@pytest_asyncio.fixture`" | ✅ Yes — affects all tests | Common Pitfalls |
| "The Notion API changed their endpoint" | ❌ No — external/temporal | Task ticket notes |

### Phase 2: LOCATE — Find the Right Section

**Use the Read tool** to read CLAUDE.md and identify the correct section:

```
Read: CLAUDE.md
```

**Section guide:**

| Learning Category | CLAUDE.md Section |
|-------------------|-------------------|
| API behavior (tokens, endpoints, responses) | Common Pitfalls → Token Types / API Contract |
| Test infrastructure (fixtures, async, paths) | Common Pitfalls → Async Test Fixtures |
| File paths and conventions | Common Pitfalls → Backend Service File Path Conventions |
| Architecture patterns | Architecture Overview |
| Debugging shortcuts | Common Debugging |
| Development process | Development Workflow |
| Security concerns | Security Considerations |
| New tool/command usage | Development Commands |
| MCP Gateway behavior | Common Pitfalls → MCP Gateway Protocol Flow |

### Phase 3: WRITE — Add the Learning

**Use the StrReplace tool** to add the learning to the correct section. Match the existing style:

**For a new pitfall/lesson:**
```markdown
### [Descriptive Title] (CRITICAL/IMPORTANT)

**LESSON LEARNED ([Month Year]):** [What happened]

| Mistake | Fix |
|---------|-----|
| [wrong approach] | [correct approach] |
```

**For a new table row in existing section:**
```markdown
| [new error/pattern] | [cause] | [fix] |
```

**For a changelog entry:**
```markdown
| [Month Year] | [Description] | [Impact] | [Section Updated] |
```

### Phase 4: VERIFY — Confirm the Update

After modifying CLAUDE.md:

1. **Read the updated section** to verify formatting is correct
2. **Check that existing rules aren't broken** by the addition
3. **Verify the changelog** at the bottom of CLAUDE.md is updated

---

## Output Format

```markdown
## CLAUDE.md Updated ✅

### Learning Added
**Section:** [section name]
**Category:** [Pitfall / Pattern / Convention / Process]

### Content Added
```
[the new content that was added, quoted]
```

### Changelog Entry
| Date | Lesson | Impact | Section |
|------|--------|--------|---------|
| [date] | [description] | [impact] | [section] |

### Verification
- [x] Learning is generalizable (not task-specific)
- [x] Not already documented (grep confirmed)
- [x] Added to correct section
- [x] Matches existing style
- [x] Changelog updated

---

This learning will apply to all future sessions.
```

---

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "This is too small to document" | Small pitfalls cost the most time because they're easy to forget. A 1-line addition prevents 30 minutes of debugging next time. |
| "Everyone knows this" | If you just spent time debugging it, it's not obvious. Document it. |
| "CLAUDE.md is already too long" | A well-organized long file is better than a short file that misses critical rules. The agent reads the whole file every session. |
| "I'll add it later" | You'll forget the exact details. Add it now while the context is fresh. |
| "This only applies to this feature" | Ask: "Could this happen in another feature?" If yes, it's generalizable. |

## Red Flags

- Discovering the same pitfall twice (means the first occurrence wasn't documented)
- CLAUDE.md changelog hasn't been updated in weeks despite active development
- `/complete-task` reports recommending CLAUDE.md updates that are never made
- Adding learnings without checking if they already exist (creates duplicates)
- Adding vague learnings ("be careful with auth") instead of specific ones ("vault endpoints require Agent JWT, not User Token")

## Verification

Before declaring the update complete:

- [ ] Learning is specific and actionable (not vague)
- [ ] Correct section identified and used
- [ ] StrReplace successfully applied (no formatting breakage)
- [ ] Changelog table at bottom of CLAUDE.md updated with new entry
- [ ] No duplicate entries created
- [ ] Existing rules not contradicted without explicit justification

---

## Reference

This command integrates with:
- `/complete-task` → Completion reports flag recommended CLAUDE.md updates
- `/debug` → Debugging sessions often produce generalizable learnings
- `/review` → Review findings may warrant permanent rules
- Boris Cherny's "Compounding Engineering" — upstream inspiration

See also:
- `CLAUDE.md` → Lessons Learned Changelog (bottom of file)
- `CLAUDE.md` → "How to Add New Lessons" section
