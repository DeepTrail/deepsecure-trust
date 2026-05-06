# Background Coding Agents & Software Factories — Landscape Research

> Last updated: May 3, 2026

Companies are building their own internal background coding agents — autonomous systems that run in the cloud, execute tasks like pull requests, code reviews, and migrations without a human at the terminal. This document maps the ecosystem as of mid-2026.

---

## Table of Contents

- [Internal Agents at Major Companies](#internal-agents-at-major-companies)
- [Deep Dives](#deep-dives)
- [Software Factory Startups & Platforms](#software-factory-startups--platforms)
- [Security & Governance](#security--governance)
- [Emerging Concepts](#emerging-concepts)
- [Background Agents Summit (May 6–7, 2026)](#background-agents-summit)
- [Sources](#sources)

---

## Internal Agents at Major Companies

| Company | Agent Name | Key Metric | Infrastructure | Trigger |
|---------|-----------|------------|---------------|---------|
| Ramp | Inspect | 50%+ of merged PRs | Modal Sandboxes + OpenCode | Slack, Web, Chrome Extension |
| Stripe | Minions | 1,000+ PRs merged/week | Fork of Block's Goose, devboxes | Slack, CLI, Web |
| HubSpot | Crucible | 7,000+ AI PRs merged | Kubernetes Jobs + Docker | GitHub, Internal UI |
| Coinbase | Forge | 5% of all merged PRs, 10x cycle time | Custom infra | Slack, GitHub, Linear |
| Uber | Minion + suite | 65-72% AI-generated code | Internal platform | Multiple interfaces |
| Google | Agent Smith | Restricted due to demand | Internal (Antigravity platform) | Async, mobile-friendly |
| Cloudflare | iMARS stack | 93% R&D adoption, 8,700 MRs/week | Own platform (Workers, D1) | Internal tooling |
| DocuSign | Elf | Handles repetitive eng tasks | Custom (multi-model routing) | Jira, Slack, GitHub |
| Shopify | Roast | AI coding harness | Structured scaffolding | Internal workflows |
| Block | Goose (open-source) | ~1,000 internal engineers | Open-source, any LLM | CLI, IDE |
| Spotify | Honk | 1,500+ AI PRs merged | Fleet management + Backstage | Fleetshift |
| Harvey | Spectre | Event-driven autonomous | Durable runs, isolated sandboxes | Incidents, Slack, automation |
| Monzo | — | 3,000+ microservices | Encoded conventions into LLM skills | Internal tooling |

---

## Deep Dives

### Ramp — Inspect

**Architecture:**
- Sandboxed VMs on Modal with full dev environment (Vite, Postgres, Temporal, Redis, RabbitMQ)
- OpenCode as the coding agent (server-first architecture, typed SDK, plugin system)
- Cloudflare Durable Objects + Agents SDK for real-time streaming and per-session SQLite
- Filesystem snapshots rebuilt every 30 minutes for near-instant startup

**Key features:**
- Multiplayer sessions — any number of people can collaborate in one session
- Chrome extension for visual edits by non-engineers (using React internals, not screenshots)
- Voice input support
- Agent can spawn child sessions for parallel work across repositories
- Sandbox warming starts when user begins typing (before hitting enter)

**Impact:** 50%+ of merged PRs. 80% of Inspect itself is written by Inspect. Adoption was organic — no mandates.

**Sources:** [builders.ramp.com/post/why-we-built-our-background-agent](https://builders.ramp.com/post/why-we-built-our-background-agent) | [modal.com/blog/how-ramp-built-a-full-context-background-coding-agent-on-modal](https://modal.com/blog/how-ramp-built-a-full-context-background-coding-agent-on-modal)

---

### Stripe — Minions

**Architecture:**
- Built on a fork of Block's open-source Goose agent
- Devboxes spin up in 10 seconds
- Access to 400+ internal tools via an MCP server called "Toolshed"
- Handles proprietary Ruby with Sorbet typing, internal-only libraries

**Why in-house:** Hundreds of millions of lines of code, proprietary type system, internal libraries that general-purpose AI tools can't handle.

**Impact:** 1,000+ PRs merged per week with zero human-written code. Published February 2026.

**Source:** [stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents)

---

### Harvey — Spectre

**Architecture:**
- Event-driven autonomous agent platform (not just prompt-triggered)
- Durable run records — each execution is persistent, trackable, resumable
- Isolated sandboxes with strictly scoped repository access and short-lived credentials
- Multiple entry points: Slack, web, CLI, scheduled automation

**Key insight:** Agent-accelerated productivity shifted bottlenecks from implementation to coordination, review, and prioritization. Building toward a "company world model" — a live picture of what's happening and what needs to happen next.

**Source:** [harvey.ai/blog/building-spectre-internal-collaborative-cloud-agent-platform](https://www.harvey.ai/blog/building-spectre-internal-collaborative-cloud-agent-platform)

---

### Cloudflare — iMARS

**Architecture:**
- Internal MCP Agent/Server Rollout Squad (iMARS) tiger team
- Built entirely on their own platform (Workers, D1, Durable Objects)
- 3,683 active users across 295 teams

**Impact:** Merged requests increased from ~5,600/week to 8,700/week. 93% of R&D organization using AI coding tools. Dogfooding their own infrastructure.

**Source:** [blog.cloudflare.com/internal-ai-engineering-stack](https://blog.cloudflare.com/internal-ai-engineering-stack/)

---

### Uber — Agent-Ready Developer Platform

**Architecture:**
- Multi-agent suite: Minion (background agent), Shepherd (large-scale migrations), uReview (code review), Autocover (5,000+ unit tests/month), Code Inbox (smart PR routing)
- 84% developer adoption as of March 2026
- 65-72% of code is AI-generated in IDE-based tools

**Challenges:** AI-related costs increased 6x since 2024. Token cost optimization is a priority.

**Source:** [newsletter.pragmaticengineer.com/p/how-uber-uses-ai-for-development](https://newsletter.pragmaticengineer.com/p/how-uber-uses-ai-for-development)

---

### Spotify — Honk (Agent Fleet)

**Architecture:**
- Extends Spotify's Fleet Management system for automated code transformations
- Uses Claude Code for complex multi-file edits
- Integrated with Backstage via Fleetshift
- Plan-Act-Conclude architecture with strong feedback loops

**Impact:** 1,500+ AI PRs merged. Automated migration of ~1,800 data pipelines across three frameworks, saving 10 engineering weeks. Published a 4-part blog series on context engineering, feedback loops, and dataset migrations.

**Source:** [engineering.atspotify.com/2025/11/spotifys-background-coding-agent-part-1](https://engineering.atspotify.com/2025/11/spotifys-background-coding-agent-part-1)

---

### HubSpot — Crucible

**Architecture:**
- Kubernetes-based platform with Claude Code pre-installed
- Docker images with HubSpot developer tooling
- Agent executions map 1:1 to Kubernetes Job resources
- Leverages existing K8s infra (1M+ builds/day, ~3,000 EC2 instances)

**Why self-hosted:** Heavy usage of internal tools and libraries made replicating their developer environment externally challenging.

**Impact:** 7,000+ fully AI-generated PRs merged. 50,000+ human-authored PRs code-reviewed. Later migrated code review to internal Java framework (Aviator) for latency/cost reasons.

**Source:** [product.hubspot.com/blog/cloud-coding-agents-at-hubspot](https://product.hubspot.com/blog/cloud-coding-agents-at-hubspot)

---

### Coinbase — Forge

**Architecture:**
- Initially called Claudebot/Cloudbot, now Forge
- Triggered from Slack, GitHub, or Linear
- Linear used as structured source of truth for context
- Built by just two engineers initially

**Impact:** 5% of all merged PRs. 10x improvement in PR cycle time (reduced from ~150 hours to ~15 hours).

**Source:** [linear.app/customers/coinbase](https://www.linear.app/customers/coinbase)

---

### Monzo — Regulated Banking Environment

**Architecture:**
- 3,000+ microservices with standardized templates
- Encoded backend engineering conventions into LLM skills
- AI tools conform to Monzo's service structure via encoded conventions

**Key principle:** "Implementation is no longer the bottleneck of the software delivery lifecycle." Focus shifts to preserving trust and compliance at speed in a regulated environment.

**Source:** [qconlondon.com/presentation/mar2026/move-fast-dont-break-trust](http://www.qconlondon.com/presentation/mar2026/move-fast-dont-break-trust-shipping-constantly-humans-and-beyond)

---

### StrongDM — Dark Software Factory

**Philosophy:**
- Code must not be written by humans
- Code must not be reviewed by humans
- Target: $1,000/day token spend per engineer to demonstrate factory maturity

**Key innovation:** Replaced traditional tests with "scenarios" — end-to-end user stories stored outside the codebase as holdout sets. Replaced boolean success with "satisfaction": probabilistic fraction of trajectories that likely satisfy users.

**Open-source:** Attractor agent — graph-based pipeline with nodes (Implement, Identify, Optimize, Validate) connected by natural-language edges.

**Source:** [factory.strongdm.ai](https://factory.strongdm.ai/)

---

### Google — Agent Smith

Built on internal "Antigravity" agentic coding platform. Became so popular that access had to be restricted. Works asynchronously; employees can check in and give instructions via mobile phones. Sergey Brin emphasized agents will play a significant role at Google in 2026.

---

### DocuSign — Elf

Autonomous coding agent for well-defined, repetitive engineering tasks. Integrates with GitHub, Jira, and Slack. Multi-model routing: Claude, Gemini, and Codex routed based on task complexity.

**Source:** [docusign.com/blog/how-we-built-an-autonomous-coding-agent-for-repetitive-engineering-tasks](https://www.docusign.com/blog/how-we-built-an-autonomous-coding-agent-for-repetitive-engineering-tasks)

---

## Software Factory Startups & Platforms

| Company | Product | Approach | Stage |
|---------|---------|----------|-------|
| Factory.ai | Factory / Droids | Agent-native dev platform. IDE + Slack + CLI + Web. | $150M Series C, $1.5B valuation |
| Replicas | Replicas.dev | Background agents in sandboxed VMs. Claude/Codex. Triggered from Slack/Linear/GitHub. | YC P26, 20+ YC startup customers |
| 8090 | Software Factory | AI-native SDLC control plane: Requirements, Blueprints, Work Orders, Tests, Feedback. | Growth |
| Refact.ai | Refact | Open-source, self-hosted AI coding agent. Fine-tunable to specific codebases. | Growth |
| Amazon/AWS | Kiro + Frontier Agents | Autonomous agents that operate for hours/days. Multi-modal input (text, diagrams). | Launch (2025-2026) |
| OpenAI | Codex | Cloud agent with computer-use, 90+ plugins, devbox connections, memory. | GA (April 2026) |
| Ona | Ona Platform + Veto | Agent infrastructure with kernel-level security enforcement. | Growth |

---

## Security & Governance

### Ona — Veto (Kernel-Level Enforcement)

Linux Security Module (LSM) that enforces at the syscall level — below the agent and userspace. Agents cannot unload the module, modify its configuration, or observe whether an action was flagged.

- **Executable Deny List:** Blocks by SHA-256 content hash (rename/symlink resistant, no TOCTOU vulnerabilities)
- **Datawall (coming):** Detects confidential data leaving the environment over the network, including through TLS
- **Modes:** Block or Audit per deny list entry

**Why kernel-level:** Traditional runtime security operates above the agent, making it observable and evadable. AI agents can reason about security boundaries and actively work around them.

**Source:** [ona.com/stories/introducing-veto-security-for-the-next-era-of-software](https://ona.com/stories/introducing-veto-security-for-the-next-era-of-software)

### Three Layers of Runtime Security (nono / Always Further)

1. **Enforce** — Prevent unauthorized actions at execution time
2. **Attest** — Prove cryptographically what happened during a run
3. **Decide** — Policy engine for real-time authorization decisions

### Why Prompt-Level Guardrails Fail

Agents can reason about and circumvent prompt-level restrictions. Enforcement must move below the agent layer to syscall, hardware, and network level where the agent has no visibility or control.

---

## Emerging Concepts

### Context is the New Code (Tessl / Patrick Debois)

The thesis: context — not code — is the primary bottleneck for AI agents. While teams have spent decades perfecting code lifecycles (version control, testing, CI/CD), context for AI agents remains poorly managed.

**The Context Development Lifecycle (CDLC):**
1. **Generate** — Create context from code, libraries, conversations, PRs
2. **Evaluate** — Test context quality through CI pipelines and evals
3. **Distribute** — Version and share context across teams via registries
4. **Observe** — Feed observations back into improving context

**The Context Flywheel:** Running CDLC repeatedly creates compounding advantage. Better context → better output → better signals → better context.

**Source:** [tessl.io/blog/context-development-lifecycle-better-context-for-ai-coding-agents](https://tessl.io/blog/context-development-lifecycle-better-context-for-ai-coding-agents/)

### Dark Factories

Fully autonomous software production with no human in the loop. StrongDM operationalizes this with "scenarios" replacing tests and "satisfaction" replacing boolean metrics. AWS presenting "Beyond Agentic Engineering" at the summit.

### Harness Engineering (OpenAI)

The work of encoding engineering best practices so agents can drive development autonomously. The scaffolding, tools, and context that transform a raw LLM into a reliable coding agent for a specific codebase.

---

## Background Agents Summit

**Event:** Virtual, May 6–7, 2026 (free)  
**Host:** Ona  
**URL:** [background-agents.com/summit](https://background-agents.com/summit)

### Day 1 — Infrastructure & Context

| Time (PT) | Session | Speaker | Company |
|-----------|---------|---------|---------|
| 9:00 AM | Opening Keynote | Will McMullen, Philipp Pietsch | Ona |
| 9:40 AM | Building Minions: agents on a 30M-line codebase | Alistair Gray | Stripe |
| 10:20 AM | GitHub Agentic Workflows | Peli de Halleux | GitHub Next |
| 11:00 AM | From Assisted to Delegated: Cloudflare's AI Engineering Stack | Rajesh Bhatia | Cloudflare |
| 11:55 AM | Building a company-internal background agent system | Cole Murray | Open Inspect |
| 12:35 PM | Background Agents for Genomics | Xiucheng Quek | Genentech |
| 1:15 PM | Why prompt-level guardrails fail for AI agents | Leo Di Donato, Lorenzo Fontana | — |
| 1:55 PM | Context is the New Code | Patrick Debois | Tessl |

### Day 2 — Security, Scale & Adoption

| Time (PT) | Session | Speaker | Company |
|-----------|---------|---------|---------|
| 9:40 AM | Spectre: Harvey's collaborative cloud agent platform | Joey Wang | Harvey |
| 10:20 AM | TBA | Lawrence Jones | incident.io |
| 11:00 AM | What I learned building a software factory in public | Zacharias Malguitou | software-factory.dev |
| 11:55 AM | Enforce, Attest, Decide — three layers of runtime security | Stephen Parkinson | nono / Always Further |
| 12:35 PM | Backgrounding the Toil: Uber's Agent-Ready Dev Platform | Nikhil Ramakrishnan | Uber |
| 1:15 PM | Dark Factories: Beyond Agentic Engineering | Shardul Vaidya | AWS |
| 1:55 PM | Enabling AI Tools Without Losing Control | Suhail Patel | Monzo |

### Summit Tracks

1. **Infrastructure** — Agents on large codebases, sandboxes & dev environments, harness & context engineering, agent fleets & orchestration
2. **Security** — Identity & permissions for agents, sandboxing & blast radius, runtime guardrails, reviewing agent code at scale
3. **Leadership** — Adoption inside engineering orgs, measuring agent ROI, the new SDLC, software factories

---

## Common Architecture Patterns

### Execution
- Sandboxed VMs or containers with full dev environments
- Near-instant startup via filesystem snapshots or pre-built images
- Isolated per-session to prevent contention
- Key providers: Modal, Kubernetes, custom solutions

### Integration
- Deep wiring into internal tools: CI/CD, observability (Sentry, Datadog), feature flags (LaunchDarkly)
- MCP servers for tool access (Stripe has 400+)
- Project management integration (Linear, Jira, GitHub Issues)

### Interface
- Multi-client: Slack (most common trigger), Web UI, CLI, Chrome extensions, GitHub/Linear
- Multiplayer support emerging (Ramp, Harvey)
- Voice and mobile access (Ramp, Google)

### Verification
- Agents run tests and CI before opening PRs
- Visual verification via browser automation (screenshots, VNC)
- Observability integration for backend verification
- Feedback loops for iterative correction

---

## Key Takeaways

1. **Custom beats generic.** Companies with large proprietary codebases find general-purpose tools insufficient. Custom agents deeply integrated with internal tooling yield dramatically higher adoption.

2. **The bottleneck is shifting.** Implementation is no longer the constraint — coordination, review, trust, and compliance are the new bottlenecks (Harvey, Monzo).

3. **Security must be below the agent.** Prompt-level guardrails fail because agents reason about boundaries. Kernel-level enforcement (Ona/Veto) represents the emerging standard.

4. **Context is the new moat.** Teams that systematically develop, version, and distribute context will build compounding advantages competitors can't replicate (Tessl).

5. **Dark factories are coming.** StrongDM and AWS are pushing toward fully autonomous software production with no humans in the loop — measuring "satisfaction" rather than test pass rates.

6. **Economics matter.** Uber's 6x cost increase and StrongDM's $1K/day target show that token spend optimization and ROI measurement are critical operational concerns.

---

## Sources

- [builders.ramp.com/post/why-we-built-our-background-agent](https://builders.ramp.com/post/why-we-built-our-background-agent)
- [modal.com/blog/how-ramp-built-a-full-context-background-coding-agent-on-modal](https://modal.com/blog/how-ramp-built-a-full-context-background-coding-agent-on-modal)
- [stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents)
- [harvey.ai/blog/building-spectre-internal-collaborative-cloud-agent-platform](https://www.harvey.ai/blog/building-spectre-internal-collaborative-cloud-agent-platform)
- [engineering.atspotify.com/2025/11/spotifys-background-coding-agent-part-1](https://engineering.atspotify.com/2025/11/spotifys-background-coding-agent-part-1)
- [product.hubspot.com/blog/cloud-coding-agents-at-hubspot](https://product.hubspot.com/blog/cloud-coding-agents-at-hubspot)
- [blog.cloudflare.com/internal-ai-engineering-stack](https://blog.cloudflare.com/internal-ai-engineering-stack/)
- [newsletter.pragmaticengineer.com/p/how-uber-uses-ai-for-development](https://newsletter.pragmaticengineer.com/p/how-uber-uses-ai-for-development)
- [linear.app/customers/coinbase](https://www.linear.app/customers/coinbase)
- [factory.strongdm.ai](https://factory.strongdm.ai/)
- [ona.com/stories/introducing-veto-security-for-the-next-era-of-software](https://ona.com/stories/introducing-veto-security-for-the-next-era-of-software)
- [tessl.io/blog/context-development-lifecycle-better-context-for-ai-coding-agents](https://tessl.io/blog/context-development-lifecycle-better-context-for-ai-coding-agents/)
- [background-agents.com/summit](https://background-agents.com/summit)
- [docusign.com/blog/how-we-built-an-autonomous-coding-agent-for-repetitive-engineering-tasks](https://www.docusign.com/blog/how-we-built-an-autonomous-coding-agent-for-repetitive-engineering-tasks)
- [incident.io/blog/ai-developer-tools](https://incident.io/blog/ai-developer-tools)
