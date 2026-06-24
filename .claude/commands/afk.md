# AFK: Toggle Between Interactive and Autonomous Mode

Switch between interactive (human-in-the-loop) and AFK (autonomous) operating modes. AFK mode adjusts verbosity, permissions, and hooks for unattended execution.

## Invocation

```
/afk [on|off|status]
```

**Parameters:**
- `on` — Switch to AFK mode
- `off` — Switch back to interactive mode
- `status` — Show current mode (default if no argument)

---

## Instructions

### When invoked with `on`

1. **Announce mode switch:**

       ## Switching to AFK Mode

       The following adjustments take effect for this session:

2. **Apply AFK settings:**

   | Setting | Interactive | AFK |
   |---------|------------|-----|
   | Permission mode | Conservative (ask) | Auto (allow known-safe) |
   | Output verbosity | Full explanations | Terse — results only |
   | Checkpoint frequency | After every task | After every batch |
   | Error handling | Stop and ask | Auto-retry once, then stop |
   | Notifications | None | Via `scripts/notify.sh` |

3. **Verify prerequisites exist:**

   ```bash
   [ -f "scripts/ralph.sh" ] && echo "✅ ralph.sh" || echo "❌ ralph.sh missing"
   [ -f "scripts/notify.sh" ] && echo "✅ notify.sh" || echo "❌ notify.sh missing"
   [ -f ".claude/settings.local.json" ] && echo "✅ permissions" || echo "❌ permissions missing"
   ```

4. **Set behavioral rules for the session:**
   - Do NOT ask for confirmation on file edits, bash commands, or git operations that match the allowlist in `.claude/settings.local.json`
   - Do NOT produce multi-paragraph explanations — one sentence per update
   - DO send notifications via `scripts/notify.sh` on task completion, errors, and circuit breaker events
   - DO auto-retry transient failures (network, docker restart) once before escalating
   - DO write structured completion reports for every task

5. **Output confirmation:**

       AFK mode: ON
       Permission: auto | Verbosity: terse | Notifications: enabled
       Use `/afk off` to return to interactive mode.

### When invoked with `off`

1. **Revert to interactive defaults:**
   - Restore verbose output
   - Restore conservative permission prompting
   - Disable auto-retry
   - Stop notifications

2. **Output confirmation:**

       AFK mode: OFF
       Permission: ask | Verbosity: full | Notifications: disabled

### When invoked with `status` (or no argument)

Report current mode:

    ## AFK Status

    | Setting | Current |
    |---------|---------|
    | Mode | Interactive / AFK |
    | Permission | ask / auto |
    | Verbosity | full / terse |
    | Notifications | disabled / enabled |
    | Ralph loop | not running / iteration N of M |

---

## When to Use

- Before starting an unattended Ralph loop (`./scripts/ralph.sh`)
- When you need to step away and want Claude to continue autonomously
- When returning from AFK to resume interactive work

**When NOT to use:**
- For single quick tasks — AFK overhead isn't worth it
- When you need to make design decisions — those require interactive mode

## Related Skills

- `/go` — AFK-friendly composite: verify + lint + review + ship
- `/afk-summary` — Generate comprehension report after AFK run
