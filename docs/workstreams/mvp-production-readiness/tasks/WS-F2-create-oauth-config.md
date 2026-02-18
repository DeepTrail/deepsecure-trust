## Metadata
# Task Ticket: WS-F2 Create OAuth Configuration

> **Status:** 🎫 Ready for Execution
>
> **Created:** February 17, 2026
> **Assigned Worktree:** mvp-prod-control

---

## Task Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-F2 |
| **Workstream** | F (OAuth Authorization Layer) |
| **Phase** | P1 (Real Backend Integration) |
| **Dependencies** | WS-F1 (OAuthService) ✅ Complete |
| **Complexity** | S (1-2 hours) |
| **Service** | deeptrail-control |
| **Validates** | OAuth provider configuration, WS-F3 (Endpoints) |

---

## Specification

> See full specification: [../specs/WS-F2-spec.md](../specs/WS-F2-spec.md)

### Key Contracts

**Module:**
| Field | Value |
|-------|-------|
| **Path** | `deeptrail-control/app/core/oauth_config.py` |
| **Type** | Pydantic Settings |
| **Purpose** | Provider-specific OAuth configuration from environment variables |

**Configuration Classes:**
| Class | Env Prefix | Auth URL | PKCE |
|-------|------------|----------|------|
| `NotionOAuthConfig` | `NOTION_OAUTH_` | `https://api.notion.com/v1/oauth/authorize` | ✅ Yes |
| `SlackOAuthConfig` | `SLACK_OAUTH_` | `https://slack.com/oauth/v2/authorize` | ❌ No |
| `HubSpotOAuthConfig` | `HUBSPOT_OAUTH_` | `https://app.hubspot.com/oauth/authorize` | ❌ No |

**Singleton Accessor:**
```python
def get_oauth_settings() -> OAuthSettings:
    """Returns cached OAuthSettings singleton."""
```

---

## API Contracts

> **Note:** This task creates a configuration module, not API endpoints.
> There are no API contracts for this task.
> See WS-F3 for OAuth API endpoints.

---

## Pre-Conditions

- [x] WS-F1 complete (OAuthService with authorization flow methods)
- [x] Pydantic and pydantic-settings dependencies available
- [x] `deeptrail-control/app/core/` directory exists
- [x] P1-B1 complete (foundation services)

---

## Task Description

### Objective

Create a Pydantic Settings configuration module that provides provider-specific OAuth configuration from environment variables for Notion, Slack, and HubSpot integrations.

### Background

The OAuthService (WS-F1) needs externalized configuration for each OAuth provider. Currently, OAuth URLs and credentials are hardcoded or missing. This task creates:
1. Provider-specific config classes (Notion, Slack, HubSpot)
2. Environment variable loading via Pydantic Settings
3. A singleton accessor for consistent configuration access
4. Default values that work for local development

---

## Implementation Steps

### Step 1: Create OAuth Config Module

**File:** `deeptrail-control/app/core/oauth_config.py`

