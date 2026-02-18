# Task: WS-G2 Notion REST API Calls

> **Status:** `ready`
> **Batch:** P1-B2
> **Worktree:** mvp-prod-gateway

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-G2 |
| **Workstream** | G (Real Backend Clients) |
| **Phase** | P1 (Real Backend Integration) |
| **Dependencies** | WS-G1 (Backend configuration) ✅ Complete |
| **Complexity** | L (3+ hours) |
| **Service** | deeptrail-gateway |
| **Validates** | Real Notion API calls, E2E Step 8 (Execute Tool) |

---

## Specification

> See full specification: [../specs/WS-G2-spec.md](../specs/WS-G2-spec.md)

### Tool → API Mapping

| Tool | Notion API | HTTP Method | Endpoint |
|------|------------|-------------|----------|
| `search_pages` | Search | POST | `/v1/search` |
| `read_page` | Retrieve page | GET | `/v1/pages/{page_id}` |
| `create_page` | Create page | POST | `/v1/pages` |
| `update_page` | Update page | PATCH | `/v1/pages/{page_id}` |
| `delete_page` | Archive page | PATCH | `/v1/pages/{page_id}` |
| `list_databases` | Search (filtered) | POST | `/v1/search` |
| `query_database` | Query database | POST | `/v1/databases/{database_id}/query` |

