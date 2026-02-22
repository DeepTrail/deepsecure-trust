# Task: WS-J2 Fix Tool Name Derivation and Cache Alignment

> **Status:** `ready`
> **Created Date:** February 22, 2026
> **Batch:** P1-B4 (Bug Fixes)
> **Worktree:** mvp-prod-gateway

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-J2 |
| **Workstream** | J (Bug Fixes) |
| **Phase** | P1 (Real Backend Integration) |
| **Dependencies** | WS-H1, WS-H2 (Credential Injection) ✅ Complete |
| **Complexity** | M (1-3 hrs) |
| **Service** | deeptrail-gateway |
| **Validates** | E2E Steps 16-17 (tools/list, tools/call), Real API Integration |

---

## Specification

> See full specification: [../specs/WS-J2-spec.md](../specs/WS-J2-spec.md)

### Key Contracts

**Root Cause:** Tool name mismatch between three sources:

| Source | Tool Name | Example |
|--------|-----------|---------|
| Initialize Handler (current) | Plural form | `read_pages` |
| Permission Mapper (expected) | Singular form | `read_page` |
| Tool Cache (expected) | Singular form | `read_page` |

**Fix Required:**
1. `initialize.py` - Use `PermissionMapper.get_all_tools_for_permission()` 
2. `tool_definitions.py` - Add missing tool definitions

---

## API Contracts

> **Note:** This task implements an internal fix, not API endpoints.
> The fix aligns internal components (initialize handler, tool cache, permission mapper).
> See WS-H1/H2 for related credential injection.

---

## Pre-Conditions

- [x] WS-H1 Complete (Credential injection from vault)
- [x] WS-H2 Complete (Token refresh integration)
- [x] `PermissionMapper` class exists with `get_all_tools_for_permission()` method
- [x] `tool_definitions.py` exists with initial tool definitions
- [x] `TOOL_TO_PERMISSION` map exists in `permission_mapper.py`

---

## Task Description

### Objective

Fix the tool name derivation in `initialize.py` to use Permission Mapper's reverse lookup, and complete the tool cache definitions to cover all tools known to the Permission Mapper.

### Background

The current `initialize.py` handler derives tool names from permissions using string manipulation:
```python
tool_name = f"{parts[2]}_{parts[1]}"  # notion:pages:read → "read_pages" (WRONG - plural)
```

But the Permission Mapper expects:
```python
"notion.read_page": "notion:pages:read"  # "read_page" (CORRECT - singular)
```

This mismatch causes:
1. `tools/list` to return minimal schemas (cache miss)
2. `tools/call` to fail with "unknown tool" warnings
3. Real Notion API calls to fail even with valid credentials

### What to Implement

**Fix 1: Update Initialize Handler (`initialize.py`)**

1. Import `PermissionMapper` at top of file
2. Replace manual tool name derivation with:
   ```python
   tools = PermissionMapper.get_all_tools_for_permission(perm)
   ```
3. Extract tool name without namespace (e.g., `"notion.search_pages"` → `"search_pages"`)
4. Apply same fix for Slack permissions

**Fix 2: Complete Tool Cache Definitions (`tool_definitions.py`)**

Add missing tools to align with Permission Mapper:

