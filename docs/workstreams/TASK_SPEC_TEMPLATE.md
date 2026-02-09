# Task Specification: [WS-ID] [Task Name]

> **Purpose**: This section defines the IMMUTABLE specification that implementation MUST match.
> It is separate from execution tracking and should not change after design approval.
> Copy this into each task ticket's "## Specification" section.

---

## API Contract (if applicable)

### Endpoint Definition

| Field | Value |
|-------|-------|
| **Method** | `POST` / `GET` / `PUT` / `DELETE` |
| **Path** | `/api/v1/exact/path/here` |
| **Auth** | Bearer token / JWT / None |
| **Content-Type** | `application/json` |

### Request Schema

```json
{
  "field_name": "string",
  "optional_field?": "number"
}
```

### Response Schema (Success - 200/201)

```json
{
  "id": "string",
  "created_at": "ISO8601 datetime"
}
```

### Error Responses

| Status | Condition | Response Body |
|--------|-----------|---------------|
| 400 | Invalid input | `{"error": "validation_error", "details": [...]}` |
| 401 | Unauthorized | `{"error": "unauthorized"}` |
| 404 | Not found | `{"error": "not_found"}` |

---

## Data Model Specification (if applicable)

### Model: `[ModelName]`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | UUID primary key |
| `created_at` | `datetime` | Yes | Creation timestamp |
| `field_name` | `str` | Yes | Description |

### Database Table

```sql
CREATE TABLE table_name (
    id UUID PRIMARY KEY,
    field_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Protocol Specification (if applicable)

### Message Format

```json
{
  "jsonrpc": "2.0",
  "method": "exact/method/name",
  "params": { ... },
  "id": "string"
}
```

### Protocol Sequence

```
1. Client sends: [message type]
2. Server responds: [response type]
3. Client must: [next action]
```

---

## Test Endpoint Specification

> **CRITICAL**: Tests MUST use these exact endpoints. Any deviation means either the spec or implementation is wrong.

### Test Cases with Expected Endpoints

| Test Case | Method | Endpoint | Expected Status |
|-----------|--------|----------|-----------------|
| Happy path | POST | `/api/v1/exact/path` | 200 |
| Invalid input | POST | `/api/v1/exact/path` | 400 |
| Unauthorized | POST | `/api/v1/exact/path` | 401 |

---

## Technical Requirements

### Framework-Specific Requirements

| Requirement | Pattern | Why |
|-------------|---------|-----|
| Async test fixtures | `@pytest_asyncio.fixture` not `@pytest.fixture` | Async generators require pytest-asyncio |
| HTTP client | `httpx.AsyncClient` | Consistent with project |
| Mock pattern | `unittest.mock.AsyncMock` | For async mocks |

### Service Dependencies

| Service | Health Check | Required For |
|---------|--------------|--------------|
| Control Plane | `curl http://localhost:8000/health` | Agent auth, delegation |
| Gateway | `curl http://localhost:8002/health` | MCP protocol |
| Redis | `redis-cli ping` | Session storage |

### Mock Strategy (when services unavailable)

```python
# Pattern for mocking this endpoint
from unittest.mock import AsyncMock, patch

@patch("module.client.post")
async def test_with_mock(mock_post):
    mock_post.return_value = AsyncMock(status_code=200, json=lambda: {"id": "test"})
    # test code
```

---

## File Location Rules

### Cross-Service Artifacts

| Artifact Type | Correct Location | Wrong Location |
|---------------|------------------|----------------|
| MVP E2E tests | `tests/e2e/` (root) | `deeptrail-gateway/tests/e2e/` |
| MVP demos | `demos/` (root) | `deeptrail-gateway/demos/` |
| Service-specific tests | `[service]/tests/` | Root level |

### Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| E2E test | `test_[persona]_journey.py` | `test_sarah_journey.py` |
| Demo | `demo_[number]_[value_prop].py` | `demo_01_unified_connection.py` |
| Unit test | `test_[module].py` | `test_session_manager.py` |

---

## Validation Mapping

### This Task Validates

| Validation Type | ID | Description |
|-----------------|----|-----------------------|
| Demo | Demo 1 | Unified MCP Connection |
| User Journey Step | Step 5 | Agent Authenticates |

### Dependent Validations

| Downstream | What They Validate | Blocked Until This Complete |
|------------|-------------------|-----------------------------|
| WS-F1 | Full E2E journey | Yes - needs this endpoint |

---

## Contract Verification Checklist

Before marking complete, verify these match exactly:

- [ ] Endpoint path matches spec: `/api/v1/exact/path`
- [ ] Request schema matches spec
- [ ] Response schema matches spec
- [ ] Error responses match spec
- [ ] Tests use correct endpoint paths
- [ ] Framework requirements met (async fixtures, etc.)
- [ ] File in correct location (root vs service-specific)
