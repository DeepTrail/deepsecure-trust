# DeepSecure Project Conventions

Reference material loaded on-demand during code review when the agent needs to verify file placement, naming, or service boundaries.

## Service Architecture

```
deepsecure/           → Python SDK (public API + CLI)
deeptrail-control/    → Control Plane (FastAPI, agent management, auth, policies)
deeptrail-gateway/    → Data Plane (FastAPI, API proxy, secret injection, MCP)
```

## File Path Conventions

| Design Doc Pattern | Actual Pattern | Convention |
|--------------------|----------------|------------|
| `[service]/models/` | `[service]/app/models/` | FastAPI `app/` prefix |
| `[service]/services/` | `[service]/app/services/` | FastAPI `app/` prefix |
| `[service]/api/[domain]/` | `[service]/app/api/v1/endpoints/` | Versioned, flat |
| `middleware/[name].py` | `security/[name].py` | Security separation |

## Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Services | `*_service.py` | `auth_service.py`, `vault_service.py` |
| Validation | `*_validation.py` | `token_validation.py` |
| Constraints | `*_checker.py` | `permission_checker.py` |
| Endpoints | Domain-grouped single files | `agent_endpoints.py` |

## Service Ports (Development)

| Service | Port | Container Port |
|---------|------|---------------|
| Control Plane | localhost:8000 | 8001 |
| Gateway | localhost:8002 | 8001 |
| PostgreSQL | localhost:5434 | 5432 |
| Redis | localhost:6380 | 6379 |

## Test File Locations

| Test Type | Location | Scope |
|-----------|----------|-------|
| SDK unit tests | `tests/_core/`, `tests/commands/`, `tests/sdk/` | Single module |
| Service unit tests | `[service]/tests/` | Single service |
| Integration tests | `tests/` (root), `@pytest.mark.integration` | SDK + service |
| E2E tests | `tests/e2e/` (root), `@pytest.mark.e2e` | Cross-service |
| Demo validation | `tests/demos/` (root) | Demo scripts |

**Rule of thumb:** If it tests functionality spanning multiple services, it belongs at the root level.

## Common Review Mistakes

| Mistake | What to Check Instead |
|---------|----------------------|
| Test uses `/api/v1/agents/challenge` | Design doc says `/api/v1/auth/agent/challenge` |
| File at `deeptrail-control/services/` | Should be `deeptrail-control/app/services/` |
| Import from `deepsecure._core` in tests | Use public `deepsecure.client` API |
| Hardcoded port `8001` | Should be `8000` (mapped port) or from env var |
