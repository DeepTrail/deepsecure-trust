# claude_celery_aws.md


## Notes from call with Mahendra


Claude / Codex / Gemini / OpenClaw / Future Skill Aggregator A
   <—> 
DeepSecure / DeepTrail

Types of orchestration:
  - API
  - CLI

USE CASE: use Tool X to perform Action Y as Teammate Z at Customer Q
  - X: LinkedIn 
  - Y: Send Connection Request
  - Z: Mahendra
  - Q: DeepTrail

ULTIMATE GOAL: Mahendra sends Bob a LinkedIn Connection Request with the exact words that Scout specified.

IDEAL CASE:
  - we run on Ubuntu box in AWS, we are a Python / Django process, we have root
  - “For this next Atomic Action of LinkedIn Connect, load in creds for Mahendra @ DeepTrail” as and API call 1
  - Run ULTIMATE GOAL above as API call 2

FALLBACK CASE:
  - when we onboard Mahendra @ DeepTrail and he pays
  - we spin up a dedicated*** Ubuntu box in AWS for Mahendra @ DeeTrail
  - use DeepSecure as normal to manage credential for Mahendra there
  - Run ULTIMATE GOAL above as API call 2
  - *** this is a lot more expensive and cumbersome to manage at scale, so not preferred

QUESTION:
  - when we first ask Mahendra: “Can we connect your LinkedIn?”
  - Mahendra says “yep”
  - browser-based OAuth, Mahendra clicks “OK”
  - can this be done on our main web-app?
  - can I avoid having to pipe a full-blown remote desktop or browser?
  - so this becomes almost like a LastPass with access keys?

Two types of connectors:
  - Central IT Managed: example is CRM
  - Personal Managed: example LinkedIn , like personal phone vs corporate phone
  - am I asking the immediate user ONLY, or ALSO NEED IT’S APPROVAL?


---

---

# Prompt:

Give me the full list of all GTM related tools that Claude Code and/or Claude Cowork supports as Connectors, Plugins, or built in. Basically everything that can be controlled by you.

(after implementing Apollo MCP as a POC)

---

---

# Response:

Here's the complete picture of GTM tools available to me, organized by what's confirmed vs. available to connect:

---

## Currently Connected & Active

### Apollo (MCP — fully operational)
All of these tools are live right now:
- **Contacts**: search, create, update
- **Accounts**: create, update
- **People**: match, bulk_match
- **Organizations**: enrich, bulk_enrich, job_postings
- **Email Campaigns**: search, add contacts, remove/stop contacts
- **Email Accounts**: index
- **Mixed Search**: people, companies

---

## Built-in Skills (available via `/skill`)
| Skill | What it does |
|---|---|
| `marketing:email-sequence` | Full drip/nurture sequences with timing & branching |
| `marketing:campaign-plan` | Campaign brief, audience, messaging, content calendar |
| `marketing:competitive-brief` | Competitive positioning, battlecards, gaps |
| `marketing:brand-review` | Copy review vs. brand voice + severity flags |
| `marketing:performance-report` | KPI analysis, trend spotting, recommendations |
| `marketing:seo-audit` | Keywords, on-page, tech issues, competitor gaps |
| `marketing:draft-content` | Blog, social, email, landing pages, press releases |
| `marketing:content-creation` | Channel-specific content with SEO |

---

## Available to Connect via Cowork Marketplace
(Not currently connected in your environment, but installable)

**CRM & Sales**
- HubSpot (CRM, automation, pipelines)
- Salesforce (enterprise CRM)
- Pipedrive

**Marketing Analytics**
- Amplitude (US + EU)
- Supermetrics (multi-channel rollup)
- Google Analytics
- Mixpanel, Segment

**Email & Automation**
- Klaviyo
- Gmail
- Mailchimp
- Intercom

**Content & SEO**
- Ahrefs
- SimilarWeb
- Notion
- Canva, Figma

**Communication**
- Slack
- Google Calendar

**Other Sales Engagement**
- Outreach, Salesloft (via custom MCP)
- LinkedIn (via custom MCP)

---

**Note:** The MCP registry search returned no results in your current session — this may mean your Cowork account has limited connectors enabled. You can check what's available to install in Cowork's connector settings.

---

---

# Prompt:

I want you to research all these tools in depth and add a table to `[this file]` summarizing them. The table should also include columns on whether each tool can be invoked & controlled via the CLI, whether it can be invoked & controlled via the API, and  a column that shows different auth types.

