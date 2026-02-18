# Task Specification: WS-G4 HubSpot REST API Calls

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
| **Task ID** | WS-G4 |
| **Task Name** | Implement HubSpot REST API Calls |
| **Type** | Backend Client |
| **Service** | deeptrail-gateway |
| **Dependencies** | WS-G1 (Backend configuration) ✅ Complete |

---

## Tool → API Mapping

| Tool | HubSpot API | HTTP Method | Endpoint |
|------|-------------|-------------|----------|
| `get_contact` | Get contact | GET | `/crm/v3/objects/contacts/{contactId}` |
| `create_contact` | Create contact | POST | `/crm/v3/objects/contacts` |
| `update_contact` | Update contact | PATCH | `/crm/v3/objects/contacts/{contactId}` |
| `list_contacts` | List contacts | GET | `/crm/v3/objects/contacts` |
| `search_contacts` | Search contacts | POST | `/crm/v3/objects/contacts/search` |
| `get_deal` | Get deal | GET | `/crm/v3/objects/deals/{dealId}` |
| `create_deal` | Create deal | POST | `/crm/v3/objects/deals` |
| `update_deal` | Update deal | PATCH | `/crm/v3/objects/deals/{dealId}` |
| `list_deals` | List deals | GET | `/crm/v3/objects/deals` |

---

## Required Headers

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}
```

---

## Implementation Pattern

### Base Structure

```python
class HubSpotClient(BaseMCPClient):
    """Direct HubSpot API client replacing MCP proxy."""

    def __init__(self, config: HubSpotConfig):
        self.base_url = config.base_url  # https://api.hubapi.com
        self.timeout = config.timeout_seconds

    def _get_headers(self, auth_token: str) -> dict:
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

    def _transform_response(self, tool_name: str, response: httpx.Response) -> ToolResult:
        """Transform HubSpot API response to ToolResult."""
        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("message", str(error_data))
            except:
                message = response.text

            return ToolResult(
                status="error",
                error_code=response.status_code,
                error_message=message
            )

        return ToolResult(
            status="success",
            data=response.json()
        )
```

### get_contact

```python
async def get_contact(
    self,
    contact_id: str = None,
    email: str = None,
    properties: list[str] = None,
    auth_token: str = None
) -> ToolResult:
    """Get a contact by ID or email."""
    if contact_id:
        url = f"{self.base_url}/crm/v3/objects/contacts/{contact_id}"
        params = {}
        if properties:
            params["properties"] = ",".join(properties)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                params=params if params else None,
                headers=self._get_headers(auth_token)
            )
    elif email:
        # Use search endpoint for email lookup
        return await self.search_contacts(
            filters=[{
                "propertyName": "email",
                "operator": "EQ",
                "value": email
            }],
            limit=1,
            auth_token=auth_token
        )
    else:
        return ToolResult(
            status="error",
            error_code="missing_identifier",
            error_message="Either contact_id or email required"
        )

    return self._transform_response("get_contact", response)
```

### create_contact

```python
async def create_contact(
    self,
    email: str,
    firstname: str = None,
    lastname: str = None,
    properties: dict = None,
    auth_token: str = None
) -> ToolResult:
    """Create a new contact."""
    url = f"{self.base_url}/crm/v3/objects/contacts"

    props = {"email": email}
    if firstname:
        props["firstname"] = firstname
    if lastname:
        props["lastname"] = lastname
    if properties:
        props.update(properties)

    payload = {"properties": props}

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.post(
            url,
            json=payload,
            headers=self._get_headers(auth_token)
        )

    return self._transform_response("create_contact", response)
```

### search_contacts

```python
async def search_contacts(
    self,
    filters: list[dict],
    sorts: list[dict] = None,
    properties: list[str] = None,
    limit: int = 10,
    after: str = None,
    auth_token: str = None
) -> ToolResult:
    """Search contacts with filters."""
    url = f"{self.base_url}/crm/v3/objects/contacts/search"

    payload = {
        "filterGroups": [{"filters": filters}],
        "limit": limit
    }
    if sorts:
        payload["sorts"] = sorts
    if properties:
        payload["properties"] = properties
    if after:
        payload["after"] = after

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.post(
            url,
            json=payload,
            headers=self._get_headers(auth_token)
        )

    return self._transform_response("search_contacts", response)
