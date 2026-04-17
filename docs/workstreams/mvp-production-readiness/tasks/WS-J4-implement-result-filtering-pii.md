# Task: WS-J4 Implement Result Filtering (PII Masking)

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-J4 |
| **Task Name** | Implement Result Filtering (PII Masking) |
| **Workstream** | mvp-production-readiness |
| **Phase** | P2 (Production Hardening) |
| **Batch** | P2-B1 |
| **Status** | `ready` |
| **Dependencies** | MP3.5 (P1.5 complete — ✅ reached Feb 23, 2026) |
| **Complexity** | M (1-3 hours) |
| **Service** | deeptrail-gateway |
| **Validates** | MCP Governance: sensitive data removal from tool call responses |

---

## Specification

| Field | Value |
|-------|-------|
| **Spec File** | [WS-J4-spec.md](../specs/WS-J4-spec.md) |
| **Source** | `deepsecure-comprehensive-architecture-consolidated.md` Section 11 (Gateway Components), MCP Governance Layer |
| **Coverage Matrix** | Result Filtering → PII masking → ❌ Not Implemented (0%) → target 80%+ |

### Key Contracts

| Component | Contract |
|-----------|----------|
| **ResultFilter** | Class with `filter_response()`, `mask_string()`, `_filter_dict()`, `_filter_list()`, `get_config_for_backend()` |
| **PIIType** | Enum: `EMAIL`, `PHONE`, `SSN`, `CREDIT_CARD`, `API_KEY`, `IP_ADDRESS` |
| **MaskingRule** | Dataclass: `pii_type`, `enabled`, `replacement`, `partial_mask`, `visible_chars` |
| **BackendFilterConfig** | Dataclass: `backend_id`, `enabled`, `masking_rules`, `excluded_fields`, `allowlisted_fields` |
| **FilterResult** | Dataclass: `filtered_content`, `masks_applied`, `pii_types_found`, `fields_excluded` |
| **Module accessors** | `get_result_filter()`, `configure_result_filter()`, `reset_result_filter()` |
| **Integration** | Called in `tools_call.py` **after** backend response, **before** returning to agent |

---

## API Contracts

> **Note:** This task implements an internal middleware module, not API endpoints.
> The result filter operates within the `tools/call` MCP handler pipeline.
> No new HTTP endpoints are created.
>
> When PII is masked, the response structure remains unchanged — only string values containing PII patterns are modified.

---

## Pre-Conditions

- [x] MP3.5 reached (P1.5 integration bugs fixed — Feb 23, 2026)
- [ ] `deeptrail-gateway` service compiles and starts
- [ ] `tools_call.py` handler exists with backend response handling
- [ ] `app/middleware/` directory exists with established patterns (`audit.py`, `credential_injection.py`)

---

## Task Description

### Objective

Implement a configurable PII masking filter that inspects tool call responses from backend APIs (Notion, Slack, HubSpot) and redacts sensitive data (emails, phone numbers, SSNs, credit cards, API keys) before returning results to agents.

### Background

Tool call responses from backend APIs are currently returned verbatim to agents. If a HubSpot contact search returns `sarah@acme.com` or `+1 (555) 123-4567`, the agent sees raw PII. The architecture specifies "Result Filtering: Mask PII, remove sensitive fields" as part of the MCP Governance Layer (Section 11).

The gateway already has input-side security (`security_filters.py` for XSS/SQLi, `sanitization.py` for request cleaning), but lacks output-side filtering. This task creates the complementary response filter.

**Key design principles:**
- Per-backend configurability (different backends may have different PII rules)
- Recursive traversal (backend responses can be deeply nested JSON)
- Fail-open on errors (availability > masking — log and return unfiltered if filter errors)
- Audit logging (log mask counts and PII types, never actual PII values)
- Module accessor pattern matching existing gateway middleware (`get_*`, `configure_*`, `reset_*`)

### What to Implement

#### 1. Core Module (`result_filter.py`)

