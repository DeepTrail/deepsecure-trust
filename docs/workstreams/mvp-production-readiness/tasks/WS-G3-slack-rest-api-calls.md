# Task: WS-G3 Slack REST API Calls

> **Status:** `completed`
> **Batch:** P1-B2
> **Worktree:** mvp-prod-gateway
> **Completed:** 2026-02-17

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-G3 |
| **Workstream** | G (Real Backend Clients) |
| **Phase** | P1 (Real Backend Integration) |
| **Dependencies** | WS-G1 (Backend configuration) ✅ Complete |
| **Complexity** | L (3+ hours) |
| **Service** | deeptrail-gateway |
| **Validates** | Real Slack API calls, E2E Step 8 (Execute Tool) |

---

## Specification

> See full specification: [../specs/WS-G3-spec.md](../specs/WS-G3-spec.md)

### Tool → API Mapping

| Tool | Slack API | HTTP Method | Endpoint |
|------|-----------|-------------|----------|
| `search_messages` | search.messages | GET | `/api/search.messages` |
| `send_message` | chat.postMessage | POST | `/api/chat.postMessage` |
| `list_channels` | conversations.list | GET | `/api/conversations.list` |
| `join_channel` | conversations.join | POST | `/api/conversations.join` |
| `post_reaction` | reactions.add | POST | `/api/reactions.add` |
| `list_users` | users.list | GET | `/api/users.list` |
| `get_channel_history` | conversations.history | GET | `/api/conversations.history` |

### Required Headers

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}
```

### Critical: Slack Response Pattern

**IMPORTANT:** Slack returns HTTP 200 even for errors. Must check `ok` field.

```json
// Success
{"ok": true, "channel": "C1234", ...}

