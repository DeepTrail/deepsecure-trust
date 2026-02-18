# Task: WS-G1 Add Backend Configuration

> **Status:** `ready`
> **Batch:** P1-B1
> **Worktree:** mvp-prod-gateway

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-G1 |
| **Workstream** | G (Real Backend Clients) |
| **Phase** | P1 (Real Backend Integration) |
| **Dependencies** | MP1 (P0 complete) ✅ |
| **Complexity** | S (< 1 hour) |
| **Service** | deeptrail-gateway |
| **Validates** | Configurable backend API URLs for Notion, Slack, HubSpot |

---

## Specification

> See full specification: [../specs/WS-G1-spec.md](../specs/WS-G1-spec.md)

### Key Contracts

**Configuration Classes:**

| Class | Purpose | Env Prefix |
|-------|---------|------------|
| `GatewaySettings` | Main gateway configuration | `GATEWAY_` |
| `NotionConfig` | Notion API settings | `NOTION_` |
| `SlackConfig` | Slack API settings | `SLACK_` |
| `HubSpotConfig` | HubSpot API settings | `HUBSPOT_` |

**Environment Variables:**

| Variable | Default |
|----------|---------|
| `GATEWAY_CONTROL_PLANE_URL` | `http://localhost:8000` |
| `NOTION_BASE_URL` | `https://api.notion.com/v1` |
| `NOTION_API_VERSION` | `2022-06-28` |
| `SLACK_BASE_URL` | `https://slack.com/api` |
| `HUBSPOT_BASE_URL` | `https://api.hubapi.com` |

---

## Pre-Conditions

- [x] MP1 reached (P0 complete, E2E demo verified)
- [x] `deeptrail-gateway/app/backends/connection_manager.py` exists (854 lines)
- [x] `BackendConfig` dataclass exists
- [x] `BackendConnectionManager` with `register_backend()` works
- [x] Backend clients (Notion, Slack, HubSpot) exist

---

## Task Description

### Objective

Create an externalized configuration module for the Gateway service that replaces hardcoded backend URLs with environment variable-based configuration using Pydantic Settings.

### Background

The gateway currently has:
- `BackendConnectionManager` with full connection pooling and health checks
- `create_default_manager()` with **hardcoded** backend URLs
- No way to configure backend URLs via environment variables

This task:
- Creates `app/core/config.py` with Pydantic Settings
- Enables environment variable configuration
- Updates connection manager to use settings
- Maintains backward compatibility (defaults work without env vars)

### What to Implement

1. **Create `app/core/__init__.py`** (if missing):
   ```python
   # Empty or minimal init
   ```

2. **Create `app/core/config.py`**:
   ```python
   from pydantic import Field
   from pydantic_settings import BaseSettings

   class BackendAPIConfig(BaseSettings):
       """Configuration for a single backend API."""
       base_url: str
       api_version: str | None = None
       version_header: str | None = None
       timeout_seconds: float = 30.0
       retry_attempts: int = 3
       retry_backoff_factor: float = 0.5
       health_endpoint: str = "/health"

   class NotionConfig(BackendAPIConfig):
       """Notion API configuration."""
       base_url: str = Field(default="https://api.notion.com/v1")
       api_version: str = Field(default="2022-06-28")
       version_header: str = "Notion-Version"

       class Config:
           env_prefix = "NOTION_"

   class SlackConfig(BackendAPIConfig):
       """Slack API configuration."""
       base_url: str = Field(default="https://slack.com/api")

       class Config:
           env_prefix = "SLACK_"

   class HubSpotConfig(BackendAPIConfig):
       """HubSpot API configuration."""
       base_url: str = Field(default="https://api.hubapi.com")

       class Config:
           env_prefix = "HUBSPOT_"

   class GatewaySettings(BaseSettings):
       """Gateway service settings."""
       control_plane_url: str = Field(default="http://localhost:8000")
       notion: NotionConfig = Field(default_factory=NotionConfig)
       slack: SlackConfig = Field(default_factory=SlackConfig)
       hubspot: HubSpotConfig = Field(default_factory=HubSpotConfig)
       max_connections_per_backend: int = Field(default=10)
       health_check_interval_seconds: float = Field(default=30.0)
       health_check_timeout_seconds: float = Field(default=5.0)

       class Config:
           env_prefix = "GATEWAY_"
           env_nested_delimiter = "__"

   _settings: GatewaySettings | None = None

   def get_settings() -> GatewaySettings:
       global _settings
       if _settings is None:
           _settings = GatewaySettings()
       return _settings
   ```

3. **Create helper function** to map settings to BackendConfig:
   ```python
   def create_backend_config_from_settings(
       backend_id: str,
       config: BackendAPIConfig
   ) -> BackendConfig:
       return BackendConfig(
           backend_id=backend_id,
           base_url=config.base_url,
           health_endpoint=config.health_endpoint,
           timeout=config.timeout_seconds,
           retry_attempts=config.retry_attempts,
           retry_backoff=config.retry_backoff_factor,
           extra_headers={
               config.version_header: config.api_version
           } if config.version_header and config.api_version else {}
       )
   ```

