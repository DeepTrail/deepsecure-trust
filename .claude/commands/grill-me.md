# Grill Me: Requirements Elicitation Before Speccing

Structured requirements interview: ask 40-80 targeted questions across 5 domains to surface assumptions, edge cases, and hidden requirements BEFORE writing a spec. Prevents the "spec describes intent, not reality" problem.

## Workflow Position

```
/grill-me → /spec → /create-design-doc → /breakdown-design → ...
    ↑
(YOU ARE HERE — Optional pre-spec step)
```

## Invocation

```
/grill-me [feature-description] [--depth shallow|medium|deep] [--domain backend|frontend|infra|all]
```

**Parameters:**
- `feature-description` — What you're building (free text or file path to a rough plan)
- `--depth` — Question depth: `shallow` (15-20 Qs), `medium` (30-40 Qs, default), `deep` (60-80 Qs)
- `--domain` — Focus area (default: `all`)

---

## Instructions

### Phase 1: Problem Domain (8-12 questions)

Surface what the feature actually solves:

1. What specific problem does this solve? (Not "it would be nice" — what breaks without it?)
2. Who experiences this problem? (Role, frequency, severity)
3. What's the current workaround? (If none exists, is the problem real?)
4. What happens if we build the wrong thing? (Cost of getting it wrong)
5. What's the simplest version that would be useful?
6. Is there an existing solution we could adapt instead of building from scratch?
7. What does "done" look like from the user's perspective?
8. What data do users need to see, and where does it come from?

**Adapt questions to context.** If the feature is infrastructure (Docker, cloud), pivot:
- What environment does this run in?
- What existing infrastructure does this interact with?
- What's the failure mode if this breaks?

### Phase 2: Scope & Constraints (10-15 questions)

Draw clear boundaries:

9. What is explicitly OUT of scope? (Force an answer — "nothing" is not acceptable)
10. What's the MVP boundary? What can wait for v2?
11. Are there performance requirements? (Latency, throughput, concurrency)
12. Are there security/compliance constraints? (Auth, encryption, audit logging)
13. What's the timeline pressure? (Affects build-vs-buy, abstraction depth)
14. How many users/requests/records will this handle initially? In 6 months?
15. What existing code will this modify vs. create from scratch?
16. Are there any hard technical constraints? (Language, framework, deployment target)
17. What dependencies does this introduce? (New packages, services, APIs)
18. What breaks if this feature is half-implemented? (Partial rollout safety)

### Phase 3: User Flows & Edge Cases (10-15 questions)

Walk through concrete scenarios:

19. Walk me through the happy path step by step.
20. What happens when the user provides invalid input?
21. What happens when an external service is down?
22. What happens on authentication failure?
23. What happens when the operation times out?
24. What happens when two users do the same thing simultaneously?
25. What happens when the data is in an unexpected state?
26. Is there an undo/rollback mechanism needed?
27. Are there rate limits or quotas to consider?
28. What notifications or feedback does the user receive at each step?

**For each answer, probe deeper:**
- "What if [edge case]?"
- "What does the error message say?"
- "Who gets notified?"

### Phase 4: Success Metrics (5-8 questions)

Define measurable outcomes:

29. How will we verify this works? (Automated tests, manual QA, both?)
30. What metrics would prove this feature is successful?
31. What would make us revert this feature?
32. Are there demo scenarios that MUST work end-to-end?
33. What's the acceptance criteria the reviewer will check?
34. Is there a performance baseline we need to meet or beat?

### Phase 5: Dependencies & Integration (5-8 questions)

Map the integration surface:

35. What other systems does this interact with?
36. What API contracts need to be defined or honored?
37. Are there data migration requirements?
38. Does this affect existing APIs (breaking changes)?
39. What monitoring/observability is needed?
40. Are there deployment prerequisites (infra, config, secrets)?

### Synthesis

After all questions are answered:

1. **Generate requirements document** at `reports/requirements-[feature].md`:

   ```markdown
   ## Requirements: [Feature Name]

   ### Problem Statement
   [Synthesized from Phase 1 answers]

   ### Scope
   **In scope:** [list]
   **Out of scope:** [list]

   ### User Flows
   [Structured from Phase 3]

   ### Edge Cases Identified
   [Numbered list from Phase 3 probing]

   ### Success Criteria
   [From Phase 4]

   ### Dependencies
   [From Phase 5]

   ### Key Decisions Needed
   [Unresolved questions flagged during interview]

   ### Recommended Next Step
   Run `/spec` with this requirements document as input.
   ```

2. **Output summary:**

       ## Grill Complete

       - Questions asked: [N]
       - Requirements captured: [M]
       - Edge cases identified: [K]
       - Open decisions: [J]
       - Report: reports/requirements-[feature].md

       Ready for: /spec [feature-name]

---

## Questioning Rules

1. **Never accept "it should just work" as an answer.** Probe: "What does 'work' mean specifically?"
2. **Force scope decisions.** If everything is "in scope," scope is undefined.
3. **Test assumptions by contradiction.** "What if we did the opposite?"
4. **Ask "why" at least twice** per domain. Requirements without reasons are wishes.
5. **Record exact quotes** where the user reveals constraints — these prevent spec drift.
6. **Batch questions** — present 3-5 at a time, not one by one. Respect the developer's time.

## When to Use

- Starting a new feature with ambiguous requirements
- Before writing a spec for a complex feature (3+ services affected)
- When translating a vague idea into actionable work
- When you suspect hidden assumptions or missing edge cases

**When NOT to use:**
- Bug fixes with clear reproduction steps
- Tasks with an existing detailed spec
- Single-file changes

## Related Skills

- `/spec` — Next step after grilling: write the formal specification
- `/create-design-doc` — Transforms spec into design doc