My goal is to create a central orchestrator that manages multiple instances of Claude Code / Cowork that run within our Celery workers (currently Ubuntu, but could be something else if necessary) each one used by a different human teammate. I want to understand what's possible here. So think about anything else I missed that would be beneficial to capture in this table.

---

---

# Response:

## GTM Tool Integration Matrix

This doc catalogs every Go-To-Market tool available via Claude Code and Cowork, evaluated specifically for headless, multi-user orchestration on Ubuntu Celery workers. The orchestrator dispatches one Claude Code instance per human teammate; each instance runs inside its own Celery task with isolated credentials. The tables below answer three questions for each tool:

1. Can it be invoked programmatically from CLI (`claude -p`) or the Agent SDK?
2. Can it run fully headless on a server with no browser?
3. Can different Celery workers use different user credentials?

### A. Connected MCP Plugins (Cowork Marketplace)

These are officially available in the Cowork marketplace. Each is an MCP server that Claude Code can call when configured via `--mcp-config` or the SDK `mcpServers` option.

| Tool            | Auth Type          | CLI Invocable | SDK Invocable | Headless-Ready                                           | Access Scope      | Multi-User Cred Isolation                                    | Setup Notes                                                                         |
|-----------------|--------------------|---------------|---------------|----------------------------------------------------------|-------------------|--------------------------------------------------------------|-------------------------------------------------------------------------------------|
| HubSpot         | OAuth 2.0          | Yes           | Yes           | Requires initial browser                                 | Read-Write        | Yes, via per-worker OAuth tokens                             | Token refresh is automatic after initial grant; store refresh tokens per user in DB |
| Amplitude (US)  | API Key            | Yes           | Yes           | Yes                                                      | Read / Read-Write | Yes, via env var per worker                                  | Separate API keys per project; US endpoint                                          |
| Amplitude (EU)  | API Key            | Yes           | Yes           | Yes                                                      | Read / Read-Write | Yes, via env var per worker                                  | EU endpoint; different base URL                                                     |
| Klaviyo         | API Key            | Yes           | Yes           | Yes                                                      | Read-Write        | Yes, via env var per worker                                  | Private API key gives full access; use per-user keys for isolation                  |
| Slack           | Bot Token          | Yes           | Yes           | Yes                                                      | Read-Write        | Yes, via env var per worker                                  | One bot token per workspace; `xoxb-` tokens are fully headless                      |
| Figma           | OAuth2 / PAT       | Yes           | Yes           | PAT is headless; OAuth requires initial browser          | Read-Write        | Yes, via env var per worker                                  | Personal Access Tokens recommended for headless; never expire                       |
| Notion          | OAuth2 / Bearer    | Yes           | Yes           | Bearer token is headless; OAuth requires initial browser | Read-Write        | Yes, via env var per worker                                  | Internal integrations use bearer tokens; fully headless                             |
| Ahrefs          | API Key            | Yes           | Yes           | Yes                                                      | Read-only         | Yes, via env var per worker                                  | Strict rate limits; credits consumed per query                                      |
| Gmail           | OAuth 2.0          | Yes           | Yes           | Service Account workaround                               | Read-Write        | Yes, via per-worker service account or stored refresh tokens | Use Google service accounts with domain-wide delegation for headless                |
| Canva           | OAuth 2.0          | Yes           | Yes           | Requires initial browser                                 | Read-Write        | Yes, via per-worker OAuth tokens                             | No service account option; must complete browser grant per user                     |
| Google Calendar | OAuth 2.0          | Yes           | Yes           | Service Account workaround                               | Read-Write        | Yes, via per-worker service account or stored refresh tokens | Same pattern as Gmail; service accounts with domain-wide delegation                 |
| SimilarWeb      | API Key            | Yes           | Yes           | Yes                                                      | Read-only         | Yes, via env var per worker                                  | Enterprise API key required; expensive                                              |
| Supermetrics    | OAuth2 / API Token | Yes           | Yes           | API Token is headless; OAuth requires initial browser    | Read-only         | Yes, via env var per worker                                  | API token access preferred for headless                                             |

### B. Active Custom MCP (Already Connected)

These are custom MCP servers already wired into the current environment. The orchestrator can reuse them directly.

