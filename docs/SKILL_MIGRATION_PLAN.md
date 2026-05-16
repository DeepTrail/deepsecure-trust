# Skill Migration Plan: Commands → Skills

> **Last Updated:** May 2026
>
> Analysis of the current `.cursor/commands/` inventory, proposed skill extraction strategy, and dual-platform skill generation for both Cursor and Claude Code.

---

## Table of Contents

1. [Current Command Inventory](#current-command-inventory)
2. [How Commands and Skills Differ](#how-commands-and-skills-differ)
3. [Cursor Skills vs Claude Code Skills](#cursor-skills-vs-claude-code-skills)
4. [Proposed Skill Migration Strategy](#proposed-skill-migration-strategy)
   - [Category A: Commands Only (No Skill Needed)](#category-a-commands-that-stay-as-commands-only)
   - [Category B: Command + Companion Skill](#category-b-commands-that-benefit-from-a-companion-skill)
   - [Category C: New Cross-Cutting Skills](#category-c-new-cross-cutting-skills-not-derived-from-commands)
   - [Category D: Agent Definitions → Skills](#category-d-agent-definitions--become-skills)
5. [Proposed Skill Directory Structure](#proposed-skill-directory-structure)
6. [How Commands and Skills Coexist](#how-commands-and-skills-coexist)
7. [Token Budget Comparison](#token-budget-comparison)
8. [Recommended Migration Order](#recommended-migration-order)
9. [Generating Skills for Both Platforms](#generating-skills-for-both-platforms)
10. [Implementation Notes](#implementation-notes)

---

## Current Command Inventory

**23 commands** (12,571 total lines), **3 agents**, **1 rule**, **3 hooks**, **1 config file**

### Commands by Size

| # | Command | Lines | Pipeline Phase | Nature |
|---|---------|-------|----------------|--------|
| 1 | `create-task-spec.md` | 1,105 | PLAN | Heavy procedural |
| 2 | `breakdown-design.md` | 911 | PLAN | Heavy procedural |
| 3 | `spec.md` | 833 | DEFINE | Gated workflow |
| 4 | `create-batch-execution-plan.md` | 829 | PLAN | Heavy procedural |
| 5 | `create-task-ticket.md` | 798 | PLAN | Template-driven |
| 6 | `create-design-doc.md` | 758 | DEFINE | Transformation |
| 7 | `run-batch.md` | 701 | EXECUTE | Orchestrator |
| 8 | `pipeline.md` | 611 | META | Top-level orchestrator |
| 9 | `run-plan.md` | 569 | PLAN | Orchestrator |
| 10 | `execute-task.md` | 547 | EXECUTE | Heavy procedural |
| 11 | `complete-task.md` | 544 | EXECUTE | Report generation |
| 12 | `create-workstream.md` | 535 | PLAN | Scaffolding |
| 13 | `verify-batch-completion.md` | 422 | VERIFY | Validation |
| 14 | `debug.md` | 384 | EXECUTE | Diagnostic |
| 15 | `sync-worktree-status.md` | 374 | VERIFY | Sync utility |
| 16 | `setup-worktrees.md` | 369 | PLAN | Git automation |
| 17 | `review.md` | 344 | REVIEW | Multi-axis review |
| 18 | `ship.md` | 339 | SHIP | Deployment checklist |
| 19 | `security-audit.md` | 333 | REVIEW | OWASP/STRIDE audit |
| 20 | `commit-push-pr.md` | 302 | REVIEW | Git/PR workflow |
| 21 | `explore-codebase.md` | 286 | EXPLORE | Discovery |
| 22 | `run-checks.md` | 258 | REVIEW | Quality gate |
| 23 | `update-claude-md.md` | 185 | LEARN | Config update |

### Agent Definitions

| Agent | File | Lines |
|-------|------|-------|
| Security Auditor | `.cursor/agents/security-auditor.md` | 199 |
| Test Engineer | `.cursor/agents/test-engineer.md` | 134 |
| Code Reviewer | `.cursor/agents/code-reviewer.md` | 103 |

### Other Files

| File | Purpose |
|------|---------|
| `.cursor/hooks.json` | Hook lifecycle configuration |
| `.cursor/hooks/after-file-edit.sh` | Lint Python files after edit |
| `.cursor/hooks/before-shell.sh` | Block dangerous shell commands |
| `.cursor/hooks/on-task-stop.sh` | macOS notification + lint summary |
| `.cursor/rules/plan-location.mdc` | Always-applied rule for plan file location |
| `.cursor/worktrees.json` | Worktree setup configuration |

---

## How Commands and Skills Differ

| Dimension | Command | Skill |
|-----------|---------|-------|
| **Location** | `.cursor/commands/name.md` (flat file) | `.cursor/skills/name/SKILL.md` (directory) |
| **Invocation** | User types `/command-name` explicitly | Auto-discovered by description match **OR** user types `/skill-name` |
| **Loading** | Entire file loaded into context when invoked | YAML frontmatter scanned first (~50 tokens); full body loaded only on match |
| **Progressive disclosure** | No — full content always loaded | Yes — heavy references live in separate files, loaded only when needed |
| **Supporting files** | Not supported | `reference.md`, `examples.md`, `scripts/` directory |
| **Token cost** | Entire command consumed on every invocation | Metadata-only scan is cheap; full load only when relevant |
| **Auto-invocation** | Never — requires explicit `/` trigger | Can auto-activate when description matches conversation context |
| **Best for** | Explicit user-triggered workflows ("do this now") | Domain knowledge, patterns, and context the agent should know when relevant |
| **Frontmatter** | Optional (supported but rarely used) | YAML frontmatter with `name`, `description`, and optional fields |
| **Backward compat** | `.claude/commands/` still works in Claude Code | Skills take precedence if same name exists in both |

**Key insight: Commands and skills serve different purposes.** Commands are imperative ("do this now"). Skills are declarative ("know this when relevant"). They coexist naturally — a `/review` command provides the workflow steps, while a `code-review-patterns` skill provides the domain knowledge the agent needs to execute that workflow well.

---

## Cursor Skills vs Claude Code Skills

Both platforms support the same core `SKILL.md` format (following the [Agent Skills](https://agentskills.io/) open standard), but Claude Code has evolved additional capabilities.

### Shared Features (Both Platforms)

| Feature | Details |
|---------|---------|
| `SKILL.md` entrypoint | Required file in a named directory |
| YAML frontmatter | `name`, `description` fields |
| Supporting files | `reference.md`, `examples.md`, `scripts/` |
| Project scope | `.cursor/skills/` or `.claude/skills/` |
| Personal scope | `~/.cursor/skills/` or `~/.claude/skills/` |
| Auto-discovery | Agent scans descriptions to decide when to load |
| Slash invocation | `/skill-name` triggers the skill explicitly |

### Claude Code Exclusive Features

| Feature | What It Does | Example |
|---------|-------------|---------|
| **`context: fork`** | Run skill in a forked subagent context (isolated, no conversation history) | `context: fork` + `agent: Explore` for read-only research |
| **`agent` field** | Specify which subagent type executes the skill (`Explore`, `Plan`, `general-purpose`, or custom agent from `.claude/agents/`) | `agent: Explore` for codebase analysis |
| **`!`command`` injection** | Run shell commands before skill content reaches Claude; output replaces the placeholder | `` !`git diff HEAD` `` injects live diff |
| **`allowed-tools`** | Pre-approve tools for the skill (no per-use permission prompt) | `allowed-tools: Bash(git add *) Bash(git commit *)` |
| **`$ARGUMENTS` / `$N`** | String substitution for positional arguments | `/fix-issue 123` → `$0` becomes `123` |
| **`${CLAUDE_SKILL_DIR}`** | Resolves to the skill's directory path at runtime | `python3 ${CLAUDE_SKILL_DIR}/scripts/validate.py` |
| **`${CLAUDE_SESSION_ID}`** | Current session ID for logging/correlation | `logs/${CLAUDE_SESSION_ID}.log` |
| **`${CLAUDE_EFFORT}`** | Current effort level (`low` through `max`) | Adapt instructions based on effort |
| **`disable-model-invocation`** | Prevent Claude from auto-invoking (user-only) | Deployment, destructive operations |
| **`user-invocable: false`** | Hide from `/` menu; Claude-only background knowledge | Legacy system context, conventions |
| **`model` field** | Override the model for this skill's turn | Use a cheaper model for simple tasks |
| **`effort` field** | Override effort level for this skill | `effort: max` for complex analysis |
| **`hooks` field** | Lifecycle hooks scoped to this skill | Pre/post validation for skill execution |
| **`paths` field** | Glob patterns limiting when skill auto-activates | `paths: "*.py"` only activates for Python files |
| **`arguments` field** | Named positional arguments | `arguments: [issue, branch]` → `$issue`, `$branch` |
| **Skill content lifecycle** | Content stays in context across turns; survives auto-compaction (first 5,000 tokens, max 25,000 combined) | Long-running skills don't need re-invocation |
| **`skillOverrides` in settings** | Control visibility per skill from settings without editing SKILL.md | `"deploy": "off"` in `.claude/settings.local.json` |
| **Live change detection** | Edits to skills take effect within session (no restart) | Edit SKILL.md → changes apply immediately |
| **Nested directory discovery** | Skills in subdirectories discovered on demand | `packages/frontend/.claude/skills/` in monorepo |
| **Plugin skills** | Distributed via plugin system with namespace isolation | `plugin-name:skill-name` |

### Cursor Exclusive Features

| Feature | What It Does |
|---------|-------------|
| **`disable-model-invocation: true` (default)** | Cursor defaults to opt-in; skills only load when named. Claude Code defaults to `false` (auto-discovery on). |

### Key Differences for Dual-Platform Generation

| Concern | Cursor | Claude Code |
|---------|--------|-------------|
| Default auto-discovery | Off by default (`disable-model-invocation: true` recommended) | On by default; set `disable-model-invocation: true` for explicit-only |
| Dynamic context | Not supported | `!`command`` injection preprocesses shell output |
| Subagent execution | Not natively supported in skills | `context: fork` + `agent` field |
| Tool pre-approval | Not in skill frontmatter | `allowed-tools` field |
| File location | `.cursor/skills/name/SKILL.md` | `.claude/skills/name/SKILL.md` |
| Agent definitions | `.cursor/agents/name.md` (separate concept) | `.claude/agents/name.md` OR skill with `context: fork` + `agent` |
| Backward compat | `.cursor/commands/` works | `.claude/commands/` works but skills preferred |

---

## Proposed Skill Migration Strategy

The strategy is **not** to convert all commands into skills. Instead:

1. **Keep commands for explicit workflows** — anything the user triggers with `/command`
2. **Extract skills for reusable domain knowledge** — patterns, checklists, and reference data that multiple commands share
3. **Create new skills for cross-cutting concerns** — knowledge that should auto-activate based on context
4. **Convert agent definitions to skills** — leverage auto-discovery for review personas

### Category A: Commands That Migrate to Skill Format (No Companion Skill Needed)

These are imperative workflows with clear start/end. They don't need a *separate* companion knowledge skill extracted — but the commands themselves **should still migrate to the skill directory format** because the format is strictly superior:

| Skill Format Advantage | Why It Matters for These Commands |
|------------------------|-----------------------------------|
| **Progressive disclosure** | A 1,105-line `create-task-spec` can put templates in `reference/` — loaded only when needed |
| **`$ARGUMENTS` substitution** | `/run-batch P0-B1 agent-lifecycle` → `$0` = `P0-B1`, `$1` = `agent-lifecycle` — cleaner than free-text parsing |
| **`!`command`` injection** (Claude Code) | `/execute-task` can auto-inject current `STATUS.md`, git branch, worktree status before Claude reads the skill |
| **`allowed-tools`** | `/commit-push-pr` can pre-approve `Bash(git *)` — no per-command permission prompts |
| **`disable-model-invocation: true`** | These are explicit-only workflows — skill format lets you declare that intent |
| **Supporting scripts** | `/verify-batch-completion` can bundle a `scripts/verify.sh` that Claude executes |

| Command | Lines | Migration Notes |
|---------|-------|----------------|
| `pipeline.md` | 611 | `disable-model-invocation: true`, `arguments: [design-doc]`, inject `!`cat PIPELINE_STATE.md`` |
| `run-batch.md` | 701 | `arguments: [batch-id, feature-name]`, inject `!`cat BATCH_EXECUTION_PLAN.md`` |
| `run-plan.md` | 569 | `arguments: [feature-name, design-doc-path]` |
| `execute-task.md` | 547 | `arguments: [task-id, feature-name]`, inject `!`git worktree list``, heavy templates → `reference/` |
| `complete-task.md` | 544 | `arguments: [task-id, feature-name]`, report template → `reference/` |
| `create-workstream.md` | 535 | `arguments: [feature-name]`, scaffolding templates → `reference/` |
| `create-batch-execution-plan.md` | 829 | `arguments: [feature-name]`, batch plan templates → `reference/` |
| `create-task-ticket.md` | 798 | `arguments: [task-id, feature-name]`, ticket template → `reference/` |
| `create-task-spec.md` | 1,105 | `arguments: [batch-number, feature-name]`, spec templates → `reference/` (~400 lines extractable) |
| `commit-push-pr.md` | 302 | `disable-model-invocation: true`, `allowed-tools: Bash(git *) Bash(gh *)` |
| `setup-worktrees.md` | 369 | `arguments: [feature-name]`, `allowed-tools: Bash(git worktree *)` |
| `sync-worktree-status.md` | 374 | `arguments: [feature-name]`, inject `!`git worktree list`` |
| `verify-batch-completion.md` | 422 | `arguments: [batch-id, feature-name]`, bundle `scripts/verify.sh` |
| `update-claude-md.md` | 185 | Smallest command — minimal benefit but still consistent format |

**Total: 14 commands** — migrate to skill format with `disable-model-invocation: true`. No separate companion skill needed.

### Category B: Commands That Benefit from a Companion Skill

These commands contain heavy domain knowledge that other commands also need. Extract the shared knowledge into a skill; keep the command for the workflow.

**Pattern:** Command (slim workflow) + Skill (domain knowledge that loads when relevant)

| Command | Proposed Companion Skill | What Moves to Skill | What Stays in Command |
|---------|-------------------------|---------------------|----------------------|
| `spec.md` (833 lines) | `deepsecure-requirements` | DeepSecure-specific spec patterns, service boundary patterns, template structure | The 4-phase gated workflow (CLARIFY → SPECIFY → VALIDATE → OUTPUT) |
| `breakdown-design.md` (911 lines) | `deepsecure-architecture` | Path conventions, naming conventions, service boundaries table, common mistakes, dependency classification rules | The breakdown workflow steps, post-breakdown verification scripts |
| `review.md` (344 lines) | `code-review-patterns` | Five-axis definitions, severity labels, contract verification patterns, DeepSecure token/path rules | The review process flow, output format |
| `security-audit.md` (333 lines) | `security-patterns` | STRIDE template, OWASP checklist, token type table, secrets scan patterns, three-tier boundary system | The 7-phase audit workflow |
| `debug.md` (384 lines) | `debug-patterns` | DeepSecure error patterns (token types, async fixtures, MCP protocol), triage checklist template | The Stop-the-Line workflow |
| `explore-codebase.md` (286 lines) | `codebase-knowledge` | Directory structure, file conventions, service port mapping, existing component inventory | The 5-phase exploration workflow |
| `ship.md` (339 lines) | `deployment-patterns` | Smoke test scripts, rollback templates, health check URLs, docker commands | The 6-phase deployment workflow |
| `run-checks.md` (258 lines) | *(shares `deepsecure-architecture`)* | Tool commands, expected outputs | The check workflow phases |
| `create-design-doc.md` (758 lines) | *(shares `deepsecure-requirements`)* | Design doc section templates, DeepSecure conventions | The 7-step conversion workflow |

**Total: 9 commands** get companion skills; **7 unique new skills** created.

**Expected impact:** Each command shrinks by ~30-40% as domain knowledge moves to skills. Skills are loaded only when relevant, and shared across multiple commands.

### Category C: New Cross-Cutting Skills (Not Derived from Commands)

These are reusable knowledge bases that should auto-activate based on context, not require explicit invocation.

| Proposed Skill | Description | Auto-Triggers When | Content Source |
|---------------|-------------|-------------------|----------------|
| `deepsecure-auth` | Token types, JWT flows, challenge-response, common auth mistakes | Agent works on auth code, endpoints, or JWT | Extracted from `CLAUDE.md` (Token Types, Agent JWT Creation Flow, MCP Gateway Protocol) + `security-auditor.md` |
| `deepsecure-testing` | Test patterns, fixture conventions (`@pytest_asyncio.fixture`), marker usage, backend setup | Agent writes or modifies tests | Extracted from `CLAUDE.md` (Testing Strategy, Async Test Fixtures) + `test-engineer.md` |
| `deepsecure-project-conventions` | File path conventions, service ports, naming rules, import patterns | Agent creates new files or modules | Extracted from `CLAUDE.md` (Backend Service File Path Conventions, Key File Locations) |
| `worktree-workflow` | Worktree lifecycle, `$MAIN_REPO` pattern, status sync rules, merge point handling | Agent works in a git worktree | Extracted from `execute-task.md`, `complete-task.md`, `sync-worktree-status.md` |

**Total: 4 new skills** — pure domain knowledge, no workflow.

**Frontmatter configuration:**

```yaml
# These should auto-activate (agent invokes them, user doesn't)
disable-model-invocation: false   # Claude Code: agent can auto-invoke
user-invocable: false             # Claude Code: hide from / menu (background knowledge)
```

### Category D: Agent Definitions → Become Skills

The agent personas (`.cursor/agents/`) would benefit from the skills format because they should auto-activate when relevant context appears, rather than requiring the user or a command to explicitly inject them.

| Current Agent | Proposed Skill | Auto-Triggers When |
|--------------|---------------|-------------------|
| `agents/code-reviewer.md` (103 lines) | `reviewer-persona` | During `/review`, PR review, or when user asks for code review |
| `agents/test-engineer.md` (134 lines) | `test-engineer-persona` | During test analysis, coverage review, or test strategy discussion |
| `agents/security-auditor.md` (199 lines) | `security-auditor-persona` | During `/security-audit`, security-related changes, or auth code |

**Note:** The `.cursor/agents/` files continue to exist for Claude Code subagent dispatch (where `.claude/agents/name.md` is a separate concept from skills). The skills versions provide auto-discovery; the agent files provide subagent configuration.

**Claude Code approach:** In Claude Code, these can alternatively be skills with `context: fork` + `agent: general-purpose`, making them both auto-discoverable AND executable as subagents:

```yaml
---
name: security-auditor
description: Security engineer perspective for OWASP assessment, threat modeling, and token verification. Use when reviewing auth code, security changes, or conducting audits.
context: fork
agent: general-purpose
---
```

---

## Proposed Skill Directory Structure

```
.cursor/skills/                              # Cursor skills
├── deepsecure-architecture/
│   ├── SKILL.md                             # Path conventions, naming rules, service boundaries
│   └── reference/
│       ├── file-conventions.md              # Extracted from CLAUDE.md + breakdown-design.md
│       └── dependency-rules.md              # Parallel vs sequential classification
│
├── deepsecure-auth/
│   ├── SKILL.md                             # Token types, JWT flows, MCP protocol
│   └── reference/
│       ├── token-types.md                   # Full table from CLAUDE.md
│       └── agent-jwt-flow.md               # Challenge-response flow
│
├── deepsecure-testing/
│   ├── SKILL.md                             # Test patterns, markers, fixtures
│   └── reference/
│       └── test-organization.md             # Test directory structure, marker usage
│
├── deepsecure-project-conventions/
│   ├── SKILL.md                             # File paths, ports, naming
│   └── reference/
│       └── service-ports.md                 # Port mapping table
│
├── code-review-patterns/
│   ├── SKILL.md                             # Five-axis review, severity labels
│   └── reference/
│       └── review-checklist.md              # Contract verification patterns
│
├── security-patterns/
│   ├── SKILL.md                             # STRIDE, OWASP, secrets scan
│   └── reference/
│       ├── stride-template.md               # STRIDE analysis template
│       └── owasp-checklist.md               # OWASP Top 10 assessment
│
├── debug-patterns/
│   ├── SKILL.md                             # Triage checklist, error patterns
│   └── reference/
│       └── deepsecure-errors.md             # Token, async, MCP error patterns
│
├── deployment-patterns/
│   ├── SKILL.md                             # Smoke tests, rollback templates
│   └── reference/
│       └── smoke-tests.sh                   # Copy-paste smoke test script
│
├── worktree-workflow/
│   ├── SKILL.md                             # $MAIN_REPO pattern, sync rules
│   └── reference/
│       └── merge-point-handling.md          # Merge point lifecycle
│
├── reviewer-persona/
│   ├── SKILL.md                             # Staff engineer review persona
│   └── reference.md                         # DeepSecure-specific review patterns
│
├── test-engineer-persona/
│   ├── SKILL.md                             # QA specialist persona
│   └── reference.md                         # Prove-It pattern details
│
└── security-auditor-persona/
    ├── SKILL.md                             # Security engineer persona
    └── reference.md                         # Three-tier boundary system


.claude/skills/                              # Claude Code skills (mirrored + enhanced)
├── deepsecure-architecture/
│   ├── SKILL.md                             # Same content + Claude Code features
│   └── reference/
│       ├── file-conventions.md
│       └── dependency-rules.md
│
├── deepsecure-auth/
│   ├── SKILL.md                             # Same + !`command` injection for live checks
│   └── reference/
│       ├── token-types.md
│       └── agent-jwt-flow.md
│
│   ... (same structure as .cursor/skills/) ...
│
├── security-auditor-persona/
│   ├── SKILL.md                             # Enhanced: context: fork, agent: general-purpose
│   └── reference.md
│
└── (same remaining skills)
```

**File count:** 12 skills × ~3 files each = ~36 new files across both platforms.

---

## How Commands and Skills Coexist

### Loading Model

```
┌──────────────────────────────────────────────────────────────┐
│                     AGENT CONTEXT WINDOW                      │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ALWAYS LOADED (cheap, ~50 tokens each):                      │
│  ┌───────────────────────────────────────────────┐           │
│  │  Skill YAML frontmatter (name + description)   │           │
│  │  × 12 skills = ~600 tokens total               │           │
│  └───────────────────────────────────────────────┘           │
│                                                               │
│  LOADED ON /command INVOCATION:                               │
│  ┌───────────────────────────────────────────────┐           │
│  │  Command body (workflow instructions)           │           │
│  │  e.g., /review → review.md (~2,000 tokens)     │           │
│  └───────────────────────────────────────────────┘           │
│                                                               │
│  AUTO-LOADED when skill description matches context:          │
│  ┌───────────────────────────────────────────────┐           │
│  │  Skill SKILL.md body (domain knowledge)         │           │
│  │  e.g., code-review-patterns SKILL.md            │           │
│  └───────────────────────────────────────────────┘           │
│                                                               │
│  LOADED ON-DEMAND by agent (progressive disclosure):          │
│  ┌───────────────────────────────────────────────┐           │
│  │  Skill reference files                          │           │
│  │  e.g., reference/review-checklist.md            │           │
│  │  Only if agent decides it needs the detail       │           │
│  └───────────────────────────────────────────────┘           │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Example Flow: User Types `/review`

```
Step 1: COMMAND LOADS
        review.md (slim: ~2,000 tokens)
        Contains: workflow phases, output format, verification checklist
        Does NOT contain: five-axis definitions, DeepSecure patterns

Step 2: SKILL AUTO-MATCHES
        code-review-patterns/SKILL.md (~800 tokens)
        Contains: five-axis definitions, severity labels, contract patterns
        Triggered by: description mentions "code review"

Step 3: SKILL AUTO-MATCHES (conditional)
        deepsecure-auth/SKILL.md (~400 tokens)
        Contains: token type table, JWT flow
        Triggered by: reviewing auth-related code

Step 4: AGENT READS ON-DEMAND (if needed)
        reference/review-checklist.md (~600 tokens)
        Contains: detailed contract verification checklist
        Loaded only if agent decides it needs the fine-grained detail
```

### Example Flow: User Types `/execute-task WS-A1 my-feature`

```
Step 1: COMMAND LOADS
        execute-task.md (full: ~5,500 tokens)
        Contains: task execution workflow, $MAIN_REPO resolution

Step 2: SKILL AUTO-MATCHES (conditional)
        worktree-workflow/SKILL.md (~500 tokens)
        Triggered by: working in a git worktree context

Step 3: SKILL AUTO-MATCHES (conditional)
        deepsecure-architecture/SKILL.md (~600 tokens)
        Triggered by: creating/modifying files in deeptrail-control/ or deeptrail-gateway/
```

### Coexistence Rules

| Scenario | What Happens |
|----------|-------------|
| Same name in commands/ and skills/ | **Skills take precedence** (Claude Code); Cursor uses commands |
| Command invoked, matching skill exists | Both load — command provides workflow, skill provides knowledge |
| No command invoked, skill description matches | Skill auto-loads as background knowledge |
| Skill references a supporting file | File loaded only when agent reads it (progressive disclosure) |

---

## Token Budget Comparison

### Per-Invocation Cost

| Scenario | Today (Commands Only) | With Skills | Savings |
|----------|----------------------|-------------|---------|
| `/review` | ~3,400 tokens (full review.md) | ~2,000 (slim command) + ~800 (auto-matched skill) + ~600 (frontmatter scan) = ~3,400 | Neutral for single invocation |
| `/security-audit` | ~3,300 tokens (full security-audit.md) | ~2,000 (slim command) + ~800 (auto-matched skill) = ~2,800 | ~15% savings |
| `/breakdown-design` | ~9,100 tokens (full file) | ~6,000 (slim command) + ~600 (architecture skill if matched) = ~6,600 | ~27% savings |
| `/execute-task` (with auth code) | ~5,500 tokens | ~5,500 (command) + 0 (skills auto-match, shared knowledge already in CLAUDE.md) = ~5,500 | Neutral |

### Cross-Command Deduplication

The real value of skills emerges when **multiple commands share the same domain knowledge**.

| Duplicated Knowledge | Commands That Embed It Today | Skill That Replaces Duplication |
|---------------------|-----------------------------|---------------------------------|
| Token types table (User Token, Agent JWT, Internal Token) | `security-audit.md`, `review.md`, `debug.md`, `CLAUDE.md` | `deepsecure-auth` |
| File path conventions (app/ prefix, naming rules) | `breakdown-design.md`, `execute-task.md`, `create-task-ticket.md`, `complete-task.md`, `CLAUDE.md` | `deepsecure-architecture` |
| Service ports and health checks | `ship.md`, `run-checks.md`, `CLAUDE.md` | `deepsecure-project-conventions` |
| $MAIN_REPO worktree pattern | `execute-task.md`, `complete-task.md`, `sync-worktree-status.md`, `setup-worktrees.md` | `worktree-workflow` |
| OWASP checklist + STRIDE template | `security-audit.md`, `security-auditor.md` (agent) | `security-patterns` |
| Five-axis review definitions | `review.md`, `code-reviewer.md` (agent) | `code-review-patterns` |

**Estimated total deduplication:** ~3,000–5,000 tokens of knowledge currently duplicated across commands. With skills, this knowledge exists once and loads when any related command is invoked.

### Session-Level Impact

| Metric | Today | With Skills |
|--------|-------|-------------|
| **Frontmatter overhead** (always in context) | 0 tokens | ~600 tokens (12 skills × ~50 each) |
| **Average command size** | ~546 tokens (12,571 / 23) | ~380 tokens (commands ~30% slimmer) |
| **Domain knowledge loaded per invocation** | Full duplicate in each command | Shared, loaded once per session |
| **Cross-invocation reuse** | None (each command is independent) | Skill content persists across turns (Claude Code) |

---

## Recommended Migration Order

Prioritize by deduplication impact (how many commands share the knowledge) and risk (how critical the knowledge is if lost).

### Phase 1: High-Impact, High-Deduplication (Do First)

| Priority | Skill | Why First | Shared By | Est. Effort |
|----------|-------|-----------|-----------|-------------|
| 1 | `deepsecure-auth` | Highest duplication — token types are in CLAUDE.md, security-auditor.md, security-audit.md, review.md, debug.md | 5+ commands | S (< 1hr) |
| 2 | `deepsecure-architecture` | Path conventions duplicated in breakdown-design, execute-task, create-task-ticket, complete-task, create-task-spec | 5+ commands | M (1-2hr) |
| 3 | `worktree-workflow` | Complex knowledge duplicated across execute-task, complete-task, sync-worktree-status, setup-worktrees | 4 commands | S (< 1hr) |

### Phase 2: Review & Security Skills (Do Second)

| Priority | Skill | Why | Shared By | Est. Effort |
|----------|-------|-----|-----------|-------------|
| 4 | `code-review-patterns` | Enables slimming 3 review-related commands | review, security-audit, commit-push-pr | S (< 1hr) |
| 5 | `security-patterns` | STRIDE/OWASP templates shared between command and agent | security-audit, security-auditor agent | S (< 1hr) |
| 6 | `debug-patterns` | Error patterns shared between debug command and CLAUDE.md | debug, execute-task | S (< 1hr) |

### Phase 3: Agent Persona Conversion (Do Third)

| Priority | Skill | Why | Source | Est. Effort |
|----------|-------|-----|--------|-------------|
| 7 | `reviewer-persona` | Auto-discovery during reviews | code-reviewer.md agent | S (< 1hr) |
| 8 | `test-engineer-persona` | Auto-discovery during test work | test-engineer.md agent | S (< 1hr) |
| 9 | `security-auditor-persona` | Auto-discovery during security work | security-auditor.md agent | S (< 1hr) |

### Phase 4: Remaining Knowledge Skills (Do Last)

| Priority | Skill | Why Last | Shared By | Est. Effort |
|----------|-------|----------|-----------|-------------|
| 10 | `deepsecure-testing` | Lower duplication — mostly in CLAUDE.md | CLAUDE.md, test-engineer agent | S (< 1hr) |
| 11 | `deepsecure-project-conventions` | Lower duplication | CLAUDE.md, ship, run-checks | S (< 1hr) |
| 12 | `deployment-patterns` | Only used by ship command currently | ship | S (< 1hr) |
| 13 | `deepsecure-requirements` | Only used by spec + create-design-doc | spec, create-design-doc | S (< 1hr) |
| 14 | `codebase-knowledge` | Only used by explore-codebase | explore-codebase | S (< 1hr) |

**Total estimated effort:** ~14 skills, mostly S-complexity = ~8-12 hours of work.

---

## Generating Skills for Both Platforms

Since this project supports both Cursor and Claude Code, each skill should be generated in both locations with platform-appropriate enhancements.

### Dual-Platform Generation Workflow

```
                    ┌─────────────────┐
                    │  Canonical Skill │
                    │  (platform-      │
                    │   agnostic core) │
                    └────────┬────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
    ┌──────────────────┐     ┌──────────────────┐
    │  .cursor/skills/  │     │  .claude/skills/  │
    │  name/SKILL.md    │     │  name/SKILL.md    │
    │  (base format)    │     │  (enhanced)       │
    │                   │     │  + context: fork   │
    │                   │     │  + !`command`      │
    │                   │     │  + allowed-tools   │
    │                   │     │  + $ARGUMENTS      │
    └──────────────────┘     └──────────────────┘
```

### Step-by-Step Generation Process

**Step 1: Write the canonical SKILL.md** (platform-agnostic)

```yaml
---
name: deepsecure-auth
description: >-
  DeepSecure authentication patterns: token types (User Token, Agent JWT,
  Internal Token), Ed25519 challenge-response flow, MCP Gateway protocol.
  Use when working on auth code, JWT validation, or API endpoint security.
---

# DeepSecure Authentication Patterns

## Token Types

| Token Type | How to Obtain | Used For |
|------------|---------------|----------|
| User Token | POST /api/v1/auth/login → .token | User-facing endpoints |
| Agent JWT  | Ed25519 challenge-response → .access_token | Agent-to-Control APIs |
| Internal   | docker-compose env var | Gateway-to-Control |

## Common Mistakes
...

## References
- For full JWT creation flow, see [reference/agent-jwt-flow.md](reference/agent-jwt-flow.md)
- For token verification table by endpoint, see [reference/token-types.md](reference/token-types.md)
```

**Step 2: Copy to `.cursor/skills/`** (verbatim)

```bash
mkdir -p .cursor/skills/deepsecure-auth/reference
cp canonical/SKILL.md .cursor/skills/deepsecure-auth/SKILL.md
cp canonical/reference/* .cursor/skills/deepsecure-auth/reference/
```

**Step 3: Enhance for `.claude/skills/`** (add Claude Code features)

```yaml
---
name: deepsecure-auth
description: >-
  DeepSecure authentication patterns: token types (User Token, Agent JWT,
  Internal Token), Ed25519 challenge-response flow, MCP Gateway protocol.
  Use when working on auth code, JWT validation, or API endpoint security.
user-invocable: false
paths: "**/*auth*,**/*token*,**/*jwt*,**/*security*"
---

# DeepSecure Authentication Patterns

## Current Auth Endpoints
!`grep -rn "@router" deeptrail-control/app/api/v1/endpoints/ 2>/dev/null | grep -i auth | head -20`

## Token Types
...
```

Key enhancements for Claude Code version:
- `user-invocable: false` — background knowledge, not a user action
- `paths` — only auto-activate when working on auth-related files
- `!`command`` — inject live codebase state into the skill

**Step 4: For agent persona skills, add `context: fork`**

```yaml
# .claude/skills/security-auditor-persona/SKILL.md
---
name: security-auditor-persona
description: >-
  Security engineer perspective for OWASP assessment, threat modeling,
  and token verification. Use when reviewing auth code or security changes.
context: fork
agent: general-purpose
allowed-tools: Bash(grep *) Bash(rg *) Read Grep
---

# Security Auditor

You are a security engineer conducting a focused security review...
```

### Automation Script (Future)

A generation script can automate the dual-platform process:

```bash
#!/bin/bash
# generate-skills.sh — Create skills in both .cursor/ and .claude/

SKILL_NAME=$1
CURSOR_DIR=".cursor/skills/$SKILL_NAME"
CLAUDE_DIR=".claude/skills/$SKILL_NAME"

# Create directories
mkdir -p "$CURSOR_DIR/reference" "$CLAUDE_DIR/reference"

# Copy canonical SKILL.md to Cursor (verbatim)
cp "skills-canonical/$SKILL_NAME/SKILL.md" "$CURSOR_DIR/SKILL.md"
cp -r "skills-canonical/$SKILL_NAME/reference/" "$CURSOR_DIR/reference/"

# Generate Claude Code enhanced version
python3 scripts/enhance-for-claude-code.py \
    "skills-canonical/$SKILL_NAME/SKILL.md" \
    "$CLAUDE_DIR/SKILL.md"
cp -r "skills-canonical/$SKILL_NAME/reference/" "$CLAUDE_DIR/reference/"

echo "Generated $SKILL_NAME for both platforms"
```

### Keeping Platforms in Sync

| Approach | Pros | Cons |
|----------|------|------|
| **Manual mirror** (current approach for commands) | Simple, no tooling | Drift risk, manual effort |
| **Canonical + enhance script** | Single source of truth, automated | Requires maintenance of enhance script |
| **Symlinks for shared files** | Zero drift for reference files | Platform-specific SKILL.md still separate |
| **Build step in Makefile** | Integrated with dev workflow | Adds build dependency |

**Recommended:** Canonical + enhance script for SKILL.md, symlinks for reference files.

```makefile
# Makefile addition
sync-skills:
	@for skill in .cursor/skills/*/; do \
		name=$$(basename $$skill); \
		rsync -a --exclude='SKILL.md' "$$skill" ".claude/skills/$$name/"; \
	done
	@echo "Synced reference files. SKILL.md files managed separately."
```

---

## Concrete Example: `code-review-and-quality` Skill (Claude Code)

A working skill modeled on [Addy Osmani's agent-skills](https://github.com/addyosmani/agent-skills) `code-review-and-quality` skill has been created at `.claude/skills/code-review-and-quality/`. This demonstrates the full anatomy of a production-grade skill.

### How Osmani's Skill Pack Works

Osmani's repo separates **commands** (thin entry points) from **skills** (full workflows):

```
# .claude/commands/review.md — the thin command (13 lines!)
---
description: Conduct a five-axis code review
---
Invoke the agent-skills:code-review-and-quality skill.
Review the current changes across all five axes...
```

```
# skills/code-review-and-quality/SKILL.md — the full skill (300+ lines)
---
name: code-review-and-quality
description: Conducts multi-axis code review. Use before merging any change...
---
[Full five-axis review process, anti-rationalization tables, red flags, etc.]
```

The command is just a trigger that delegates to the skill. The skill contains the actual workflow. The skill can also auto-activate when Claude detects you're reviewing code.

### Our DeepSecure Equivalent

```
.claude/skills/code-review-and-quality/
├── SKILL.md                              # 287 lines — full review workflow
├── reference/
│   ├── deepsecure-conventions.md         # 59 lines — file paths, ports, naming
│   └── auth-patterns.md                  # 66 lines — token types, JWT flow, MCP protocol
```

**Total: 412 lines across 3 files.** Compare to our current `review.md` command at 344 lines (monolithic, all in context always).

### Anatomy: What Makes This a "Production-Grade" Skill

Following Osmani's pattern, every skill has these sections:

```
┌─────────────────────────────────────────────────┐
│  SKILL.md                                       │
│                                                 │
│  ┌─ Frontmatter ─────────────────────────────┐  │
│  │ name: code-review-and-quality              │  │
│  │ description: Conducts five-axis code       │  │
│  │   review for DeepSecure... Use when...     │  │
│  └────────────────────────────────────────────┘  │
│                                                 │
│  Overview         → What, approval standard     │
│  When to Use      → Triggering conditions       │
│  Dynamic Context  → !`git diff` injected live   │  ← Claude Code exclusive
│  Five-Axis Review → Step-by-step per axis       │
│    └─ DS-specific  → Token table, file paths    │
│  Change Sizing    → ~100 / ~300 / ~1000 rule    │
│  Review Process   → 5 steps with severity labels│
│  Multi-Agent      → code-reviewer, test-eng...  │
│  Review Checklist → Copy-paste template         │
│  See Also         → Links to reference/ files   │  ← Progressive disclosure
│  Rationalizations → 6 excuses + rebuttals       │
│  Red Flags        → 10 warning signs            │
│  Verification     → Evidence requirements       │
└─────────────────────────────────────────────────┘
```

### Key Differences from Osmani's Generic Version

| Aspect | Osmani's (generic) | Ours (DeepSecure-specific) |
|--------|-------------------|---------------------------|
| Axis 3: Architecture | Generic module boundaries | DeepSecure service boundaries, `app/` prefix convention, file path table |
| Axis 4: Security | Generic input validation | Token type verification table (User Token / Agent JWT / Internal), MCP protocol |
| Reference files | `references/security-checklist.md` (generic OWASP) | `reference/auth-patterns.md` (Ed25519 flow, MCP initialize, token mistakes) |
| Dynamic context | None | `!`git diff --stat HEAD~1`` injected before Claude reads the skill |
| Multi-agent | Generic "Model A writes, Model B reviews" | Specific agent files: `code-reviewer.md`, `test-engineer.md`, `security-auditor.md` |

### How the Slash Command Would Work

If we create a thin command at `.claude/commands/review.md`, it becomes a 10-line entry point:

```yaml
---
description: Conduct a five-axis code review for DeepSecure
---

Invoke the code-review-and-quality skill.

Review the current changes across all five axes:
1. Correctness — matches spec, edge cases, tests
2. Readability — clear names, straightforward logic
3. Architecture — DeepSecure service boundaries, correct file paths
4. Security — correct token types per endpoint, no secrets
5. Performance — no N+1, no unbounded operations

Categorize findings as Critical, Important, Nit, or FYI.
Output the structured review checklist from the skill.
```

The command is cheap (~100 tokens). The skill loads automatically because its description matches. Reference files load only if auth code or path conventions need checking.

---

## Concrete Example: `run-tests` Skill (Claude Code)

A working example skill has been created at `.claude/skills/run-tests/` to demonstrate how the skill format improves on flat commands.

### Directory Structure

```
.claude/skills/run-tests/
├── SKILL.md                         # Main skill (86 lines)
├── reference/
│   └── debug-test-failures.md       # Loaded on-demand (100 lines)
└── scripts/
    └── coverage-gaps.sh             # Bundled executable script
```

### What Makes This Better Than a Flat Command

**1. Dynamic context injection (`!`command``):**

The SKILL.md contains:
```yaml
!`python -c "import sys; print(f'Python {sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null`
```
```
!`git diff --name-only HEAD~1 2>/dev/null | grep '\.py$' | head -20`
```

Before Claude reads the skill, these commands **execute and their output replaces the placeholders**. So Claude sees:
```
Python 3.11
=== Recently modified Python files ===
deepsecure/_core/vault_client.py
deepsecure/commands/agent.py
```

No flat command can do this. The agent would have to run these commands itself, consuming a tool-call turn.

**2. Named arguments (`$scope`):**

```yaml
arguments: [scope]
argument-hint: "[scope: all | changed | file-path]"
```

User types: `/run-tests changed`
Claude receives: `$scope` = `changed` — no free-text parsing needed.

**3. Tool pre-approval (`allowed-tools`):**

```yaml
allowed-tools: Bash(pytest *) Bash(python -m pytest *) Bash(git diff *)
```

Claude can run `pytest -v` without asking the user for permission each time.

**4. Progressive disclosure (reference files):**

The SKILL.md says:
```markdown
For detailed debugging patterns, see [reference/debug-test-failures.md](reference/debug-test-failures.md)
```

The 100-line debug reference is **only loaded when Claude decides it needs it** (e.g., tests are failing). If tests pass, those 100 lines never enter the context window.

**5. Bundled scripts:**

```bash
# Claude can execute the coverage gap analysis
bash ${CLAUDE_SKILL_DIR}/scripts/coverage-gaps.sh
```

The script is bundled with the skill, versioned alongside it, and uses `${CLAUDE_SKILL_DIR}` so it resolves correctly regardless of working directory.

### How to Invoke

```
# User-triggered (explicit)
/run-tests all
/run-tests changed
/run-tests tests/_core/test_vault_client.py

# Auto-triggered (Claude matches description)
User: "Can you run the tests for the vault client?"
Claude: (sees description matches → loads skill → runs pytest)
```

### Comparison: Flat Command vs Skill

| Feature | Flat `run-checks.md` command | `run-tests` skill |
|---------|------------------------------|-------------------|
| Lines always in context | 258 (entire file) | ~86 (SKILL.md only) |
| Dynamic context | None — agent runs commands itself | `!`command`` pre-injects Python version, changed files |
| Failure debugging | Inline in same 258 lines | Separate `reference/` file — loaded only on failures |
| Parameter handling | Free-text parsing | `$scope` named argument |
| Tool permissions | Agent asks per-command | Pre-approved via `allowed-tools` |
| Bundled scripts | Not supported | `scripts/coverage-gaps.sh` bundled and executable |
| Auto-discovery | Never — must type `/run-checks` | Can auto-activate when user mentions tests |

---

## Implementation Notes

### Migration Checklist Per Skill

- [ ] Write canonical SKILL.md with YAML frontmatter
- [ ] Create reference files for heavy content (>100 lines)
- [ ] Copy to `.cursor/skills/name/`
- [ ] Enhance and copy to `.claude/skills/name/`
- [ ] Slim the source command (remove extracted domain knowledge)
- [ ] Add "For [topic] patterns, this command uses the `name` skill" note to command
- [ ] Verify command still works without the skill (graceful degradation)
- [ ] Test auto-discovery in both platforms

### Graceful Degradation

Commands must work even if skills aren't loaded (e.g., user has a fresh clone without skills). The command should contain enough context to function, with skills providing enhanced knowledge:

```markdown
# In review.md (slim version):

## Five-Axis Review

Review across: Correctness, Readability, Architecture, Security, Performance.

> For detailed axis definitions and DeepSecure-specific patterns,
> see the `code-review-patterns` skill.
```

### What NOT to Extract

- **Workflow steps** — keep in commands (they define the "how")
- **Output format templates** — keep in commands (tied to the workflow)
- **Verification checklists** — keep in commands (tied to the specific command's purpose)
- **Anti-rationalization tables** — keep in commands (specific to each workflow's failure modes)

### What TO Extract

- **Domain knowledge** — move to skills (shared across commands)
- **Reference tables** — move to skill reference files (loaded on demand)
- **Templates for analysis** — move to skills (reusable structures like STRIDE, OWASP)
- **Project conventions** — move to skills (apply broadly, not to one workflow)

---

## Changelog

| Date | Change |
|------|--------|
| May 2026 | Initial skill migration plan created |
| May 2026 | Added dual-platform generation (Cursor + Claude Code) |
| May 2026 | Documented Claude Code exclusive features (context: fork, !command, allowed-tools, etc.) |