```python
"""
OAuth Provider Configuration Module

Provides externalized OAuth configuration via environment variables.
Each provider has its own config class with appropriate defaults.

Environment Variables:
    OAUTH_REDIRECT_BASE_URL: Base URL for OAuth callbacks
    OAUTH_STATE_TTL_SECONDS: State token TTL in seconds
    NOTION_OAUTH_CLIENT_ID: Notion app client ID
    NOTION_OAUTH_CLIENT_SECRET: Notion app client secret
    SLACK_OAUTH_CLIENT_ID: Slack app client ID
    SLACK_OAUTH_CLIENT_SECRET: Slack app client secret
    HUBSPOT_OAUTH_CLIENT_ID: HubSpot app client ID
    HUBSPOT_OAUTH_CLIENT_SECRET: HubSpot app client secret
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class OAuthProviderConfig(BaseSettings):
    """Base configuration for a single OAuth provider."""
    client_id: str = ""
    client_secret: str = ""
    authorization_url: str
    token_url: str
    scopes: list[str] = Field(default_factory=list)
    redirect_uri: str = ""
    uses_pkce: bool = False


class NotionOAuthConfig(OAuthProviderConfig):
    """Notion OAuth configuration."""
    client_id: str = Field(default="")
    client_secret: str = Field(default="")
    authorization_url: str = "https://api.notion.com/v1/oauth/authorize"
    token_url: str = "https://api.notion.com/v1/oauth/token"
    scopes: list[str] = Field(default_factory=list)  # Notion manages scopes via integration
    uses_pkce: bool = True

    class Config:
        env_prefix = "NOTION_OAUTH_"


class SlackOAuthConfig(OAuthProviderConfig):
    """Slack OAuth configuration."""
    client_id: str = Field(default="")
    client_secret: str = Field(default="")
    authorization_url: str = "https://slack.com/oauth/v2/authorize"
    token_url: str = "https://slack.com/api/oauth.v2.access"
    scopes: list[str] = Field(default=["channels:read", "channels:history", "chat:write", "users:read"])
    uses_pkce: bool = False

    class Config:
        env_prefix = "SLACK_OAUTH_"


class HubSpotOAuthConfig(OAuthProviderConfig):
    """HubSpot OAuth configuration."""
    client_id: str = Field(default="")
    client_secret: str = Field(default="")
    authorization_url: str = "https://app.hubspot.com/oauth/authorize"
    token_url: str = "https://api.hubapi.com/oauth/v1/token"
    scopes: list[str] = Field(default=["crm.objects.contacts.read", "crm.objects.deals.read"])
    uses_pkce: bool = False

    class Config:
        env_prefix = "HUBSPOT_OAUTH_"


class OAuthSettings(BaseSettings):
    """All OAuth provider configurations."""
    redirect_base_url: str = Field(default="http://localhost:8000")
    state_ttl_seconds: int = Field(default=600)
    notion: NotionOAuthConfig = Field(default_factory=NotionOAuthConfig)
    slack: SlackOAuthConfig = Field(default_factory=SlackOAuthConfig)
    hubspot: HubSpotOAuthConfig = Field(default_factory=HubSpotOAuthConfig)

    class Config:
        env_prefix = "OAUTH_"


# Singleton instance
_oauth_settings: OAuthSettings | None = None


def get_oauth_settings() -> OAuthSettings:
    """Get OAuth settings singleton."""
    global _oauth_settings
    if _oauth_settings is None:
        _oauth_settings = OAuthSettings()
    return _oauth_settings
```

### Step 2: Create Tests

**File:** `deeptrail-control/tests/core/test_oauth_config.py`

