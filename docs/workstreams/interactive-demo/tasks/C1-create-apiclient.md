# Task: C1 Create APIClient with Display Formatting

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `completed` |
| **Design Doc** | [Interactive Demo Plan](../../../../.cursor/plans/interactive_demo_plan_7ee6283a.plan.md) |
| **Specification** | [C1-spec.md](../specs/C1-spec.md) |
| **Workstream** | Interactive Demo |
| **Code Dependencies** | None |
| **Runtime Dependencies** | None (backend services needed for actual HTTP calls) |
| **Blocked By** | None |
| **Assigned** | - |
| **Created** | February 2026 |
| **Estimated Complexity** | `M` (1-3hr) |
| **Batch** | 1 |
| **Target Worktree** | `deepsecure-mvp` (main repo) |

---

## Dependencies

### Code Dependencies (must complete before starting)

None - this is a standalone utility with no internal dependencies.

### Runtime Dependencies (must be deployed for integration testing)

| Service | Endpoint | Required For |
|---------|----------|--------------|
| Control Plane | http://localhost:8000 | Actual HTTP requests |
| Gateway | http://localhost:8002 | Gateway/MCP requests |

> **Note:** The APIClient can be developed and unit tested without backend services. Runtime dependencies are only needed for integration testing with real API calls.

### Development Mode

- [x] **Fallback behavior**: Can display formatted requests/responses with mock data
- [x] **Local testing**: Display methods can be tested without HTTP calls
- [x] **Integration testing**: Requires backend services for actual requests

---

## Pre-Conditions

Before starting this task, ensure:

- [x] No blocking code dependencies - can start immediately
- [x] `demos/interactive/` directory exists
- [x] External dependencies available: `httpx`, `rich`

---

## Task Description

Create an async HTTP client wrapper that displays formatted requests and responses in the terminal using the `rich` library. This makes API interactions visible and educational during the interactive demo.

### Context

The interactive demo needs to show users what's happening "under the hood" when API calls are made:
- Display the HTTP method, URL, headers, and JSON body for requests
- Display status codes (color-coded), response times, and JSON bodies for responses
- Provide utility methods for displaying informational messages, errors, and raw JSON

### Technical Notes

- Use `httpx.AsyncClient` as the underlying HTTP client
- Use `rich.console.Console` for terminal output
- Use `rich.panel.Panel` for bordered display boxes
- Use `rich.syntax.Syntax` for JSON syntax highlighting
- Status code colors: green (2xx), yellow (4xx), red (5xx)
- Support async context manager pattern (`async with APIClient() as client:`)

---

## Specification (IMMUTABLE)

> **Source:** [C1-spec.md](../specs/C1-spec.md)

### Interface Contract

```python
class APIClient:
    def __init__(
        self,
        control_plane_url: str = "http://localhost:8000",
        gateway_url: str = "http://localhost:8002",
        console: Console | None = None,
    ) -> None: ...
    
    async def request(
        self, method: str, url: str,
        json: dict | None = None, headers: dict | None = None,
        show_request: bool = True, show_response: bool = True,
    ) -> httpx.Response: ...
    
    async def get(self, url: str, ...) -> httpx.Response: ...
    async def post(self, url: str, json: dict | None = None, ...) -> httpx.Response: ...
    
    def show_request(self, method: str, url: str, body: dict | None = None, headers: dict | None = None) -> None: ...
    def show_response(self, response: httpx.Response, highlight_fields: list[str] | None = None) -> None: ...
    def show_json(self, data: dict, title: str | None = None) -> None: ...
    def show_info(self, message: str, title: str | None = None) -> None: ...
    def show_error(self, message: str, title: str = "Error") -> None: ...
    
    async def close(self) -> None: ...
    async def __aenter__(self) -> "APIClient": ...
    async def __aexit__(self, *args) -> None: ...
```

### URL Resolution Logic

```python
def _resolve_url(self, url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if "gateway" in url or "mcp" in url:
        return f"{self.gateway_url}{url}"
    return f"{self.control_plane_url}{url}"
```