// Error (still HTTP 200!)
{"ok": false, "error": "channel_not_found"}
```

---

## Pre-Conditions

- [x] WS-G1 complete (SlackConfig with base_url, timeout)
- [x] `BaseMCPClient` exists
- [x] `ToolResult` dataclass exists
- [x] httpx library available

---

## Task Description

### Objective

Replace the mock implementation in SlackClient with direct REST API calls to the Slack API. The client must handle Slack's unique response pattern where errors return HTTP 200 with `ok: false`.

### Background

Currently, the Gateway's SlackClient returns mock responses. This task implements real API calls, paying special attention to Slack's error handling pattern.

### What to Implement

1. **Update `app/backends/slack_client.py`**:

   ```python
   import httpx
   from app.core.config import get_settings
   from app.backends.base_mcp_client import BaseMCPClient, ToolResult

   class SlackClient(BaseMCPClient):
       """Direct Slack API client."""

       def __init__(self):
           settings = get_settings()
           self.base_url = settings.slack.base_url  # https://slack.com/api
           self.timeout = settings.slack.timeout_seconds

       def _get_headers(self, auth_token: str) -> dict:
           return {
               "Authorization": f"Bearer {auth_token}",
               "Content-Type": "application/json"
           }

       def _transform_response(self, tool_name: str, response: httpx.Response) -> ToolResult:
           """Transform Slack API response.

           CRITICAL: Slack returns HTTP 200 even for errors!
           Must check the 'ok' field in the response body.
           """
           data = response.json()

           if not data.get("ok"):
               return ToolResult(
                   status="error",
                   error_code=data.get("error", "unknown_error"),
                   error_message=data.get("error", "Unknown Slack error")
               )

           return ToolResult(status="success", data=data)

       async def send_message(self, channel: str, text: str, thread_ts: str = None,
                             auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/chat.postMessage"
           payload = {"channel": channel, "text": text}
           if thread_ts:
               payload["thread_ts"] = thread_ts
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.post(url, json=payload, headers=self._get_headers(auth_token))
           return self._transform_response("send_message", response)

       async def list_channels(self, types: str = "public_channel,private_channel",
                              limit: int = 100, cursor: str = None,
                              auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/conversations.list"
           params = {"types": types, "limit": limit}
           if cursor:
               params["cursor"] = cursor
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.get(url, params=params, headers=self._get_headers(auth_token))
           return self._transform_response("list_channels", response)

       async def search_messages(self, query: str, count: int = 20, sort: str = "score",
                                auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/search.messages"
           params = {"query": query, "count": count, "sort": sort}
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.get(url, params=params, headers=self._get_headers(auth_token))
           return self._transform_response("search_messages", response)

       async def join_channel(self, channel: str, auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/conversations.join"
           payload = {"channel": channel}
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.post(url, json=payload, headers=self._get_headers(auth_token))
           return self._transform_response("join_channel", response)

       async def post_reaction(self, channel: str, timestamp: str, name: str,
                              auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/reactions.add"
           payload = {"channel": channel, "timestamp": timestamp, "name": name}
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.post(url, json=payload, headers=self._get_headers(auth_token))
           return self._transform_response("post_reaction", response)

       async def list_users(self, limit: int = 100, cursor: str = None,
                           auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/users.list"
           params = {"limit": limit}
           if cursor:
               params["cursor"] = cursor
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.get(url, params=params, headers=self._get_headers(auth_token))
           return self._transform_response("list_users", response)

       async def get_channel_history(self, channel: str, limit: int = 100,
                                    cursor: str = None, auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/conversations.history"
           params = {"channel": channel, "limit": limit}
           if cursor:
               params["cursor"] = cursor
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.get(url, params=params, headers=self._get_headers(auth_token))
           return self._transform_response("get_channel_history", response)
   ```

2. **Add comprehensive tests** mocking httpx responses

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/backends/slack_client.py` | Modify | Replace mock with real API calls |
| `deeptrail-gateway/tests/backends/test_slack_client.py` | Modify | Add httpx mock tests |

---

## Acceptance Criteria

### Functional Criteria

- [ ] All 7 tools implemented with direct Slack API calls
- [ ] `send_message` calls POST `/api/chat.postMessage`
- [ ] `list_channels` calls GET `/api/conversations.list`
- [ ] `search_messages` calls GET `/api/search.messages`
- [ ] `join_channel` calls POST `/api/conversations.join`
- [ ] `post_reaction` calls POST `/api/reactions.add`
- [ ] `list_users` calls GET `/api/users.list`
- [ ] `get_channel_history` calls GET `/api/conversations.history`

### Slack-Specific Criteria

- [ ] Response transformation checks `ok` field (NOT HTTP status)
- [ ] Error codes from Slack preserved in ToolResult.error_code
- [ ] Pagination support via `cursor` parameter
- [ ] Thread support (`thread_ts`) in send_message

### Integration Criteria

- [ ] Uses `SlackConfig` from WS-G1
- [ ] Auth token passed via `Authorization: Bearer` header
- [ ] Returns `ToolResult` compatible with existing handlers

### Error Handling Criteria

| Error Code | Handled? |
|------------|----------|
| `channel_not_found` | [ ] |
| `not_in_channel` | [ ] |
| `invalid_auth` | [ ] |
| `ratelimited` | [ ] |
| `missing_scope` | [ ] |

---

## Test Cases

| Test Case | Tool | Mock Response | Expected |
|-----------|------|---------------|----------|
| Send message success | `send_message` | `{"ok": true, "ts": "123"}` | ToolResult(status="success") |
| Send message fail | `send_message` | `{"ok": false, "error": "channel_not_found"}` | ToolResult(status="error") |
| Send threaded message | `send_message` | `{"ok": true, ...}` | thread_ts in payload |
| List channels | `list_channels` | `{"ok": true, "channels": [...]}` | ToolResult with channels |
| List channels paginated | `list_channels` | `{"ok": true, "response_metadata": {"next_cursor": "..."}}` | cursor in response |
| Search messages | `search_messages` | `{"ok": true, "messages": {...}}` | ToolResult with results |
| Join channel | `join_channel` | `{"ok": true, "channel": {...}}` | ToolResult success |
| Post reaction | `post_reaction` | `{"ok": true}` | ToolResult success |
| List users | `list_users` | `{"ok": true, "members": [...]}` | ToolResult with users |
| Channel history | `get_channel_history` | `{"ok": true, "messages": [...]}` | ToolResult with messages |
| Rate limited | Any | `{"ok": false, "error": "ratelimited"}` | ToolResult with rate limit error |
| Invalid token | Any | `{"ok": false, "error": "invalid_auth"}` | ToolResult with auth error |

---

## Post-Conditions

After this task is complete:
- [ ] SlackClient makes real API calls (when given valid token)
- [ ] Mock implementation removed
- [ ] Slack-specific error handling works correctly
- [ ] E2E Step 8 (Execute Tool) works with real Slack data

---

## Validation

### Unit Tests
```bash
cd deeptrail-gateway
pytest tests/backends/test_slack_client.py -v
```

### Manual Verification (with real token)
```python
from app.backends.slack_client import SlackClient

client = SlackClient()
result = await client.list_channels(auth_token="<real_slack_token>")
print(result.status)  # "success" or "error"
print(result.data if result.status == "success" else result.error_message)
```

---

## References

- **Specification:** [../specs/WS-G3-spec.md](../specs/WS-G3-spec.md)
- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **Slack API Docs:** https://api.slack.com/methods
- **Upstream:** WS-G1 (Backend configuration) ✅ Complete
- **Downstream:** WS-H1, WS-H2 (Credential injection)
- **Related Code:**
  - `deeptrail-gateway/app/core/config.py` (SlackConfig)
  - `deeptrail-gateway/app/backends/base_mcp_client.py`

---

## Execution

```bash
# Run in mvp-prod-gateway worktree:
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-G3 mvp-production-readiness
```