```python
"""
Tests for OAuth Configuration Module
"""

import os
import pytest
from unittest.mock import patch


class TestOAuthProviderConfig:
    """Test base OAuth provider configuration."""

    def test_notion_default_urls(self):
        """Test Notion has correct OAuth URLs."""
        from app.core.oauth_config import NotionOAuthConfig
        config = NotionOAuthConfig()
        assert config.authorization_url == "https://api.notion.com/v1/oauth/authorize"
        assert config.token_url == "https://api.notion.com/v1/oauth/token"
        assert config.uses_pkce is True

    def test_slack_default_urls(self):
        """Test Slack has correct OAuth URLs."""
        from app.core.oauth_config import SlackOAuthConfig
        config = SlackOAuthConfig()
        assert config.authorization_url == "https://slack.com/oauth/v2/authorize"
        assert config.token_url == "https://slack.com/api/oauth.v2.access"
        assert config.uses_pkce is False

    def test_hubspot_default_urls(self):
        """Test HubSpot has correct OAuth URLs."""
        from app.core.oauth_config import HubSpotOAuthConfig
        config = HubSpotOAuthConfig()
        assert config.authorization_url == "https://app.hubspot.com/oauth/authorize"
        assert config.token_url == "https://api.hubapi.com/oauth/v1/token"
        assert config.uses_pkce is False

    def test_slack_default_scopes(self):
        """Test Slack has correct default scopes."""
        from app.core.oauth_config import SlackOAuthConfig
        config = SlackOAuthConfig()
        assert "channels:read" in config.scopes
        assert "chat:write" in config.scopes

    def test_hubspot_default_scopes(self):
        """Test HubSpot has correct default scopes."""
        from app.core.oauth_config import HubSpotOAuthConfig
        config = HubSpotOAuthConfig()
        assert "crm.objects.contacts.read" in config.scopes


class TestOAuthSettings:
    """Test OAuth settings singleton."""

    def test_default_settings(self):
        """Test default OAuth settings without env vars."""
        from app.core.oauth_config import OAuthSettings
        settings = OAuthSettings()
        assert settings.redirect_base_url == "http://localhost:8000"
        assert settings.state_ttl_seconds == 600

    def test_providers_initialized(self):
        """Test all providers are initialized."""
        from app.core.oauth_config import OAuthSettings
        settings = OAuthSettings()
        assert settings.notion is not None
        assert settings.slack is not None
        assert settings.hubspot is not None

    @patch.dict(os.environ, {"NOTION_OAUTH_CLIENT_ID": "test-notion-id"})
    def test_env_override_notion_client_id(self):
        """Test Notion client ID can be overridden via env var."""
        from app.core.oauth_config import NotionOAuthConfig
        config = NotionOAuthConfig()
        assert config.client_id == "test-notion-id"

    @patch.dict(os.environ, {"OAUTH_REDIRECT_BASE_URL": "https://prod.example.com"})
    def test_env_override_redirect_url(self):
        """Test redirect base URL can be overridden via env var."""
        from app.core.oauth_config import OAuthSettings
        settings = OAuthSettings()
        assert settings.redirect_base_url == "https://prod.example.com"


class TestGetOAuthSettings:
    """Test singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """Test get_oauth_settings returns singleton."""
        # Reset singleton for test
        import app.core.oauth_config as oauth_config_module
        oauth_config_module._oauth_settings = None
        
        from app.core.oauth_config import get_oauth_settings
        settings1 = get_oauth_settings()
        settings2 = get_oauth_settings()
        assert settings1 is settings2
```

### Step 3: Create Test Directory (if needed)

```bash
mkdir -p deeptrail-control/tests/core
touch deeptrail-control/tests/core/__init__.py
```

---

## Validation Commands

```bash
# Navigate to worktree
cd /Users/imaxxs/repositories/mvp-prod-control/deeptrail-control

# Run tests
pytest tests/core/test_oauth_config.py -v

# Verify imports work
python -c "from app.core.oauth_config import get_oauth_settings; print(get_oauth_settings())"

# Verify env var override
NOTION_OAUTH_CLIENT_ID=test123 python -c "from app.core.oauth_config import NotionOAuthConfig; print(NotionOAuthConfig().client_id)"
```

---

## Acceptance Criteria

- [ ] `deeptrail-control/app/core/oauth_config.py` created
- [ ] `deeptrail-control/tests/core/test_oauth_config.py` created
- [ ] All provider configs have correct authorization/token URLs
- [ ] Environment variable prefixes correct (NOTION_OAUTH_, SLACK_OAUTH_, HUBSPOT_OAUTH_)
- [ ] Singleton pattern implemented correctly
- [ ] Default values work without env vars
- [ ] PKCE flags set correctly per provider (Notion=True, others=False)
- [ ] Scopes match provider requirements
- [ ] All tests pass

---

## Test Cases

