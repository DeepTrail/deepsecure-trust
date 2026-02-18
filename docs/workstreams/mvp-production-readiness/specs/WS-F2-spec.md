# Task Specification: WS-F2 OAuth Configuration

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** BATCH_EXECUTION_PLAN.md - P1-B2

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-F2 |
| **Task Name** | Create OAuth Configuration |
| **Type** | Configuration Module |
| **Service** | deeptrail-control |
| **Dependencies** | WS-F1 (OAuthService) ✅ Complete |

---

## Component Specification

### Module Definition

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-control/app/core/oauth_config.py` |
| **Type** | Pydantic Settings |
| **Purpose** | Provider-specific OAuth configuration from environment variables |

---

## Configuration Classes

### Base Provider Config

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class OAuthProviderConfig(BaseSettings):
    """Configuration for a single OAuth provider."""
    client_id: str = ""
    client_secret: str = ""
    authorization_url: str
    token_url: str
    scopes: list[str] = Field(default_factory=list)
    redirect_uri: str = ""
    uses_pkce: bool = False
```

### Notion OAuth Config

```python
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
```

### Slack OAuth Config

```python
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
```

### HubSpot OAuth Config

```python
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
```

### Main OAuth Settings

```python
class OAuthSettings(BaseSettings):
    """All OAuth provider configurations."""
    redirect_base_url: str = Field(default="http://localhost:8000")
    state_ttl_seconds: int = Field(default=600)
    notion: NotionOAuthConfig = Field(default_factory=NotionOAuthConfig)
    slack: SlackOAuthConfig = Field(default_factory=SlackOAuthConfig)
    hubspot: HubSpotOAuthConfig = Field(default_factory=HubSpotOAuthConfig)

    class Config:
        env_prefix = "OAUTH_"

_oauth_settings: OAuthSettings | None = None

def get_oauth_settings() -> OAuthSettings:
    """Get OAuth settings singleton."""
    global _oauth_settings
    if _oauth_settings is None:
        _oauth_settings = OAuthSettings()
    return _oauth_settings
```

---

## Environment Variables

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

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/core/oauth_config.py` | Create | OAuth settings module |
| `deeptrail-control/tests/core/test_oauth_config.py` | Create | Configuration tests |

---

## Test Cases

| Test Case | Method | Input | Expected Output |
|-----------|--------|-------|-----------------|
| Default settings | `OAuthSettings()` | No env vars | All defaults populated |
| Override Notion ID | `OAuthSettings()` | `NOTION_OAUTH_CLIENT_ID=xyz` | `settings.notion.client_id == "xyz"` |
| Override redirect URL | `OAuthSettings()` | `OAUTH_REDIRECT_BASE_URL=https://...` | Updated URL |
| Singleton consistency | `get_oauth_settings()` x2 | N/A | Same instance returned |
| Notion PKCE enabled | `NotionOAuthConfig()` | N/A | `uses_pkce == True` |
| Slack PKCE disabled | `SlackOAuthConfig()` | N/A | `uses_pkce == False` |
| Default scopes | `SlackOAuthConfig()` | N/A | Contains expected scopes |

---

## Contract Verification Checklist

- [ ] All provider configs have correct authorization/token URLs
- [ ] Environment variable prefixes correct (NOTION_OAUTH_, SLACK_OAUTH_, HUBSPOT_OAUTH_)
- [ ] Singleton pattern implemented correctly
- [ ] Default values work without env vars
- [ ] PKCE flags set correctly per provider
- [ ] Scopes match provider requirements

---

## References

- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **Upstream:** WS-F1 (OAuthService) ✅ Complete
- **Downstream:** WS-F3 (OAuth endpoints)
- **Provider Docs:**
  - Notion: https://developers.notion.com/docs/authorization
  - Slack: https://api.slack.com/authentication/oauth-v2
  - HubSpot: https://developers.hubspot.com/docs/api/oauth-quickstart-guide
