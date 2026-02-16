# Update CLAUDE.md with Learning

Add a new rule, pattern, or learning to CLAUDE.md.

## Instructions

1. **Get the learning from the user:**
   - What was the mistake or inefficiency?
   - What's the correct approach?
   - Which section of CLAUDE.md should it go in?

2. **Read current CLAUDE.md** to understand existing structure and avoid duplicates

3. **Determine the appropriate section:**
   - Development Commands → new command patterns
   - Architecture Overview → structural guidance
   - Testing Strategy → test-related learnings
   - Development Workflow → process improvements
   - Task Breakdown Workflow → task management learnings
   - Security Considerations → security rules
   - Common Debugging → debugging tips
   - Or create a new section if needed

4. **Add the learning** in the appropriate format:
   - Keep it concise (1-3 lines typically)
   - Match the style of existing entries
   - Include examples if helpful

5. **Commit the change** (if requested by user)

## Output Format

```markdown
## CLAUDE.md Updated

**Section:** [section name]

**Added:**
```
[the new content that was added]
```

**Reason:** [brief explanation of why this was added]

---

This learning will now apply to all future sessions.
```

## Common Learning Categories

### Code Style
```markdown
- Prefer X over Y because Z
- Never use X, always use Y instead
- When doing X, always remember to Y
```

### Testing
```markdown
- Always test X when changing Y
- Use `pytest -k "pattern"` for Z scenarios
- Mock X instead of Y for unit tests
```

### Architecture
```markdown
- X changes require updating Y
- When modifying X, also check Z
- X and Y must stay in sync
```

### Common Mistakes
```markdown
- Don't forget to X after Y
- X won't work unless Y is done first
- Always run X before committing changes to Y
```

## Example Usage

User: "Add to CLAUDE.md that we should never use print() for debugging, always use the logger"

Then add to Development Workflow or Code Style section:
```markdown
- Never use `print()` for debugging; always use `logger.debug()` from `deepsecure._core.logging`
```

## Reference
- Based on Boris Cherny's "Compounding Engineering" approach
- Every mistake becomes a rule that prevents future mistakes
- The team contributes to CLAUDE.md continuously
