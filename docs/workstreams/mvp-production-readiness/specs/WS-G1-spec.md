# Task Specification: WS-G1 Add Backend Configuration

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** plans/mvp_production_readiness.plan.md - P1-3: Real Backend MCP Server Connections

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-G1 |
| **Task Name** | Add backend configuration |
| **Type** | Configuration Module |
| **Service** | deeptrail-gateway |
| **Complexity** | S (< 1 hour) |
| **Validates** | Configurable backend API URLs for Notion, Slack, HubSpot |

---

## Current State Analysis

**Existing Implementation:**
- `deeptrail-gateway/app/backends/connection_manager.py` (854 lines) - Full implementation
- `deeptrail-gateway/app/backends/base_mcp_client.py` (761 lines) - Abstract base class
- `deeptrail-gateway/app/backends/notion_client.py` - Notion MCP client
- `deeptrail-gateway/app/backends/slack_client.py` - Slack MCP client
- `deeptrail-gateway/app/backends/hubspot_client.py` - HubSpot MCP client

**What Exists:**
- `BackendConfig` dataclass with `base_url`, `health_endpoint`, timeouts
- `BackendConnectionManager` with `register_backend()` method
- `create_default_manager()` with hardcoded backend URLs

**What's Missing:**
- Externalized configuration file (`app/core/config.py`)
- Environment variable support for backend URLs
- Configuration validation
- API version headers configuration

---

## Component Specification

### Module: `BackendSettings`

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-gateway/app/core/config.py` |
| **Type** | Pydantic Settings (create new) |
| **Purpose** | Externalized backend API configuration |

### Interface Contract

```python
from pydantic import Field
from pydantic_settings import BaseSettings

class BackendAPIConfig(BaseSettings):
    """Configuration for a single backend API."""

    base_url: str
    api_version: str | None = None
    version_header: str | None = None  # e.g., "Notion-Version"
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_backoff_factor: float = 0.5
    health_endpoint: str = "/health"

class NotionConfig(BackendAPIConfig):
    """Notion API configuration."""

    base_url: str = Field(
        default="https://api.notion.com/v1",
        description="Notion API base URL"
    )
    api_version: str = Field(
        default="2022-06-28",
        description="Notion API version"
    )
    version_header: str = "Notion-Version"

    class Config:
        env_prefix = "NOTION_"

class SlackConfig(BackendAPIConfig):
    """Slack API configuration."""

    base_url: str = Field(
        default="https://slack.com/api",
        description="Slack API base URL"
    )

    class Config:
        env_prefix = "SLACK_"

class HubSpotConfig(BackendAPIConfig):
    """HubSpot API configuration."""

    base_url: str = Field(
        default="https://api.hubapi.com",
        description="HubSpot API base URL"
    )

    class Config:
        env_prefix = "HUBSPOT_"