### Required Headers

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}
```

---

## API Contracts

> **Note:** This task implements an internal client module, not API endpoints.
> The NotionClient calls the external Notion API but does not expose any DeepSecure API endpoints.
> See WS-E2/E3 for vault endpoints or WS-F3 for OAuth endpoints.

---

## Pre-Conditions

- [x] WS-G1 complete (NotionConfig with base_url, api_version, timeout)
- [x] `BaseMCPClient` exists with `call_tool`, `transform_tool_result` methods
- [x] `ToolResult` dataclass exists
- [x] httpx library available

---

## Task Description

### Objective

Replace the mock implementation in NotionClient with direct REST API calls to the Notion API. The client should use the configuration from WS-G1 and transform responses into the existing `ToolResult` format.

### Background

Currently, the Gateway's NotionClient returns mock responses for all tool calls. This task implements real API calls using:
- Configuration from `NotionConfig` (WS-G1)
- OAuth tokens from credential injection (WS-H1/H2)
- Direct httpx calls to Notion API

### What to Implement

1. **Update `app/backends/notion_client.py`**:

   ```python
   import httpx
   from app.core.config import get_settings
   from app.backends.base_mcp_client import BaseMCPClient, ToolResult

   class NotionClient(BaseMCPClient):
       """Direct Notion API client."""

       def __init__(self):
           settings = get_settings()
           self.base_url = settings.notion.base_url
           self.api_version = settings.notion.api_version
           self.timeout = settings.notion.timeout_seconds

       def _get_headers(self, auth_token: str) -> dict:
           return {
               "Authorization": f"Bearer {auth_token}",
               "Notion-Version": self.api_version,
               "Content-Type": "application/json"
           }

       def _transform_response(self, tool_name: str, response: httpx.Response) -> ToolResult:
           if response.status_code >= 400:
               try:
                   error_data = response.json()
                   message = error_data.get("message", "Unknown error")
               except:
                   message = response.text
               return ToolResult(
                   status="error",
                   error_code=response.status_code,
                   error_message=message
               )
           return ToolResult(status="success", data=response.json())

       async def search_pages(self, query: str, page_size: int = 10, auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/search"
           payload = {
               "query": query,
               "page_size": page_size,
               "filter": {"property": "object", "value": "page"}
           }
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.post(url, json=payload, headers=self._get_headers(auth_token))
           return self._transform_response("search_pages", response)

       async def read_page(self, page_id: str, auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/pages/{page_id}"
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.get(url, headers=self._get_headers(auth_token))
           return self._transform_response("read_page", response)

       async def create_page(self, parent_id: str, title: str, properties: dict = None,
                            children: list = None, auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/pages"
           payload = {
               "parent": {"page_id": parent_id},
               "properties": {"title": [{"text": {"content": title}}]}
           }
           if properties:
               payload["properties"].update(properties)
           if children:
               payload["children"] = children
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.post(url, json=payload, headers=self._get_headers(auth_token))
           return self._transform_response("create_page", response)

       async def update_page(self, page_id: str, properties: dict, auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/pages/{page_id}"
           payload = {"properties": properties}
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.patch(url, json=payload, headers=self._get_headers(auth_token))
           return self._transform_response("update_page", response)

       async def delete_page(self, page_id: str, auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/pages/{page_id}"
           payload = {"archived": True}
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.patch(url, json=payload, headers=self._get_headers(auth_token))
           return self._transform_response("delete_page", response)

       async def list_databases(self, auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/search"
           payload = {"filter": {"property": "object", "value": "database"}}
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.post(url, json=payload, headers=self._get_headers(auth_token))
           return self._transform_response("list_databases", response)

       async def query_database(self, database_id: str, filter: dict = None,
                               sorts: list = None, page_size: int = 100,
                               auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/databases/{database_id}/query"
           payload = {"page_size": page_size}
           if filter:
               payload["filter"] = filter
           if sorts:
               payload["sorts"] = sorts
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.post(url, json=payload, headers=self._get_headers(auth_token))
           return self._transform_response("query_database", response)
   ```

2. **Update `call_tool` dispatcher** to route to correct methods

3. **Add comprehensive tests** mocking httpx responses

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/backends/notion_client.py` | Modify | Replace mock with real API calls |
| `deeptrail-gateway/tests/backends/test_notion_client.py` | Modify | Add httpx mock tests |

---

## Acceptance Criteria

### Functional Criteria

- [ ] All 7 tools implemented with direct Notion API calls
- [ ] `search_pages` calls POST `/v1/search` with page filter
- [ ] `read_page` calls GET `/v1/pages/{page_id}`
- [ ] `create_page` calls POST `/v1/pages` with parent and properties
- [ ] `update_page` calls PATCH `/v1/pages/{page_id}`
- [ ] `delete_page` calls PATCH with `{"archived": true}`
- [ ] `list_databases` calls POST `/v1/search` with database filter
- [ ] `query_database` calls POST `/v1/databases/{id}/query`

### Integration Criteria

- [ ] Uses `NotionConfig` from WS-G1 (base_url, api_version, timeout)
- [ ] `Notion-Version` header set to `2022-06-28`
- [ ] Auth token passed via `Authorization: Bearer` header
- [ ] Returns `ToolResult` compatible with existing handlers

### Error Handling Criteria

- [ ] Handles 401 (unauthorized) - returns ToolResult with error
- [ ] Handles 404 (not found) - returns ToolResult with error
- [ ] Handles 429 (rate limit) - returns ToolResult with error
- [ ] Preserves Notion error messages in ToolResult.error_message

### Contract Verification (from spec)

- [ ] All 7 tools mapped to correct endpoints
- [ ] Tests mock httpx client (not actual API)
- [ ] Timeout from configuration used

---

## Test Cases

| Test Case | Tool | Mock Response | Expected |
|-----------|------|---------------|----------|
| Search success | `search_pages` | `{"results": [{"id": "page1"}]}` | ToolResult(status="success", data=...) |
| Search empty | `search_pages` | `{"results": []}` | ToolResult(status="success", data=...) |
| Read page success | `read_page` | `{"id": "x", "properties": {...}}` | ToolResult with page |
| Read page not found | `read_page` | 404 + `{"message": "..."}` | ToolResult(status="error", error_code=404) |
| Create page success | `create_page` | `{"id": "new-id"}` | ToolResult with new page |
| Update page | `update_page` | `{"id": "x", ...}` | ToolResult with updated page |
| Delete page (archive) | `delete_page` | `{"archived": true}` | ToolResult success |
| List databases | `list_databases` | `{"results": [...]}` | ToolResult with databases |
| Query database | `query_database` | `{"results": [...]}` | ToolResult with rows |
| Auth error | Any | 401 response | ToolResult(status="error", error_code=401) |
| Rate limit | Any | 429 response | ToolResult with rate limit error |

---

## Post-Conditions

After this task is complete:
- [ ] NotionClient makes real API calls (when given valid token)
- [ ] Mock implementation removed
- [ ] WS-H1/H2 can inject real tokens for Notion calls
- [ ] E2E Step 8 (Execute Tool) works with real Notion data

---

## Validation

### Unit Tests
```bash
cd deeptrail-gateway
pytest tests/backends/test_notion_client.py -v
```

### Manual Verification (with real token)
```python
# In Python REPL
from app.backends.notion_client import NotionClient

client = NotionClient()
result = await client.search_pages("test", auth_token="<real_notion_token>")
print(result.status)  # Should be "success" or "error" based on token validity
```

---

## References

- **Specification:** [../specs/WS-G2-spec.md](../specs/WS-G2-spec.md)
- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **Notion API Docs:** https://developers.notion.com/reference
- **Upstream:** WS-G1 (Backend configuration) ✅ Complete
- **Downstream:** WS-H1, WS-H2 (Credential injection)
- **Related Code:**
  - `deeptrail-gateway/app/core/config.py` (NotionConfig)
  - `deeptrail-gateway/app/backends/base_mcp_client.py` (BaseMCPClient)

---

## Execution

```bash
# Run in mvp-prod-gateway worktree:
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-G2 mvp-production-readiness
```
