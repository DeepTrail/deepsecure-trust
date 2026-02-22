# Task Specification: WS-J2 Fix Tool Name Derivation and Cache Alignment

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** Debug session findings, tools/list and tools/call regression

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-J2 |
| **Task Name** | Fix Tool Name Derivation and Cache Alignment |
| **Type** | Bug Fix (Handler + Configuration) |
| **Service** | deeptrail-gateway |
| **Complexity** | M (1-3 hrs) |
| **Dependencies** | WS-H1, WS-H2 (Credential Injection) |
| **Validates** | E2E Steps 16-17 (tools/list, tools/call), Real API Integration |

---

## Problem Statement

### Root Cause Analysis

Three interrelated issues cause tools/list to return minimal schemas and tools/call to fail:

| Issue | Location | Problem | Effect |
|-------|----------|---------|--------|
| Issue 1 | `initialize.py` line 230 | Tool names derived incorrectly from permissions | Session stores `read_pages` (plural) instead of `read_page` (singular) |
| Issue 2 | `tool_definitions.py` | Missing tool definitions | Cache doesn't have `read_page`, `list_databases`, etc. |
| Issue 3 | Multiple files | Naming inconsistency | Permission Mapper expects `read_page`, session has `read_pages` |

### Failure Flow

```
Permission: "notion:pages:read"
        ↓
initialize.py derives: "read_pages" (parts[2]_parts[1])
        ↓
Session stores: ["notion.read_pages"]
        ↓
PermissionMapper.is_tool_permitted("notion.read_pages")
        ↓
TOOL_TO_PERMISSION["notion.read_pages"] → NOT FOUND
(expects "notion.read_page" singular)
        ↓
Tool DENIED ❌
```

---

## Fix 1: Initialize Handler - Use Permission Mapper Reverse Lookup

### File: `deeptrail-gateway/app/mcp/handlers/initialize.py`

### Current Implementation (Lines 221-237)

```python
# Check for notion permissions
notion_perms = [p for p in delegated_permissions if p.startswith("notion:")]
if notion_perms:
    # Create tools from permissions (e.g., notion:pages:search -> search_pages)
    notion_tools = []
    for perm in notion_perms:
        parts = perm.split(":")
        if len(parts) >= 3:
            # Map permission to tool name (e.g., pages:search -> search_pages)
            tool_name = f"{parts[2]}_{parts[1]}" if len(parts) == 3 else parts[2]
            notion_tools.append(tool_name)
    
    connected_services.append({
        "service_id": "notion",
        "oauth_token_ref": f"vault://notion-oauth-{agent_session_id}",
        "available_tools": notion_tools or ["search_pages", "get_page"],
    })
```

### Fixed Implementation

```python
from ..permission_mapper import PermissionMapper

# Check for notion permissions
notion_perms = [p for p in delegated_permissions if p.startswith("notion:")]
if notion_perms:
    # Use Permission Mapper to get correct tool names
    notion_tools = []
    for perm in notion_perms:
        # Get all tools that require this permission
        tools = PermissionMapper.get_all_tools_for_permission(perm)
        for tool in tools:
            # Extract tool name without namespace (e.g., "notion.search_pages" → "search_pages")
            if "." in tool:
                _, tool_name = tool.split(".", 1)
                notion_tools.append(tool_name)
    
    # Remove duplicates while preserving order
    notion_tools = list(dict.fromkeys(notion_tools))
    
    if notion_tools:
        connected_services.append({
            "service_id": "notion",
            "oauth_token_ref": f"vault://notion-oauth-{agent_session_id}",
            "available_tools": notion_tools,
        })
```

### Apply Same Fix for Slack (Lines 240-253)

```python
# Check for slack permissions
slack_perms = [p for p in delegated_permissions if p.startswith("slack:")]
if slack_perms:
    # Use Permission Mapper to get correct tool names
    slack_tools = []
    for perm in slack_perms:
        tools = PermissionMapper.get_all_tools_for_permission(perm)
        for tool in tools:
            if "." in tool:
                _, tool_name = tool.split(".", 1)
                slack_tools.append(tool_name)
    
    slack_tools = list(dict.fromkeys(slack_tools))
    
    if slack_tools:
        connected_services.append({
            "service_id": "slack",
            "oauth_token_ref": f"vault://slack-oauth-{agent_session_id}",
            "available_tools": slack_tools,
        })
```

---

## Fix 2: Complete Tool Cache Definitions

### File: `deeptrail-gateway/app/mcp/tool_definitions.py`

### Current Notion Tools (Missing Several)

```python
NOTION_TOOLS = [
    CachedTool(name="search_pages", ...),
    CachedTool(name="get_page", ...),
    CachedTool(name="create_page", ...),
    CachedTool(name="update_page", ...),
]
```

### Required: Add All Tools from Permission Mapper

Add these missing Notion tools to align with `TOOL_TO_PERMISSION`:

```python
# Add to NOTION_TOOLS list:
CachedTool(
    name="read_page",
    description="Read a specific Notion page by ID",
    inputSchema={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "The Notion page ID (UUID format)"
            }
        },
        "required": ["page_id"]
    }
),
CachedTool(
    name="delete_page",
    description="Archive/delete a Notion page",
    inputSchema={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "The Notion page ID to delete"
            }
        },
        "required": ["page_id"]
    }
),
CachedTool(
    name="list_databases",
    description="List all databases in Notion workspace",
    inputSchema={
        "type": "object",
        "properties": {
            "page_size": {
                "type": "integer",
                "description": "Number of results to return",
                "default": 10
            }
        }
    }
),
CachedTool(
    name="query_database",
    description="Query a Notion database with filters",
    inputSchema={
        "type": "object",
        "properties": {
            "database_id": {
                "type": "string",
                "description": "The Notion database ID"
            },
            "filter": {
                "type": "object",
                "description": "Filter conditions"
            },
            "page_size": {
                "type": "integer",
                "description": "Number of results",
                "default": 100
            }
        },
        "required": ["database_id"]
    }
),
```

### Add Missing Slack Tools

```python
# Add to SLACK_TOOLS list:
CachedTool(
    name="send_message",
    description="Send a message to a Slack channel",
    inputSchema={
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "description": "Channel ID to send message to"
            },
            "text": {
                "type": "string",
                "description": "Message text"
            }
        },
        "required": ["channel", "text"]
    }
),
CachedTool(
    name="join_channel",
    description="Join a Slack channel",
    inputSchema={
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "description": "Channel ID to join"
            }
        },
        "required": ["channel"]
    }
),
CachedTool(
    name="list_users",
    description="List users in Slack workspace",
    inputSchema={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum users to return",
                "default": 100
            }
        }
    }
),
```

---

## Alignment Verification Table

### Permission Mapper ↔ Tool Cache ↔ Notion Client

| Permission | Permission Mapper Tool | Tool Cache | Notion Client Method |
|------------|------------------------|------------|---------------------|
| `notion:pages:search` | `notion.search_pages` | `search_pages` ✅ | `search_pages` ✅ |
| `notion:pages:read` | `notion.read_page` | `read_page` ⚠️ ADD | `read_page` ✅ |
| `notion:pages:create` | `notion.create_page` | `create_page` ✅ | `create_page` ✅ |
| `notion:pages:update` | `notion.update_page` | `update_page` ✅ | `update_page` ✅ |
| `notion:pages:delete` | `notion.delete_page` | `delete_page` ⚠️ ADD | `delete_page` ✅ |
| `notion:databases:list` | `notion.list_databases` | `list_databases` ⚠️ ADD | `list_databases` ✅ |
| `notion:databases:query` | `notion.query_database` | `query_database` ⚠️ ADD | `query_database` ✅ |

### Slack Alignment

| Permission | Permission Mapper Tool | Tool Cache | Slack Client Method |
|------------|------------------------|------------|---------------------|
| `slack:messages:search` | `slack.search_messages` | `search_messages` ✅ | N/A (MVP) |
| `slack:messages:send` | `slack.send_message` | `send_message` ⚠️ ADD | N/A (MVP) |
| `slack:channels:list` | `slack.list_channels` | `list_channels` ✅ | N/A (MVP) |
| `slack:channels:join` | `slack.join_channel` | `join_channel` ⚠️ ADD | N/A (MVP) |
| `slack:users:list` | `slack.list_users` | `list_users` ⚠️ ADD | N/A (MVP) |

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Initialize handler fix | `deeptrail-gateway/app/mcp/handlers/initialize.py` |
| Tool cache definitions | `deeptrail-gateway/app/mcp/tool_definitions.py` |
| Permission mapper (no changes) | `deeptrail-gateway/app/mcp/permission_mapper.py` |
| Unit tests | `deeptrail-gateway/tests/mcp/handlers/test_initialize.py` |

---

## Expected Results After Fix

### tools/list Response

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "notion.search_pages",
        "description": "Search for pages in Notion workspace",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": {"type": "string", "description": "Search query string"},
            "limit": {"type": "integer", "default": 10}
          },
          "required": ["query"]
        }
      }
    ],
    "nextCursor": null
  }
}
```

### tools/call Response (Real API)

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"object\":\"list\",\"results\":[...],\"has_more\":false}"
      }
    ],
    "isError": false
  }
}
```

---

## Test Verification

| Test Case | Expected Outcome |
|-----------|------------------|
| Permission `notion:pages:read` | Session has `read_page` (singular) |
| Session tool `notion.read_page` | PermissionMapper returns `notion:pages:read` |
| Tool cache lookup `read_page` | Returns full schema with inputSchema |
| No "Permission denied for unknown tool" warnings | Clean tools/list execution |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `initialize.py` uses `PermissionMapper.get_all_tools_for_permission()`
- [ ] No more tool name derivation with `parts[2]_parts[1]`
- [ ] All tools from `TOOL_TO_PERMISSION` have definitions in `tool_definitions.py`
- [ ] Tool names are singular (`read_page`, not `read_pages`)
- [ ] No "Permission denied for unknown tool" warnings in logs
- [ ] tools/list returns proper descriptions and inputSchema
- [ ] tools/call with real Notion API returns actual data (not "token invalid")
- [ ] Bearer token capitalization is correct (`Bearer`, not `bearer`)

---

## References

- **Debug Session:** Tool name mismatch between session, cache, and permission mapper
- **Related Specs:** [WS-H1-spec.md](./WS-H1-spec.md), [WS-H2-spec.md](./WS-H2-spec.md)
- **Upstream Dependencies:** None (this is a bug fix)
- **Downstream Dependents:** All tools/list and tools/call functionality