| Tool to Add | Permission | Backend |
|-------------|------------|---------|
| `read_page` | `notion:pages:read` | Notion |
| `delete_page` | `notion:pages:delete` | Notion |
| `list_databases` | `notion:databases:list` | Notion |
| `query_database` | `notion:databases:query` | Notion |
| `send_message` | `slack:messages:send` | Slack |
| `join_channel` | `slack:channels:join` | Slack |
| `list_users` | `slack:users:list` | Slack |

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/mcp/handlers/initialize.py` | Modify | Use PermissionMapper reverse lookup instead of manual derivation |
| `deeptrail-gateway/app/mcp/tool_definitions.py` | Modify | Add missing tool definitions for all Permission Mapper tools |

---

## Acceptance Criteria

### Functional Criteria

- [ ] Initialize handler uses `PermissionMapper.get_all_tools_for_permission()`
- [ ] No more manual tool name derivation with `parts[2]_parts[1]`
- [ ] Session stores singular tool names (e.g., `read_page`, not `read_pages`)
- [ ] Tool cache contains definitions for ALL tools in `TOOL_TO_PERMISSION`
- [ ] `tools/list` returns proper descriptions and inputSchema (not minimal)
- [ ] No "Permission denied for unknown tool" warnings in Gateway logs

### Security Criteria

- [ ] Permission checking still works correctly (fail-closed behavior preserved)
- [ ] No regression in existing tool permission validation

### Integration Criteria

- [ ] `tools/list` returns expected tool schemas
- [ ] `tools/call` with real Notion API returns actual data (not "token invalid")
- [ ] Bearer token capitalization is correct (`Bearer`, not `bearer`)

---

## Test Cases

| Test Case | Input | Expected Outcome |
|-----------|-------|------------------|
| Permission `notion:pages:read` | JWT with this permission | Session contains `read_page` (singular) |
| Permission `notion:databases:query` | JWT with this permission | Session contains `query_database` (singular) |
| `tools/list` after fix | Valid AGENT_JWT | Returns tools with full inputSchema |
| `tools/call` search_pages | Valid AGENT_JWT + Notion API key | Returns real Notion API response |
| Gateway logs | After tools/list | No "unknown tool" warnings |

---

## Post-Conditions

After completing this task:

- [x] `tools/list` returns proper tool descriptions and schemas
- [x] `tools/call` works with real Notion API
- [x] Real API integration validation can proceed
- [x] E2E Steps 16-17 pass with real API keys

---

## Validation

### Unit Tests

```bash
cd deeptrail-gateway
pytest tests/mcp/handlers/test_initialize.py -v
pytest tests/mcp/test_tool_definitions.py -v
```

### Manual Verification

```bash
# 1. Rebuild Gateway
docker compose build --no-cache deeptrail-gateway
docker compose up -d deeptrail-gateway
sleep 15

# 2. Check logs for tool cache population
docker compose logs deeptrail-gateway --tail=30 | grep -i "tool"
# Expected: "Tool cache populated with backend tool definitions"

# 3. Re-login and setup (if needed)
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "sarah@acme.com", "password": "test_password"}' | jq -r '.token')

# 4. Initialize MCP session
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}' | jq .

# 5. Verify tools/list returns full schemas
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 2, "params": {}}' | jq '.result.tools[0]'
# Expected: description with full text, inputSchema with properties

# 6. Verify no unknown tool warnings
docker compose logs deeptrail-gateway --tail=20 | grep "unknown tool"
# Expected: No matches

# 7. Test real API call (if Notion connected)
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "id": 3, "params": {"name": "notion.search_pages", "arguments": {"query": "", "limit": 5}}}' | jq .
# Expected: Real Notion API response with "object": "list"
```

---

## References

- **Spec:** [../specs/WS-J2-spec.md](../specs/WS-J2-spec.md)
- **Related Specs:** [WS-H1-spec.md](../specs/WS-H1-spec.md), [WS-H2-spec.md](../specs/WS-H2-spec.md)
- **Upstream Dependencies:** WS-H1, WS-H2 (Credential Injection)
- **Downstream Dependents:** All tools/list and tools/call functionality
- **Related Code:**
  - `deeptrail-gateway/app/mcp/handlers/initialize.py` (lines 221-253)
  - `deeptrail-gateway/app/mcp/tool_definitions.py`
  - `deeptrail-gateway/app/mcp/permission_mapper.py` (TOOL_TO_PERMISSION map)

---

## Execution

```bash
# Run in mvp-prod-gateway worktree:
cd /Users/imaxxs/repositories/mvp-prod-gateway

# Execute the task
# /execute-task WS-J2 mvp-production-readiness
```