- Define data models: `PIIType`, `MaskingRule`, `BackendFilterConfig`, `FilterResult`
- Implement `ResultFilter` class:
  - Compile 6 regex patterns at `__init__` time for performance
  - `filter_response()` — entry point, dispatches to dict/list/string handlers
  - `mask_string()` — applies all enabled masking rules to a string value
  - `_filter_dict()` — recursively processes dictionaries, respects excluded/allowlisted fields
  - `_filter_list()` — recursively processes lists
  - `get_config_for_backend()` — returns backend-specific or default config
- Define default masking rules (all PII types enabled except `IP_ADDRESS`)
- Implement module-level accessors: `get_result_filter()`, `configure_result_filter()`, `reset_result_filter()`

#### 2. PII Detection Patterns (6 types)

| PII Type | Replacement | Pattern |
|----------|-------------|---------|
| EMAIL | `[EMAIL REDACTED]` | RFC 5322 local@domain format |
| PHONE | `[PHONE REDACTED]` | US format with optional country code |
| SSN | `[SSN REDACTED]` | `XXX-XX-XXXX` format |
| CREDIT_CARD | `[CC REDACTED]` | 16-digit with optional separators |
| API_KEY | `[API_KEY REDACTED]` | `sk-*`, `xoxb-*`, `Bearer` prefixed |
| IP_ADDRESS | `[IP REDACTED]` | IPv4 dotted decimal (disabled by default) |

#### 3. Integration into tools/call Handler

- Import `get_result_filter` in `tools_call.py`
- After backend response is received and before returning MCP result:
  - Call `result_filter.filter_response(content, backend_id, tool_name)`
  - Replace response content with filtered version
  - Log audit info if any masks applied (tool, backend, count, types)

#### 4. Startup Configuration

- Add `configure_result_filter()` call in `main.py` during app startup (in `lifespan` or after middleware setup)

#### 5. Middleware Exports