4. **Update connection manager** to use settings:
   ```python
   def create_connection_manager() -> BackendConnectionManager:
       settings = get_settings()
       manager = BackendConnectionManager()

       manager.register_backend(
           create_backend_config_from_settings("notion", settings.notion)
       )
       manager.register_backend(
           create_backend_config_from_settings("slack", settings.slack)
       )
       manager.register_backend(
           create_backend_config_from_settings("hubspot", settings.hubspot)
       )

       return manager
   ```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/core/__init__.py` | Create | Package init |
| `deeptrail-gateway/app/core/config.py` | Create | Gateway settings |
| `deeptrail-gateway/app/backends/connection_manager.py` | Modify | Use settings instead of hardcoded URLs |
| `deeptrail-gateway/tests/core/__init__.py` | Create | Test package init |
| `deeptrail-gateway/tests/core/test_config.py` | Create | Configuration tests |

---

## Acceptance Criteria

### Functional Criteria

- [ ] `GatewaySettings` class created with all fields documented in spec
- [ ] `NotionConfig`, `SlackConfig`, `HubSpotConfig` classes created
- [ ] `get_settings()` returns singleton instance
- [ ] Default values work without any environment variables set
- [ ] Environment variable overrides work correctly
- [ ] `create_backend_config_from_settings()` maps all fields correctly
- [ ] Notion version header (`Notion-Version: 2022-06-28`) included in config

### Integration Criteria

- [ ] `create_connection_manager()` uses settings instead of hardcoded URLs
- [ ] Existing backend clients continue to work
- [ ] Health checks still work with new configuration
- [ ] No breaking changes to existing code

### Configuration Criteria

- [ ] `GATEWAY_CONTROL_PLANE_URL` configures Control Plane URL
- [ ] `NOTION_BASE_URL` overrides Notion API URL
- [ ] `SLACK_BASE_URL` overrides Slack API URL
- [ ] `HUBSPOT_BASE_URL` overrides HubSpot API URL
- [ ] `NOTION_API_VERSION` sets version header value

---

## Test Cases

| Test Case | Method | Input | Expected Output |
|-----------|--------|-------|-----------------|
| Default settings | `GatewaySettings()` | No env vars | All defaults populated |
| Override Notion URL | `GatewaySettings()` | `NOTION_BASE_URL=x` | `settings.notion.base_url == "x"` |
| Override Gateway URL | `GatewaySettings()` | `GATEWAY_CONTROL_PLANE_URL=y` | `settings.control_plane_url == "y"` |
| Singleton consistency | `get_settings()` x2 | N/A | Same instance returned |
| Backend config mapping | `create_backend_config_from_settings()` | NotionConfig | Valid BackendConfig |
| Version header mapping | Map NotionConfig | N/A | `extra_headers["Notion-Version"] == "2022-06-28"` |
| Create connection manager | `create_connection_manager()` | Settings | All 3 backends registered |

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `GATEWAY_CONTROL_PLANE_URL` | Control Plane API URL | `http://localhost:8000` |
| `NOTION_BASE_URL` | Notion API base URL | `https://api.notion.com/v1` |
| `NOTION_API_VERSION` | Notion API version header | `2022-06-28` |
| `NOTION_TIMEOUT_SECONDS` | Notion request timeout | `30.0` |
| `SLACK_BASE_URL` | Slack API base URL | `https://slack.com/api` |
| `SLACK_TIMEOUT_SECONDS` | Slack request timeout | `30.0` |
| `HUBSPOT_BASE_URL` | HubSpot API base URL | `https://api.hubapi.com` |
| `HUBSPOT_TIMEOUT_SECONDS` | HubSpot request timeout | `30.0` |
| `GATEWAY_MAX_CONNECTIONS_PER_BACKEND` | Connection pool size | `10` |
| `GATEWAY_HEALTH_CHECK_INTERVAL_SECONDS` | Health check interval | `30.0` |

---

## Post-Conditions

After this task is complete:
- [ ] Backend URLs configurable via environment variables
- [ ] Gateway works without any env vars (uses defaults)
- [ ] Existing tests continue to pass
- [ ] Connection manager uses configuration module

---

## Validation

### Unit Tests
```bash
cd deeptrail-gateway
pytest tests/core/test_config.py -v
```

### Manual Verification
```python
# In Python REPL or test
from app.core.config import get_settings, GatewaySettings

# Test defaults
settings = get_settings()
assert settings.notion.base_url == "https://api.notion.com/v1"
assert settings.notion.api_version == "2022-06-28"
assert settings.slack.base_url == "https://slack.com/api"
assert settings.hubspot.base_url == "https://api.hubapi.com"
assert settings.control_plane_url == "http://localhost:8000"

# Test singleton
settings2 = get_settings()
assert settings is settings2

print("All configuration checks passed!")
```

```bash
# Test env var override
export NOTION_BASE_URL="https://custom.notion.api/v1"
python -c "from app.core.config import get_settings; print(get_settings().notion.base_url)"
# Should output: https://custom.notion.api/v1
```

---

## References

- **Specification:** [../specs/WS-G1-spec.md](../specs/WS-G1-spec.md)
- **Design Doc:** `plans/mvp_production_readiness.plan.md` - P1-3
- **Pydantic Settings:** [pydantic-settings docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- **Related Files:**
  - `deeptrail-gateway/app/backends/connection_manager.py` (uses config)
  - `deeptrail-gateway/app/backends/base_mcp_client.py` (backend clients)
- **Downstream Tasks:** WS-G2 (Notion), WS-G3 (Slack), WS-G4 (HubSpot)

---

## Execution

```bash
# Run in mvp-prod-gateway worktree:
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-G1 mvp-production-readiness
```
