# AFK Developer Workflow — End-to-End Guide

> **For:** Mahendra Kutare, sole developer on DeepSecure
> **After:** Full implementation of [`docs/AFK_WORKFLOWS.md`](AFK_WORKFLOWS.md) and [`docs/spec/afk-workflow-enablement-spec.md`](spec/afk-workflow-enablement-spec.md)
> **Architecture:** Claude Code (execution) + Hermes Agent (orchestration) + DeepSecure (identity)

---

## Tools on Your Phone

You will track and control AFK work from your phone using these apps:

| App | What You See | What You Can Do | When You Use It |
|-----|-------------|-----------------|-----------------|
| **Claude iOS App** | Push notifications for completion, failure, permission blocks, cost alerts | Approve permissions via Remote Control, read agent output, respond to stuck agents | Primary — always-on AFK monitoring |
| **Slack** (personal DM) | AFK event messages: `[info] AFK Complete`, `[warning] Circuit breaker OPEN`, `[urgent] Cost 80%` | Read notification history, share status with team if needed | Secondary — reliable fallback, message history |
| **Telegram** | Same AFK event messages as Slack | Read notifications | Tertiary — backup channel |
| **GitHub Mobile** | PR notifications, CI status, review comments from AFK agents and Routines | Review PRs, read agent-generated review comments, merge from phone | Morning review — check what agents produced overnight |
| **GCP Console / AWS Console** (mobile apps) | Cloud Run Job status, ECS task logs, Cloud Scheduler execution history | Check if cloud-deployed AFK container ran, view logs, trigger manual runs | Cloud AFK monitoring — when running on GCP/AWS |

### Notification Priority and What Each Means

```
Claude App push (primary)
  ├── "AFK Complete — 7/10 tasks done"          → Morning: review and merge
  ├── "Permission blocked — needs approval"      → Now: open Claude App, approve or deny
  ├── "Circuit breaker OPEN — 3 iterations, no progress" → Now: check what's stuck
  ├── "Cost alert — 80% of Agent SDK credits"    → Soon: check claude.ai/settings
  └── "Agent SDK credits exhausted"              → Now: enable overflow or pause AFK

Slack personal DM (secondary)
  ├── Same messages as above                     → Reliable history, searchable
  └── Hermes multi-platform (Phase 5+)           → 22 channels including Slack threads

GitHub Mobile
  ├── "PR opened: [afk] Fix auth endpoint"       → Review when ready
  ├── "Review comment from Claude"               → Read Routine's nightly PR review
  └── "CI passed/failed on afk branch"           → Check if AFK commits are clean

macOS native (local only)
  └── Banner notification                        → Only when at laptop
```

---

## Your Daily Workflow

### Phase 1: Morning Review (30 minutes)

You wake up. Your phone has notifications from overnight AFK runs.

**On your phone (before opening laptop):**

1. **Claude App** — Check push notifications
   - "AFK Complete — 8/10 tasks done, cost: $12.40" → Good, open laptop when ready
   - "Circuit breaker OPEN" → Something's stuck, read the message for details

2. **GitHub Mobile** — Check PRs
   - AFK agent opened PRs overnight? Skim the diff summaries
   - Routine left PR review comments at 11pm? Read them

3. **Slack DM** — Scroll notification history for anything you missed

**On your laptop:**

```bash
# Pull overnight work
git pull

# What happened?
cat docs/workstreams/auth-improvements/ralph_progress.json | jq '.metadata'
# {
#   "total_iterations": 8,
#   "total_cost_usd": 12.40,
#   "last_iteration_at": "2026-06-10T02:15:00Z",
#   "circuit_breaker": "CLOSED"
# }

# Read the auto-generated comprehension report
cat reports/afk-summary-2026-06-10.md
# What changed: 6 tasks completed (WS-A1 through WS-A6)
# Why: Auth endpoint + delegation flow + tests
# What was surprising: pytest fixture needed cleanup (added to learnings)
# What failed: WS-A7 blocked — missing dependency on WS-B1

# Review the actual code (comprehension debt guardrail — never skip this)
git log --oneline -8
git diff main...HEAD

# Review cost
cat .afk/cost-log.txt
# Iteration 1 cost: $1.82 at 2026-06-10T22:15:00Z
# Iteration 2 cost: $1.34 at 2026-06-10T22:28:00Z
# ...
```

**Merge with comprehension:** Leave at least one review comment on the PR confirming you understand the changes. Then merge. AFK PRs are never auto-merged.

