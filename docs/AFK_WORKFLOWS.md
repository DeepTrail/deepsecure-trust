# AFK (Away From Keyboard) Workflows for DeepSecure

> **Goal:** Enable developers to write a spec, walk away, and come back to passing tests and open PRs.
> This document synthesizes research from 20 industry sources into a concrete implementation plan for DeepSecure.

---

## Table of Contents

- [Research Sources](#research-sources)
- [Design Principles](#design-principles)
- [Industry Consensus: 8 Pillars of AFK Development](#industry-consensus-8-pillars-of-afk-development)
  - [1. Plan First, Execute Autonomously](#1-plan-first-execute-autonomously)
  - [2. Fresh Context Per Iteration (Ralph Wiggum Pattern)](#2-fresh-context-per-iteration-the-ralph-wiggum-pattern)
  - [3. Manual First, Automate Second](#3-manual-first-automate-second)
  - [4. Worktree Isolation for Parallelism](#4-worktree-isolation-for-parallelism)
  - [5. Permission Handling That Doesn't Block](#5-permission-handling-that-doesnt-block)
  - [6. Self-Healing (Verify, Fix, Retry)](#6-self-healing-verify-fix-retry)
  - [7. Notification When Stuck or Done](#7-notification-when-stuck-or-done)
  - [8. CLAUDE.md as Table of Contents](#8-claudemd-as-table-of-contents-not-encyclopedia)
- [DeepSecure on Shapiro's Five Levels](#where-deepsecure-sits-on-shapiros-five-levels)
- [DeepSecure as AFK Security Infrastructure](#deepsecure-as-afk-security-infrastructure-dog-fooding)
- [What DeepSecure Already Has](#what-deepsecure-already-has)
- [What's Missing for AFK](#whats-missing-for-afk)
- [Implementation Plan](#concrete-action-plan-enabling-afk-for-deepsecure)
  - [Phase 1: Low-Hanging Fruit](#phase-1-low-hanging-fruit-can-implement-today)
  - [Phase 1.5: Agent Frontmatter Upgrade](#phase-15-agent-frontmatter-upgrade)
  - [Phase 2: Ralph Wiggum Loop](#phase-2-ralph-wiggum-loop-for-deepsecure)
  - [Phase 3: Notification System](#phase-3-notification-system)
  - [Phase 3.5: AFK Permissions and Hooks](#phase-35-afk-permissions-and-hooks)
  - [Phase 4: New Skills](#phase-4-new-skills-for-afk-operation)
  - [Phase 5: CLAUDE.md Refactoring](#phase-5-claudemd-refactoring-openai-pattern)
  - [Phase 6: Parallel Orchestration](#phase-6-sandcastle-style-parallel-orchestration)
- [Priority Ranking](#priority-ranking)
- [The Contrarian Views](#the-contrarian-views)
- [Key Takeaways by Practitioner](#key-takeaways-by-practitioner)

---

## Research Sources

| # | Source | Author / Org | Key Concept | Link |
|---|--------|-------------|-------------|------|
| 1 | Managed Agents | Anthropic | Decoupled brain/hands/session architecture | [anthropic.com](https://www.anthropic.com/engineering/managed-agents) |
| 2 | Agent Harness | Cursor | Dynamic context, keep-rate metric, tool reliability tracking | [cursor.com](https://cursor.com/blog/continually-improving-agent-harness) |
| 3 | Cloud Agent Lessons | Cursor | Three-layer state decoupling, simplicity and control | [cursor.com](https://cursor.com/blog/cloud-agent-lessons) |
| 4 | Software Factory | Harvey AI | Cloud sandboxes, durable audit objects, team visibility | [lightsprint.ai](https://lightsprint.ai/blog/harvey-built-their-own-software-factory) |
| 5 | Background Agent (Inspect) | Ramp | Modal sandboxes, child sessions, multiplayer, 30% of PRs from agents | [builders.ramp.com](https://builders.ramp.com/post/why-we-built-our-background-agent) |
| 6 | Five Levels | Dan Shapiro | L0 Manual to L5 Dark Factory progression | [danshapiro.com](https://www.danshapiro.com/blog/2026/01/the-five-levels-from-spicy-autocomplete-to-the-software-factory/) |
| 7 | Harness Engineering | OpenAI | AGENTS.md as TOC, docs/ as truth, dependency layering, 1M LOC zero human-written | [openai.com](https://openai.com/index/harness-engineering/) |
| 8 | Everything is a Ralph Loop | Geoffrey Huntley | Monolithic Ralph, manual-first methodology, evolutionary software | [ghuntley.com/loop](https://ghuntley.com/loop/) |
| 9 | Claude Code Cheatsheet | awesomeclaude.ai | Hook events, headless flags, permission profiles, subagent frontmatter | [awesomeclaude.ai](https://awesomeclaude.ai/code-cheatsheet) |
| 10 | X threads | Boris Cherny (Claude Code creator) | 5 parallel Claudes in worktrees, hooks taxonomy, agent swarms | [x.com/bcherny](https://x.com/bcherny) |
| 11 | X thread | Thariq (Anthropic) | 9 skill categories, skills as folders, `/babysit-pr` | [x.com/trq212](https://x.com/trq212/status/2033949937936085378) |
| 12 | X threads | Noah Zweben (Anthropic PM) | `/autofix-pr`, Routines, `/schedule`, Monitor tool, Remote Control | [x.com/noahzweben](https://x.com/noahzweben/status/2032533699116355819) |
| 13 | X threads | Matt Pocock | Ralph Wiggum loop, Sandcastle, Grill/Spec/Slice/Ship | [x.com/mattpocockuk](https://x.com/mattpocockuk/status/2007924876548637089) |
| 14 | X threads | Dax Raad (OpenCode) | Contrarian: "agents come later", one fast agent > many slow | [x.com/thdxr](https://x.com/thdxr/status/2038969038135582990) |
| 15 | X thread | Mike Piccolo | Agent AFK: spec, research, plan, parallelize, build, verify, heal, ship | [x.com/mfpiccolo](https://x.com/mfpiccolo/status/2049139067359568032) |
| 16 | One-Person Code Factory | Ryan Carson | `prd.json` with `passes`, skills staleness, 15 simultaneous agents | [O'Reilly interview](https://www.oreilly.com/radar/ryan-carson-is-a-one-person-code-factory/) |
| 17 | Software 3.0 / Sequoia Ascent | Andrej Karpathy | "Automate what you can verify", jagged intelligence, agent-native docs | [karpathy.bearblog.dev](https://karpathy.bearblog.dev/sequoia-ascent-2026/) |
| 18 | Dark Software Factory | Deep Research Synthesis | Zero-trust AFK identity, fast-merge philosophy, sediment problem, skill engineering patterns | [Building AFK Workflows for DeepSecure](../chats/cursor_deepsecure_repository_afk_workfl.md) |
| 19 | Hermes Agent | Nous Research | Persistent self-improving autonomous agent; meta-orchestrator delegating to Claude Code/Codex/OpenCode; 6 terminal backends, built-in cron, multi-platform messaging, self-improving skills | [github.com/nousresearch/hermes-agent](https://github.com/nousresearch/hermes-agent) |
| 20 | Skill Quality Scoring | omriariav/omri-cc-stuff | Automated marketplace plugins scoring skills against multi-dimensional rubrics | [claudemarketplaces.com](https://claudemarketplaces.com/plugins/omriariav-omri-cc-stuff) |

---

## Design Principles

These foundational principles should guide all AFK decisions for DeepSecure. They come from Karpathy, Huntley, and OpenAI.

### Principle 1: Automate What You Can Verify (Karpathy)

> "Traditional software automates what you can specify. LLMs and RL automate what you can verify."

This is the classification framework for which DeepSecure tasks are AFK-safe:

| Task Type | Verifiable? | AFK Classification | Example |
|-----------|-------------|-------------------|---------|
| CRUD endpoints with tests | Yes (tests pass/fail) | Full AFK | Adding a new API endpoint with pytest coverage |
| Database migrations | Yes (migration runs, rollback works) | Full AFK with extra verification |  Schema changes with up/down migration |
| Crypto/auth code | Partially (tests exist but domain is a training valley) | HITL (human-in-the-loop) | Ed25519 challenge-response, JWT creation |
| Security architecture | No (requires judgment) | Human-only | Trust model design, permission boundaries |
| API contract design | No (requires judgment) | Human-only | New endpoint schema decisions |
| Frontend UI polish | Partially (screenshot comparison) | HITL | Visual verification needed |

**For DeepSecure specifically:** The crypto/auth code is in what Karpathy calls a "jagged intelligence" valley -- less training data than standard CRUD, so models spike on common patterns but struggle on domain-specific security code. AFK agents on auth tasks need extra verification compared to standard endpoints.

### Principle 2: Outsource Thinking, Never Understanding (Karpathy)

AFK workflows automate *implementation*, not *architecture*. Humans retain ownership of:
- Security boundaries and trust model
- API design and contract decisions
- Cryptographic protocol choices
- Service boundary definitions

The plan must be human-owned. Execution can be agent-owned.

### Principle 3: Ralph is Monolithic (Huntley)

> "Consider what microservices would look like if the microservices (agents) themselves are non-deterministic -- a red hot mess."

Single process. Single task. Single repo. The Ralph loop is deliberately simple:
- One agent per iteration
- One task per iteration
- Fresh context each time
- File-based memory (git commits), not context-based memory

Multi-agent coordination adds non-determinism on top of non-determinism. Use it only for truly independent workstreams (e.g., control plane + gateway that don't share schemas).

### Principle 4: Agent Legibility Over Human Taste (OpenAI)

Code produced by AFK agents should be optimized first for the agent's ability to reason about it in future iterations. This means:
- Clear, explicit naming over clever abstractions
- Flat structures over deep nesting
- Verbose but unambiguous over concise but contextual
- Standard patterns over custom idioms

This doesn't mean ugly code -- it means code that reads well in a 200k-token context window.

### Principle 5: Agent-Native Documentation (Karpathy + OpenAI)

> "Context window is the new program." -- Karpathy

Documentation should be optimized for agent consumption:
- Structured, machine-parseable formats (YAML frontmatter, explicit headers)
- Progressive disclosure: agents start with a small, stable entry point (CLAUDE.md) and are taught where to look next
- Everything that matters lives in-repo as versioned artifacts -- "anything it can't access in-context while running effectively doesn't exist"
- Cross-linked documentation mechanically enforced through linters and CI

### Principle 6: Failure is the Curriculum (Huntley + Boris)

> "Every caught mistake becomes future prevention." -- Boris Cherny

The **"watch the loop" methodology**: developer learning comes from observing loop failures, then fixing the failure domain so it never recurs.

```
AFK loop iteration fails
  -> Developer observes failure
  -> Identifies root cause
  -> Fixes CLAUDE.md / skills / hooks
  -> That class of failure never happens again
  -> Loop quality compounds over time
```

This is the mechanism by which AFK quality improves. Each failure produces a permanent fix encoded into the repo. Document failures in `.afk/learnings.md` (see Phase 2).

### Principle 7: Application Legibility (OpenAI)

> "If an agent cannot 'see' the application, it cannot verify its own work."

The runtime state, application interfaces, logs, and metrics must be directly queryable by the agent. For DeepSecure this means:
- Health check endpoints (`/health`) on both control plane and gateway
- Structured logging queryable by agents (not just human-readable)
- `docker compose logs` accessible from within AFK scripts
- Test output parseable by the agent (JSON format preferred)
- Database state queryable via standard tools (`psql`, `redis-cli`)

Without legibility, an agent can generate code but has no way to verify it works in the running system.

### Principle 8: Taste Encoded as Rules (OpenAI)

> "Subjective architectural preferences cause non-deterministic behavior in agents. Preferences must be codified into strict linters and automated policies."

The agent should self-correct *mechanically*, not *probabilistically*. Every style preference that would require human review must become an automated check:
- Code formatting: `ruff format` + `isort` via PostToolUse hook (not relying on the agent to remember)
- Import ordering: enforced by `isort`, not by CLAUDE.md instructions
- Naming conventions: enforced by custom linters, not by prose rules
- Architecture boundaries: enforced by structural tests (e.g., "gateway cannot import control plane modules")
- File size limits: enforced by linters, not by judgment

**For DeepSecure:** The `app/` prefix convention, `*_service.py` naming, and dependency layering documented in CLAUDE.md should become mechanical checks, not prose rules.

### Principle 9: Managing Entropy (OpenAI)

> "High-velocity AI output generates digital garbage and unnecessary complexity over time."

AFK agents generate code at unprecedented velocity. Without active cleanup, the repo collapses under entropy:
- **Golden principles**: Core invariants (e.g., "all endpoints require auth", "all services have health checks") enforced by structural tests
- **Automated garbage collection**: Recurring background agents scan for deviations from golden principles and open targeted refactoring PRs
- **Dead code detection**: Agents remove unused imports, unreachable code, orphaned test fixtures
- **Complexity budgets**: Monitor cyclomatic complexity per module, flag when thresholds exceeded

This is not optional at scale -- OpenAI found that without entropy management, agent-generated repos become unmaintainable within weeks.

### Principle 10: The Capability Architect (OpenAI + Shapiro)

> "Engineers must abandon writing implementation details and instead serve as 'capability architects,' designing the environments and feedback loops in which agents operate."

At L4 and above, the human role shifts from "writes code" or "reviews diffs" to:
- Designing skill directories and their gotchas files
- Configuring permission profiles and hook pipelines
- Building verification infrastructure (tests, linters, structural checks)
- Maintaining the golden principles and entropy GC routines
- Evaluating and improving the AFK loop's success rate

The output of a capability architect is not code -- it's the **environment** in which agents produce code.

---

## Industry Consensus: 8 Pillars of AFK Development

### 1. Plan First, Execute Autonomously

Every successful AFK setup front-loads planning and specification. The agent doesn't wing it.

| Practitioner | Planning Approach |
|-------------|-------------------|
| Boris Cherny | Plan mode (Shift+Tab x2), iterate until plan is solid, then one-shot the implementation |
| Matt Pocock | `/grill-me` (40-80 questions) then PRD then vertical tracer bullets then ship |
| Mike Piccolo (Agent AFK) | spec, research, plan, parallelize, build, verify, heal, ship |
| OpenAI | Structured `docs/` directory, design specs as agent input, 3.5 PRs/engineer/day |
| Ryan Carson | `prd.json` with explicit `passes: true/false` per story, machine-parseable |
| DeepSecure (today) | `/run-plan` then `/breakdown-design` then `/create-workstream` then `/run-batch` |

**Why it matters:** Without a clear plan, AFK agents drift, hallucinate file paths, and produce code that doesn't integrate. The plan is the contract between human intent and autonomous execution.

**Boris's key insight:** "Pour energy into the plan. Once the plan is good, Claude will one-shot the implementation almost every time."

**Matt's evolution:** He initially used Plan mode but shifted to `/grill-me` -- a skill that forces the agent to ask 40-80 questions before generating anything. "The whole point of planning is to get on the same wavelength with the LLM, not to generate an asset you don't read."

**Carson's `prd.json` format:** Machine-parseable completion tracking with `passes: true/false` per story, plus an append-only `progress.txt` for learnings. The boolean makes completion detection trivial for scripts.

---

### 2. Fresh Context Per Iteration (The Ralph Wiggum Pattern)

Run the agent in a `while true` loop, each iteration starting with a clean context window.

**How it works:**
1. A bash loop repeatedly invokes `claude` with a prompt file
2. Each iteration: agent reads a PRD + progress file, finds the next unchecked task, implements it, commits, updates progress
3. Fresh context window each iteration -- avoids context pollution from long sessions
4. Originally by Geoffrey Huntley; Ryan Carson built the [snarktank/ralph](https://github.com/snarktank/ralph/) repo (17k stars); Matt Pocock popularized and refined the workflow

```bash
# The core Ralph pattern (simplified)
while true; do
  claude --print \
    --output-format json \
    --prompt-file ralph-prompt.md \
    --allowedTools "Edit,Write,Bash(git:*),Bash(pytest:*)" \
    --max-turns 50
done
```

**Why fresh context matters — The Sediment Problem:** Long-running single sessions accumulate stale context, outdated file contents, and compaction artifacts — what the Dark Software Factory paper calls the **Sediment Problem**. After ~100k tokens, compacted context becomes increasingly unreliable: the agent may reference deleted files, use outdated API signatures, or repeat already-completed work. Each fresh Ralph iteration sees the codebase as it actually is right now because it starts clean.

**The Smart Zone (~0–100k tokens):** Agent performance peaks in this range. Beyond it, compaction artifacts and stale references cause quality degradation that compounds with each additional compaction cycle. Matt Pocock's rule: "Keep LLM context under ~100k tokens; clear and restart rather than compact to avoid sediment degrading quality." The Ralph pattern enforces the Smart Zone structurally — each iteration is a fresh context window that never exceeds it.

**Matt's HITL-to-AFK graduation:**
> "I had a full day of HITL Ralph yesterday, watching it like a hawk and improving my prompt. Today has been almost all AFK, leaving it for long periods and coming back to good code."

**Key constraints from Matt's experience:**
- Cap iterations (5-10 for small tasks, 30-50 for larger ones) -- infinite loops with stochastic systems are dangerous
- Block commits unless tests pass
- Build end-to-end vertical tracer bullets, not layer by layer
- Bias toward small tasks for AFK, slightly larger for HITL

**The deliberate simplicity is the feature** (community consensus):
```
loop:
  1. Launch fresh agent (clean context)
  2. Point at repo + structured task file
  3. Execute single scoped unit of work
  4. Run verification (tests, lint, typecheck)
  5. Commit if successful
  6. Record progress
  7. Exit -> restart loop
```

Each task has explicit acceptance criteria. `passes: false` -> `passes: true` only when criteria are satisfied.

---

### 3. Manual First, Automate Second

Geoffrey Huntley's critical methodology insight: **do the loop manually first with Ctrl+C pauses before automating**.

> "Ralph is about getting the most out of how the underlying models work through context engineering."

**The progression:**

| Stage | What You Do | Why |
|-------|-------------|-----|
| 1. Manual single-task | Run `afk-once.sh`, watch output, Ctrl+C if off-track | Learn the failure domains |
| 2. Manual loop | Run Ralph manually, pause between iterations, review each commit | Build intuition for what works |
| 3. Supervised AFK | Run Ralph unattended but check every 30 min | Verify the loop is stable |
| 4. Full AFK | Run Ralph and walk away | Confidence earned through stages 1-3 |

**Why this matters for DeepSecure:** The repo has complex auth flows, dual-service architecture, and security-critical code. Jumping straight to full AFK without understanding how the agent handles these domains will produce silent failures. Start with manual single-task execution to learn where the agent struggles (crypto code, token types, service boundaries) before automating.

---

### 4. Worktree Isolation for Parallelism

Boris Cherny calls this "the single biggest productivity unlock." Run 3-5 git worktrees, each with its own Claude session, working on different tasks simultaneously.

**Boris's workflow:**
- 5 Claude instances in parallel in iTerm2 tabs, numbered 1-5
- Uses iTerm2 system notifications to know when a Claude needs input
- While one agent runs tests, another refactors, a third drafts docs
- Also runs 5-10 Claudes on claude.ai in browser simultaneously
- Ships 20-30 PRs per day (normal), peaked at 150 PRs/day as an experiment
- Runs "hundreds of agents at any given moment, thousands more doing overnight work"
- His key human skill: "It's not about deep work, it's about how good I am at context switching and jumping across multiple different contexts very quickly."

**Noah Zweben's fire-and-forget pattern:**
```bash
claude --worktree --tmux
# Spin up an autonomous Claude on its own worktree, in its own terminal.
# Fire and forget. Come back to a PR.
```

**Matt Pocock's Sandcastle framework:**
- Single `sandcastle.run()` TypeScript call
- Creates a git worktree per agent (isolation primitive)
- Each agent runs inside a Docker container (sandbox)
- Docker bind-mounts the worktree (no file sync needed)
- **Staged orchestration pattern:** Planner -> Implementer -> Reviewer -> Merger
- **Branch strategies:** `head`, `merge-to-head`, `branch`
- `createWorktree()` API for lifecycle management
- Agent commits land on dedicated branches, then merge back
- Result: "889 commits, none of them hand-coded"

**Key detail:** Some people name worktrees and set up shell aliases (`za`, `zb`, `zc`) to hop between them in one keystroke. Others have a dedicated "analysis" worktree only for reading logs and running queries.

**Lock mechanisms for shared resources:** When multiple worktree agents run in parallel, they may contend on shared resources: a single PostgreSQL instance, Redis, Docker ports, or the same test database. Use file-based locks or port allocation to prevent collisions:

```bash
# File-based lock for shared database access
LOCK="/tmp/deepsecure-db-${SVC}.lock"
exec 200>"$LOCK"
flock -n 200 || { echo "Resource locked by another agent. Waiting..."; flock 200; }
# ... run migration or test ...
```

For DeepSecure, allocate distinct port ranges per worktree (e.g., worktree 1 → 8000/8002, worktree 2 → 8010/8012) via `.env` overrides in each worktree.

**Tmux-based headless pattern:** Instead of bare `&` backgrounding, map each worktree to a named tmux session for persistent, observable, and recoverable agent execution:

```bash
# Spawn N agents in named tmux sessions (one per worktree)
for i in 1 2 3; do
  tmux new-session -d -s "agent-$i" \
    "cd /path/to/worktree-$i && claude --print --prompt-file ralph-prompt.md --max-turns 80"
done

# Observe any agent: tmux attach -t agent-2
# List all agents: tmux list-sessions
# Kill one agent:  tmux kill-session -t agent-3
```

Tmux sessions survive terminal disconnection, can be observed in real-time, and integrate cleanly with Noah Zweben's `claude --worktree --tmux` flag. This is strictly superior to `&` backgrounding for AFK workloads.

---

### 5. Permission Handling That Doesn't Block

AFK operation breaks down completely when the agent hits a permission prompt and waits forever for human input. This is the single biggest blocker for going AFK.

| Approach | Who Uses It | How It Works |
|----------|-------------|--------------|
| `/permissions` allowlist | Boris Cherny | Pre-approve safe commands so they never prompt |
| `PermissionRequest` hook to Slack | Boris Cherny | Route risky prompts to phone for approval while AFK |
| Auto-approve via Opus 4.5 hook | Boris Cherny | Hook sends permission request to a model that scans for attacks and auto-approves safe ones |
| Permission bubbling | Agent AFK (Piccolo) | Nested subagents forward permission requests up to parent/user |
| `--permission-mode auto` | Claude Code headless flag | Auto-approve in headless/AFK scripts (use with allowlist) |
| `--dangerously-skip-permissions` | (not recommended) | Boris explicitly does NOT use this -- use allowlists instead |

**Boris's philosophy:** "I don't use `--dangerously-skip-permissions`. Instead, use `/permissions` to pre-allow specific safe commands. Fewer interruptions while keeping guardrails."

**The auto-approve pattern (advanced):**
A `PermissionRequest` hook that sends the command to a fast model (Claude Haiku or Opus 4.5) which evaluates whether it's safe. If safe, auto-approve. If risky, forward to Slack for human review.

**The `/afk` toggle pattern (OpenCode's `opencode-afk` plugin):**
A single command that flips the agent into AFK mode and back in <100ms. Instead of manually reconfiguring permissions each time you leave, `/afk` toggles a boolean state:

```
/afk on   → Loads AFK permission profile, enables auto-approve, starts notification hooks
/afk off  → Restores interactive permission profile, disables auto-approve
/afk      → Toggles current state (shortcut)
```

For DeepSecure, implement as a Claude Code command skill that writes to `.afk/state.json` (`{"mode": "afk" | "interactive"}`). Hook scripts read this state to decide behavior (e.g., auto-approve in AFK mode, prompt in interactive mode). See [Phase 3.5](#phase-35-afk-permissions-and-hooks) for the permission profile details.

**AFK Security Profile (from Claude Code Cheatsheet):**
A distinct permission profile that allows development tools but explicitly denies secrets access and network exfiltration. See [Phase 3.5](#phase-35-afk-permissions-and-hooks) for the full template.

---

### 6. Self-Healing (Verify, Fix, Retry)

AFK agents must handle failures without human intervention. If tests fail, the agent should diagnose and fix, not stop and wait.

| Pattern | Source | Description |
|---------|--------|-------------|
| `verify -> heal -> ship` | Agent AFK (Piccolo) | If verification fails, automatically diagnose and fix before shipping |
| `/autofix-pr` | Noah Zweben (Anthropic) | Cloud agent autonomously fixes CI failures and addresses review comments |
| `/babysit-pr` | Thariq (Anthropic) | Monitors PR: retries flaky CI, resolves conflicts, enables auto-merge |
| Block commits unless tests pass | Matt Pocock | The agent can't declare victory if tests are red |
| `Stop` hook ("keep going") | Boris Cherny | Nudges Claude to continue if work remains |
| TDD enforcement | Prior pipeline analysis | Red-green-refactor cycle built into task execution |
| Anti-rationalization tables | Addy Osmani pattern | Prevent agent from rationalizing shortcuts during AFK |
| Golden principles + GC | OpenAI | Recurring background tasks scan for deviations and open refactoring PRs |

**Noah Zweben's /autofix-pr lifecycle:**
1. Developer finishes a PR locally
2. Runs `/autofix-pr` -- entire session (conversation, edits, reasoning) ships to the cloud
3. The autofixer autonomously fixes CI failures and addresses review comments
4. Developer walks away and comes back to a green PR

**Thariq's /babysit-pr skill:**
- Monitors PR after creation
- Retries flaky CI runs
- Resolves merge conflicts
- Enables auto-merge when all checks pass
- You literally walk away after opening the PR

**OpenAI's agent-to-agent review:**
Over time, almost all review becomes agent-to-agent. The Ralph Wiggum loop at OpenAI: agent writes code, reviews its own changes, requests additional agent reviews, responds to feedback, iterates until all agent reviewers are satisfied, then merges. Humans may review but aren't required. This is where AFK matures toward L5 (Dark Factory).

**Huntley's "Evolutionary Software" (Loom concept):**
The most advanced self-healing: the loop identifies a problem, studies the codebase, fixes it, deploys it, verifies it worked -- automatically. This is L5 Dark Factory aspiration. Relevant as a long-term target for DeepSecure.

**Fast-merge philosophy:** When agent throughput exceeds human review capacity, traditional blocking merge gates (mandatory human approval, long CI pipelines) become the bottleneck. The fast-merge approach inverts the model:

| Traditional | Fast-Merge (AFK) |
|-------------|------------------|
| Block merge until human approves | Merge after automated checks pass |
| Long CI pipeline (30+ min) | Fast CI (< 5 min) + post-merge verification |
| Revert is exceptional | Automated rollback is routine |
| Large PRs | Small incremental PRs (easier to verify, easier to revert) |

**Blast radius limiting** supports fast-merge by ensuring any bad merge has minimal impact:
- **Small incremental PRs:** Each PR touches one concern, making automated verification more reliable and rollback trivial
- **Feature flags:** New behavior behind flags allows merge without activation
- **Anomaly detection:** Post-merge monitoring triggers automatic rollback on error-rate spikes
- **Lineage records:** Every agent-generated PR records its source task, prompt, and verification results for audit trail

**The Day Shift / Night Shift pattern:** A formal separation of human and agent operating modes:
- **Day Shift (human):** Planning, architecture, spec writing, reviewing blocked items, updating CLAUDE.md/skills based on overnight learnings
- **Night Shift (agent):** Autonomous execution of the Ralph loop, PR babysitting, CI fixing, doc gardening
- The handoff artifact is the RALPH_PROGRESS.md file — humans update it during the day, agents consume and update it overnight

This maps to Shapiro's L4: "You write a spec. You argue with it about the spec. You craft skills... Then you leave for 12 hours."

**Anti-rationalization tables (Osmani pattern):**
During AFK execution, agents may rationalize skipping steps (e.g., "tests aren't needed for this small change"). Anti-rationalization tables are explicit rules embedded in skills that list common rationalizations and why they're wrong:

```markdown
## Anti-Rationalization Table
| Agent Might Say | Why It's Wrong | Do This Instead |
|----------------|----------------|-----------------|
| "Tests aren't needed for this change" | Every change needs tests in this repo | Write at least one test |
| "I'll fix the lint errors later" | Later never comes in AFK | Fix before committing |
| "This import cycle is fine" | Import cycles break the build | Refactor to eliminate |
```

---

### 7. Notification When Stuck or Done

You can't be AFK if you don't know when to come back.

| Method | Who Uses It | Pros | Cons |
|--------|------------|------|------|
| iTerm2 system notifications | Boris Cherny | Built-in, zero setup | macOS only, must be at laptop |
| Telegram messages | Agent AFK (Piccolo) | True mobile AFK | Extra service dependency |
| Slack bot with custom emojis | Ramp Inspect | Team-wide visibility | Requires webhook setup |
| Monitor tool (event-driven) | Noah Zweben (Anthropic) | Token-efficient, real-time | Claude Code specific |
| macOS `osascript` notifications | Common pattern | Simple, built-in | macOS only |
| Remote Control | Noah Zweben | Start local, continue from phone | Requires claude.ai account |

**The Monitor tool (Noah Zweben):** Claude can spawn a background watcher script. Every line of stdout streams back as a real-time event. Claude reacts immediately. Massive token saver because it replaces polling loops. Use cases: follow logs for errors, poll PR statuses, watch directory changes, monitor dev servers.

**Noah's Remote Control:** Start local sessions from the terminal, then continue them from your phone via the Claude iOS app. Combined with Boris's "Teleport" (`&` command or `--teleport` flag), this means you can kick off AFK work on your machine and monitor/approve from your phone.

---

### 8. CLAUDE.md as Table of Contents, Not Encyclopedia

OpenAI keeps their AGENTS.md to ~100 lines, pointing to structured docs/. Matt Pocock recommends moving code standards to `CODE_STANDARDS.md` and running them through a reviewer agent on PRs instead of bloating the implementation context.

**OpenAI's approach:**
- AGENTS.md is the "table of contents" (~100 lines)
- `docs/` directory is the "system of record"
- Cross-linked documentation mechanically enforced through linters and CI
- **Progressive disclosure:** agents start with a small, stable entry point and are taught where to look next
- Agents load what they need, when they need it

**OpenAI's key metric:** ~1,500 PRs merged, 3.5 PRs/engineer/day, ~1M lines of code, zero manually-written. With 6+ hour autonomous runs.

**Matt Pocock's token optimization:**
> "Want to put something in CLAUDE.md? Stick it in CODE_STANDARDS.md instead. Then pass it to a reviewer agent that runs on every PR. Save tokens during implementation, spend them during review."

**Boris Cherny on CLAUDE.md as compounding engineering:**
> "Every project needs a CLAUDE.md checked into git. When Claude gets something wrong, fix it, then ask Claude to update CLAUDE.md so it never happens again. Every caught mistake becomes future prevention."

The tension: CLAUDE.md should compound learnings, but it shouldn't grow unbounded. The solution is the OpenAI pattern -- keep the root file slim and pointer-rich, with detailed rules in referenced files that agents load on demand.

**Skill engineering discipline:** Skills are not throwaway markdown files — they are engineered artifacts with quality requirements:

| Skill Engineering Practice | Why It Matters |
|---------------------------|----------------|
| **Mandatory `gotchas.md` per skill directory** | Domain-specific pitfalls the agent would otherwise rediscover each run (e.g., Ed25519 gotchas for crypto skills) |
| **Run logging/telemetry in every skill execution** | Track success rates, failure modes, execution time — feeds back into skill improvement |
| **Semantic deduplication before task execution** | Before an agent starts a task, check if identical or substantially similar work exists — prevents redundant effort |
| **Structured constraints (tables over prose)** | Tables are mechanically parseable; prose rules are ambiguous. Prefer `| Constraint | Value |` over "you should try to..." |
| **Skill quality scoring via marketplace plugins** | Automated rubrics scoring skills on dimensions: completeness, error handling, anti-rationalization coverage, gotchas depth |

```
.claude/skills/
├── code-review-and-quality/
│   ├── skill.md              # Main skill instructions
│   ├── gotchas.md            # Domain-specific pitfalls
│   ├── anti-rationalization.md  # Common shortcuts to block
│   └── telemetry.sh          # Run logging script
├── run-tests/
│   ├── skill.md
│   ├── gotchas.md
│   └── pytest-patterns.md    # Reference patterns
└── deploy/
    ├── skill.md
    ├── gotchas.md
    └── rollback-runbook.md
```

**Ryan Carson's skills decay warning:**
> "Skills decay. A Next.js skill from six months ago may conflict with your current component library. He'd gladly pay for a system that audits his skills library, flags conflicts, and surfaces what's gone stale."

This applies to DeepSecure's CLAUDE.md and skills -- they need a staleness audit mechanism (see `doc-gardener` agent in Phase 4).

---

## Where DeepSecure Sits on Shapiro's Five Levels

Dan Shapiro's framework maps organizations from "spicy autocomplete" (L0) to "dark factory" (L5):

| Level | Name | Description | DeepSecure Status |
|-------|------|-------------|-------------------|
| L0 | Manual | Human-controlled, minimal AI | Past this |
| L1 | Assisted Tasks | Delegating discrete tasks (tests, docs) | Past this |
| L2 | Collaborative Pairing | AI as junior colleague, flow state | Past this |
| **L3** | **Human-in-Loop Manager** | **Developer becomes code reviewer. "Your life is diffs."** | **Current state** |
| L4 | Asynchronous Autonomy | Write spec, walk away, check tests in 12 hours | **Target** |
| L5 | Dark Factory | Fully autonomous, "humans neither needed nor welcome" | Future aspiration |

**Current state (L3):** DeepSecure has a sophisticated pipeline (`/run-plan` then `/breakdown-design` then `/run-batch` then `/execute-task`), but each step requires human invocation. The human is managing, not coding, but still present.

**Target (L4):** Write a design doc, invoke a single command, and walk away. The system plans, decomposes, executes in parallel, self-heals on test failures, and notifies when done or stuck. Shapiro describes L4: "You write a spec. You argue with it about the spec. You craft skills... Then you leave for 12 hours, and check to see if the tests pass."

**L3 to L4 gap:** Automated orchestration + self-healing + notification. The planning infrastructure is there; the autonomous execution loop is not.

**L5 aspiration (Huntley's Loom):** The loop identifies problems, studies the codebase, fixes them, deploys, and verifies -- automatically. Combined with OpenAI's agent-to-agent review where humans aren't required, this is the "dark factory" where specs go in and software comes out.

---

## DeepSecure as AFK Security Infrastructure (Dog-Fooding)

DeepSecure's product — Identity-as-Code for AI agents — is precisely the security infrastructure that AFK agent swarms need. This creates a unique dog-fooding opportunity: use DeepSecure to secure DeepSecure's own AFK development.

### The Problem with Static Credentials in AFK

When multiple agents run in parallel across worktrees, they need access to shared services (databases, APIs, Docker registries, CI systems). The naive approach — static API keys in `.env` files — creates security risks:

- Agents running with overly broad credentials (violates least-privilege)
- Shared secrets across worktrees (one compromised agent exposes all)
- No audit trail of which agent accessed what
- No credential rotation during long AFK sessions
- No way to revoke a single agent's access without affecting others

### Zero-Trust AFK Identity

Replace static API keys in AFK sandboxes with DeepSecure's own Ed25519 identity system:

| Static Credentials (Current) | Zero-Trust AFK (Target) |
|------------------------------|------------------------|
| Shared `.env` per worktree | Per-agent Ed25519 keypair |
| No expiration | TTL-scoped `delegation_tokens` |
| Manual revocation | Automatic expiry + instant revocation |
| No audit trail | Immutable audit log per agent action |
| Same permissions for all agents | Scoped permissions per agent role |

### Implementation Pattern

```
Orchestrator (scripts/ralph.sh or scripts/parallel-build.sh)
  │
  ├── Generates Ed25519 keypair per worktree agent
  ├── Requests delegation_token from DeepSecure Control Plane
  │     scope: ["repo:read", "test:execute", "docker:build"]
  │     ttl: 3600  (1 hour, auto-renew on heartbeat)
  │     agent_id: "ralph-worktree-1"
  │
  ├── Injects identity into worktree environment
  │     DEEPSECURE_AGENT_ID=ralph-worktree-1
  │     DEEPSECURE_AGENT_KEY=/tmp/agent-1.key
  │     DEEPSECURE_DELEGATION_TOKEN=<token>
  │
  └── Agent authenticates to shared services via delegation_token
        (not static API keys)
```

### Why This Matters

1. **Least privilege:** Each agent gets only the permissions it needs for its specific task
2. **Temporal scoping:** Credentials expire after the AFK session ends
3. **Audit trail:** Every agent action is traceable to a specific delegation chain
4. **Blast radius:** A compromised agent's credentials are limited in scope and time
5. **Dog-fooding:** Every AFK session stress-tests DeepSecure's own product

### Hermes Agent as the Ideal Dog-Food Target

Hermes Agent (see [Phase 6](#hermes-agent-as-orchestration-layer)) is the perfect test harness for DeepSecure's product because it naturally creates **every security problem DeepSecure is designed to solve**: persistent agents with broad credentials, long-lived tokens, delegated authority, unaudited tool access, parallel agents, and remote execution.

**Without DeepSecure controls:**
```
Hermes Agent (dangerous)
  └── has broad GitHub token (read + write + admin)
  └── has Docker access (full daemon)
  └── has Slack webhook (can post anything)
  └── runs forever (no credential expiry)
  └── no audit trail of what it did or why
```

**With DeepSecure controls:**
```
Hermes Orchestrator
  └── requests delegation_token from DeepSecure Control Plane
        scope: [repo:read, pr:create, ci:retry]
        ttl: 1 hour
        agent_id: hermes-orchestrator-1

  Worker Agent (spawned by Hermes)
    └── receives attenuated token (subset of orchestrator's scope)
          scope: [repo:read, file:write:deeptrail-gateway/*]
          ttl: 30 minutes
    └── cannot escalate permissions
    └── all actions fully audited
    └── token auto-revoked on session end
```

This tests DeepSecure's core primitives under real conditions:
- **Execution-scoped authorization:** Tokens valid only for the current AFK session
- **Delegation chains:** Orchestrator → worker attenuation works correctly
- **Runtime governance:** Agents cannot exceed their granted scope
- **Auditability:** Every tool invocation traceable to a delegation chain
- **Revocation:** Kill one agent's access without affecting others
- **Bounded blast radius:** A compromised worker can't escalate to orchestrator-level access

The insight is not that Hermes is "the best coding framework" — it's that Hermes naturally creates the exact security/control problems DeepSecure is designed to solve, making it the highest-value internal deployment target.

---

## What DeepSecure Already Has

The repo has significant infrastructure for agent-assisted development:

| Category | What Exists | Status |
|----------|-------------|--------|
| **CLAUDE.md** | Comprehensive project guidance (~800+ lines) | Strong but too large (encyclopedia, not TOC) |
| **Skills** | `code-review-and-quality`, `run-tests` | 2 of 9 recommended categories |
| **Command Skills** | `pipeline`, `run-plan`, `breakdown-design`, `execute-task`, `run-batch`, `complete-task`, `verify-batch-completion`, `commit-push-pr`, `ship`, `debug`, `explore-codebase`, `create-workstream`, `create-batch-execution-plan`, `create-task-ticket`, `create-task-spec`, `create-design-doc`, `run-checks`, `review`, `security-audit`, `setup-worktrees`, `sync-worktree-status`, `update-claude-md`, `spec` | Extensive pipeline (23 commands) |
| **Agents** | `code-reviewer`, `security-auditor`, `test-engineer` | 3 agents, but plain markdown (no YAML frontmatter) |
| **Hooks** | `afterFileEdit`, `beforeShellExecution`, `stop` | Basic set -- missing 6+ AFK-critical hook types |
| **Worktree Guide** | `docs/WORKTREE_GUIDE.md` | Documented but manual |
| **Parallel Guide** | `docs/PARALLEL_EXECUTION_GUIDE.md` | Documented but manual |
| **Pipeline System** | Full plan-to-ship lifecycle with pre-flight checks | Solid L3 infrastructure |
| **Permissions** | Partial allowlist in `settings.local.json` | Incomplete, no AFK-specific security profile |

---

## What's Missing for AFK

| # | Gap | Impact | Reference Pattern |
|---|-----|--------|-------------------|
| 1 | No Ralph Wiggum loop | Can't iterate autonomously with fresh context | Matt Pocock, Huntley, Carson |
| 2 | No `afk-once.sh` (manual single-task) | Can't learn failure domains before automating | Huntley |
| 3 | No permission auto-approval for AFK | Agent stalls on every non-allowlisted command | Boris Cherny |
| 4 | No AFK-specific security profile | Broad allowlist risks secrets/network exposure | Claude Code Cheatsheet |
| 5 | No notification system | Don't know when agent is stuck or done | All practitioners |
| 6 | No `PostCompact` hook | Context loss during long sessions | Boris Cherny |
| 7 | No `PostToolUse` auto-format hook | CI failures from formatting issues | Boris Cherny |
| 8 | Missing hook events | No `SubagentStop`, `PreCompact`, `SessionEnd`, `afterTaskComplete` | Claude Code Cheatsheet |
| 9 | No `/babysit-pr` skill | PRs require manual CI babysitting | Thariq (Anthropic) |
| 10 | No `/autofix-pr` skill | CI failures and review comments require manual fixing | Noah Zweben (Anthropic) |
| 11 | No `/grill-me` skill | Specs may be underspecified before implementation | Matt Pocock |
| 12 | No `/verify-app` subagent | No end-to-end testing subagent | Boris Cherny |
| 13 | No `doc-gardener` agent | Skills and docs accumulate staleness without audit | Ryan Carson |
| 14 | No `ci-fixer` agent | CI failure diagnosis requires manual intervention | Prior pipeline analysis |
| 15 | No context engineering skill | No guidance on compaction, context feeding, MCP | Prior pipeline analysis |
| 16 | No automated worktree spawning | Parallel execution requires manual setup | Sandcastle (Matt Pocock) |
| 17 | CLAUDE.md too large | Excess token cost on every session, context pollution | OpenAI pattern |
| 18 | No `CODE_STANDARDS.md` split | Standards enforced during implementation (expensive) instead of review (cheap) | Matt Pocock |
| 19 | No Monitor tool usage | Not leveraging event-driven monitoring | Noah Zweben |
| 20 | Skills are markdown files only | Missing scripts, gotchas, assets in skill folders | Thariq's 9-category framework |
| 21 | Agent definitions lack YAML frontmatter | No `tools:`, `model:`, `isolation:` fields | Claude Code Cheatsheet |
| 22 | No model override in commands | Can't specify Opus for planning, Sonnet for implementation | Claude Code Cheatsheet |
| 23 | No `.afk/learnings.md` | AFK failures not systematically captured | Huntley |
| 24 | No TDD enforcement in `/execute-task` | Tasks don't enforce red-green-refactor cycle | Prior pipeline analysis |
| 25 | No anti-rationalization tables | Agents can rationalize skipping steps during AFK | Osmani pattern |
| 26 | No `/loop` command integration | Can't run cron-style repeating tasks | Boris Cherny |
| 27 | No `/schedule` integration | Can't schedule cloud-based recurring tasks | Noah Zweben |
| 28 | No agent-to-agent review pipeline | Human review still required for all PRs | OpenAI |
| 29 | No golden principles GC | No automated tech debt scanning | OpenAI |
| 30 | No machine-parseable completion tracking | Using markdown checklists instead of `passes: true/false` | Carson |
| 31 | No zero-trust AFK identity | Agents use static credentials, not scoped delegation_tokens | DeepSecure dog-fooding |
| 32 | No `/afk` toggle command | Switching AFK mode requires manual reconfiguration | OpenCode `opencode-afk` |
| 33 | No fast-merge policy | All PRs blocked on human review, bottleneck at scale | Dark Factory synthesis |
| 34 | No vulnerability scanning hook | Security issues can be committed during AFK | Bandit + safety integration |
| 35 | No keepalive mechanism | Long AFK sessions may be killed by idle timeouts | Tmux watchdog, session_keepalive |
| 36 | No skill `gotchas.md` files | Agents rediscover domain pitfalls on every run | Skill engineering discipline |
| 37 | No semantic deduplication | Agents may redo already-completed work | Pre-execution task matching |
| 38 | No skill quality scoring | No way to measure or improve skill effectiveness | Marketplace plugin rubrics |

---

## Concrete Action Plan: Enabling AFK for DeepSecure

### Phase 1: Low-Hanging Fruit (Can Implement Today)

#### 1a. Permission Allowlisting

Expand `settings.local.json` to cover all safe development commands so AFK sessions don't stall on routine operations:

```json
{
  "permissions": {
    "allow": [
      "Bash(git:*)",
      "Bash(make:*)",
      "Bash(docker:*)",
      "Bash(docker compose:*)",
      "Bash(grep:*)",
      "Bash(ruff:*)",
      "Bash(black:*)",
      "Bash(isort:*)",
      "Bash(mypy:*)",
      "Bash(pytest:*)",
      "Bash(python:*)",
      "Bash(python3:*)",
      "Bash(pip:*)",
      "Bash(curl:*)",
      "Bash(gh:*)",
      "Bash(find:*)",
      "Bash(ls:*)",
      "Bash(cat:*)",
      "Bash(echo:*)",
      "Bash(wc:*)",
      "Bash(sort:*)",
      "Bash(head:*)",
      "Bash(tail:*)",
      "Bash(xargs:*)",
      "Bash(jq:*)",
      "Edit",
      "Write",
      "Read",
      "WebSearch",
      "WebFetch(domain:*)"
    ]
  }
}
```

**Effort:** 30 minutes | **Impact:** High -- unblocks all AFK work

#### 1b. Stop Hook Enhancement

Update the stop hook to nudge Claude to continue if tasks remain, preventing premature stopping (Boris Cherny's pattern):

```bash
#!/bin/bash
# .cursor/hooks/on-task-stop.sh (enhanced)

# Check if there are remaining tasks in any active workstream
for status_file in docs/workstreams/*/STATUS.md; do
  if [ -f "$status_file" ]; then
    REMAINING=$(grep -c "^|.*|.*Pending\||.*In Progress" "$status_file" 2>/dev/null || echo 0)
    if [ "$REMAINING" -gt 0 ]; then
      WORKSTREAM=$(dirname "$status_file" | xargs basename)
      echo "NOTICE: $REMAINING tasks still pending in workstream '$WORKSTREAM'. Consider continuing."
    fi
  fi
done

# Check Ralph progress if active
for progress_file in docs/workstreams/*/RALPH_PROGRESS.md; do
  if [ -f "$progress_file" ]; then
    REMAINING=$(grep -c "^- \[ \]" "$progress_file" 2>/dev/null || echo 0)
    if [ "$REMAINING" -gt 0 ]; then
      echo "NOTICE: $REMAINING Ralph tasks remaining. Don't stop yet."
    fi
  fi
done
```

**Effort:** 30 minutes | **Impact:** High -- prevents premature agent stopping

#### 1c. PostToolUse Auto-Format Hook

Auto-format Python files after every edit, eliminating CI formatting failures (Boris's top hook recommendation):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": {
          "tool_name": "Edit|Write"
        },
        "command": "FILE_PATH=$(echo $TOOL_INPUT | jq -r '.file_path // empty'); if [ -n \"$FILE_PATH\" ] && echo \"$FILE_PATH\" | grep -q '\\.py$'; then ruff format --quiet \"$FILE_PATH\" 2>/dev/null; isort --quiet \"$FILE_PATH\" 2>/dev/null; fi"
      }
    ]
  }
}
```

**Effort:** 1 hour | **Impact:** Medium -- eliminates a class of CI failures

#### 1d. PostCompact Context Recovery Hook

Re-inject critical context after Claude compresses its context window. This prevents "amnesia" during long AFK sessions:

```json
{
  "hooks": {
    "PostCompact": [
      {
        "command": "cat .claude/compact-recovery.md 2>/dev/null || true"
      }
    ]
  }
}
```

Create `.claude/compact-recovery.md` with the absolute minimum critical rules:
- Token type usage (User Token vs Agent JWT vs Internal Token)
- File path conventions (`app/` prefix for backend services)
- Test organization rules
- Current task context pointer
- Anti-rationalization reminders

**Effort:** 1 hour | **Impact:** Medium -- prevents context loss in long sessions

#### 1e. SessionStart Hook

Load recent context at the beginning of every session (Boris's pattern):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "command": "echo '--- Recent commits ---'; git log --oneline -5 2>/dev/null; echo '--- Branch ---'; git branch --show-current 2>/dev/null; echo '--- Open PRs ---'; gh pr list --limit 3 2>/dev/null || true"
      }
    ]
  }
}
```

The `SessionStart` hook has a `source` field: `"startup"`, `"resume"`, `"clear"`, or `"compact"`. Use this to vary behavior (e.g., load more context on startup, less on resume).

**Effort:** 30 minutes | **Impact:** Medium -- agents start with situational awareness

---

### Phase 1.5: Agent Frontmatter Upgrade

The 3 existing agents (`code-reviewer`, `test-engineer`, `security-auditor`) are plain markdown files. They need proper Claude Code subagent YAML frontmatter with `name:`, `description:`, `tools:`, `model:`, `isolation:` fields (per the Claude Code Cheatsheet format).

#### Before (current):

```markdown
# Code Reviewer Agent
You are a code reviewer for the DeepSecure project...
```

#### After (upgraded):

```markdown
---
name: code-reviewer
description: Reviews code changes for correctness, security, and style compliance
model: sonnet
tools:
  - Read
  - Bash(git:*)
  - Bash(ruff:*)
  - Bash(grep:*)
  - WebSearch
---

# Code Reviewer Agent

## Anti-Rationalization Table
| Agent Might Say | Why It's Wrong | Do This Instead |
|----------------|----------------|-----------------|
| "This change is too small to review" | Small changes cause big bugs | Review every change |
| "The tests pass so it's fine" | Tests don't catch all issues | Review logic, not just test results |
| "I'll note this for later" | Later never comes | Flag it now |

You are a code reviewer for the DeepSecure project...
```

#### Model Selection Strategy

| Agent Role | Recommended Model | Rationale |
|-----------|-------------------|-----------|
| Planning / architecture | `opus` | Needs deep reasoning for design decisions |
| Code review | `sonnet` | Good balance of speed and quality for diffs |
| Implementation / task execution | `sonnet` | Fast iteration, good enough for scoped tasks |
| Security audit | `opus` | Security requires thorough reasoning |
| Test generation | `sonnet` | Formulaic enough for fast model |
| Doc gardening | `haiku` | Simple comparison tasks, high volume |

**Files to update:**
- `.claude/agents/code-reviewer.md`
- `.claude/agents/security-auditor.md`
- `.claude/agents/test-engineer.md`

**Effort:** 2 hours | **Impact:** Medium -- agents get correct tool access and model selection

---

### Phase 2: Ralph Wiggum Loop for DeepSecure

The Ralph Wiggum pattern is the core engine for AFK execution. Each iteration gets a fresh context window, reads progress, implements the next task, and commits.

#### Step 2a: Manual Single-Task Script (Start Here)

Per Huntley's "manual first" principle, start with a single-iteration script before the full loop:

```bash
#!/bin/bash
# scripts/afk-once.sh - Single AFK task execution (manual stepping stone)
# Usage: ./scripts/afk-once.sh <workstream-name>
#
# Run this manually first. Watch the output. Learn the failure domains.
# Only move to ralph.sh after you've done 5-10 successful afk-once runs.

set -euo pipefail

WORKSTREAM=${1:?"Usage: afk-once.sh <workstream-name>"}
PROGRESS_FILE="docs/workstreams/$WORKSTREAM/RALPH_PROGRESS.md"
PROMPT_FILE="docs/workstreams/$WORKSTREAM/ralph-prompt.md"

if [ ! -f "$PROGRESS_FILE" ]; then
  echo "ERROR: $PROGRESS_FILE not found."
  exit 1
fi

REMAINING=$(grep -c "^- \[ \]" "$PROGRESS_FILE" 2>/dev/null || echo 0)
echo "Tasks remaining: $REMAINING"
echo "Running single iteration..."
echo ""

claude --print \
  --output-format json \
  --prompt-file "$PROMPT_FILE" \
  --allowedTools "Edit,Write,Read,Bash(git:*),Bash(pytest:*),Bash(make:*),Bash(ruff:*),Bash(python:*),Bash(mypy:*),Bash(black:*),Bash(isort:*),Bash(find:*),Bash(grep:*),Bash(ls:*),Bash(cat:*)" \
  --max-turns 80 \
  --append-system-prompt "Read $PROGRESS_FILE. Find the FIRST unchecked task (line starting with '- [ ]'). Implement it fully. Run tests to verify. If tests pass, git add and commit. Then update $PROGRESS_FILE: change '- [ ]' to '- [x]' for the completed task. If tests fail after 3 attempts, add '(BLOCKED: <reason>)' to the task line."

echo ""
echo "=== Iteration complete ==="
echo "Review the changes: git log -1 --stat"
echo "Check progress: cat $PROGRESS_FILE"
echo ""
echo "Satisfied? Run again, or graduate to: ./scripts/ralph.sh $WORKSTREAM"
```

#### Step 2b: Full Ralph Loop Script

Only use this after you've done 5-10 successful `afk-once.sh` runs:

```bash
#!/bin/bash
# scripts/ralph.sh - AFK batch executor for DeepSecure
# Usage: ./scripts/ralph.sh <workstream-name> [max-iterations]
#
# Prerequisites:
#   - Workstream must exist in docs/workstreams/<name>/
#   - RALPH_PROGRESS.md must exist with task checklist
#   - Tests must be runnable via `make test` or `pytest`
#   - You have done 5+ successful afk-once.sh runs first

set -euo pipefail

WORKSTREAM=${1:?"Usage: ralph.sh <workstream-name> [max-iterations]"}
MAX_ITERATIONS=${2:-10}
PROGRESS_FILE="docs/workstreams/$WORKSTREAM/RALPH_PROGRESS.md"
PROMPT_FILE="docs/workstreams/$WORKSTREAM/ralph-prompt.md"
LOG_DIR="docs/workstreams/$WORKSTREAM/ralph-logs"
LEARNINGS_FILE=".afk/learnings.md"

# Validate prerequisites
if [ ! -f "$PROGRESS_FILE" ]; then
  echo "ERROR: $PROGRESS_FILE not found. Create it with a task checklist first."
  exit 1
fi

if [ ! -f "$PROMPT_FILE" ]; then
  echo "ERROR: $PROMPT_FILE not found. Create the Ralph prompt first."
  exit 1
fi

mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$LEARNINGS_FILE")"
touch "$LEARNINGS_FILE"

echo "=== Ralph Wiggum Loop ==="
echo "Workstream: $WORKSTREAM"
echo "Max iterations: $MAX_ITERATIONS"
echo "Progress file: $PROGRESS_FILE"
echo "Learnings: $LEARNINGS_FILE"
echo "Started: $(date)"
echo ""

FAILURES=0

for i in $(seq 1 $MAX_ITERATIONS); do
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  LOG_FILE="$LOG_DIR/iteration_${i}_${TIMESTAMP}.log"

  echo "--- Iteration $i/$MAX_ITERATIONS ($(date)) ---"

  # Check if all tasks complete before starting
  if ! grep -q "^- \[ \]" "$PROGRESS_FILE" 2>/dev/null; then
    echo "All tasks complete! Stopping."
    scripts/notify.sh "Ralph [$WORKSTREAM]" "ALL TASKS COMPLETE! Run finished." "urgent" 2>/dev/null || \
      osascript -e 'display notification "All tasks complete!" with title "Ralph Finished" sound name "Glass"' 2>/dev/null || true
    break
  fi

  # Count remaining tasks
  REMAINING=$(grep -c "^- \[ \]" "$PROGRESS_FILE" 2>/dev/null || echo 0)
  echo "Tasks remaining: $REMAINING"

  # Run Claude with fresh context
  if claude --print \
    --output-format json \
    --prompt-file "$PROMPT_FILE" \
    --allowedTools "Edit,Write,Read,Bash(git:*),Bash(pytest:*),Bash(make:*),Bash(ruff:*),Bash(python:*),Bash(mypy:*),Bash(black:*),Bash(isort:*),Bash(find:*),Bash(grep:*),Bash(ls:*),Bash(cat:*)" \
    --max-turns 80 \
    --append-system-prompt "Read $PROGRESS_FILE. Find the FIRST unchecked task (line starting with '- [ ]'). Implement it fully. Run tests to verify. If tests pass, git add and commit with a descriptive message. Then update $PROGRESS_FILE: change '- [ ]' to '- [x]' for the completed task. If tests fail after 3 attempts, add '(BLOCKED: <reason>)' to the task line and move to the next task." \
    2>&1 | tee "$LOG_FILE"; then
    FAILURES=0
  else
    FAILURES=$((FAILURES + 1))
    echo "$(date): Iteration $i failed (consecutive failures: $FAILURES)" >> "$LEARNINGS_FILE"
    if [ "$FAILURES" -ge 3 ]; then
      echo "3 consecutive failures. Stopping and notifying."
      scripts/notify.sh "Ralph [$WORKSTREAM]" "STOPPED: 3 consecutive failures. Check $LEARNINGS_FILE" "urgent" 2>/dev/null || true
      break
    fi
  fi

  # Notify progress
  scripts/notify.sh "Ralph [$WORKSTREAM]" "Iteration $i done. $REMAINING tasks remaining." 2>/dev/null || true

  echo "Iteration $i complete. Sleeping 5 seconds before next iteration..."
  sleep 5
done

echo ""
echo "=== Ralph Loop Complete ==="
echo "Finished: $(date)"
echo "Check progress: cat $PROGRESS_FILE"
echo "Check learnings: cat $LEARNINGS_FILE"

# Final notification
COMPLETED=$(grep -c "^- \[x\]" "$PROGRESS_FILE" 2>/dev/null || echo 0)
REMAINING=$(grep -c "^- \[ \]" "$PROGRESS_FILE" 2>/dev/null || echo 0)
BLOCKED=$(grep -c "BLOCKED" "$PROGRESS_FILE" 2>/dev/null || echo 0)
scripts/notify.sh "Ralph Finished ($WORKSTREAM)" "Done: $COMPLETED, Remaining: $REMAINING, Blocked: $BLOCKED" "urgent" 2>/dev/null || \
  osascript -e "display notification \"Done: $COMPLETED, Left: $REMAINING, Blocked: $BLOCKED\" with title \"Ralph Finished\" sound name \"Glass\"" 2>/dev/null || true
```

#### Step 2c: Learnings File

Create `.afk/learnings.md` to capture failures systematically:

```markdown
# AFK Learnings

Failures observed during AFK loop execution. Each entry should lead to a
fix in CLAUDE.md, skills, or hooks so the failure class never recurs.

## Template
```
### YYYY-MM-DD: <short description>
**Symptom:** What went wrong
**Root cause:** Why it went wrong
**Fix applied:** What was changed (CLAUDE.md rule, hook, skill update)
**Prevents:** What class of failure this fix prevents
```

## Entries
(Populated by developers observing AFK loop failures)
```

#### Ralph Prompt Template

Create `docs/workstreams/<name>/ralph-prompt.md` for each workstream:

```markdown
# Ralph Prompt: <Workstream Name>

You are implementing tasks for the DeepSecure <workstream> workstream.

## Context
- Project: DeepSecure -- Identity-as-Code for AI agents
- Read CLAUDE.md for project conventions
- Read docs/workstreams/<name>/RALPH_PROGRESS.md for the task list

## Your Mission
1. Read RALPH_PROGRESS.md
2. Find the FIRST unchecked task (line starting with `- [ ]`)
3. Read the linked task ticket if one exists
4. Implement the task fully using TDD:
   a. Write a failing test first (red)
   b. Implement the minimum code to pass (green)
   c. Refactor if needed
5. Run `pytest` on affected tests
6. Run `ruff check` on modified files
7. If all checks pass: `git add` changed files and `git commit`
8. Update RALPH_PROGRESS.md: change `- [ ]` to `- [x]`
9. If tests fail after 3 fix attempts: add `(BLOCKED: <reason>)` to the task line

## Anti-Rationalization Table
| You Might Think | Why It's Wrong | Do This Instead |
|----------------|----------------|-----------------|
| "Tests aren't needed for this change" | Every change needs tests in this repo | Write at least one test |
| "I'll fix the lint errors later" | Later never comes in AFK mode | Fix before committing |
| "This is close enough" | Close enough fails in CI | Match the spec exactly |
| "I can skip the TDD cycle for this" | TDD is mandatory, not optional | Red-green-refactor every time |

## Rules
- One task per iteration (you will be re-invoked for the next task)
- Do not modify tasks you are not currently implementing
- Always run tests before committing
- Never commit with failing tests
- Follow the existing code patterns in the codebase
- Follow TDD: write test first, then implementation
```

#### Ralph Progress File Template

Create `docs/workstreams/<name>/RALPH_PROGRESS.md`:

```markdown
# Ralph Progress: <Workstream Name>

## Tasks
- [ ] Task 1: <description> (see WS-A1 ticket) | passes: false
- [ ] Task 2: <description> (see WS-A2 ticket) | passes: false
- [ ] Task 3: <description> (see WS-B1 ticket) | passes: false
- [ ] Task 4: <description> (see WS-B2 ticket) | passes: false

## Blocked Tasks
(Tasks that failed after 3 attempts are moved here with their error notes)

## Completed
(Summary of what was accomplished, updated by the agent)
```

**Effort:** 3 hours | **Impact:** Very High -- core AFK execution engine with manual stepping stone

---

### Phase 3: Notification System

#### 3a. Unified Notification Script

```bash
#!/bin/bash
# scripts/notify.sh - Unified notification sender
TITLE=${1:-"DeepSecure"}
MESSAGE=${2:-"Agent needs attention"}
URGENCY=${3:-"normal"}  # normal, urgent

# macOS notification
osascript -e "display notification \"$MESSAGE\" with title \"$TITLE\" sound name \"Glass\"" 2>/dev/null || true

# Slack webhook (if configured)
if [ -n "$DEEPSECURE_SLACK_WEBHOOK" ]; then
  EMOJI=":robot_face:"
  [ "$URGENCY" = "urgent" ] && EMOJI=":rotating_light:"
  curl -s -X POST "$DEEPSECURE_SLACK_WEBHOOK" \
    -H 'Content-Type: application/json' \
    -d "{\"text\": \"$EMOJI *$TITLE*: $MESSAGE\"}" > /dev/null 2>&1
fi
```

#### 3b. Slack Webhook Setup

```bash
# Set in .env or shell profile
export DEEPSECURE_SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

#### 3c. PermissionRequest Hook (Route to Slack for AFK Approval)

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "command": "scripts/notify.sh 'Permission Request' 'Claude needs: $TOOL_NAME -- $DESCRIPTION' urgent"
      }
    ]
  }
}
```

#### 3d. Integration with Ralph Loop

Already integrated into the `ralph.sh` script in Phase 2 -- sends notifications on iteration completion, all-tasks-done, and consecutive failures.

**Effort:** 2 hours | **Impact:** High -- enables true AFK (away from machine)

---

### Phase 3.5: AFK Permissions and Hooks

#### AFK Security Permission Profile

A distinct profile for AFK mode that allows development tools but explicitly denies secrets access and network exfiltration:

```json
{
  "permissions": {
    "allow": [
      "Bash(git:*)",
      "Bash(make:*)",
      "Bash(docker compose:*)",
      "Bash(grep:*)",
      "Bash(ruff:*)",
      "Bash(black:*)",
      "Bash(isort:*)",
      "Bash(mypy:*)",
      "Bash(pytest:*)",
      "Bash(python:*)",
      "Bash(python3:*)",
      "Bash(pip:*)",
      "Bash(gh:*)",
      "Bash(find:*)",
      "Bash(ls:*)",
      "Bash(cat:*)",
      "Bash(echo:*)",
      "Bash(wc:*)",
      "Bash(sort:*)",
      "Bash(head:*)",
      "Bash(tail:*)",
      "Bash(xargs:*)",
      "Bash(jq:*)",
      "Edit",
      "Write",
      "Read"
    ],
    "deny": [
      "Bash(curl:* --upload-file *)",
      "Bash(scp:*)",
      "Bash(rsync:*)",
      "Bash(cat ~/.ssh/*)",
      "Bash(cat */.env*)",
      "Bash(cat */credentials*)",
      "Bash(cat */secrets*)",
      "Bash(rm -rf:*)",
      "Bash(git push --force:*)"
    ]
  }
}
```

**Key difference from Phase 1a:** Phase 1a is a broad allowlist for interactive use. This AFK profile adds explicit denials for dangerous operations that an unsupervised agent should never do.

#### Additional Hook Events

Expand hooks beyond Phase 1 to cover AFK-critical events:

```json
{
  "version": 1,
  "hooks": {
    "PostToolUse": [
      {
        "matcher": { "tool_name": "Edit|Write" },
        "command": "FILE_PATH=$(echo $TOOL_INPUT | jq -r '.file_path // empty'); if [ -n \"$FILE_PATH\" ] && echo \"$FILE_PATH\" | grep -q '\\.py$'; then ruff format --quiet \"$FILE_PATH\" 2>/dev/null; isort --quiet \"$FILE_PATH\" 2>/dev/null; fi"
      }
    ],
    "PostCompact": [
      {
        "command": "cat .claude/compact-recovery.md 2>/dev/null || true"
      }
    ],
    "PreCompact": [
      {
        "command": "echo 'CONTEXT COMPACTING: saving state snapshot'; git stash list 2>/dev/null | head -3"
      }
    ],
    "Stop": [
      {
        "command": ".cursor/hooks/on-task-stop.sh"
      }
    ],
    "PermissionRequest": [
      {
        "command": "scripts/notify.sh 'Permission Request' \"Claude needs: $TOOL_NAME\" urgent"
      }
    ],
    "SessionStart": [
      {
        "command": "echo '--- Recent commits ---'; git log --oneline -5 2>/dev/null; echo '--- Branch ---'; git branch --show-current 2>/dev/null; echo '--- Open PRs ---'; gh pr list --limit 3 2>/dev/null || true"
      }
    ],
    "SessionEnd": [
      {
        "command": "scripts/notify.sh 'Session Ended' 'Claude Code session finished on branch: $(git branch --show-current 2>/dev/null)'"
      }
    ],
    "SubagentStop": [
      {
        "command": "echo 'Subagent completed: $SUBAGENT_NAME'"
      }
    ]
  }
}
```

**Effort:** 2 hours | **Impact:** High -- comprehensive AFK safety net and event tracking

---

### Phase 4: New Skills for AFK Operation

Based on Thariq's 9-category skill framework, Boris's patterns, and gaps identified in research:

#### Skill: `/babysit-pr` (Deployment & Workflow category)

Monitors a PR through its lifecycle, retrying flaky CI runs, resolving merge conflicts, and enabling auto-merge when green. Designed to work with Boris's `/loop` command for continuous monitoring.

```markdown
---
name: babysit-pr
description: Monitor a PR through CI, review, and merge lifecycle
model: sonnet
tools:
  - Bash(gh:*)
  - Bash(git:*)
  - Read
  - Monitor
---

# Babysit PR

## Purpose
Monitor a PR through its full lifecycle until it's merged or needs human intervention.

## Anti-Rationalization Table
| Agent Might Say | Why It's Wrong | Do This Instead |
|----------------|----------------|-----------------|
| "CI is just flaky, ignore it" | Flaky CI masks real failures | Re-run once, then investigate |
| "The merge conflict is trivial" | Trivial conflicts can corrupt logic | Resolve carefully, run tests after |
| "Auto-merge is safe now" | Only if ALL checks pass | Verify every check before enabling |

## Workflow
1. Get PR number from user or detect from current branch
2. Check PR status: CI checks, review status, merge conflicts
3. If CI is flaky (failed then passed on re-run history): trigger re-run via `gh run rerun`
4. If merge conflicts exist: attempt automatic resolution, run tests after
5. If reviews are approved and CI is green: enable auto-merge via `gh pr merge --auto`
6. If stuck for >30 minutes: notify via scripts/notify.sh
7. Loop until merged or human intervention needed (use Monitor tool for event-driven waiting)

## Integration with /loop
Can be invoked as: `/loop 5m /babysit-pr 123`
```

#### Skill: `/autofix-pr` (Code Quality category)

```markdown
---
name: autofix-pr
description: Autonomously fix CI failures and address review comments on a PR
model: sonnet
tools:
  - Edit
  - Write
  - Read
  - Bash(git:*)
  - Bash(gh:*)
  - Bash(pytest:*)
  - Bash(ruff:*)
  - Bash(make:*)
---

# Auto-Fix PR

## Purpose
Take an existing PR and autonomously fix CI failures and address review comments.

## Anti-Rationalization Table
| Agent Might Say | Why It's Wrong | Do This Instead |
|----------------|----------------|-----------------|
| "This review comment is wrong" | Reviewer may have context you don't | Implement it, note disagreement in commit msg |
| "Fixing this will break something else" | That's why we run tests after | Fix it and run full test suite |
| "This CI failure is unrelated" | Prove it by reading the log | Read the full failure log first |

## Workflow
1. Get PR number and fetch current status
2. Read CI failure logs: `gh pr checks <number>`
3. Read review comments: `gh api repos/{owner}/{repo}/pulls/{number}/comments`
4. For each CI failure:
   a. Identify the failing test or lint error
   b. Read the relevant source code
   c. Fix the issue
   d. Run the test locally to verify
   e. Commit with message referencing the CI failure
5. For each review comment:
   a. Read the comment and surrounding code context
   b. Implement the requested change
   c. Commit with message referencing the review
6. Push all fixes
7. Notify when done

## Rules
- Never force-push
- Each fix gets its own commit with clear message
- If a fix is ambiguous, skip it and notify for human review
- Run full test suite before pushing
```

#### Skill: `/grill-me` (Workflow Automation category)

```markdown
---
name: grill-me
description: Interview user relentlessly about a feature before generating any code or plan
model: opus
tools:
  - Read
  - Bash(find:*)
  - Bash(grep:*)
---

# Grill Me

## Purpose
Interview the user relentlessly about every aspect of a feature before generating any code or plan. Based on Matt Pocock's methodology of reaching shared understanding through 40-80 questions.

## Workflow
1. Read the user's initial description
2. Ask questions in these categories (minimum 5 questions per category):
   - Scope: What's in? What's explicitly out?
   - Users: Who uses this? What's their current workflow?
   - Data: What data flows in/out? What's the schema?
   - Edge cases: What happens when X fails? What about empty state?
   - Security: What are the auth requirements? What can go wrong?
   - Integration: How does this connect to existing systems?
   - Testing: How will we know it works? What are the acceptance criteria?
3. After exhausting questions, summarize the shared understanding
4. Ask: "Is this understanding complete and correct?"
5. Only then generate a PRD or design doc

## Rules
- NEVER generate code during this skill
- NEVER generate a plan during this skill
- Ask follow-up questions on every answer
- Challenge vague answers: "What specifically do you mean by X?"
- Minimum 20 questions before summarizing
```

#### Skill: `/verify-app` (Product Verification category)

```markdown
---
name: verify-app
description: End-to-end verification that a feature works in the running DeepSecure stack
model: sonnet
tools:
  - Read
  - Bash(curl:*)
  - Bash(docker:*)
  - Bash(docker compose:*)
  - Bash(python:*)
  - Bash(python3:*)
---

# Verify App

## Purpose
Verify that a feature or fix actually works end-to-end in the running DeepSecure stack.

## Workflow
1. Ensure backend services are running: `docker compose ps`
2. If not running: `docker compose up -d`
3. Wait for health checks:
   - `curl http://localhost:8000/health` (Control plane)
   - `curl http://localhost:8002/health` (Gateway)
4. Execute the verification scenario:
   a. Create test user and login (get User Token)
   b. Register test agent (get Agent JWT via challenge-response)
   c. Execute the feature being verified
   d. Assert expected outcomes
5. Capture results and report

## Token Type Reference
- User Token: POST /api/v1/auth/login -> .token (NOT .access_token)
- Agent JWT: challenge-response flow (see CLAUDE.md)
- Internal Token: From docker-compose.yml env var

## MCP Gateway Requirement
Always call `initialize` before `tools/call` on the Gateway.
```

#### Agent: `doc-gardener` (Infrastructure Operations category)

Audits skills, CLAUDE.md, and documentation for staleness. Addresses Carson's "skills decay" problem.

```markdown
---
name: doc-gardener
description: Audits skills, CLAUDE.md, and docs for staleness and conflicts
model: haiku
tools:
  - Read
  - Bash(git:*)
  - Bash(grep:*)
  - Bash(find:*)
---

# Doc Gardener

## Purpose
Periodically audit the repo's agent infrastructure for staleness, conflicts, and drift.

## Checks
1. **Skills staleness**: Compare skill instructions against current codebase
   - Do referenced file paths still exist?
   - Do referenced commands still work?
   - Do referenced APIs still have the same signatures?
2. **CLAUDE.md drift**: Compare documented patterns against actual code
   - Are "Lessons Learned" entries still relevant?
   - Do documented ports/URLs match docker-compose.yml?
3. **Agent frontmatter**: Verify all agents have YAML frontmatter
4. **Hook validity**: Verify all hook scripts exist and are executable
5. **Dead references**: Find broken links in docs/

## Output
Markdown report listing:
- Stale items (with suggested updates)
- Conflicts found
- Items verified as current

## Scheduling
Run via: `/loop 24h /doc-gardener` or as a weekly cron routine
```

#### Skill: `/context-engineering` (Data & Monitoring category)

Guidance on managing context for long-running and AFK sessions.

```markdown
---
name: context-engineering
description: Manage context window efficiently for long-running and AFK sessions
model: sonnet
tools:
  - Read
  - Bash(wc:*)
---

# Context Engineering

## When to Use
- Before starting a long AFK session
- When context window is >80% full
- After compaction produces unexpected behavior

## Rules
1. **Keep context under 100k tokens** -- clear and restart rather than compact
2. **Use files, not context, for memory** -- write state to disk, read it back next iteration
3. **Progressive disclosure** -- start with CLAUDE.md, load detailed docs only when needed
4. **MCP for external data** -- use MCP tools for databases, APIs, monitoring instead of dumping data into context

## Compaction Strategy
- PostCompact hook re-injects critical rules from .claude/compact-recovery.md
- If quality degrades after compaction, exit and restart with fresh context
- For Ralph loops: each iteration is naturally a fresh context (no compaction needed)

## Context Budget
| Content Type | Token Budget | Notes |
|-------------|-------------|-------|
| CLAUDE.md | ~2k (after refactoring) | Currently ~8k -- too large |
| Task context | ~5k | Current task ticket + acceptance criteria |
| Code context | ~30k | Files being modified |
| Test output | ~5k | Recent test results |
| Reserve | ~58k | For agent reasoning |
| **Total** | **~100k** | Stay under this |
```

#### Skill: `/identity-management` (Infrastructure Operations category)

Integrates with DeepSecure's own Control Plane for AFK agent identity provisioning. Part of the dog-fooding strategy (see [DeepSecure as AFK Security Infrastructure](#deepsecure-as-afk-security-infrastructure-dog-fooding)).

```markdown
---
name: identity-management
description: Provision and manage Ed25519 identities and delegation_tokens for AFK agent swarms
model: sonnet
tools:
  - Bash(curl:*)
  - Bash(python:*)
  - Bash(python3:*)
  - Read
  - Write
---

# Identity Management

## Purpose
Provision ephemeral identities for AFK agents using DeepSecure's own identity system.

## Workflow
1. Generate Ed25519 keypair for the new agent/worktree
2. Register agent with Control Plane (POST /api/v1/agents/)
3. Create delegation with scoped permissions (POST /api/v1/auth/delegate)
4. Inject credentials into worktree environment (.env)
5. Verify identity works (challenge-response flow)
6. Set up credential rotation for long-running sessions

## Gotchas
- See .claude/skills/identity-management/gotchas.md
- Login API returns `.token` not `.access_token`
- Agent JWT requires full challenge-response flow (not just a token swap)
- delegation_tokens have TTL -- set renewal before expiry
```

#### Skill: `/security-scan` (Code Quality category)

Forces vulnerability scanning on Python diffs before git commit during AFK execution.

```markdown
---
name: security-scan
description: Run security scans on modified Python files before committing
model: sonnet
tools:
  - Bash(git:*)
  - Bash(bandit:*)
  - Bash(safety:*)
  - Bash(ruff:*)
  - Read
---

# Security Scan

## Purpose
Prevent AFK agents from committing code with known security vulnerabilities.

## Workflow
1. Get list of modified Python files: `git diff --name-only --cached -- '*.py'`
2. Run bandit on modified files: `bandit -f json <files>`
3. Check for high/critical severity findings
4. If found: block commit, report findings, attempt auto-fix
5. If clean: allow commit to proceed

## Integration
Add as a PreToolUse hook matching `Bash(git commit:*)` to enforce on every commit:
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": { "tool_name": "Bash", "command": "git commit*" },
      "command": "scripts/security-scan.sh"
    }]
  }
}
```

## Anti-Rationalization Table
| Agent Might Say | Why It's Wrong | Do This Instead |
|----------------|----------------|-----------------|
| "Bandit is too noisy" | Filter by severity, don't skip | Use `-ll` for high-severity only |
| "This finding is a false positive" | Prove it with a `# nosec` + comment | Add targeted suppression, not blanket skip |
| "Security scan is slow" | 2-3 seconds per file is acceptable | Run only on changed files, not full repo |
```

#### Ed25519 Gotchas File

Create `.claude/skills/identity-management/gotchas.md`:

```markdown
# Ed25519 Gotchas for AFK Agents

## Critical Pitfalls
| Pitfall | What Goes Wrong | Prevention |
|---------|----------------|------------|
| Using `nacl.signing.SigningKey.generate()` without seeding | Non-reproducible keys | Always store keys to disk after generation |
| Base64 vs hex encoding mismatch | Signature verification fails silently | Control Plane expects base64 public keys |
| Challenge replay | Old challenges are rejected | Always request fresh challenge before signing |
| Token field naming | Login returns `token`, verify returns `access_token` | Check the endpoint-specific field name |
| Private key in env var | Leaked via `ps` or `/proc` | Use keyring or file with 0600 permissions |
```

**Effort:** 4 hours per skill/agent (40 hours total for 10 items) | **Impact:** High

---

### Phase 5: CLAUDE.md Refactoring (OpenAI Pattern)

Split the current ~800-line CLAUDE.md into a slim root file with pointers to detailed references, following OpenAI's progressive disclosure pattern.

#### Target Structure

```
CLAUDE.md                              (~100 lines, TOC + critical rules only)
CODE_STANDARDS.md                      (enforced by reviewer agent on PRs, not during implementation)
.claude/compact-recovery.md            (re-injected after compaction)
.afk/learnings.md                      (AFK loop failure log -- see Phase 2c)
docs/
  DEVELOPMENT_COMMANDS.md              (extracted: setup, test, lint, build commands)
  ARCHITECTURE.md                      (extracted: module structure, patterns)
  TESTING_STRATEGY.md                  (extracted: test org, markers, fixtures)
  TOKEN_TYPES.md                       (extracted: critical auth gotchas)
  LESSONS_LEARNED.md                   (extracted: pitfalls, anti-patterns)
  TASK_WORKFLOW.md                     (extracted: breakdown, ticket structure)
  BACKEND_CONVENTIONS.md               (extracted: file paths, naming)
  AFK_WORKFLOWS.md                     (this document)
```

#### Slim CLAUDE.md Template

```markdown
# CLAUDE.md

## Project
DeepSecure: Identity-as-Code for AI agents. Python CLI/SDK + backend services.

## Quick Reference
- Install: `make install-dev`
- Test: `pytest` | `make test-cov`
- Lint: `ruff check .` | `mypy deepsecure/`
- Format: `black .` | `isort .`
- All checks: `make check-all`

## Critical Rules
1. Always run `make check-all` before declaring done
2. Use correct token types (see docs/TOKEN_TYPES.md)
3. Verify file paths exist before documenting them
4. Never commit secrets or private keys
5. Login API returns `.token` not `.access_token`
6. MCP Gateway requires `initialize` before `tools/call`

## Architecture (read docs/ARCHITECTURE.md for details)
- `deepsecure/_core/`: Internal implementation
- `deepsecure/`: Public API layer
- `deeptrail-control/`: Control plane (port 8000)
- `deeptrail-gateway/`: Data plane (port 8002)

## Detailed References
| Topic | File |
|-------|------|
| Development commands | docs/DEVELOPMENT_COMMANDS.md |
| Architecture & patterns | docs/ARCHITECTURE.md |
| Testing strategy | docs/TESTING_STRATEGY.md |
| Token types & auth | docs/TOKEN_TYPES.md |
| Lessons learned | docs/LESSONS_LEARNED.md |
| Task workflow | docs/TASK_WORKFLOW.md |
| Backend conventions | docs/BACKEND_CONVENTIONS.md |
| Code standards | CODE_STANDARDS.md |
| AFK workflows | docs/AFK_WORKFLOWS.md |
```

#### CODE_STANDARDS.md Pattern

Move code quality rules out of CLAUDE.md into a separate file used only by the reviewer agent:

```markdown
# CODE_STANDARDS.md
# This file is consumed by the code-review skill, NOT during implementation.
# Saves tokens during coding, spends them during review.

## DRY Violations
Flag any function >10 lines that appears in substantially similar form elsewhere.

## Error Handling
Every external API call must have explicit error handling.
Every database query must handle connection failures.

## Security
No raw SQL queries -- use parameterized queries only.
No hardcoded secrets -- use environment variables or vault.
JWT tokens must have expiration times.

## Testing
Every new function needs at least one unit test.
Every new API endpoint needs at least one integration test.
E2E tests for cross-service features.
```

**Effort:** 4 hours | **Impact:** Medium -- reduces token cost per session, faster startup, progressive disclosure

---

### Phase 6: Sandcastle-Style Parallel Orchestration

For truly parallel AFK operation on multi-service features. This combines worktree isolation with automated agent spawning, following Matt Pocock's Sandcastle orchestration pattern.

#### Orchestration Pattern

Following Sandcastle's staged pipeline:

```
1. Planner    -- Reads design doc, creates task prompts per service
2. Implementer -- N parallel agents, each in own worktree (scripts/parallel-build.sh)
3. Reviewer   -- Agent reviews each worktree's changes (code-reviewer agent)
4. Merger     -- Merges branches back to feature branch (scripts/merge-parallel.sh)
```

#### Parallel Build Script

```bash
#!/bin/bash
# scripts/parallel-build.sh
# Spawn parallel Claude agents on separate worktrees for multi-service work
#
# Usage: ./scripts/parallel-build.sh <feature-name> [service1 service2 ...]
# Example: ./scripts/parallel-build.sh idp-sso control gateway

set -euo pipefail

FEATURE=${1:?"Usage: parallel-build.sh <feature-name> [services...]"}
shift
SERVICES=${@:-"control gateway"}
BASE_DIR=$(git rev-parse --show-toplevel)
LOG_DIR="$BASE_DIR/docs/workstreams/$FEATURE/parallel-logs"
PIDS=()

mkdir -p "$LOG_DIR"

echo "=== Parallel Build: $FEATURE ==="
echo "Services: $SERVICES"
echo "Base: $BASE_DIR"
echo "Started: $(date)"
echo ""

# Create worktrees and spawn agents
for SVC in $SERVICES; do
  BRANCH="feature/${FEATURE}-${SVC}"
  WORKTREE="$BASE_DIR/../${FEATURE}-${SVC}"
  PROMPT="docs/workstreams/$FEATURE/tasks/${SVC}-prompt.md"
  LOG="$LOG_DIR/${SVC}.log"

  echo "--- Setting up $SVC ---"

  # Create worktree if it doesn't exist
  if [ ! -d "$WORKTREE" ]; then
    git worktree add "$WORKTREE" -b "$BRANCH" dev 2>/dev/null || \
    git worktree add "$WORKTREE" "$BRANCH" 2>/dev/null
    echo "Created worktree: $WORKTREE ($BRANCH)"
  else
    echo "Worktree exists: $WORKTREE"
  fi

  # Copy Claude configuration
  cp -r "$BASE_DIR/.claude" "$WORKTREE/" 2>/dev/null || true
  cp "$BASE_DIR/CLAUDE.md" "$WORKTREE/" 2>/dev/null || true

  # Verify prompt file exists
  if [ ! -f "$BASE_DIR/$PROMPT" ]; then
    echo "WARNING: $PROMPT not found. Skipping $SVC."
    continue
  fi

  # Spawn Claude agent in background
  echo "Spawning agent for $SVC (log: $LOG)"
  (
    cd "$WORKTREE"
    claude --print \
      --output-format json \
      --prompt-file "$BASE_DIR/$PROMPT" \
      --allowedTools "Edit,Write,Read,Bash(git:*),Bash(pytest:*),Bash(make:*),Bash(ruff:*),Bash(python:*),Bash(find:*),Bash(grep:*),Bash(ls:*)" \
      --max-turns 100 \
      2>&1 | tee "$LOG"

    # Notify on completion
    "$BASE_DIR/scripts/notify.sh" "Parallel Build" "$SVC agent complete for $FEATURE"
  ) &
  PIDS+=($!)
  echo "Agent PID: ${PIDS[-1]}"
  echo ""
done

echo "=== All agents spawned ==="
echo "PIDs: ${PIDS[*]}"
echo ""
echo "Waiting for all agents to complete..."
echo "(You can safely go AFK now)"
echo ""

# Wait for all agents
for PID in "${PIDS[@]}"; do
  wait $PID 2>/dev/null || true
done

echo ""
echo "=== All agents complete ==="
echo "Finished: $(date)"
echo ""

# Summary
for SVC in $SERVICES; do
  WORKTREE="$BASE_DIR/../${FEATURE}-${SVC}"
  if [ -d "$WORKTREE" ]; then
    COMMITS=$(cd "$WORKTREE" && git log --oneline dev..HEAD 2>/dev/null | wc -l | tr -d ' ')
    echo "$SVC: $COMMITS new commits"
  fi
done

echo ""
echo "Next steps:"
echo "  1. Review changes in each worktree"
echo "  2. Create PRs: cd ../${FEATURE}-<service> && gh pr create"
echo "  3. Cleanup: git worktree remove ../${FEATURE}-<service>"

# Final notification
"$BASE_DIR/scripts/notify.sh" "Parallel Build Complete" "All agents finished for $FEATURE" "urgent"
```

#### Merge-Back Script

After parallel agents complete, merge their work:

```bash
#!/bin/bash
# scripts/merge-parallel.sh
# Merge parallel worktree branches back to a feature branch
#
# Usage: ./scripts/merge-parallel.sh <feature-name> [services...]

set -euo pipefail

FEATURE=${1:?"Usage: merge-parallel.sh <feature-name> [services...]"}
shift
SERVICES=${@:-"control gateway"}
MERGE_BRANCH="feature/$FEATURE"

echo "=== Merging parallel work for $FEATURE ==="

# Create merge branch from dev
git checkout -b "$MERGE_BRANCH" dev 2>/dev/null || git checkout "$MERGE_BRANCH"

for SVC in $SERVICES; do
  BRANCH="feature/${FEATURE}-${SVC}"

  echo "--- Merging $BRANCH ---"

  if git merge "$BRANCH" --no-edit; then
    echo "Merged $BRANCH successfully"
  else
    echo "CONFLICT merging $BRANCH. Resolve manually."
    echo "  git mergetool"
    echo "  git merge --continue"
    exit 1
  fi
done

echo ""
echo "=== All branches merged into $MERGE_BRANCH ==="
echo "Run tests: make check-all"
echo "Create PR: gh pr create --base dev"
```

**Branch strategies** (from Sandcastle):
- `head`: Each agent commits directly to the feature branch (simple, risk of conflict)
- `merge-to-head`: Each agent works on a sub-branch, merged back at the end (safer)
- `branch`: Each agent stays on its own branch, human merges (safest)

For DeepSecure, use `merge-to-head` as the default since control and gateway rarely conflict.

#### Tmux-Based Headless Orchestration

For long-running AFK sessions (overnight), prefer tmux over bare `&` backgrounding. This gives observability, persistence, and recovery:

```bash
#!/bin/bash
# scripts/parallel-build-tmux.sh
# Tmux-based variant of parallel-build.sh for overnight AFK sessions

FEATURE=${1:?"Usage: parallel-build-tmux.sh <feature-name> [services...]"}
shift
SERVICES=${@:-"control gateway"}
BASE_DIR=$(git rev-parse --show-toplevel)

# Create a tmux session group for the feature
tmux new-session -d -s "${FEATURE}-orchestrator" "echo 'Orchestrator for $FEATURE'; bash"

for SVC in $SERVICES; do
  WORKTREE="$BASE_DIR/../${FEATURE}-${SVC}"
  PROMPT="docs/workstreams/$FEATURE/tasks/${SVC}-prompt.md"

  # Each agent gets its own tmux window within the session
  tmux new-window -t "${FEATURE}-orchestrator" -n "$SVC" \
    "cd $WORKTREE && claude --print --prompt-file $BASE_DIR/$PROMPT --max-turns 100 2>&1 | tee $BASE_DIR/docs/workstreams/$FEATURE/parallel-logs/${SVC}.log; echo 'DONE'; bash"
done

echo "Agents spawned in tmux session: ${FEATURE}-orchestrator"
echo "  Observe:  tmux attach -t ${FEATURE}-orchestrator"
echo "  List:     tmux list-windows -t ${FEATURE}-orchestrator"
echo "  Kill all: tmux kill-session -t ${FEATURE}-orchestrator"
```

#### Keepalive Mechanisms

Long-running AFK sessions may be terminated by idle timeouts (SSH, tmux, cloud instances). Prevent this with keepalive strategies:

| Mechanism | How | When to Use |
|-----------|-----|-------------|
| `session_keepalive_interval_ms` | Claude Code config option, sends periodic pings | Cloud-hosted sessions |
| Tmux watchdog script | Sends keystrokes or checks process health | Long overnight runs |
| Heartbeat hook | SessionStart hook with periodic check-in | Any AFK session |

```bash
# Tmux watchdog: restart agent if it dies unexpectedly
while true; do
  if ! tmux has-session -t "agent-1" 2>/dev/null; then
    scripts/notify.sh "Watchdog" "agent-1 session died. Restarting..." "urgent"
    tmux new-session -d -s "agent-1" "cd /path/to/worktree-1 && claude --print --prompt-file ralph-prompt.md --max-turns 80"
  fi
  sleep 300
done
```

#### Hermes Agent as Orchestration Layer

Nous Research's [Hermes Agent](https://github.com/nousresearch/hermes-agent) (169k+ stars) is a persistent, self-improving autonomous agent that can serve as a meta-orchestrator above Claude Code. It doesn't replace Claude Code — it delegates coding work to it while handling scheduling, memory, notifications, and multi-agent coordination.

**What Hermes provides that bash scripts don't:**

| Capability | Bash Scripts (Current) | Hermes Agent |
|------------|----------------------|--------------|
| **Scheduling** | `cron` + `ralph.sh` | Built-in cron with natural-language task definitions |
| **Notifications** | `scripts/notify.sh` + Slack webhook | Native multi-platform: Slack, Telegram, Discord, WhatsApp, Signal, SMS, Email from one process |
| **Memory** | File-based (`RALPH_PROGRESS.md`, `.afk/learnings.md`) | Agent-curated persistent memory with FTS5 search over session history, cross-session recall |
| **Parallelism** | `&` backgrounding or tmux sessions | ThreadPoolExecutor (up to 8 parallel workers), subagent spawning |
| **Isolation** | Git worktrees | 6 terminal backends: local, Docker, SSH, Singularity, Modal (serverless), Daytona |
| **Skills** | Static markdown files | Auto-created, self-improving skills compatible with agentskills.io standard |
| **Coding agents** | Claude Code only | Delegates to Claude Code, OpenAI Codex, or OpenCode — picks best tool per task |

**Architecture if adopted:**
```
Hermes Agent (orchestrator)
  ├── Cron: "every night at 2am, run the Ralph loop on workstream X"
  ├── Memory: persistent cross-session learnings (replaces .afk/learnings.md)
  ├── Notifications: Slack + Telegram natively (replaces scripts/notify.sh)
  ├── Parallel workers: up to 8 concurrent subagents
  │
  └── Delegates coding to:
      └── Claude Code (subordinate)
          ├── Your 23 command skills
          ├── CLAUDE.md context
          ├── Hooks pipeline
          └── Worktree isolation
```

**Trade-offs:**
- **Pro:** Solves scheduling, notifications, memory, and multi-agent coordination in one tool
- **Pro:** Serverless backends (Modal, Daytona) eliminate keepalive problems — agents hibernate and resume
- **Pro:** Self-improving skills address Carson's "skills decay" problem structurally
- **Con:** Adds a Python dependency and abstraction layer between you and Claude Code
- **Con:** Debugging becomes harder (is the issue Hermes orchestration or Claude Code execution?)
- **Con:** Your existing 23 command skills and hooks are Claude Code native — they'd work through Hermes but with an extra layer of indirection

**Recommended adoption path for DeepSecure (three-phase authority escalation):**

The critical distinction: Hermes should gain authority gradually, not all at once. Start as an observer, graduate to invoker, then to autonomous manager — each phase gated by earning trust.

| Phase | Hermes Role | Code Authority | What It Replaces |
|-------|------------|----------------|------------------|
| **1: Observer/Operator** | Schedule AFK jobs, send notifications, remember cross-session learnings, watch CI/logs, monitor repo state | **None** — Claude Code does all code writing via Ralph loop | `scripts/notify.sh`, `cron`, `.afk/learnings.md` |
| **2: Controlled Invoker** | Triggers Ralph loop runs, reviews output, decides whether to continue or escalate to human | **Indirect** — starts AFK runs and evaluates results, but doesn't write code itself | `scripts/ralph.sh` invocation, manual "check progress" |
| **3: Autonomous Manager** | Full AFK lifecycle: plan → decompose → spawn parallel agents → review → merge → deploy | **Full** — but scoped via DeepSecure delegation_tokens with TTL, audit trail, and revocation | `parallel-build.sh`, manual merge review, human orchestration |

**Phase 1 is safe to start now** (after Ralph loop is stable). Hermes scheduling + notifications are strictly superior to bash scripts. It observes and reports but changes nothing.

**Phase 2 requires trust earned in Phase 1.** Hermes invokes Claude Code but doesn't bypass the verification gates (tests, lint, review).

**Phase 3 requires DeepSecure identity controls.** This is where the dog-fooding story becomes critical — Hermes should not get autonomous merge authority without scoped delegation_tokens, audit trails, and bounded blast radius. See [DeepSecure as AFK Security Infrastructure](#deepsecure-as-afk-security-infrastructure-dog-fooding) for the identity pattern that gates this phase.

**Effort:** 10 hours | **Impact:** Very High -- enables multi-service parallel AFK development with observability, recovery, and keepalive

---

## Priority Ranking

| Priority | Action | Effort | Impact | What It Enables |
|----------|--------|--------|--------|-----------------|
| **P0** | Permission allowlisting (1a) | 30 min | High | Unblocks all AFK work |
| **P0** | Stop hook enhancement (1b) | 30 min | High | Prevents premature agent stopping |
| **P0** | SessionStart hook (1e) | 30 min | Medium | Agents start with situational awareness |
| **P1** | PostToolUse auto-format (1c) | 1 hr | Medium | Eliminates CI format failures |
| **P1** | Notification system (Phase 3) | 2 hr | High | Know when to come back |
| **P1** | `afk-once.sh` manual script (2a) | 1 hr | High | Learn failure domains before automating |
| **P1** | Ralph loop script (2b) | 2 hr | Very High | Core AFK execution engine |
| **P1** | `.afk/learnings.md` (2c) | 30 min | Medium | Systematic failure capture |
| **P2** | Agent frontmatter upgrade (1.5) | 2 hr | Medium | Correct tool access and model selection |
| **P2** | AFK security profile (3.5) | 2 hr | High | Safe unsupervised execution |
| **P2** | `/babysit-pr` skill | 4 hr | High | Autonomous PR lifecycle |
| **P2** | `/autofix-pr` skill | 4 hr | High | Autonomous CI fixing |
| **P2** | PostCompact hook (1d) | 1 hr | Medium | Prevents context loss |
| **P2** | Additional hook events (3.5) | 1 hr | Medium | Complete AFK event tracking |
| **P3** | CLAUDE.md refactoring (Phase 5) | 4 hr | Medium | Token savings, progressive disclosure |
| **P3** | `/grill-me` skill | 2 hr | Medium | Better specs before implementation |
| **P3** | `/verify-app` skill | 4 hr | Medium | End-to-end feature verification |
| **P3** | `doc-gardener` agent | 4 hr | Medium | Skills staleness audit |
| **P3** | `/context-engineering` skill | 2 hr | Medium | Context management guidance |
| **P3** | Parallel orchestration (Phase 6) | 10 hr | Very High | Multi-service parallel AFK |
| **P2** | `/afk` toggle command | 2 hr | High | One-command AFK mode switching |
| **P2** | `/security-scan` skill | 3 hr | High | Prevent vulnerable code in AFK commits |
| **P3** | `/identity-management` skill | 4 hr | Medium | Zero-trust AFK agent identity |
| **P3** | Skill `gotchas.md` files | 3 hr | Medium | Domain-specific pitfall prevention |
| **P4** | Zero-trust AFK identity integration | 8 hr | High | Dog-food DeepSecure for AFK security |
| **P4** | Fast-merge policy + automated rollback | 6 hr | Medium | Remove human bottleneck at scale |
| **P4** | Hermes Agent evaluation | 6 hr | Medium | Evaluate as orchestration layer (scheduling, notifications, memory, multi-agent) |

**Total estimated effort:** ~74 hours across all phases

**Recommended order:**
1. **P0 items first** (1.5 hours) -- immediately unblocks AFK
2. **P1 items next** (6.5 hours) -- gives you a working AFK loop with manual stepping stone and notifications
3. **P2 items** (19 hours) -- completes autonomous PR lifecycle with safe security profile, AFK toggle, vulnerability scanning
4. **P3 items** (27 hours) -- optimization, scaling, identity management, and maintenance automation
5. **P4 items** (20 hours) -- zero-trust dog-fooding, fast-merge policy, Hermes Agent evaluation

---

## The Contrarian Views

### Dax Raad (OpenCode Creator, 165k+ GitHub Stars)

Argues that multi-agent parallelism feels productive but often isn't:

> "Opening eight agents and watching them all run at once feels incredible. But it's what I call the sinister thing about multitasking. The productivity feeling is real but the productivity is not."

> "You'd probably ship more doing things one at a time with a faster model."

**His advice:**
1. Define interfaces and architecture manually first ("agent comes later")
2. Bring in agents for well-scoped implementation work, not design
3. Use one agent at a time with a fast model rather than many in parallel
4. Be honest about whether parallelism is actually productive or just feels good

**Additional from Dax:**
- Client-server architecture for remote driving -- run on your computer, drive from mobile app
- Provider-agnostic design (75+ models) -- don't lock into one provider
- 80% of OpenCode effort goes to UX, 20% to harness -- "most users cannot notice harness quality differences beyond a minimum threshold, but UX determines adoption"

### Geoffrey Huntley (Ralph Loop Creator)

Explicitly argues against multi-agent coordination:

> "Consider what microservices would look like if the microservices (agents) themselves are non-deterministic -- a red hot mess."

Advocates single-process, single-task execution. The deliberate simplicity is the feature. Complexity in orchestration adds non-determinism on top of non-determinism.

### How to Reconcile

- The existing DeepSecure pipeline's emphasis on planning (`/run-plan`, `/breakdown-design`, `/explore-codebase`) aligns with Dax's "interfaces first" philosophy
- Don't skip planning in favor of throwing more agents at the problem
- **Default to the Ralph loop (sequential, one-at-a-time)**; parallel orchestration only when work is genuinely independent
- Reserve multi-agent parallelism for truly independent workstreams (e.g., control plane + gateway when they don't share schemas)
- Measure actual output (merged PRs, passing tests) not activity (number of agents running)
- Start manual (`afk-once.sh`), graduate to supervised AFK, then full AFK -- per Huntley's methodology

---

## Key Takeaways by Practitioner

### Boris Cherny (Claude Code Creator)
- **Plan mode:** Shift+Tab x2, iterate on the plan, one-shot implementation
- **Worktrees:** 5 parallel Claudes in terminal tabs, numbered 1-5
- **Scale:** 20-30 PRs/day normal, 150 PRs/day peak, hundreds of agents running simultaneously
- **CLAUDE.md:** Compounding engineering -- every mistake becomes a rule
- **Permissions:** `/permissions` allowlist, never `--dangerously-skip-permissions`
- **Top hooks:** PostToolUse (auto-format), PostCompact (context recovery), PermissionRequest (Slack), Stop (keep going)
- **Subagents:** `code-simplifier`, `verify-app` -- automate the most common PR workflows
- **Key commands:** `/loop` (cron-style), `/batch` (parallel migrations), `/quality` (PR health)
- **Teleport:** Hand work between local and web/mobile with `&` command
- **Context switching:** "It's not about deep work, it's about how good I am at context switching"

### Thariq (Anthropic -- Skills Framework)
- **9 skill categories:** Library/API Reference, Product Verification, Data/Monitoring, Workflow Automation, Code Quality, Deployment, Scaffolding, Runbooks, Infrastructure Operations
- **Skills are folders, not files:** Include scripts, assets, gotchas, reference code
- **Top skills for AFK:** `/babysit-pr` (monitors PR through lifecycle), `/deploy-<service>` (build, smoke test, gradual rollout, auto-rollback)
- **Measurement:** PreToolUse hook to track skill usage and find under-triggering skills
- **Anthropic runs hundreds of skills internally**

### Noah Zweben (Anthropic PM)
- **`/autofix-pr`:** Ships conversation + edits to cloud, agent autonomously fixes CI + review comments
- **`claude --worktree --tmux`:** Fire and forget -- spin up autonomous Claude on its own worktree in its own terminal
- **`/schedule`:** Cloud-based recurring tasks (sweeping open PRs, building features from approved issues, analyzing CI failures overnight, syncing docs, auto-maintaining a twin Go library for a Python library)
- **Monitor tool:** Event-driven (not polling) background watcher -- every stdout line is a real-time event
- **Remote Control:** Start local, continue from phone via Claude iOS app

### Matt Pocock
- **Ralph Wiggum:** `while true` loop with fresh context each iteration -- the core AFK engine
- **Sandcastle:** Framework for spawning N parallel agents in worktrees + Docker (Planner -> Implementer -> Reviewer -> Merger)
- **Grill, Spec, Slice, Ship:** 5-stage workflow: interview (40-80 questions) then PRD then vertical tracer bullets then AFK ship
- **CODE_STANDARDS.md:** Move standards out of CLAUDE.md, enforce them via reviewer agent on PRs
- **Cap iterations:** 5-10 for small AFK tasks, 30-50 for larger ones
- **Vertical tracer bullets:** Build end-to-end (schema through UI), not layer by layer
- **Context limit:** "Keep LLM context under ~100k tokens; clear and restart rather than compact to avoid sediment degrading quality"
- **Result:** "889 commits, none of them hand-coded"

### Geoffrey Huntley (Ralph Loop Creator)
- **Monolithic Ralph:** Single process, single task, no multi-agent coordination
- **Manual first:** Do the loop manually with Ctrl+C pauses before automating
- **Watch the loop:** Learning comes from observing failures and fixing failure domains
- **Evolutionary software (Loom):** Long-term aspiration -- auto-identify, fix, deploy, verify
- **Simplicity is the feature:** The loop is deliberately simple because agents are non-deterministic

### Ryan Carson (One-Person Code Factory)
- **`prd.json` with `passes: true/false`:** Machine-parseable completion tracking
- **Skills decay:** "A Next.js skill from six months ago may conflict with your current component library." Need staleness audit.
- **15 simultaneous agents, $2-3k/month token burn** -- the economics of AFK
- **"AI Chief of Staff":** Cron job triaging inbox/Slack through a priority map
- **Code factory = automations + skills for daily repeatable jobs**

### Andrej Karpathy (Software 3.0)
- **"Automate what you can verify":** Tasks with tests = full AFK. Tasks needing judgment = human gates.
- **"Jagged intelligence":** Models spike where tasks are verifiable AND received training attention. Crypto/auth is in a valley.
- **"Outsource thinking, never understanding":** AFK for implementation, not architecture.
- **Agent-native docs:** "Context window is the new program." Optimize documentation for agents.

### Mike Piccolo (Agent AFK)
- **Full pipeline:** spec, research, plan, parallelize, build, verify, heal, ship
- **Permission bubbling:** Nested subagents forward permission requests up to parent/user
- **Transitive abort:** Cancel parent = cancel all children
- **Self-healing:** If verification fails, automatically diagnose and fix before shipping
- **Notification:** Texts via Telegram when done or stuck

### Ramp (Inspect)
- **Cloud sandboxes:** Modal with pre-built snapshots every 30 minutes, near-instant start
- **Child sessions:** Agents can spawn sub-sessions for parallel research or approach exploration
- **Multiplayer:** Multiple team members collaborate in single sessions
- **Statistics page:** Track sessions-to-merged-PRs as the key metric
- **Result:** ~30% of all PRs merged to frontend and backend repos are written by Inspect

### Harvey AI (Spectre)
- **Durable objects:** Every agent session records all actions for audit
- **Team visibility:** Real-time observation of agent work across Slack, web, PRs
- **Same runtime for interactive and automated:** No distinction between human-prompted and scheduled work
- **Pattern convergence:** Stripe and other scale companies independently built similar platforms

### OpenAI (Harness Engineering)
- **1M LOC, zero human-written:** 5-month experiment, ~1,500 PRs, 3.5 PRs/engineer/day
- **AGENTS.md as TOC:** ~100 lines, progressive disclosure, points to structured `docs/`
- **Dependency layering:** Types, Config, Repo, Service, Runtime, UI -- agents restricted to their layer
- **Structural enforcement:** Custom linters and tests enforce architecture, not just documentation
- **Golden principles + GC:** Recurring background tasks scan for deviations and open refactoring PRs
- **Agent-to-agent review:** Over time, almost all review is agent-to-agent. Humans not required.
- **Agent legibility over human taste:** Code optimized for agent's ability to reason about it
- **6+ hour autonomous runs** while humans sleep

### Cursor (Agent Harness)
- **Dynamic context:** Remove guardrails as models improve. Let agents pull own context.
- **Keep Rate metric:** Track what fraction of agent code remains after fixed intervals
- **Tool reliability at 3 9s:** Drive unexpected tool errors down by order of magnitude
- **Three-layer state decoupling:** Agent loop (Temporal), machine state (VM), conversation state
- **"Simplicity and control":** Better tools + clear prompts beat complex harness logic
- **Multi-agent future:** Specialized agents for planning, fast edits, debugging -- harness orchestrates dispatch

### Dark Software Factory Synthesis (Academic Paper)
- **Sediment Problem:** Context quality degrades after ~100k tokens; agents must stay in the "Smart Zone"
- **Zero-trust AFK identity:** Use DeepSecure's own Ed25519 + delegation_tokens to secure AFK agent swarms (dog-fooding)
- **Fast-merge philosophy:** At agent scale, blocking merge gates are the bottleneck — merge fast, rollback automatically
- **Day Shift / Night Shift:** Formal separation of human planning (day) and agent execution (night)
- **Skill engineering discipline:** Mandatory gotchas.md, run telemetry, semantic deduplication, quality scoring
- **Keepalive mechanisms:** `session_keepalive_interval_ms`, tmux watchdog scripts for long-running sessions
- **Blast radius limiting:** Small PRs, feature flags, anomaly detection, automated rollback, lineage records
- **Hermes Agent:** Persistent meta-orchestrator as potential scheduling/notification/memory layer above Claude Code

### Nous Research (Hermes Agent)
- **Meta-orchestrator:** Persistent autonomous agent that delegates coding work to Claude Code, Codex, or OpenCode
- **Self-improving skills:** Skills auto-created after complex tasks and improve during use; compatible with agentskills.io standard
- **6 terminal backends:** Local, Docker, SSH, Singularity, Modal (serverless), Daytona — solves keepalive via serverless hibernation
- **Built-in cron:** Natural-language task scheduling ("run Ralph loop every night at 2am")
- **Multi-platform messaging:** Slack, Telegram, Discord, WhatsApp, Signal, SMS, Email from one process
- **Persistent memory:** Agent-curated cross-session recall with FTS5 search, replaces file-based `.afk/learnings.md`
- **Parallel workers:** ThreadPoolExecutor (up to 8 concurrent subagents) with isolated terminal backends
- **Adoption path:** Not a default replacement for Claude Code; evaluate as orchestration layer once Ralph loop is stable (Phase 3+)

---

## Appendix: Complete Hook Configuration Reference

Full hooks.json for AFK-optimized DeepSecure development:

```json
{
  "version": 1,
  "hooks": {
    "PostToolUse": [
      {
        "matcher": { "tool_name": "Edit|Write" },
        "command": "FILE_PATH=$(echo $TOOL_INPUT | jq -r '.file_path // empty'); if [ -n \"$FILE_PATH\" ] && echo \"$FILE_PATH\" | grep -q '\\.py$'; then ruff format --quiet \"$FILE_PATH\" 2>/dev/null; isort --quiet \"$FILE_PATH\" 2>/dev/null; fi"
      }
    ],
    "PostCompact": [
      {
        "command": "cat .claude/compact-recovery.md 2>/dev/null || true"
      }
    ],
    "PreCompact": [
      {
        "command": "echo 'CONTEXT COMPACTING: saving state snapshot'; git stash list 2>/dev/null | head -3"
      }
    ],
    "Stop": [
      {
        "command": ".cursor/hooks/on-task-stop.sh"
      }
    ],
    "PermissionRequest": [
      {
        "command": "scripts/notify.sh 'Permission Request' \"Claude needs: $TOOL_NAME\" urgent"
      }
    ],
    "SessionStart": [
      {
        "command": "echo '--- Recent commits ---'; git log --oneline -5 2>/dev/null; echo '--- Branch ---'; git branch --show-current 2>/dev/null; echo '--- Open PRs ---'; gh pr list --limit 3 2>/dev/null || true"
      }
    ],
    "SessionEnd": [
      {
        "command": "scripts/notify.sh 'Session Ended' 'Claude Code session finished on branch: $(git branch --show-current 2>/dev/null)'"
      }
    ],
    "SubagentStop": [
      {
        "command": "echo 'Subagent completed: $SUBAGENT_NAME'"
      }
    ]
  }
}
```

---

## Appendix: Environment Variables for AFK

```bash
# Add to .env or shell profile

# Slack notifications for AFK
export DEEPSECURE_SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Ralph loop defaults
export RALPH_MAX_ITERATIONS=10
export RALPH_MAX_TURNS=80

# Claude Code permissions (reduce prompts)
export CLAUDE_CODE_ALLOW_TOOLS="Edit,Write,Read,Bash(git:*),Bash(pytest:*),Bash(make:*)"
```

---

## Appendix: Quick Start Checklist

To go AFK on a DeepSecure workstream today:

```
Phase 0: Setup (one-time)
[ ] Expand permission allowlist in settings.local.json (Phase 1a)
[ ] Set up hooks (Phase 1b-1e)
[ ] Set up notifications: scripts/notify.sh + Slack webhook (Phase 3)
[ ] Upgrade agent frontmatter (Phase 1.5)

Phase 1: Planning (per feature)
[ ] Complete planning: /run-plan <feature> <design-doc>
[ ] Or use /grill-me for requirements elicitation first
[ ] Verify prerequisites: all 7 workstream files exist
[ ] Create RALPH_PROGRESS.md with task checklist
[ ] Create ralph-prompt.md with workstream context

Phase 2: Manual Stepping Stone
[ ] Run ./scripts/afk-once.sh <workstream> -- watch the output
[ ] Fix any failures, update CLAUDE.md/skills
[ ] Repeat 5-10 times until stable

Phase 3: AFK Execution
[ ] Run: ./scripts/ralph.sh <workstream-name> <max-iterations>
[ ] Go AFK
[ ] Come back when notified (or check RALPH_PROGRESS.md)

Phase 4: Review and Ship
[ ] Review changes: git log, git diff
[ ] Run full checks: make check-all
[ ] Create PR: /commit-push-pr
[ ] Optionally: /babysit-pr to automate merge lifecycle
```

---

## Appendix: AFK Task Classification for DeepSecure

Based on Karpathy's "automate what you can verify" principle, applied to DeepSecure's specific domains:

| Domain | Verifiable? | AFK Level | Reasoning |
|--------|-------------|-----------|-----------|
| Standard CRUD endpoints | Yes (pytest) | Full AFK | Well-understood patterns, easy to test |
| Database migrations | Yes (migrate up/down) | Full AFK | Deterministic, testable |
| CLI commands | Yes (click testing) | Full AFK | Clear input/output contract |
| SDK client methods | Yes (unit tests) | Full AFK | Isolated, mockable |
| Gateway routing | Yes (integration tests) | Full AFK with review | Cross-service, needs integration test |
| Auth challenge-response | Partially | HITL | Crypto domain valley, subtle bugs |
| JWT creation/validation | Partially | HITL | Security-critical, edge cases |
| Ed25519 key operations | Partially | HITL | Crypto domain valley |
| Split-key architecture | Partially | HITL | Novel pattern, low training data |
| Permission/delegation model | No (judgment) | Human-only | Security architecture decision |
| API contract design | No (judgment) | Human-only | Requires product understanding |
| Trust model changes | No (judgment) | Human-only | Security-critical design |

---

*Document created: 2026-05-26*
*Last updated: 2026-05-27 (incorporated 31 items from Dark Software Factory paper)*
*Based on research from 20 industry sources (see [Research Sources](#research-sources))*