class GatewaySettings(BaseSettings):
    """Gateway service settings."""

    # Control Plane connection
    control_plane_url: str = Field(
        default="http://localhost:8000",
        description="Control Plane API URL for vault access"
    )

    # Backend configurations
    notion: NotionConfig = Field(default_factory=NotionConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    hubspot: HubSpotConfig = Field(default_factory=HubSpotConfig)

    # Connection pooling
    max_connections_per_backend: int = Field(
        default=10,
        description="Max HTTP connections per backend"
    )

    # Health check settings
    health_check_interval_seconds: float = Field(
        default=30.0,
        description="Interval between backend health checks"
    )
    health_check_timeout_seconds: float = Field(
        default=5.0,
        description="Timeout for health check requests"
    )

    class Config:
        env_prefix = "GATEWAY_"
        env_nested_delimiter = "__"

# Singleton accessor
_settings: GatewaySettings | None = None

def get_settings() -> GatewaySettings:
    """Get gateway settings singleton."""
    global _settings
    if _settings is None:
        _settings = GatewaySettings()
    return _settings
```

---

## Backend Configuration Mapping

### Environment Variables

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

### BackendConfig Mapping

Map `GatewaySettings` to existing `BackendConfig`:

```python
def create_backend_config_from_settings(
    backend_id: str,
    config: BackendAPIConfig
) -> BackendConfig:
    """
    Create BackendConfig from settings.

    Args:
        backend_id: Backend identifier (notion, slack, hubspot)
        config: Backend-specific configuration

    Returns:
        BackendConfig for connection manager
    """
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

---

## Integration with Connection Manager

### Updated `create_default_manager()`

```python
# In connection_manager.py or a new factory module

from app.core.config import get_settings, create_backend_config_from_settings

def create_connection_manager() -> BackendConnectionManager:
    """
    Create connection manager with configured backends.

    Uses settings from environment/config.
    """
    settings = get_settings()
    manager = BackendConnectionManager()

    # Register Notion backend
    notion_config = create_backend_config_from_settings(
        "notion", settings.notion
    )
    manager.register_backend(notion_config)

    # Register Slack backend
    slack_config = create_backend_config_from_settings(
        "slack", settings.slack
    )
    manager.register_backend(slack_config)

    # Register HubSpot backend
    hubspot_config = create_backend_config_from_settings(
        "hubspot", settings.hubspot
    )
    manager.register_backend(hubspot_config)

    return manager
```

---

## Technical Requirements

### Framework-Specific

| Requirement | Pattern | Why |
|-------------|---------|-----|
| Settings | `pydantic-settings` | Type-safe configuration |
| Env vars | Prefix-based | Namespace separation |
| Defaults | Hardcoded in class | Works without .env |
| Singleton | Module-level function | Consistent settings |

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `pydantic-settings` | >=2.0 | Settings management |
| `pydantic` | existing | Data validation |

### File Structure

```
deeptrail-gateway/
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py      # NEW: GatewaySettings
│   ├── backends/
│   │   ├── connection_manager.py  # MODIFY: Use settings
│   │   └── ...
```

---

## File Location Rules

| Artifact | Correct Location | Notes |
|----------|------------------|-------|
| Implementation | `deeptrail-gateway/app/core/config.py` | Create new |
| Unit tests | `deeptrail-gateway/tests/core/test_config.py` | Create new |

---

## Test Cases

| Test Case | Method | Expected | Notes |
|-----------|--------|----------|-------|
| Default settings | `GatewaySettings()` | All defaults populated | No env vars set |
| Override via env | `GatewaySettings()` | Env vars take precedence | Set `NOTION_BASE_URL` |
| Nested env vars | `GatewaySettings()` | Nested config works | `GATEWAY__NOTION__BASE_URL` |
| Create backend config | `create_backend_config_from_settings()` | Valid `BackendConfig` | All fields mapped |
| Version header mapping | `create_backend_config_from_settings()` | `extra_headers` populated | Notion version header |
| Connection manager integration | `create_connection_manager()` | All backends registered | Health checks work |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `GatewaySettings` class created with all backend configs
- [ ] `NotionConfig`, `SlackConfig`, `HubSpotConfig` classes created
- [ ] Environment variable prefixes work correctly
- [ ] `get_settings()` singleton returns consistent instance
- [ ] `create_backend_config_from_settings()` maps all fields
- [ ] Connection manager uses settings (not hardcoded URLs)
- [ ] Notion version header included in config
- [ ] Default values work without any env vars set
- [ ] Override via env vars works
- [ ] Unit tests cover all configuration scenarios

---

## Usage Example

```python
# In application startup
from app.core.config import get_settings
from app.backends.connection_manager import create_connection_manager

settings = get_settings()
print(f"Control Plane URL: {settings.control_plane_url}")
print(f"Notion API: {settings.notion.base_url}")

# Create connection manager with configured backends
manager = create_connection_manager()

# Use in backend clients
notion_client = NotionMCPClient(connection_manager=manager)
```

```bash
# Override in production
export GATEWAY_CONTROL_PLANE_URL=https://control.deepsecure.io
export NOTION_BASE_URL=https://api.notion.com/v1
export NOTION_API_VERSION=2022-06-28
export SLACK_BASE_URL=https://slack.com/api
export HUBSPOT_BASE_URL=https://api.hubapi.com
```

---

## References

- **Design Doc Section:** P1-3: Real Backend MCP Server Connections
- **Related Specs:** WS-G2-spec.md (Notion client), WS-G3-spec.md (Slack client), WS-G4-spec.md (HubSpot client)
- **Upstream Dependencies:** MP1 (P0 complete)
- **Downstream Dependents:** WS-G2, WS-G3, WS-G4 (backend clients use config)