| Tool      | Auth Type | CLI Invocable | SDK Invocable | Headless-Ready | Access Scope | Multi-User Cred Isolation   | Available Operations                                                                                                                                                                                               | Setup Notes                                                                                           |
|-----------|-----------|---------------|---------------|----------------|--------------|-----------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| Apollo.io | API Key   | Yes           | Yes           | Yes            | Full CRUD    | Yes, via env var per worker | contacts search/create/update, accounts create/update, people match/bulk_match, org enrich/bulk_enrich, org job_postings, emailer_campaigns search/add_contacts/remove_contacts, email_accounts list, user profile | Single API key per Apollo workspace; different teammates can share key or use separate workspace keys |

### C. Not-in-Marketplace Tools (Require Custom MCP Server or Agent SDK Custom Tools)

These tools are not available as Cowork marketplace plugins. Using them requires building a custom MCP server or wiring them as Agent SDK custom tools. The orchestrator team must implement and maintain these integrations.

| Tool       | Auth Type                   | CLI Invocable              | SDK Invocable              | Headless-Ready                                                       | Access Scope                        | Multi-User Cred Isolation                     | Setup Notes                                                                    |
|------------|-----------------------------|----------------------------|----------------------------|----------------------------------------------------------------------|-------------------------------------|-----------------------------------------------|--------------------------------------------------------------------------------|
| Salesforce | OAuth 2.0                   | Partial (needs custom MCP) | Partial (needs custom MCP) | JWT Bearer flow is headless; standard OAuth requires initial browser | Full CRUD                           | Yes, via per-worker connected app credentials | Use JWT Bearer Token flow with X.509 cert for headless; pre-authorize per user |
| Pipedrive  | API Key / OAuth2            | Partial (needs custom MCP) | Partial (needs custom MCP) | API Key is headless; OAuth requires initial browser                  | Full CRUD                           | Yes, via env var per worker                   | API token available in user settings; one token per Pipedrive user             |
| Mixpanel   | API Token / Service Account | Partial (needs custom MCP) | Partial (needs custom MCP) | Yes                                                                  | Read (analytics) / Write (tracking) | Yes, via env var per worker                   | Service account tokens are project-scoped and fully headless                   |
| Segment    | API Token                   | Partial (needs custom MCP) | Partial (needs custom MCP) | Yes                                                                  | Write (tracking) / Read (config)    | Yes, via env var per worker                   | Write keys are source-scoped; separate key per source                          |
| Mailchimp  | API Key                     | Partial (needs custom MCP) | Partial (needs custom MCP) | Yes                                                                  | Full CRUD                           | Yes, via env var per worker                   | One API key per Mailchimp account; `dc` prefix required in base URL            |
| Intercom   | OAuth 2.0 / Access Token    | Partial (needs custom MCP) | Partial (needs custom MCP) | Access Token is headless; OAuth requires initial browser             | Full CRUD                           | Yes, via env var per worker                   | Personal Access Tokens available for headless; scoped per workspace            |

### D. Built-in Marketing Skills (No Auth Required)

These are Claude Code built-in skills invoked via slash commands or skill names. They require no external authentication, no MCP configuration, and no API keys. They run entirely within Claude’s reasoning and produce text/structured output.

| Skill Name                     | CLI Invocable | SDK Invocable | Headless-Ready | Output Type     | Multi-User Isolation       | Purpose                                                       |
|--------------------------------|---------------|---------------|----------------|-----------------|----------------------------|---------------------------------------------------------------|
| `marketing:email-sequence`     | Yes           | Yes           | Yes            | Structured text | Yes, inherent per-instance | Multi-email drip sequences with copy, timing, branching       |
| `marketing:campaign-plan`      | Yes           | Yes           | Yes            | Structured text | Yes, inherent per-instance | Full campaign brief with objectives, audience, calendar       |
| `marketing:competitive-brief`  | Yes           | Yes           | Yes            | Structured text | Yes, inherent per-instance | Positioning and messaging comparison, battlecards             |
| `marketing:brand-review`       | Yes           | Yes           | Yes            | Structured text | Yes, inherent per-instance | Content review against brand voice and style guide            |
| `marketing:performance-report` | Yes           | Yes           | Yes            | Structured text | Yes, inherent per-instance | Marketing performance report with metrics and recommendations |
| `marketing:seo-audit`          | Yes           | Yes           | Yes            | Structured text | Yes, inherent per-instance | Keyword research, on-page analysis, content gaps              |
| `marketing:draft-content`      | Yes           | Yes           | Yes            | Structured text | Yes, inherent per-instance | Blog posts, social media, email, landing pages                |
| `marketing:content-creation`   | Yes           | Yes           | Yes            | Structured text | Yes, inherent per-instance | Channel-specific marketing content with SEO                   |

