# Task: WS-G4 HubSpot REST API Calls

> **Status:** `completed`
> **Completion Date:** February 17, 2026
> **Batch:** P1-B2
> **Worktree:** mvp-prod-gateway

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-G4 |
| **Workstream** | G (Real Backend Clients) |
| **Phase** | P1 (Real Backend Integration) |
| **Dependencies** | WS-G1 (Backend configuration) ✅ Complete |
| **Complexity** | L (3+ hours) |
| **Service** | deeptrail-gateway |
| **Validates** | Real HubSpot API calls, E2E Step 8 (Execute Tool) |

---

## Specification

> See full specification: [../specs/WS-G4-spec.md](../specs/WS-G4-spec.md)

### Tool → API Mapping

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

### Required Headers

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}
```

### HubSpot-Specific Notes

- **Pagination:** Uses cursor-based pagination with `after` parameter
- **Email lookup:** Must use search endpoint (no direct email lookup)
- **Deal amount:** Must be string, not number
- **API Version:** CRM v3 (`/crm/v3/objects/...`)

---

## Pre-Conditions

- [x] WS-G1 complete (HubSpotConfig with base_url, timeout)
- [x] `BaseMCPClient` exists
- [x] `ToolResult` dataclass exists
- [x] httpx library available

---

## Task Description

### Objective

Replace the mock implementation in HubSpotClient with direct REST API calls to the HubSpot CRM API v3. The client should handle HubSpot's specific patterns for search, pagination, and property handling.

### Background

Currently, the Gateway's HubSpotClient returns mock responses. This task implements real API calls for both Contacts and Deals objects in HubSpot CRM.

### What to Implement

1. **Update `app/backends/hubspot_client.py`**:

   ```python
   import httpx
   from app.core.config import get_settings
   from app.backends.base_mcp_client import BaseMCPClient, ToolResult

   class HubSpotClient(BaseMCPClient):
       """Direct HubSpot CRM API client."""

       def __init__(self):
           settings = get_settings()
           self.base_url = settings.hubspot.base_url  # https://api.hubapi.com
           self.timeout = settings.hubspot.timeout_seconds

       def _get_headers(self, auth_token: str) -> dict:
           return {
               "Authorization": f"Bearer {auth_token}",
               "Content-Type": "application/json"
           }

       def _transform_response(self, tool_name: str, response: httpx.Response) -> ToolResult:
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
           return ToolResult(status="success", data=response.json())

       # --- CONTACTS ---

       async def get_contact(self, contact_id: str = None, email: str = None,
                            properties: list[str] = None, auth_token: str = None) -> ToolResult:
           if contact_id:
               url = f"{self.base_url}/crm/v3/objects/contacts/{contact_id}"
               params = {"properties": ",".join(properties)} if properties else None
               async with httpx.AsyncClient(timeout=self.timeout) as client:
                   response = await client.get(url, params=params, headers=self._get_headers(auth_token))
               return self._transform_response("get_contact", response)
           elif email:
               return await self.search_contacts(
                   filters=[{"propertyName": "email", "operator": "EQ", "value": email}],
                   limit=1, auth_token=auth_token
               )
           else:
               return ToolResult(status="error", error_code="missing_identifier",
                               error_message="Either contact_id or email required")

       async def create_contact(self, email: str, firstname: str = None, lastname: str = None,
                               properties: dict = None, auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/crm/v3/objects/contacts"
           props = {"email": email}
           if firstname: props["firstname"] = firstname
           if lastname: props["lastname"] = lastname
           if properties: props.update(properties)
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.post(url, json={"properties": props}, headers=self._get_headers(auth_token))
           return self._transform_response("create_contact", response)

       async def update_contact(self, contact_id: str, properties: dict,
                               auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/crm/v3/objects/contacts/{contact_id}"
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.patch(url, json={"properties": properties}, headers=self._get_headers(auth_token))
           return self._transform_response("update_contact", response)

       async def list_contacts(self, limit: int = 10, after: str = None,
                              properties: list[str] = None, auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/crm/v3/objects/contacts"
           params = {"limit": limit}
           if after: params["after"] = after
           if properties: params["properties"] = ",".join(properties)
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.get(url, params=params, headers=self._get_headers(auth_token))
           return self._transform_response("list_contacts", response)

       async def search_contacts(self, filters: list[dict], sorts: list[dict] = None,
                                properties: list[str] = None, limit: int = 10,
                                after: str = None, auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/crm/v3/objects/contacts/search"
           payload = {"filterGroups": [{"filters": filters}], "limit": limit}
           if sorts: payload["sorts"] = sorts
           if properties: payload["properties"] = properties
           if after: payload["after"] = after
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.post(url, json=payload, headers=self._get_headers(auth_token))
           return self._transform_response("search_contacts", response)

       # --- DEALS ---

       async def get_deal(self, deal_id: str, properties: list[str] = None,
                         auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/crm/v3/objects/deals/{deal_id}"
           params = {"properties": ",".join(properties)} if properties else None
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.get(url, params=params, headers=self._get_headers(auth_token))
           return self._transform_response("get_deal", response)

       async def create_deal(self, dealname: str, pipeline: str = "default",
                            dealstage: str = None, amount: float = None,
                            properties: dict = None, auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/crm/v3/objects/deals"
           props = {"dealname": dealname, "pipeline": pipeline}
           if dealstage: props["dealstage"] = dealstage
           if amount is not None: props["amount"] = str(amount)  # HubSpot requires string
           if properties: props.update(properties)
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.post(url, json={"properties": props}, headers=self._get_headers(auth_token))
           return self._transform_response("create_deal", response)

       async def update_deal(self, deal_id: str, properties: dict,
                            auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/crm/v3/objects/deals/{deal_id}"
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.patch(url, json={"properties": properties}, headers=self._get_headers(auth_token))
           return self._transform_response("update_deal", response)

       async def list_deals(self, limit: int = 10, after: str = None,
                           properties: list[str] = None, auth_token: str = None) -> ToolResult:
           url = f"{self.base_url}/crm/v3/objects/deals"
           params = {"limit": limit}
           if after: params["after"] = after
           if properties: params["properties"] = ",".join(properties)
           async with httpx.AsyncClient(timeout=self.timeout) as client:
               response = await client.get(url, params=params, headers=self._get_headers(auth_token))
           return self._transform_response("list_deals", response)
   ```

2. **Add comprehensive tests** mocking httpx responses

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/backends/hubspot_client.py` | Modify | Replace mock with real API calls |
| `deeptrail-gateway/tests/backends/test_hubspot_client.py` | Modify | Add httpx mock tests |

---

## Acceptance Criteria

### Functional Criteria - Contacts

- [ ] `get_contact` by ID calls GET `/crm/v3/objects/contacts/{id}`
- [ ] `get_contact` by email uses search endpoint
- [ ] `create_contact` calls POST `/crm/v3/objects/contacts`
- [ ] `update_contact` calls PATCH `/crm/v3/objects/contacts/{id}`
- [ ] `list_contacts` calls GET `/crm/v3/objects/contacts`
- [ ] `search_contacts` calls POST `/crm/v3/objects/contacts/search`

### Functional Criteria - Deals

- [ ] `get_deal` calls GET `/crm/v3/objects/deals/{id}`
- [ ] `create_deal` calls POST `/crm/v3/objects/deals`
- [ ] `update_deal` calls PATCH `/crm/v3/objects/deals/{id}`
- [ ] `list_deals` calls GET `/crm/v3/objects/deals`

### HubSpot-Specific Criteria

- [ ] CRM v3 API paths used (`/crm/v3/objects/...`)
- [ ] Search uses POST with `filterGroups` structure
- [ ] Pagination support via `after` cursor
- [ ] Deal amount converted to string (HubSpot requirement)
- [ ] Email lookup uses search (not direct endpoint)

### Integration Criteria

- [ ] Uses `HubSpotConfig` from WS-G1
- [ ] Auth token passed via `Authorization: Bearer` header
- [ ] Returns `ToolResult` compatible with existing handlers

---

## Test Cases

| Test Case | Tool | Mock Response | Expected |
|-----------|------|---------------|----------|
| Get contact by ID | `get_contact` | `{"id": "123", "properties": {...}}` | ToolResult with contact |
| Get contact by email | `get_contact` | Search result with 1 contact | ToolResult with contact |
| Get contact missing ID | `get_contact` | N/A | ToolResult with error "missing_identifier" |
| Create contact | `create_contact` | `{"id": "new-id", ...}` | ToolResult with new contact |
| Update contact | `update_contact` | `{"id": "123", ...}` | ToolResult with updated contact |
| List contacts | `list_contacts` | `{"results": [...]}` | ToolResult with contacts |
| List contacts paginated | `list_contacts` | `{"results": [...], "paging": {"next": {"after": "..."}}}` | ToolResult with cursor |
| Search contacts | `search_contacts` | `{"results": [...]}` | ToolResult with results |
| Get deal | `get_deal` | `{"id": "deal1", "properties": {...}}` | ToolResult with deal |
| Create deal | `create_deal` | `{"id": "deal-id", ...}` | ToolResult with deal |
| Create deal with amount | `create_deal` | Payload has `amount: "1000"` (string) | Amount is string |
| Update deal | `update_deal` | `{"id": "deal1", ...}` | ToolResult with updated deal |
| List deals | `list_deals` | `{"results": [...]}` | ToolResult with deals |
| Contact not found | `get_contact` | 404 response | ToolResult(status="error", error_code=404) |
| Validation error | `create_contact` | 400 response | ToolResult with validation error |
| Rate limited | Any | 429 response | ToolResult with rate limit error |

---

## Post-Conditions

After this task is complete:
- [ ] HubSpotClient makes real API calls (when given valid token)
- [ ] Mock implementation removed
- [ ] Both Contacts and Deals CRUD operations work
- [ ] E2E Step 8 (Execute Tool) works with real HubSpot data

---

## Validation

### Unit Tests
```bash
cd deeptrail-gateway
pytest tests/backends/test_hubspot_client.py -v
```

### Manual Verification (with real token)
```python
from app.backends.hubspot_client import HubSpotClient

client = HubSpotClient()
result = await client.list_contacts(limit=5, auth_token="<real_hubspot_token>")
print(result.status)
print(result.data if result.status == "success" else result.error_message)
```

---

## References

- **Specification:** [../specs/WS-G4-spec.md](../specs/WS-G4-spec.md)
- **Design Doc:** `plans/mvp_production_readiness.plan.md`
- **HubSpot API Docs:** https://developers.hubspot.com/docs/api/crm/contacts
- **Upstream:** WS-G1 (Backend configuration) ✅ Complete
- **Downstream:** WS-H1, WS-H2 (Credential injection)
- **Related Code:**
  - `deeptrail-gateway/app/core/config.py` (HubSpotConfig)
  - `deeptrail-gateway/app/backends/base_mcp_client.py`

---

## Execution

```bash
# Run in mvp-prod-gateway worktree:
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-G4 mvp-production-readiness
```