- Update `app/middleware/__init__.py` to export result filter symbols

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/middleware/result_filter.py` | Create | `ResultFilter` class, data models, regex patterns, module accessors |
| `deeptrail-gateway/app/middleware/__init__.py` | Modify | Export `ResultFilter`, `get_result_filter`, `configure_result_filter`, `reset_result_filter` |
| `deeptrail-gateway/app/mcp/handlers/tools_call.py` | Modify | Add filter invocation after backend response |
| `deeptrail-gateway/app/main.py` | Modify | Add `configure_result_filter()` during startup |
| `deeptrail-gateway/tests/middleware/test_result_filter.py` | Create | Unit tests for all filter functionality |

---

## Acceptance Criteria

### Functional

- [ ] `ResultFilter` class exists in `deeptrail-gateway/app/middleware/result_filter.py`
- [ ] All 6 PII types have compiled regex patterns
- [ ] `filter_response()` recursively traverses nested dicts and lists
- [ ] `filter_response()` returns `FilterResult` with audit metadata (`masks_applied`, `pii_types_found`)
- [ ] `mask_string()` applies all enabled rules, returns masked string + detected types
- [ ] Per-backend configuration works via `BackendFilterConfig`
- [ ] `excluded_fields` are removed from responses
- [ ] `allowlisted_fields` are preserved (not masked)
- [ ] Disabled filter (`enabled=False`) passes content through unchanged
- [ ] Disabled individual rules (`rule.enabled=False`) are skipped
- [ ] Default config fallback when backend ID not in config
- [ ] Module accessor pattern: `get_result_filter()`, `configure_result_filter()`, `reset_result_filter()`
- [ ] Empty/null content handled gracefully (no exceptions)

### Security

- [ ] PII values never appear in log output (only counts and type names)
- [ ] Regex patterns tested against ReDoS with pathological inputs
- [ ] No false positives on short/normal strings (e.g., `"test"`, `"hello"`)
- [ ] Only string values are masked (dict keys, integers, booleans untouched)
- [ ] Binary/base64 content skipped (not treated as strings for masking)
- [ ] Fail-open: if filter errors internally, log error and return unfiltered content

### Integration

- [ ] `tools_call.py` invokes filter after backend response, before MCP return
- [ ] `main.py` calls `configure_result_filter()` during startup
- [ ] Exports added to `app/middleware/__init__.py`
- [ ] Existing tool call flows (Notion, Slack, HubSpot) continue working with filter active
- [ ] No regression in existing middleware pipeline

---

## Test Cases

| Test Case | Method | Module | Expected | Notes |
|-----------|--------|--------|----------|-------|
| Mask email in string | `mask_string()` | `test_result_filter.py` | `"Contact [EMAIL REDACTED] for info"` | Basic email pattern |
| Mask phone US format | `mask_string()` | `test_result_filter.py` | `"Call [PHONE REDACTED]"` | `+1 (555) 123-4567` |
| Mask SSN | `mask_string()` | `test_result_filter.py` | `"SSN: [SSN REDACTED]"` | `123-45-6789` |
| Mask credit card | `mask_string()` | `test_result_filter.py` | `"CC: [CC REDACTED]"` | With/without dashes |
| Mask OpenAI API key | `mask_string()` | `test_result_filter.py` | `"Key: [API_KEY REDACTED]"` | `sk-abc...` (32+ chars) |
| Mask Slack bot token | `mask_string()` | `test_result_filter.py` | `"Token: [API_KEY REDACTED]"` | `xoxb-*` format |
| No false positive on "test" | `mask_string()` | `test_result_filter.py` | `"test"` unchanged | Short string |
| Nested dict filtering | `filter_response()` | `test_result_filter.py` | PII masked at all depths | 3-level nesting |
| List filtering | `filter_response()` | `test_result_filter.py` | PII masked in list items | Array of objects |
| Excluded fields removed | `filter_response()` | `test_result_filter.py` | Field absent from result | `excluded_fields` config |
| Allowlisted fields preserved | `filter_response()` | `test_result_filter.py` | Field NOT masked | `allowlisted_fields` config |
| Disabled filter passthrough | `filter_response()` | `test_result_filter.py` | Content unchanged, `masks_applied=0` | `enabled=False` |
| Disabled rule skipped | `filter_response()` | `test_result_filter.py` | Only enabled rules apply | Individual rule disabled |
| Backend-specific config | `filter_response()` | `test_result_filter.py` | Per-backend rules used | Different backends |
| Default config fallback | `get_config_for_backend()` | `test_result_filter.py` | Default rules for unknown backend | Fallback |
| FilterResult metadata | `filter_response()` | `test_result_filter.py` | `masks_applied > 0`, `pii_types_found` populated | Audit |
| Multiple PII in one string | `mask_string()` | `test_result_filter.py` | All instances masked | Email + phone combo |
| Only string values masked | `filter_response()` | `test_result_filter.py` | Keys/numbers untouched | Dict keys preserved |
| Empty/null content | `filter_response()` | `test_result_filter.py` | `None` returned, `masks_applied=0` | Edge case |
| Module accessor pattern | `configure/get/reset` | `test_result_filter.py` | Lifecycle works correctly | Global state |

---

## Post-Conditions

After this task is complete:

- [ ] MCP `tools/call` responses have PII masked before reaching agents
- [ ] WS-J6 (Keycloak Token Exchange) can proceed — governance layer partially in place
- [ ] Audit logs capture PII masking events (type counts per tool call)
- [ ] Per-backend PII rules can be configured for Notion, Slack, HubSpot independently
- [ ] Coverage Matrix "Result Filtering" moves from 0% to ~80%

---

## Validation

### Unit Tests

```bash
cd /Users/imaxxs/repositories/mvp-prod-gateway/deeptrail-gateway

# Run result filter tests
pytest tests/middleware/test_result_filter.py -v

# Run all middleware tests to check no regression
pytest tests/middleware/ -v
```

### Manual Verification

```bash
# 1. Start services
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d
sleep 15