### Headless Deployment Notes

These notes are critical for running Claude Code instances inside Celery workers on Ubuntu servers with no display or browser.

* **OAuth 2.0 tools are the primary headless obstacle.** Any tool that uses OAuth 2.0 as its sole auth method requires an initial browser-based authorization flow. This cannot be done from a headless Celery worker. The workaround is to complete the OAuth grant once per user from a machine with a browser, capture the refresh token, and store it in the database. The Celery worker then uses the stored refresh token to obtain access tokens programmatically. This is the pattern already used by the project’s Gmail integration (see `gmail.md`).

* **API-key-based tools are fully headless from day one.** Apollo.io, Klaviyo, Ahrefs, Amplitude, SimilarWeb, Mailchimp, and Segment all use API keys that can be injected as environment variables. No browser interaction is ever needed.

* **Bot tokens and Personal Access Tokens are headless.** Slack bot tokens (`xoxb-`), Figma PATs, Notion internal integration tokens, and Intercom access tokens are all generated once via a web dashboard and then used as static credentials. They never require browser-based refresh.

* **Google services have a headless path via service accounts.** For Gmail and Google Calendar, create a Google Cloud service account with domain-wide delegation. This allows the Celery worker to impersonate any user in the Google Workspace domain without any browser flow. This is the recommended production pattern for multi-user orchestration.

* **Salesforce has a headless path via JWT Bearer flow.** Create a Connected App with a X.509 certificate. Pre-authorize each user. The Celery worker can then obtain access tokens using the JWT assertion flow without any browser interaction.

* **MCP config must be passed per invocation.** Each `claude -p` call or SDK `query()` call must include its own `--mcp-config` pointing to a JSON file (or in-memory config for SDK) that specifies which MCP servers to connect and their credentials. Do not rely on a shared `~/.claude/` config across workers.

* **Rate limits are per-upstream-account, not per-worker.** If multiple Celery workers share the same API key (e.g., one Apollo workspace key), they share the same rate limit budget. The orchestrator must implement rate limiting at the Django/Celery level to avoid 429 errors. Use `CELERY_WORKER_PREFETCH_MULTIPLIER = 1` and add per-tool concurrency limits via Celery task routing or a distributed rate limiter (e.g., Redis token bucket).

* **`CELERY_WORKER_MAX_TASKS_PER_CHILD = 1` is correct for Claude Code tasks.** Each Claude Code invocation is a long-running subprocess that should get a fresh worker process. This prevents memory leaks and ensures clean subprocess environments.

* **Built-in marketing skills are the safest starting point.** They require zero external configuration, zero auth, and are guaranteed headless. Use them to validate the orchestrator pipeline before wiring up MCP tools.

### Credential Management for Multi-User Workers

The orchestrator manages one Claude Code instance per human teammate, each running inside a Celery task. Each instance needs its own credentials for the external tools it uses.

#### Strategy 1: Per-worker environment variable injection (API-key tools)

For each Celery task, the orchestrator:

1. Looks up the teammate’s credentials from the database (encrypted at rest).
2. Builds a subprocess environment dictionary with the teammate’s API keys.
3. Passes the environment to the Claude Code subprocess.

```text
# Example: Worker for teammate "alice" calling Apollo + Klaviyo
APOLLO_API_KEY=alice_apollo_key_here
KLAVIYO_API_KEY=alice_klaviyo_key_here
```

Each Celery task gets its own subprocess environment. The Django process itself never mutates its global `os.environ`. This is subprocess-scoped injection, consistent with the env-var schema described in Section 12.

#### Strategy 2: Per-worker MCP config files (MCP plugin tools)

For MCP-based tools, each Celery task must generate a temporary MCP config JSON file containing the teammate’s credentials:

```json
{
  "mcpServers": {
    "hubspot": {
      "command": "npx",
      "args": ["-y", "@anthropic/hubspot-mcp"],
      "env": {
        "HUBSPOT_ACCESS_TOKEN": "alice_hubspot_token_here"
      }
    },
    "apollo": {
      "command": "npx",
      "args": ["-y", "@apollo/mcp-server"],
      "env": {
        "APOLLO_API_KEY": "alice_apollo_key_here"
      }
    }
  }
}
```

The orchestrator writes this file to a temporary location, passes it via `--mcp-config /tmp/mcp_alice_<task_id>.json`, and deletes it after the task completes. For the Agent SDK, pass the config as an in-memory dictionary to the `mcpServers` parameter.