---

### Phase 2: Plan the Day (15 minutes)

**Option A: You decide what's next**

```bash
# Start a Claude session
claude

# Use the planning pipeline
> /run-plan next-feature docs/design/next-feature.md
```

**Option B: Let triage discover work**

```bash
claude

> /triage
# Reads: GitHub issues, failing CI, Linear tickets, stale ralph_progress.json
# Outputs: prioritized work list to ralph-prompt.md
# You review and approve the list before anything executes
```

---

### Phase 3: Daytime — Active Work with AFK Assist

You're at your laptop. Use the right AFK mode for the task:

#### Quick single task — `/goal` (10-30 minutes)

```bash
# Fix a specific bug, then walk away
claude -p "/goal all tests in tests/e2e/test_agent_auth.py pass \
  and no other test file is modified, or stop after 20 turns" \
  --max-budget-usd 3 --permission-mode auto < /dev/null
```

- A separate Haiku model checks after each turn: "are all tests passing?"
- When condition is met → agent stops → push notification on your phone
- You review the diff when you're ready

**Track from phone:** Claude App push notification when done or stuck.

#### Parallel multi-service work — Dynamic Workflows (30-60 minutes)

You need control plane and gateway changes simultaneously:

```bash
claude

> /effort ultracode
```

Claude spawns 2-4 subagents, each in its own git worktree (no file collisions):
- Subagent 1: control plane changes in `.claude/worktrees/afk-agent-1/`
- Subagent 2: gateway changes in `.claude/worktrees/afk-agent-2/`

An adversarial review subagent checks each one's output before commit (maker/checker split).

**Track from phone:** Claude App shows session progress. Permission prompts forwarded to phone via Remote Control.

#### Background session — Agent View (hours)

```bash
# Launch a task to background
claude --bg --name "fix-vault-tests" "Fix all failing tests in deeptrail-control/tests/vault/"

# Launch another
claude --bg --name "update-docs" "Update API docs to match current endpoints"

# Check on them
claude agents
# Shows: fix-vault-tests [Working *], update-docs [Working *]

# Go do something else — sessions survive terminal close and macOS sleep
```

**Track from phone:** Claude App push notifications for each session's completion or failure.

---

### Phase 4: Evening — Launch Overnight AFK

You've got a planned workstream with an approved `PIPELINE_STATE.md`. One command starts the overnight run.

#### Option A: Run locally (laptop stays open or sleeps)

```bash
./scripts/ralph.sh auth-improvements 10
```

Close your laptop. Agent View supervisor keeps sessions alive through macOS sleep.

#### Option B: Run on cloud (laptop can shut down)

```bash
# Deploy and trigger on GCP
./scripts/deploy-afk-cloud.sh auth-improvements 10

# Or trigger an existing Cloud Run Job
gcloud run jobs execute afk-workstream
```

Same `ralph.sh` runs in a container — clones the repo, checks out the branch, iterates autonomously. No laptop needed.

#### Option C: Schedule via Routines (no manual trigger)

Already configured — runs every night on Anthropic's cloud:

```bash
# One-time setup (already done)
claude
> /schedule daily at 10pm: run /run-batch on the next pending batch in auth-improvements
```