# 2. Login and get tokens
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')
echo "User token: ${USER_TOKEN:0:20}..."
# Expected: Token string (not "null")

# 3. Create agent JWT (abbreviated — see CLAUDE.md for full flow)
# ... (Ed25519 challenge-response flow) ...

# 4. Initialize MCP session
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "method": "initialize", "id": 1,
    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
               "clientInfo": {"name": "test", "version": "1.0.0"}}
  }' | jq '.result.serverInfo'
# Expected: Server info object

# 5. Call a tool that returns contact data
RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "method": "tools/call", "id": 2,
    "params": {"name": "hubspot.search_contacts",
               "arguments": {"query": "sarah"}}
  }')
echo "$RESULT" | jq '.'
# Expected: Email addresses show as "[EMAIL REDACTED]"
# Expected: Phone numbers show as "[PHONE REDACTED]"

# 6. Check Gateway logs for masking events
docker compose logs deeptrail-gateway --tail=10 | grep -i "PII masked"
# Expected: Log line with tool name, backend, masks_applied count

# 7. Verify non-PII content preserved
echo "$RESULT" | jq '.result.content[0].text' | grep -v "REDACTED"
# Expected: Non-PII data (names, IDs, timestamps) preserved intact

# 8. Verify existing tools still work
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "method": "tools/list", "id": 3,
    "params": {}
  }' | jq '.result.tools | length'
# Expected: Same number of tools as before (no regression)
```

### Regex Pattern Validation

```bash
# Quick validation of PII patterns (run in Python)
cd /Users/imaxxs/repositories/mvp-prod-gateway/deeptrail-gateway
python -c "
from app.middleware.result_filter import ResultFilter, PIIType

rf = ResultFilter()

# Test each PII type
tests = [
    ('sarah@acme.com', PIIType.EMAIL),
    ('+1 (555) 123-4567', PIIType.PHONE),
    ('123-45-6789', PIIType.SSN),
    ('4111-1111-1111-1111', PIIType.CREDIT_CARD),
    ('sk-abc123def456ghi789jkl012mno345pqr678', PIIType.API_KEY),
]

for value, expected_type in tests:
    result, types = rf.mask_string(value, rf._default_rules)
    found = expected_type in types
    print(f'{'✅' if found else '❌'} {expected_type.value}: \"{value}\" → \"{result}\"')

# False positive test
clean, types = rf.mask_string('hello world', rf._default_rules)
assert len(types) == 0, f'False positive: {types}'
print('✅ No false positives on clean string')
"
```

---

## References

- **Spec:** [WS-J4-spec.md](../specs/WS-J4-spec.md) — full interface contract, regex patterns, test code
- **Architecture:** `deepsecure-comprehensive-architecture-consolidated.md` — MCP Governance Layer: "Result Filtering: Mask PII, remove sensitive fields"
- **Coverage Matrix:** `MVP_COVERAGE_MATRIX.md` — Result Filtering: 0% → target 80%+
- **Existing Patterns:**
  - `deeptrail-gateway/app/middleware/audit.py` — module accessor pattern (`get_*`, `configure_*`, `reset_*`)
  - `deeptrail-gateway/app/middleware/credential_injection.py` — module accessor pattern
  - `deeptrail-gateway/app/core/security_filters.py` — regex-based pattern detection (XSS, SQLi)
- **Integration Point:** `deeptrail-gateway/app/mcp/handlers/tools_call.py` — where filter is invoked
- **Startup:** `deeptrail-gateway/app/main.py` — where `configure_result_filter()` is called
- **Upstream Dependencies:** MP3.5 (✅ reached Feb 23, 2026)
- **Downstream Dependents:** WS-J6 (Keycloak token exchange — governance layer must be in place)

---

## Execution

```bash
# Run in mvp-prod-gateway worktree:
cd /Users/imaxxs/repositories/mvp-prod-gateway

# Execute the task
/execute-task WS-J4 mvp-production-readiness

# After completion
/complete-task WS-J4 mvp-production-readiness
```