### File Location

| Artifact | Path |
|----------|------|
| Implementation | `demos/interactive/api_client.py` |
| Unit tests | `tests/demos/test_api_client.py` (optional) |

---

## Acceptance Criteria

### Functional Criteria
- [ ] `APIClient` class can be instantiated with default URLs
- [ ] `APIClient` class can be instantiated with custom URLs and console
- [ ] `request()` makes HTTP calls and optionally displays request/response
- [ ] `get()` and `post()` convenience methods work correctly
- [ ] `show_request()` displays formatted request panel with method, URL, headers, body
- [ ] `show_response()` displays formatted response with color-coded status
- [ ] `show_response()` supports field highlighting
- [ ] `show_json()` displays arbitrary JSON in a panel
- [ ] `show_info()` displays informational message in a panel
- [ ] `show_error()` displays error message in red panel
- [ ] URL resolution routes to correct base URL (control plane vs gateway)
- [ ] Async context manager works (`async with APIClient() as client:`)

### Contract Verification (REQUIRED)
- [ ] Implementation matches [C1-spec.md](../specs/C1-spec.md) exactly
- [ ] All method signatures match spec
- [ ] URL resolution logic matches spec

### Technical Criteria
- [ ] Type hints on all methods
- [ ] Docstrings on class and all public methods
- [ ] Uses `httpx.AsyncClient` for HTTP
- [ ] Uses `rich` for terminal formatting
- [ ] No linting errors: `ruff check demos/interactive/api_client.py`

---

## Files to Modify/Create

### Files to Create
- `demos/interactive/api_client.py` - APIClient class

### Tests to Add (Optional)
- `tests/demos/test_api_client.py` - Unit tests for display methods

---

## Post-Conditions

### Code Complete

- [ ] All acceptance criteria met
- [ ] File created at correct path: `demos/interactive/api_client.py`
- [ ] Linting passes: `ruff check demos/interactive/`
- [ ] Contract verified against spec

### Verification Command

```bash
# Verify implementation exists
ls demos/interactive/api_client.py

# Quick import test
python -c "from demos.interactive.api_client import APIClient; print('APIClient imported successfully')"

# Test display methods (no HTTP calls needed)
python -c "
from demos.interactive.api_client import APIClient
client = APIClient()
client.show_info('Test message', title='Test')
client.show_json({'key': 'value'}, title='JSON Test')
"
```

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| A3 | Code dependency satisfied | Can export APIClient in __init__.py |
| D1 | Code dependency satisfied | Can use APIClient in step handlers |
| E1 | Code dependency satisfied | Can use APIClient in main entry point |

---

## References

- Design Doc: [Interactive Demo Plan](../../../../.cursor/plans/interactive_demo_plan_7ee6283a.plan.md)
- Specification: [C1-spec.md](../specs/C1-spec.md)
- Reference: `demos/demo_sarah_journey_e2e.py` (simpler HTTP calls without display)
- External: [Rich documentation](https://rich.readthedocs.io/)
- External: [httpx documentation](https://www.python-httpx.org/)

---

## Notes

- Consider caching the `httpx.AsyncClient` instance for connection reuse
- Password fields should be masked in display (show `********`)
- Long tokens can be truncated with `...` for readability
- Response time can be calculated using `response.elapsed`

---

## Execution Log

<!-- Updated during task execution -->

### Progress Updates

| Date | Update |
|------|--------|
| - | Task ticket created |
| 2026-02-10 | Started task |
| 2026-02-10 | Implemented APIClient with all methods |
| 2026-02-10 | Display methods verified working |
| 2026-02-10 | URL resolution verified working |
| 2026-02-10 | Async context manager verified |
| 2026-02-10 | Ruff linting passed |
| 2026-02-10 | Ready for completion |

### Blockers Encountered

| Date | Blocker | Resolution |
|------|---------|------------|
| - | - | - |
