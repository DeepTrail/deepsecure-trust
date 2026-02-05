# Task: WS-B7 Implement tools/call Handler

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-B: Gateway MCP Core |
| **Dependencies** | B3 (MCP Session tracking), B4 (Namespace prefixer) |
| **Blocked By** | None (B3, B4 are complete ✅) |
| **Assigned** | - |
| **Created** | January 30, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 4 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 3: Delegation Execution, Demo 4: Permission Enforcement |
| **Validates User Journey Step** | Step 8: Agent Executes Task, Step 9: Agent Denied |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] B3 (MCP Session tracking) is complete
- [x] B4 (Namespace prefixer) is complete
- [ ] `deeptrail-gateway/` service structure exists
- [ ] MCP Session Manager can be imported
- [ ] Namespace Prefixer can be imported
- [ ] Permission Mapper from B6 can be imported

---

## Task Description

Implement the MCP `tools/call` request handler that routes tool calls to backends with credential injection and permission validation. This is the core handler enabling Step 8 of Sarah's journey where the agent executes tools using Sarah's credentials.

### Context

From the MVP design (Section 2.9 - Step 8: Agent Executes Task):

```
Gateway Processing for tools/call:

1. PARSE namespace: "notion.search_pages" → server: "notion", tool: "search_pages"

2. VALIDATE permission:
   - Required permission: notion:pages:search
   - Agent has: [notion:pages:search, ...] ✓ ALLOWED

3. VALIDATE constraints:
   - max_actions_per_day: 100
   - Current count: 0 → Increment to 1 ✓ ALLOWED

4. GET CREDENTIALS for Notion:
   - Lookup MCP Session mcpsess-notion-jkl012
   - Get credential ref: vault://sarah-notion-oauth-xyz
   - Decrypt Sarah's Notion OAuth token

5. FORWARD to backend Notion MCP Server:
   POST https://mcp.notion.com/tools/call
   Authorization: Bearer {sarah's-notion-oauth-token}

6. RECEIVE response from Notion

7. AUDIT LOG: Record tool call with attribution

8. RETURN result to agent
```

### Request/Response Format (MCP Protocol)

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "notion.search_pages",
    "arguments": {
      "query": "competitor analysis",
      "limit": 5
    }
  }
}
```

**Success Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {"type": "text", "text": "Found 3 pages: ..."}
    ]
  }
}
```

