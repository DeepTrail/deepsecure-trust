# Task Specification: WS-G2 Notion REST API Calls

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
| **Task ID** | WS-G2 |
| **Task Name** | Implement Notion REST API Calls |
| **Type** | Backend Client |
| **Service** | deeptrail-gateway |
| **Dependencies** | WS-G1 (Backend configuration) ✅ Complete |

---

## Tool → API Mapping

| Tool | Notion API | HTTP Method | Endpoint |
|------|------------|-------------|----------|
| `search_pages` | Search | POST | `/v1/search` |
| `read_page` | Retrieve page | GET | `/v1/pages/{page_id}` |
| `create_page` | Create page | POST | `/v1/pages` |
| `update_page` | Update page | PATCH | `/v1/pages/{page_id}` |
| `delete_page` | Archive page | PATCH | `/v1/pages/{page_id}` |
| `list_databases` | Search (filtered) | POST | `/v1/search` |
| `query_database` | Query database | POST | `/v1/databases/{database_id}/query` |

---

## Required Headers

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "Notion-Version": "2022-06-28",  # From WS-G1 config
    "Content-Type": "application/json"
}
```

---

## Implementation Pattern

### Base Structure

```python
class NotionClient(BaseMCPClient):
    """Direct Notion API client replacing MCP proxy."""

    def __init__(self, config: NotionConfig):
        self.base_url = config.base_url  # https://api.notion.com/v1
        self.api_version = config.api_version  # 2022-06-28
        self.timeout = config.timeout_seconds

    def _get_headers(self, auth_token: str) -> dict:
        return {
            "Authorization": f"Bearer {auth_token}",
            "Notion-Version": self.api_version,
            "Content-Type": "application/json"
        }
```

### search_pages

```python
async def search_pages(
    self,
    query: str,
    page_size: int = 10,
    auth_token: str = None
) -> ToolResult:
    """Search for pages in Notion."""
    url = f"{self.base_url}/search"
    payload = {
        "query": query,
        "page_size": page_size,
        "filter": {"property": "object", "value": "page"}
    }

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.post(
            url,
            json=payload,
            headers=self._get_headers(auth_token)
        )

    return self._transform_response("search_pages", response)
```

### read_page

```python
async def read_page(
    self,
    page_id: str,
    auth_token: str = None
) -> ToolResult:
    """Retrieve a page by ID."""
    url = f"{self.base_url}/pages/{page_id}"

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.get(
            url,
            headers=self._get_headers(auth_token)
        )

    return self._transform_response("read_page", response)
```

### create_page

```python
async def create_page(
    self,
    parent_id: str,
    title: str,
    properties: dict = None,
    children: list = None,
    auth_token: str = None
) -> ToolResult:
    """Create a new page."""
    url = f"{self.base_url}/pages"
    payload = {
        "parent": {"page_id": parent_id},
        "properties": {
            "title": [{"text": {"content": title}}]
        }
    }
    if properties:
        payload["properties"].update(properties)
    if children:
        payload["children"] = children

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.post(
            url,
            json=payload,
            headers=self._get_headers(auth_token)
        )

    return self._transform_response("create_page", response)
```

### query_database

```python
async def query_database(
    self,
    database_id: str,
    filter: dict = None,
    sorts: list = None,
    page_size: int = 100,
    auth_token: str = None
) -> ToolResult:
    """Query a database."""
    url = f"{self.base_url}/databases/{database_id}/query"
    payload = {"page_size": page_size}
    if filter:
        payload["filter"] = filter
    if sorts:
        payload["sorts"] = sorts

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.post(
            url,
            json=payload,
            headers=self._get_headers(auth_token)
        )

    return self._transform_response("query_database", response)
```

---

## Response Transformation

```python
def _transform_response(self, tool_name: str, response: httpx.Response) -> ToolResult:
    """Transform Notion API response to ToolResult."""
    if response.status_code >= 400:
        error_data = response.json()
        return ToolResult(
            status="error",
            error_code=response.status_code,
            error_message=error_data.get("message", "Unknown error")
        )

    return ToolResult(
        status="success",
        data=response.json()
    )
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/backends/notion_client.py` | Modify | Replace MCP calls with direct API |
| `deeptrail-gateway/tests/backends/test_notion_client.py` | Modify | Add direct API tests |

---

## Test Cases

| Test Case | Tool | Mock Response | Expected |
|-----------|------|---------------|----------|
| Search success | `search_pages` | `{"results": [...]}` | ToolResult with results |
| Search empty | `search_pages` | `{"results": []}` | ToolResult with empty list |
| Read page success | `read_page` | `{"id": "...", "properties": {...}}` | ToolResult with page |
| Read page not found | `read_page` | 404 response | ToolResult with error |
| Create page success | `create_page` | `{"id": "new-id", ...}` | ToolResult with new page |
| Query database | `query_database` | `{"results": [...]}` | ToolResult with rows |
| Auth error | Any | 401 response | ToolResult with auth error |
| Rate limit | Any | 429 response | ToolResult with rate limit error |

---

## Contract Verification Checklist

- [ ] All 7 tools mapped to correct Notion API endpoints
- [ ] `Notion-Version` header set to `2022-06-28`
- [ ] Auth token passed via `Authorization: Bearer` header
- [ ] Response transformation handles success and error cases
- [ ] Timeout from WS-G1 configuration used
- [ ] Tests mock httpx client, not actual API
- [ ] Error responses preserve Notion error messages

---

## References

- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **Notion API Docs:** https://developers.notion.com/reference
- **Upstream:** WS-G1 (Backend configuration) ✅ Complete
- **Downstream:** WS-H1, WS-H2 (Credential injection)