**What happens overnight (you're asleep):**

```
10:00 PM  Ralph iteration 1 starts
          → claude --print with fresh context
          → wraps /run-batch B3
          → implements tasks in isolated worktree
          → runs tests + lint + /goal evaluator
          → commits, updates ralph_progress.json
          → pushes to remote
10:18 PM  Iteration 1 complete
          [no notification — still working]

10:19 PM  Iteration 2 starts (completely fresh context)
          → reads ralph_progress.json to see what's done
          → picks up next incomplete task
          ...
10:35 PM  Iteration 2 complete

11:00 PM  Routine fires: "review all open PRs on dev"
          → Posts review comments on GitHub PRs
          → [GitHub Mobile notification]

12:15 AM  Iteration 5 complete

 2:00 AM  Routine fires: "run bandit + safety, open PR if issues"
          → Security scan clean, no PR needed

 2:30 AM  Iteration 7 → agent outputs <promise>COMPLETE</promise>
          → Ralph loop exits early (sentinel detection)
          → notify.sh fires:
            - Claude App push: "AFK Complete — 7/10 tasks done"
            - Slack DM: "[info] AFK Complete — auth-improvements — 7 tasks, $11.20"
          → afk-summary report auto-generated
          → Circuit breaker stays CLOSED

 6:00 AM  You wake up, check phone → notifications waiting
```

---

### Phase 5: Weekend / Multi-Day AFK

For larger workstreams spanning multiple days:

**Friday evening:**

```bash
# Cloud-deployed — runs all weekend
./scripts/deploy-afk-cloud.sh p7-aws-integration 30

# Or with Hermes orchestration (Phase 5+):
# Hermes triggers Ralph on a schedule, reviews output between runs,
# decides whether to continue or escalate to you
```

**Saturday/Sunday — check phone occasionally:**

| What You Check | App | Frequency |
|---------------|-----|-----------|
| Push notifications — completion, failure, cost | Claude App | As they arrive |
| Notification history, cost accumulation | Slack DM | 1-2x per day |
| PRs opened by agents | GitHub Mobile | Morning |
| Cloud Run Job status / logs | GCP Console app | If something seems stuck |
| Agent SDK credit consumption | `claude.ai/settings` (browser) | Once per day |

**Monday morning:**

```bash
git pull
# 15-20 commits from weekend runs

# Read the summary reports
ls reports/afk-summary-2026-06-1*.md
cat reports/afk-summary-2026-06-12.md
cat reports/afk-summary-2026-06-13.md

# Comprehension review (30-60 min for weekend's work)
git diff main...HEAD --stat   # Overview of what changed
git log --oneline -20         # Read commit messages
# Then review the actual code for anything surprising

# Merge
gh pr merge --squash
```

---

## What Each Tool Does in the Stack

### Execution Layer (Claude Code)

| Tool | What It Does | When You Use It |
|------|-------------|-----------------|
| `ralph.sh` | Core AFK loop — fresh context per iteration, wraps `/run-batch`, JSON progress, circuit breaker, cost tracking | Overnight workstreams |
| `/goal` | Single-task AFK — separate Haiku evaluator checks completion each turn | Quick tasks during the day |
| Dynamic Workflows | Parallel subagents in isolated worktrees — `/effort ultracode` | Multi-service parallel work |
| Agent View | `claude agents` dashboard — supervisor for background sessions, sleep resilience | Managing multiple background tasks |
| `claude --bg` | Launch session to background | Long tasks you don't want to watch |
| `claude respawn --all` | Restart sessions after crash/reboot | Recovery |
| Routines / `/schedule` | Cloud-based scheduled agents — run on Anthropic infra, no laptop needed | Nightly PR review, security scan, docs sync |
| Remote Control / `claude --remote` | Start local, continue from phone via Claude iOS app | Approving permissions while away |
| Hooks (`.claude/hooks.json`) | Auto-format on edit, context injection on session start, notification on permission prompt, security gate on bash | Always-on guardrails |
| Skills (`.claude/commands/`) | `/triage`, `/babysit-pr`, `/autofix-pr`, `/security-scan`, `/verify-app`, `/afk`, `/afk-summary` | Specific AFK operations |

### Orchestration Layer (Hermes Agent — Phase 5+)

| Tool | What It Does | When You Use It |
|------|-------------|-----------------|
| Hermes Observer | Schedules AFK jobs, sends notifications across 22 platforms, remembers cross-session learnings | Always-on background orchestrator |
| Hermes Invoker | Triggers Ralph loop, reviews output, decides continue vs escalate | Automated multi-run management |
| Hermes Manager | Full lifecycle: plan → decompose → spawn agents → review → merge (gated by DeepSecure tokens) | Advanced autonomous operation |
| Cross-session memory | FTS5-indexed knowledge base of what worked, what failed, what to avoid | Replaces `.afk/learnings.md` |
| `/handoff` | Transfer session between models without context loss | Switch to cheaper model for simple tasks |

### Identity Layer (DeepSecure — Phase 6, Optional)

| Tool | What It Does | When You Use It |
|------|-------------|-----------------|
| `afk-identity.sh` | Bootstrap agent identity, request scoped delegation_token | Cloud-deployed agents with DeepSecure auth |
| `identity-check.sh` hook | Verify token validity before each AFK iteration, auto-refresh on expiry | Every iteration (when configured) |
| Audit trail | Every tool call from every AFK agent logged in DeepSecure Control Plane | Post-run review, compliance |
| Token revocation | Immediately stop any agent by revoking its delegation_token | Emergency kill switch |

### Monitoring and Mobile Tools

| Tool | Platform | Primary Use |
|------|----------|-------------|
| **Claude iOS App** | iPhone | Push notifications, Remote Control (approve permissions, read output) |
| **Slack** | iPhone / Desktop | Notification history, searchable AFK event log, personal DM channel |
| **Telegram** | iPhone / Desktop | Backup notification channel |
| **GitHub Mobile** | iPhone | PR reviews, CI status, agent-generated comments |
| **GCP Console App** | iPhone | Cloud Run Job status, container logs |
| **AWS Console App** | iPhone | ECS task status, CloudWatch logs |
| `claude.ai/settings` | Browser (phone/desktop) | Agent SDK credit usage, overflow billing toggle |

---

## Notification Setup (One-Time)

```bash
# 1. Claude App push notifications
# Install Claude iOS app → sign in → enable notifications
# Start local sessions with: claude --remote
# Push notifications are automatic for permission prompts, completion, errors

# 2. Slack personal DM
# Create a Slack webhook for your personal DM channel
# Set in shell profile (~/.zshrc):
export DEEPSECURE_SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# 3. Telegram (optional backup)
export DEEPSECURE_TELEGRAM_TOKEN="your-bot-token"
export DEEPSECURE_TELEGRAM_CHAT_ID="your-chat-id"

# 4. Test notifications
./scripts/notify.sh "Test" "AFK notification working" info
# → Should appear on: Claude App, Slack DM, Telegram, macOS notification
```

---

## Cost Tracking from Your Phone

| What | Where to Check | Alert Threshold |
|------|---------------|-----------------|
| Per-iteration cost | Slack DM (included in completion message) | $5/iteration default (`--max-budget-usd`) |
| Cumulative run cost | `.afk/cost-log.txt` (in repo) or Slack message history | Review in morning |
| Agent SDK credit pool | `claude.ai/settings` (browser on phone) | Alert at 80% via `notify.sh` |
| Overflow billing | `claude.ai/settings` → enable/disable | Toggle OFF to hard-stop on exhaustion |
| Cloud compute cost | GCP Console app → Billing | Set GCP budget alerts separately |

---

## Quick Reference — Common Scenarios

| I want to... | Command | Track from phone via |
|--------------|---------|---------------------|
| Fix a bug and walk away | `claude -p "/goal <condition>" --max-budget-usd 3 < /dev/null` | Claude App push |
| Run overnight workstream (local) | `./scripts/ralph.sh <workstream> 10` | Claude App + Slack DM |
| Run overnight workstream (cloud) | `./scripts/deploy-afk-cloud.sh <workstream> 10` | Slack DM + GCP Console |
| Schedule nightly PR review | `/schedule daily at 11pm: review all open PRs on dev` | GitHub Mobile |
| Schedule nightly security scan | `/schedule daily at 2am: run bandit and safety check` | Slack DM |
| Check what agents are doing | `claude agents` (laptop) or Claude App (phone) | Claude App |
| Approve a permission from phone | Claude App → Remote Control → approve/deny | Claude App |
| Stop a runaway agent | Revoke delegation_token (DeepSecure) or `claude kill <id>` | N/A (laptop) |
| Check overnight cost | Slack DM history or `claude.ai/settings` | Slack + browser |
| Review agent's code | `git pull && git diff main...HEAD` (laptop) or GitHub Mobile (phone) | GitHub Mobile |
| Discover next work | `/triage` (laptop) | N/A (laptop) |
| See overnight summary | `cat reports/afk-summary-*.md` (laptop) | N/A (laptop) |

---

## What Changes in Your Role

| Before AFK | After AFK |
|-----------|-----------|
| You write code line by line | You write specs and review agent output |
| You run tests manually | Agents run tests, you read results |
| You're blocked when away from keyboard | Work continues while you sleep, eat, exercise |
| One task at a time | Multiple agents working in parallel |
| You decide what to work on each morning | `/triage` discovers and prioritizes work from GitHub/Linear/CI |
| You review your own code | Adversarial verifier agent reviews before commit |
| Context lost between sessions | Hermes remembers cross-session learnings |
| Static API keys for everything | DeepSecure ephemeral tokens with audit trail (dog-fooding) |
| Weekends = no progress | Cloud agents + Routines continue working |

**Your irreducible responsibilities (never delegated to agents):**
1. Write and approve specs/plans (`PIPELINE_STATE.md`)
2. Review and merge AFK PRs (comprehension debt guardrail)
3. Make architectural and design decisions
4. Monitor cost and credit consumption
5. Maintain comprehension of the codebase — read what agents produce