```

### create_deal

```python
async def create_deal(
    self,
    dealname: str,
    pipeline: str = "default",
    dealstage: str = None,
    amount: float = None,
    properties: dict = None,
    auth_token: str = None
) -> ToolResult:
    """Create a new deal."""
    url = f"{self.base_url}/crm/v3/objects/deals"

    props = {
        "dealname": dealname,
        "pipeline": pipeline
    }
    if dealstage:
        props["dealstage"] = dealstage
    if amount is not None:
        props["amount"] = str(amount)
    if properties:
        props.update(properties)

    payload = {"properties": props}

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.post(
            url,
            json=payload,
            headers=self._get_headers(auth_token)
        )

    return self._transform_response("create_deal", response)
```

### list_deals

```python
async def list_deals(
    self,
    limit: int = 10,
    after: str = None,
    properties: list[str] = None,
    auth_token: str = None
) -> ToolResult:
    """List deals with pagination."""
    url = f"{self.base_url}/crm/v3/objects/deals"

    params = {"limit": limit}
    if after:
        params["after"] = after
    if properties:
        params["properties"] = ",".join(properties)

    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.get(
            url,
            params=params,
            headers=self._get_headers(auth_token)
        )

    return self._transform_response("list_deals", response)
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/backends/hubspot_client.py` | Modify | Replace MCP calls with direct API |
| `deeptrail-gateway/tests/backends/test_hubspot_client.py` | Modify | Add direct API tests |

---

## Test Cases

| Test Case | Tool | Mock Response | Expected |
|-----------|------|---------------|----------|
| Get contact by ID | `get_contact` | `{"id": "123", "properties": {...}}` | ToolResult with contact |
| Get contact by email | `get_contact` | Search result with 1 contact | ToolResult with contact |
| Create contact | `create_contact` | `{"id": "new-id", ...}` | ToolResult with new contact |
| Search contacts | `search_contacts` | `{"results": [...], "paging": {...}}` | ToolResult with results |
| Create deal | `create_deal` | `{"id": "deal-id", ...}` | ToolResult with deal |
| List deals | `list_deals` | `{"results": [...]}` | ToolResult with deals |
| Contact not found | `get_contact` | 404 response | ToolResult with error |
| Invalid properties | `create_contact` | 400 response | ToolResult with validation error |
| Rate limited | Any | 429 response | ToolResult with rate limit |

---

## HubSpot-Specific Considerations

### Pagination

HubSpot uses cursor-based pagination with `after` parameter:

```json
{
  "results": [...],
  "paging": {
    "next": {
      "after": "cursor_string"
    }
  }
}
```

### Filter Operators

| Operator | Description |
|----------|-------------|
| `EQ` | Equal |
| `NEQ` | Not equal |
| `LT` | Less than |
| `LTE` | Less than or equal |
| `GT` | Greater than |
| `GTE` | Greater than or equal |
| `CONTAINS_TOKEN` | Contains word |
| `NOT_CONTAINS_TOKEN` | Doesn't contain word |

### Common Error Codes

| Status | Meaning | Action |
|--------|---------|--------|
| 400 | Validation error | Check property names/values |
| 401 | Invalid/expired token | Refresh token |
| 403 | Scope missing | Re-authorize with required scopes |
| 404 | Resource not found | Handle gracefully |
| 429 | Rate limited | Retry with exponential backoff |

---

## Contract Verification Checklist

- [ ] All 9 tools mapped to correct HubSpot API endpoints
- [ ] CRM v3 API paths used (`/crm/v3/objects/...`)
- [ ] Search uses POST with filterGroups structure
- [ ] Pagination support via `after` cursor
- [ ] Email lookup uses search (not direct endpoint)
- [ ] Deal amount converted to string (HubSpot requirement)
- [ ] Tests mock httpx client, not actual API
- [ ] Error messages preserved from HubSpot response

---

## References

- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **HubSpot API Docs:** https://developers.hubspot.com/docs/api/crm/contacts
- **Upstream:** WS-G1 (Backend configuration) ✅ Complete
- **Downstream:** WS-H1, WS-H2 (Credential injection)
