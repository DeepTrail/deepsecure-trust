# Task Specification: WS-G3 Slack REST API Calls

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
| **Task ID** | WS-G3 |
| **Task Name** | Implement Slack REST API Calls |
| **Type** | Backend Client |
| **Service** | deeptrail-gateway |
| **Dependencies** | WS-G1 (Backend configuration) ✅ Complete |

---

## Tool → API Mapping

| Tool | Slack API | HTTP Method | Endpoint |
|------|-----------|-------------|----------|
| `search_messages` | search.messages | GET | `/api/search.messages` |
| `send_message` | chat.postMessage | POST | `/api/chat.postMessage` |
| `list_channels` | conversations.list | GET | `/api/conversations.list` |
| `join_channel` | conversations.join | POST | `/api/conversations.join` |
| `post_reaction` | reactions.add | POST | `/api/reactions.add` |
| `list_users` | users.list | GET | `/api/users.list` |
| `get_channel_history` | conversations.history | GET | `/api/conversations.history` |

---

## Required Headers

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}
```

---

## Slack API Response Pattern

**IMPORTANT:** Slack returns HTTP 200 even for errors. Must check `ok` field.

```json
// Success
{"ok": true, "channel": "C1234", ...}

// Error
{"ok": false, "error": "channel_not_found"}
```

---

## Implementation Pattern

### Base Structure

```python
class SlackClient(BaseMCPClient):
    """Direct Slack API client replacing MCP proxy."""

    def __init__(self, config: SlackConfig):
        self.base_url = config.base_url  # https://slack.com/api
        self.timeout = config.timeout_seconds

    def _get_headers(self, auth_token: str) -> dict:
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

    def _transform_response(self, tool_name: str, response: httpx.Response) -> ToolResult:
        """Transform Slack API response to ToolResult.

        Note: Slack returns 200 even for errors, check 'ok' field.
        """
        data = response.json()

        if not data.get("ok"):
            return ToolResult(
                status="error",
                error_code=data.get("error", "unknown_error"),
                error_message=data.get("error", "Unknown Slack error")
            )

        return ToolResult(
            status="success",
            data=data
        )
```

### send_message

```python
async def send_message(
    self,
    channel: str,
    text: str,
    thread_ts: str = None,
    auth_token: str = None
) -> ToolResult:
    """Send a message to a channel."""
    url = f"{self.base_url}/chat.postMessage"
    payload = {
        "channel": channel,
        "text": text
    }
    if thread_ts:
        payload["thread_ts"] = thread_ts

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.post(
            url,
            json=payload,
            headers=self._get_headers(auth_token)
        )

    return self._transform_response("send_message", response)
```

### list_channels

```python
async def list_channels(
    self,
    types: str = "public_channel,private_channel",
    limit: int = 100,
    cursor: str = None,
    auth_token: str = None
) -> ToolResult:
    """List channels the bot has access to."""
    url = f"{self.base_url}/conversations.list"
    params = {
        "types": types,
        "limit": limit
    }
    if cursor:
        params["cursor"] = cursor

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.get(
            url,
            params=params,
            headers=self._get_headers(auth_token)
        )

    return self._transform_response("list_channels", response)
```

### search_messages

```python
async def search_messages(
    self,
    query: str,
    count: int = 20,
    sort: str = "score",
    auth_token: str = None
) -> ToolResult:
    """Search for messages."""
    url = f"{self.base_url}/search.messages"
    params = {
        "query": query,
        "count": count,
        "sort": sort
    }

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.get(
            url,
            params=params,
            headers=self._get_headers(auth_token)
        )

    return self._transform_response("search_messages", response)
```

### post_reaction

```python
async def post_reaction(
    self,
    channel: str,
    timestamp: str,
    name: str,
    auth_token: str = None
) -> ToolResult:
    """Add a reaction to a message."""
    url = f"{self.base_url}/reactions.add"
    payload = {
        "channel": channel,
        "timestamp": timestamp,
        "name": name  # emoji name without colons
    }

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.post(
            url,
            json=payload,
            headers=self._get_headers(auth_token)
        )

    return self._transform_response("post_reaction", response)
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/backends/slack_client.py` | Modify | Replace MCP calls with direct API |
| `deeptrail-gateway/tests/backends/test_slack_client.py` | Modify | Add direct API tests |

---

## Test Cases

| Test Case | Tool | Mock Response | Expected |
|-----------|------|---------------|----------|
| Send message success | `send_message` | `{"ok": true, "ts": "123"}` | ToolResult with success |
| Send message fail | `send_message` | `{"ok": false, "error": "channel_not_found"}` | ToolResult with error |
| List channels | `list_channels` | `{"ok": true, "channels": [...]}` | ToolResult with channels |
| List channels pagination | `list_channels` | `{"ok": true, ..., "response_metadata": {"next_cursor": "..."}}` | ToolResult with cursor |
| Search messages | `search_messages` | `{"ok": true, "messages": {...}}` | ToolResult with results |
| Post reaction | `post_reaction` | `{"ok": true}` | ToolResult success |
| Rate limited | Any | `{"ok": false, "error": "ratelimited"}` | ToolResult with rate limit error |
| Invalid token | Any | `{"ok": false, "error": "invalid_auth"}` | ToolResult with auth error |

---

## Slack-Specific Error Codes

| Error Code | Meaning | Action |
|------------|---------|--------|
| `channel_not_found` | Channel doesn't exist or bot not member | Report to user |
| `not_in_channel` | Bot not in the channel | Join channel first |
| `invalid_auth` | Token is invalid | Refresh token |
| `ratelimited` | Rate limit hit | Retry with backoff |
| `missing_scope` | Token lacks required scope | Re-authorize with scopes |

---

## Contract Verification Checklist

- [ ] All 7 tools mapped to correct Slack API endpoints
- [ ] Response transformation checks `ok` field (not HTTP status)
- [ ] Error codes from Slack preserved in ToolResult
- [ ] Pagination support via `cursor` parameter
- [ ] Timeout from WS-G1 configuration used
- [ ] Tests mock httpx client, not actual API
- [ ] Thread support in send_message

---

## References

- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **Slack API Docs:** https://api.slack.com/methods
- **Upstream:** WS-G1 (Backend configuration) ✅ Complete
- **Downstream:** WS-H1, WS-H2 (Credential injection)
