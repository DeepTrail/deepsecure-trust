# Task Specifications: Batch P1-B1 - MVP Production Readiness

## Context

Batch P1-B1 is the first batch of Phase 1 (Real Backend Integration) in the MVP Production Readiness workstream. It follows MP1 (P0 complete, E2E flow verified) and establishes the foundation for OAuth token storage, OAuth flows, and backend API configuration.

**Purpose:** Enable real OAuth integration and backend API calls by:
1. Enhancing vault client for token lifecycle management
2. Creating OAuth service for authorization flows
3. Externalizing gateway backend configuration

---

## Specifications Created

| Task ID | Spec File | Type | Status |
|---------|-----------|------|--------|
| WS-E1 | `specs/WS-E1-spec.md` | Service Enhancement | Created |
| WS-F1 | `specs/WS-F1-spec.md` | Service Creation | Created |
| WS-G1 | `specs/WS-G1-spec.md` | Configuration Module | Created |

### Spec Directory
```
docs/workstreams/mvp-production-readiness/specs/
├── WS-E1-spec.md      # Enhance vault client for token storage
├── WS-F1-spec.md      # Create OAuth service
└── WS-G1-spec.md      # Add backend configuration
```

---

## Key Findings from Codebase Exploration

### Existing Implementation State

| Task | Current State | What Exists | What's Missing |
|------|--------------|-------------|-----------------|
| **E1** | ~95% Complete | VaultClient with Fernet encryption, in-memory storage, full token CRUD | Token expiration tracking, refresh scheduling, usage tracking |
| **F1** | ~60% Complete | Connect endpoint, token storage, service metadata | OAuth authorization URL generation, callback handler, PKCE, state management |
| **G1** | ~100% Complete | Connection manager, all 3 backend clients, health checks | Externalized config file, environment variable support |

### Key Existing Files

**Control Plane (deeptrail-control):**
- `app/services/vault_client.py` (283 lines) - Encrypted token storage
- `app/services/connected_service_service.py` (433 lines) - Service connection logic
- `app/models/connected_service.py` (210 lines) - SQLAlchemy model
- `app/api/v1/endpoints/users.py` - Connect service endpoint

**Gateway (deeptrail-gateway):**
- `app/backends/connection_manager.py` (854 lines) - Connection pooling & health checks
- `app/backends/base_mcp_client.py` (761 lines) - Abstract MCP client
- `app/backends/notion_client.py` (529 lines) - Notion backend
- `app/backends/slack_client.py` (554 lines) - Slack backend
- `app/backends/hubspot_client.py` (80+ lines) - HubSpot backend

---

## Contracts Defined

### E1: Vault Client Enhancement

**New Methods:**
| Method | Purpose |
|--------|---------|
| `store_token(user_id, service_id, token_data, expires_in)` | Store with expiration metadata |
| `retrieve_token(token_ref, update_usage=True)` | Get token, track usage |
| `refresh_token(token_ref, new_access_token, ...)` | Update after OAuth refresh |
| `get_expiring_tokens(threshold_minutes=15)` | Find tokens needing refresh |
| `is_token_expired(token_ref)` | Check expiration status |

**New Data Classes:**
- `TokenMetadata` - Created, expires, last used timestamps
- `StoredTokenData` - Complete token with metadata

### F1: OAuth Service

**OAuth Flow Support:**
| Provider | Auth URL | Token URL | PKCE |
|----------|----------|-----------|------|
| Notion | `api.notion.com/v1/oauth/authorize` | `api.notion.com/v1/oauth/token` | Required |
| Slack | `slack.com/oauth/v2/authorize` | `slack.com/api/oauth.v2.access` | No |
| HubSpot | `app.hubspot.com/oauth/authorize` | `api.hubapi.com/oauth/v1/token` | No |

**New Methods:**
| Method | Purpose |
|--------|---------|
| `get_authorization_url(request)` | Generate OAuth URL with state/PKCE |
| `exchange_code_for_tokens(request)` | Exchange auth code for tokens |
| `refresh_tokens(request)` | Refresh expired tokens |
| `get_provider_config(provider)` | Get provider configuration |

### G1: Gateway Configuration

**Environment Variables:**
| Variable | Default |
|----------|---------|
| `GATEWAY_CONTROL_PLANE_URL` | `http://localhost:8000` |
| `NOTION_BASE_URL` | `https://api.notion.com/v1` |
| `NOTION_API_VERSION` | `2022-06-28` |
| `SLACK_BASE_URL` | `https://slack.com/api` |
| `HUBSPOT_BASE_URL` | `https://api.hubapi.com` |

**New Files:**
- `deeptrail-gateway/app/core/config.py` - Pydantic settings

---

## Execution Plan

### Worktree Setup (Required)

```bash
# From main repo
cd /Users/imaxxs/repositories/deepsecure-mvp
git worktree add ../mvp-prod-control -b feature/mvp-prod-control dev
git worktree add ../mvp-prod-gateway -b feature/mvp-prod-gateway dev

# Copy .cursor commands
cp -r .cursor ../mvp-prod-control/
cp -r .cursor ../mvp-prod-gateway/
```

### Parallel Execution

All 3 tasks can run in parallel:
- **Terminal 1 (Control):** E1, F1
- **Terminal 2 (Gateway):** G1

### Commands

```bash
# Create task tickets
/create-task-ticket WS-E1 mvp-production-readiness
/create-task-ticket WS-F1 mvp-production-readiness
/create-task-ticket WS-G1 mvp-production-readiness

# Execute (parallel in separate worktrees)
# Control worktree:
cd ../mvp-prod-control
/execute-task WS-E1 mvp-production-readiness
/execute-task WS-F1 mvp-production-readiness

# Gateway worktree:
cd ../mvp-prod-gateway
/execute-task WS-G1 mvp-production-readiness
```

---

## Verification

### E1 Verification
```bash
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control
pytest tests/services/test_vault_client.py -v
```

### F1 Verification
```bash
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control
pytest tests/services/test_oauth_service.py -v
```

### G1 Verification
```bash
cd /Users/imaxxs/repositories/mvp-prod-gateway/deeptrail-gateway
pytest tests/core/test_config.py -v
grep -r "NOTION_API_URL\|SLACK_API_URL" app/core/config.py
```

---

## Next Steps

1. Review specifications for accuracy
2. Get design approval (this plan)
3. Create task tickets: `/create-task-ticket WS-E1 mvp-production-readiness`
4. Execute tasks in parallel across worktrees

---

*Specifications ready for task ticket creation.*