**Permission Denied Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "code": -32001,
    "message": "Permission denied: notion:pages:create not delegated"
  }
}
```

### Technical Notes

- Handler receives parsed MCP request from protocol layer (B1)
- Must extract agent session from request context
- Uses Namespace Prefixer (B4) to split `{backend}.{tool}`
- Uses Permission Mapper (B6) for permission validation
- Uses MCP Session Manager (B3) to get backend session and credentials
- MVP: Credential injection via vault reference (simulated)
- Must create audit log entry for every call (success or denied)
- Fail-closed: Deny if any validation fails

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/gateway/mcp/handlers/tools_call.py` | **CREATE** | tools/call request handler |
| `deeptrail-gateway/gateway/mcp/handlers/__init__.py` | **MODIFY** | Export handler |
| `deeptrail-gateway/tests/mcp/handlers/test_tools_call.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. Tools Call Handler (`deeptrail-gateway/gateway/mcp/handlers/tools_call.py`)

```python
"""MCP tools/call request handler for Virtual MCP Server.

Handles the tools/call MCP method by:
1. Parsing namespaced tool name to extract backend and tool
2. Validating permission against agent's delegation
3. Validating constraints (rate limits)
4. Injecting backend credentials
5. Forwarding to backend MCP server
6. Logging audit event
7. Returning result to agent

This is the core handler demonstrating delegation-based execution.
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import logging

from gateway.mcp.session_manager import MCPSessionManager
from gateway.mcp.namespace import NamespacePrefixer
from gateway.mcp.permission_mapper import PermissionMapper


logger = logging.getLogger(__name__)


# MCP Error Codes
ERROR_PERMISSION_DENIED = -32001
ERROR_BACKEND_UNAVAILABLE = -32002
ERROR_CONSTRAINT_VIOLATED = -32003
ERROR_INVALID_TOOL = -32004


class ToolsCallHandler:
    """
    Handler for MCP tools/call requests.
    
    Demonstrates key Virtual MCP Server capabilities:
    - Permission validation: Only delegated tools can be called
    - Credential injection: Agent never sees OAuth tokens
    - Audit trail: Every call logged with attribution
    - Fail-closed: Deny on any validation failure
    
    Example flow:
    1. Agent calls tools/call with "notion.search_pages"
    2. Handler parses namespace → backend="notion", tool="search_pages"
    3. Handler validates agent has "notion:pages:search" permission
    4. Handler gets Sarah's Notion OAuth token from vault
    5. Handler forwards to Notion backend with injected token
    6. Handler logs audit event
    7. Handler returns result to agent
    """
    
    def __init__(
        self,
        session_manager: MCPSessionManager,
        namespace_prefixer: NamespacePrefixer,
        permission_mapper: Optional[PermissionMapper] = None,
        audit_logger: Optional[Any] = None,
        backend_client: Optional[Any] = None
    ):
        """
        Initialize ToolsCallHandler.
        
        Args:
            session_manager: For accessing MCP backend sessions
            namespace_prefixer: For parsing {backend}.{tool} naming
            permission_mapper: For tool→permission validation
            audit_logger: For logging tool calls (optional, uses logging if None)
            backend_client: For forwarding to backends (optional, mock for MVP)
        """
        self.session_manager = session_manager
        self.namespace_prefixer = namespace_prefixer
        self.permission_mapper = permission_mapper or PermissionMapper
        self.audit_logger = audit_logger
        self.backend_client = backend_client
    
    async def handle(
        self,
        request: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle MCP tools/call request.
        
        Args:
            request: Parsed MCP JSON-RPC request with:
                - method: "tools/call"
                - params.name: Namespaced tool name
                - params.arguments: Tool arguments
            context: Request context containing:
                - agent_session: Validated AgentSession
                - mcp_sessions: Dict of backend MCP sessions
                
        Returns:
            MCP JSON-RPC response (success or error)
        """
        request_id = request.get("id")
        params = request.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        agent_session = context.get("agent_session")
        
        if not agent_session:
            return self._error_response(
                request_id,
                -32600,
                "Invalid Request: No agent session"
            )
        
        logger.info(
            f"tools/call request from agent {agent_session.agent_id}: "
            f"tool={tool_name}"
        )
        
        try:
            # Step 1: Parse namespace
            backend_id, original_tool = self._parse_namespace(tool_name)
            if not backend_id:
                await self._log_audit(
                    agent_session, tool_name, arguments,
                    success=False, error="Invalid tool name format"
                )
                return self._error_response(
                    request_id,
                    ERROR_INVALID_TOOL,
                    f"Invalid tool name format: {tool_name}"
                )
            
            # Step 2: Validate permission
            permission_check = self._validate_permission(
                tool_name,
                agent_session.scoped_permissions or []
            )
            if not permission_check["allowed"]:
                await self._log_audit(
                    agent_session, tool_name, arguments,
                    success=False,
                    error=f"Permission denied: {permission_check['required_permission']}"
                )
                return self._error_response(
                    request_id,
                    ERROR_PERMISSION_DENIED,
                    f"Permission denied: {permission_check['required_permission']} not delegated"
                )
            
            # Step 3: Validate constraints (MVP: basic check)
            constraint_check = await self._validate_constraints(
                agent_session,
                tool_name
            )
            if not constraint_check["allowed"]:
                await self._log_audit(
                    agent_session, tool_name, arguments,
                    success=False, error=constraint_check["reason"]
                )
                return self._error_response(
                    request_id,
                    ERROR_CONSTRAINT_VIOLATED,
                    constraint_check["reason"]
                )
            
            # Step 4: Get backend session and credentials
            mcp_sessions = context.get("mcp_sessions", {})
            backend_session = mcp_sessions.get(backend_id)
            
            if not backend_session:
                await self._log_audit(
                    agent_session, tool_name, arguments,
                    success=False, error=f"Backend {backend_id} not connected"
                )
                return self._error_response(
                    request_id,
                    ERROR_BACKEND_UNAVAILABLE,
                    f"Backend {backend_id} not connected"
                )
            
            # Step 5: Forward to backend with credential injection
            result = await self._forward_to_backend(
                backend_id=backend_id,
                backend_session=backend_session,
                tool_name=original_tool,
                arguments=arguments
            )
            
            # Step 6: Log successful call
            await self._log_audit(
                agent_session, tool_name, arguments,
                success=True, result_summary=self._summarize_result(result)
            )
            
            # Step 7: Return result
            return self._success_response(request_id, result)
            
        except Exception as e:
            logger.error(f"Error handling tools/call: {e}", exc_info=True)
            await self._log_audit(
                agent_session, tool_name, arguments,
                success=False, error=str(e)
            )
            return self._error_response(
                request_id,
                -32603,
                f"Internal error: {str(e)}"
            )
    
    def _parse_namespace(self, tool_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse namespaced tool name to extract backend and tool.
        
        Args:
            tool_name: Namespaced name (e.g., "notion.search_pages")
            
        Returns:
            Tuple of (backend_id, original_tool) or (None, None) if invalid
        """
        return self.namespace_prefixer.unprefix(tool_name)
    
    def _validate_permission(
        self,
        tool_name: str,
        delegated_permissions: list
    ) -> Dict[str, Any]:
        """
        Validate tool call against delegated permissions.
        
        Args:
            tool_name: Namespaced tool name
            delegated_permissions: Agent's delegated permissions
            
        Returns:
            Dict with:
                - allowed: bool
                - required_permission: str (the permission that was checked)
        """
        required_permission = self.permission_mapper.get_permission(tool_name)
        
        if required_permission is None:
            # Unknown tool - fail closed
            return {
                "allowed": False,
                "required_permission": f"unknown:{tool_name}"
            }
        
        allowed = required_permission in delegated_permissions
        
        return {
            "allowed": allowed,
            "required_permission": required_permission
        }
    
    async def _validate_constraints(
        self,
        agent_session: Any,
        tool_name: str
    ) -> Dict[str, Any]:
        """
        Validate tool call against delegation constraints.
        
        MVP: Basic implementation, always allows.
        Production: Check rate limits, action counts, etc.
        
        Args:
            agent_session: Agent's session with delegation info
            tool_name: Tool being called
            
        Returns:
            Dict with:
                - allowed: bool
                - reason: str (if denied)
        """
        # MVP: Always allow (constraint enforcement is in C6/E5)
        # This is a placeholder for future constraint validation
        return {"allowed": True}
    
    async def _forward_to_backend(
        self,
        backend_id: str,
        backend_session: Dict[str, Any],
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Forward tool call to backend MCP server with credential injection.
        
        Args:
            backend_id: Backend identifier (e.g., "notion")
            backend_session: MCP session with credential reference
            tool_name: Original tool name (without namespace)
            arguments: Tool arguments
            
        Returns:
            Backend response content
        """
        # MVP: Mock backend response
        # Production: Use backend_client to make actual MCP call
        
        if self.backend_client:
            # Get credentials from vault reference
            credential_ref = backend_session.get("injected_credentials", {}).get("ref")
            
            # Forward to backend
            return await self.backend_client.call_tool(
                backend_id=backend_id,
                tool_name=tool_name,
                arguments=arguments,
                credential_ref=credential_ref
            )
        
        # Mock response for MVP testing
        logger.info(
            f"MVP: Mock forwarding {tool_name} to {backend_id} "
            f"with credential ref: {backend_session.get('injected_credentials', {}).get('ref')}"
        )
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"[MVP Mock] Tool {backend_id}.{tool_name} executed successfully"
                }
            ]
        }
    
    async def _log_audit(
        self,
        agent_session: Any,
        tool_name: str,
        arguments: Dict[str, Any],
        success: bool,
        result_summary: str = None,
        error: str = None
    ) -> None:
        """
        Log audit event for tool call.
        
        Args:
            agent_session: Agent's session
            tool_name: Tool that was called
            arguments: Tool arguments
            success: Whether call succeeded
            result_summary: Summary of result (if success)
            error: Error message (if failed)
        """
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": "mcp_tool_call" if success else "permission_denied",
            "agent_id": agent_session.agent_id,
            "on_behalf_of": agent_session.owner_email,
            "tool": tool_name,
            "arguments": arguments,
            "session_id": agent_session.session_id,
            "success": success
        }
        
        if result_summary:
            event["result_summary"] = result_summary
        if error:
            event["error"] = error
            event["event_type"] = "permission_denied" if "Permission denied" in error else "tool_call_error"
        
        if self.audit_logger:
            await self.audit_logger.log(event)
        else:
            logger.info(f"AUDIT: {event}")
    
    def _summarize_result(self, result: Dict[str, Any]) -> str:
        """
        Create a summary of the tool result for audit log.
        
        Args:
            result: Backend response
            
        Returns:
            Brief summary string
        """
        content = result.get("content", [])
        if content:
            first_item = content[0]
            if first_item.get("type") == "text":
                text = first_item.get("text", "")
                return text[:100] + "..." if len(text) > 100 else text
        return "Result received"
    
    def _success_response(
        self,
        request_id: Any,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build successful MCP tools/call response.
        
        Args:
            request_id: Original request ID
            result: Backend response content
            
        Returns:
            MCP JSON-RPC response
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
    
    def _error_response(
        self,
        request_id: Any,
        code: int,
        message: str
    ) -> Dict[str, Any]:
        """
        Build MCP error response.
        
        Args:
            request_id: Original request ID
            code: JSON-RPC error code
            message: Error message
            
        Returns:
            MCP JSON-RPC error response
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }


# Factory function for handler registration
def create_tools_call_handler(
    session_manager: MCPSessionManager,
    namespace_prefixer: NamespacePrefixer,
    audit_logger: Optional[Any] = None,
    backend_client: Optional[Any] = None
) -> ToolsCallHandler:
    """
    Create a configured ToolsCallHandler.
    
    Args:
        session_manager: MCP session manager instance
        namespace_prefixer: Namespace prefixer instance
        audit_logger: Optional audit logger
        backend_client: Optional backend client
        
    Returns:
        Configured ToolsCallHandler
    """
    return ToolsCallHandler(
        session_manager=session_manager,
        namespace_prefixer=namespace_prefixer,
        audit_logger=audit_logger,
        backend_client=backend_client
    )
```

### 2. Update Namespace Prefixer

Add `unprefix` method to `gateway/mcp/namespace.py` if not present:

```python
def unprefix(self, namespaced_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse namespaced tool name to extract backend and original name.
    
    Args:
        namespaced_name: e.g., "notion.search_pages"
        
    Returns:
        Tuple of (backend_id, original_name) or (None, None) if invalid
    """
    if "." not in namespaced_name:
        return None, None
    
    parts = namespaced_name.split(".", 1)
    if len(parts) != 2:
        return None, None
    
    return parts[0], parts[1]
```

### 3. Update `__init__.py`

```python
# Add to deeptrail-gateway/gateway/mcp/handlers/__init__.py
from .tools_call import ToolsCallHandler, create_tools_call_handler

__all__ = [
    # ... existing exports ...
    "ToolsCallHandler",
    "create_tools_call_handler",
]
```

---

## Acceptance Criteria

### Namespace Parsing Criteria

- [ ] Handler parses `{backend}.{tool}` format correctly
- [ ] Handler returns error for invalid tool name format
- [ ] Backend ID and original tool name extracted correctly

### Permission Validation Criteria

- [ ] Handler validates tool against delegated permissions
- [ ] Permission denied returns error code -32001
- [ ] Permission denied message includes required permission
- [ ] Unknown tools are denied (fail-closed)

### Constraint Validation Criteria

- [ ] Handler has placeholder for constraint validation
- [ ] MVP always allows (actual enforcement in C6/E5)
- [ ] Constraint violation returns error code -32003

### Credential Injection Criteria

- [ ] Handler retrieves backend session from context
- [ ] Handler accesses credential reference from session
- [ ] MVP logs credential ref (actual injection in D1/C7)
- [ ] Missing backend returns error code -32002

### Backend Forwarding Criteria

- [ ] Handler forwards tool call to backend
- [ ] Tool name stripped of namespace before forwarding
- [ ] Arguments passed through unmodified
- [ ] Backend response returned to agent

### Audit Logging Criteria

- [ ] Every tool call logged (success and failure)
- [ ] Audit includes: agent_id, on_behalf_of, tool, arguments
- [ ] Success logs include result_summary
- [ ] Failures log error reason
- [ ] Permission denied logged as "permission_denied" event

### Protocol Criteria

- [ ] Response follows MCP JSON-RPC format
- [ ] Success returns `result.content` array
- [ ] Errors use proper JSON-RPC error format
- [ ] Error codes are consistent (-32001, -32002, etc.)

### Integration Criteria

- [ ] Handler uses MCPSessionManager from B3
- [ ] Handler uses NamespacePrefixer from B4
- [ ] Handler uses PermissionMapper from B6
- [ ] Handler exported from `handlers/__init__.py`
- [ ] All tests pass

---

## Test Cases

Create `deeptrail-gateway/tests/mcp/handlers/test_tools_call.py`:

```python
"""Tests for tools/call handler."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from gateway.mcp.handlers.tools_call import (
    ToolsCallHandler,
    ERROR_PERMISSION_DENIED,
    ERROR_BACKEND_UNAVAILABLE,
    ERROR_INVALID_TOOL
)


@pytest.fixture
def mock_session_manager():
    return MagicMock()


@pytest.fixture
def mock_namespace_prefixer():
    prefixer = MagicMock()
    prefixer.unprefix = lambda name: tuple(name.split(".", 1)) if "." in name else (None, None)
    return prefixer


@pytest.fixture
def mock_agent_session():
    session = MagicMock()
    session.agent_id = "agent-sdr-001"
    session.session_id = "asess-sdr-001-abc123"
    session.owner_email = "sarah@acme.com"
    session.scoped_permissions = [
        "notion:pages:search",
        "notion:pages:read",
        "slack:channels:list"
    ]
    return session


@pytest.fixture
def handler(mock_session_manager, mock_namespace_prefixer):
    return ToolsCallHandler(
        session_manager=mock_session_manager,
        namespace_prefixer=mock_namespace_prefixer
    )


class TestToolsCallPermission:
    """Test permission validation."""
    
    @pytest.mark.asyncio
    async def test_permitted_tool_succeeds(self, handler, mock_agent_session):
        """Test that permitted tool call succeeds."""
        context = {
            "agent_session": mock_agent_session,
            "mcp_sessions": {
                "notion": {
                    "injected_credentials": {"ref": "vault://sarah-notion-oauth"}
                }
            }
        }
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "notion.search_pages",
                "arguments": {"query": "test"}
            }
        }
        
        response = await handler.handle(request, context)
        
        assert "error" not in response
        assert response["result"]["content"] is not None
    
    @pytest.mark.asyncio
    async def test_unpermitted_tool_denied(self, handler, mock_agent_session):
        """Test that unpermitted tool call is denied."""
        context = {
            "agent_session": mock_agent_session,
            "mcp_sessions": {"notion": {}}
        }
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "notion.create_page",  # NOT in permissions
                "arguments": {"title": "Test"}
            }
        }
        
        response = await handler.handle(request, context)
        
        assert "error" in response
        assert response["error"]["code"] == ERROR_PERMISSION_DENIED
        assert "notion:pages:create" in response["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_unknown_tool_denied(self, handler, mock_agent_session):
        """Test that unknown tool is denied (fail-closed)."""
        context = {
            "agent_session": mock_agent_session,
            "mcp_sessions": {"unknown": {}}
        }
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "unknown.mystery_tool",
                "arguments": {}
            }
        }
        
        response = await handler.handle(request, context)
        
        assert "error" in response
        assert response["error"]["code"] == ERROR_PERMISSION_DENIED


class TestToolsCallNamespace:
    """Test namespace parsing."""
    
    @pytest.mark.asyncio
    async def test_invalid_tool_name_format(self, handler, mock_agent_session):
        """Test error for invalid tool name format."""
        context = {
            "agent_session": mock_agent_session,
            "mcp_sessions": {}
        }
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "no_namespace_tool",  # No dot
                "arguments": {}
            }
        }
        
        response = await handler.handle(request, context)
        
        assert "error" in response
        assert response["error"]["code"] == ERROR_INVALID_TOOL


class TestToolsCallBackend:
    """Test backend interaction."""
    
    @pytest.mark.asyncio
    async def test_missing_backend_returns_error(self, handler, mock_agent_session):
        """Test error when backend not connected."""
        context = {
            "agent_session": mock_agent_session,
            "mcp_sessions": {}  # No backends
        }
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "notion.search_pages",
                "arguments": {"query": "test"}
            }
        }
        
        response = await handler.handle(request, context)
        
        assert "error" in response
        assert response["error"]["code"] == ERROR_BACKEND_UNAVAILABLE


class TestToolsCallAudit:
    """Test audit logging."""
    
    @pytest.mark.asyncio
    async def test_successful_call_logged(
        self, mock_session_manager, mock_namespace_prefixer, mock_agent_session
    ):
        """Test that successful calls are logged."""
        mock_audit = MagicMock()
        mock_audit.log = AsyncMock()
        
        handler = ToolsCallHandler(
            session_manager=mock_session_manager,
            namespace_prefixer=mock_namespace_prefixer,
            audit_logger=mock_audit
        )
        
        context = {
            "agent_session": mock_agent_session,
            "mcp_sessions": {
                "notion": {"injected_credentials": {"ref": "vault://test"}}
            }
        }
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "notion.search_pages",
                "arguments": {"query": "test"}
            }
        }
        
        await handler.handle(request, context)
        
        mock_audit.log.assert_called_once()
        logged_event = mock_audit.log.call_args[0][0]
        assert logged_event["agent_id"] == "agent-sdr-001"
        assert logged_event["on_behalf_of"] == "sarah@acme.com"
        assert logged_event["tool"] == "notion.search_pages"
        assert logged_event["success"] is True
    
    @pytest.mark.asyncio
    async def test_permission_denied_logged(
        self, mock_session_manager, mock_namespace_prefixer, mock_agent_session
    ):
        """Test that permission denied is logged."""
        mock_audit = MagicMock()
        mock_audit.log = AsyncMock()
        
        handler = ToolsCallHandler(
            session_manager=mock_session_manager,
            namespace_prefixer=mock_namespace_prefixer,
            audit_logger=mock_audit
        )
        
        context = {
            "agent_session": mock_agent_session,
            "mcp_sessions": {"notion": {}}
        }
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "notion.create_page",
                "arguments": {}
            }
        }
        
        await handler.handle(request, context)
        
        mock_audit.log.assert_called_once()
        logged_event = mock_audit.log.call_args[0][0]
        assert logged_event["event_type"] == "permission_denied"
        assert logged_event["success"] is False
```

---

## Post-Conditions

After completing this task:

- [ ] ToolsCallHandler is available for import
- [ ] Agents can call tools/call for permitted tools
- [ ] Unauthorized tool calls are denied with proper error
- [ ] All tool calls are logged with audit trail
- [ ] Demo 3 (Delegation Execution) can be demonstrated
- [ ] Demo 4 (Permission Enforcement) can be demonstrated
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.9 Step 8: Agent Executes Task, 2.10 Step 9: Agent Denied
- **MCP Protocol**: [tools/call method](https://modelcontextprotocol.io/specification)
- **Related Tasks**:
  - [WS-B3: MCP Session Tracking](./WS-B3-mcp-session-tracking.md)
  - [WS-B4: Namespace Prefixer](./WS-B4-namespace-prefixer.md)
  - [WS-B6: tools/list Handler](./WS-B6-tools-list-handler.md)
- **Downstream Tasks**:
  - [WS-C6: Delegation Validator](./WS-C6-delegation-validator.md)
  - [WS-C7: Credential Injection](./WS-C7-credential-injection.md)
  - [WS-E3: Audit Middleware](./WS-E3-audit-middleware.md)

---

## Notes

- MVP uses mock backend forwarding; production will use D2 base MCP client
- Constraint validation is placeholder; actual enforcement in E5
- Credential injection is via vault reference; actual decryption in C7
- This handler is the core demonstration of "delegation execution" value proposition
- Agent NEVER sees OAuth tokens - only the gateway handles them