| Test Case | Module | Method | Expected | Notes |
|-----------|--------|--------|----------|-------|
| Notion default URLs | NotionOAuthConfig | `test_notion_default_urls` | URLs match official endpoints | Auth + token URLs |
| Slack default URLs | SlackOAuthConfig | `test_slack_default_urls` | URLs match official endpoints | Auth + token URLs |
| HubSpot default URLs | HubSpotOAuthConfig | `test_hubspot_default_urls` | URLs match official endpoints | Auth + token URLs |
| Slack default scopes | SlackOAuthConfig | `test_slack_default_scopes` | Contains channels:read, chat:write | Min required scopes |
| HubSpot default scopes | HubSpotOAuthConfig | `test_hubspot_default_scopes` | Contains crm.objects.contacts.read | Min required scopes |
| Settings default values | OAuthSettings | `test_default_settings` | redirect_base_url=localhost, ttl=600 | No env vars |
| Providers initialized | OAuthSettings | `test_providers_initialized` | notion, slack, hubspot not None | All providers present |
| Env override client_id | NotionOAuthConfig | `test_env_override_notion_client_id` | Reads from env var | NOTION_OAUTH_CLIENT_ID |
| Env override redirect URL | OAuthSettings | `test_env_override_redirect_url` | Reads from env var | OAUTH_REDIRECT_BASE_URL |
| Singleton pattern | get_oauth_settings | `test_singleton_returns_same_instance` | Same object returned | Cache check |

---

## Post-Conditions

After this task is complete:
- [ ] All OAuth providers have externalized configuration
- [ ] OAuthService can use provider configs for authorization URLs
- [ ] Environment variables control OAuth credentials (dev vs prod)
- [ ] PKCE configuration is correct per provider
- [ ] WS-F3 (OAuth Endpoints) unblocked
- [ ] No hardcoded OAuth credentials in codebase

---

## Validation

### Unit Tests
```bash
cd deeptrail-control
pytest tests/core/test_oauth_config.py -v
```

### Manual Verification
```bash
# 1. Verify imports work
cd deeptrail-control
python -c "from app.core.oauth_config import get_oauth_settings; print(get_oauth_settings())"

# 2. Verify env var override works
NOTION_OAUTH_CLIENT_ID=test123 python -c "from app.core.oauth_config import NotionOAuthConfig; print(NotionOAuthConfig().client_id)"
# Expected: test123

# 3. Verify default URLs
python -c "from app.core.oauth_config import NotionOAuthConfig; print(NotionOAuthConfig().authorization_url)"
# Expected: https://api.notion.com/v1/oauth/authorize
```

---

## Files to Create

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/core/oauth_config.py` | Create | OAuth settings module |
| `deeptrail-control/tests/core/__init__.py` | Create | Test package init |
| `deeptrail-control/tests/core/test_oauth_config.py` | Create | Configuration tests |

---

## Environment Variables Reference

| Variable | Purpose | Default |
|----------|---------|---------|
| `OAUTH_REDIRECT_BASE_URL` | Base URL for OAuth callbacks | `http://localhost:8000` |
| `OAUTH_STATE_TTL_SECONDS` | State token TTL | `600` |
| `NOTION_OAUTH_CLIENT_ID` | Notion app client ID | `""` |
| `NOTION_OAUTH_CLIENT_SECRET` | Notion app client secret | `""` |
| `SLACK_OAUTH_CLIENT_ID` | Slack app client ID | `""` |
| `SLACK_OAUTH_CLIENT_SECRET` | Slack app client secret | `""` |
| `HUBSPOT_OAUTH_CLIENT_ID` | HubSpot app client ID | `""` |
| `HUBSPOT_OAUTH_CLIENT_SECRET` | HubSpot app client secret | `""` |

---

## References

- **Spec:** [WS-F2-spec.md](../specs/WS-F2-spec.md)
- **Upstream:** WS-F1 (OAuthService) ✅ Complete - [Completion Report](../reports/WS-F1-completion.md)
- **Downstream:** WS-F3 (OAuth Endpoints)
- **Provider Docs:**
  - Notion: https://developers.notion.com/docs/authorization
  - Slack: https://api.slack.com/authentication/oauth-v2
  - HubSpot: https://developers.hubspot.com/docs/api/oauth-quickstart-guide

---

## Execution

```bash
# Execute this task
cd /Users/imaxxs/repositories/mvp-prod-control
/execute-task WS-F2 mvp-production-readiness

# Complete this task
/complete-task WS-F2 mvp-production-readiness
```