#### Strategy 3: Per-worker stored OAuth tokens (OAuth tools)

For OAuth-based tools (HubSpot, Gmail, Google Calendar, Canva):

1. Each teammate completes the OAuth grant once via the Django web app (browser required).
2. The Django app stores the refresh token and access token in the database, encrypted, keyed to the teammate.
3. When a Celery task starts for that teammate, the orchestrator retrieves the stored tokens, refreshes the access token if expired, and injects it into the MCP config or environment.
4. Token refresh happens in Django (Python `requests` to the OAuth provider’s token endpoint), not inside the Claude Code subprocess.

#### Strategy 4: Service account impersonation (Google services)

For Gmail and Google Calendar in production:

1. Create one Google Cloud service account with domain-wide delegation.
2. The Celery worker uses the service account credentials to impersonate each teammate’s Google Workspace email.
3. No per-user OAuth tokens needed; the service account key file is shared but the `subject` parameter differs per teammate.

```python
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file(
    ‘service-account-key.json’,
    scopes=[‘https://www.googleapis.com/auth/gmail.modify’],
    subject=’alice@company.com’  # impersonate Alice
)
```

#### Credential isolation summary

| Auth Pattern           | Isolation Method                         | Credential Source         | Refresh Responsibility                     |
|------------------------|------------------------------------------|---------------------------|--------------------------------------------|
| API Key                | Per-worker env var                       | DB lookup                 | None (keys do not expire)                  |
| Bot Token / PAT        | Per-worker env var                       | DB lookup                 | None (tokens are long-lived)               |
| OAuth 2.0              | Per-worker MCP config with stored tokens | DB lookup + token refresh | Django app refreshes before task dispatch  |
| Google Service Account | Shared key file + per-worker `subject`   | Filesystem + DB for email | None (service account keys are long-lived) |

### Claude Code Headless Invocation Reference

Quick reference for programmatic invocation from Python (Celery tasks).

#### CLI mode (`claude -p`)

```bash
claude -p "Run the campaign plan for Q3" \
  --output-format json \
  --permission-mode acceptEdits \
  --allowedTools "mcp__hubspot__*,mcp__apollo__*,marketing:campaign-plan" \
  --mcp-config /tmp/mcp_alice_taskid.json \
  --session-id "alice-session-uuid"
```

Key flags:

* `--output-format json` — returns structured JSON instead of streaming text; essential for programmatic parsing
* `--permission-mode acceptEdits` — auto-accepts file edits; use `bypassPermissions` for fully unattended operation
* `--allowedTools` — whitelist of tools the instance may use; critical for security in multi-tenant
* `--mcp-config` — path to per-worker MCP configuration JSON
* `--session-id` — enables session persistence and resumption across Celery task retries
* `--max-turns` — limits agentic iterations; prevents runaway loops
* `--max-budget-usd` — hard spend cap per invocation
* `--bare` — skips auto-discovery (hooks, skills, plugins, MCP, CLAUDE.md) for faster startup; pass everything explicitly instead

#### Agent SDK mode (`claude_agent_sdk`)

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for event in query(
    prompt="Run the campaign plan for Q3",
    options=ClaudeAgentOptions(
        output_format="json",
        permission_mode="acceptEdits",
        allowed_tools=["mcp__hubspot__*", "mcp__apollo__*"],
        mcp_servers={
            "hubspot": {
                "command": "npx",
                "args": ["-y", "@anthropic/hubspot-mcp"],
                "env": {"HUBSPOT_ACCESS_TOKEN": "alice_token"}
            }
        },
        session_id="alice-session-uuid",
        max_turns=20,
        max_budget_usd=5.00,
    ),
):
    handle_event(event)
```

#### Auth for the Claude Code process itself

Each Celery worker needs an `ANTHROPIC_API_KEY` to authenticate the Claude Code process. Options:

* **Shared key**: All workers use the same API key. Simplest. Rate limits and billing are shared.
* **Per-user key**: Each teammate has their own API key. Best isolation but requires multiple Anthropic accounts or projects.
* **`apiKeyHelper` script**: A script that returns the API key dynamically. Useful if keys are rotated or fetched from a secrets manager (AWS Secrets Manager, HashiCorp Vault).
* **AWS Bedrock / Google Vertex / Azure AI Foundry**: Use cloud provider IAM instead of API keys. Each worker authenticates via IAM role or service account. Best for production on cloud infrastructure.
