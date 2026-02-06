# Task: WS-E3 Implement Audit Middleware

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-E: Audit & Security |
| **Dependencies** | E2 (Audit logger service) ✅, C6 (Delegation validator) ✅ |
| **Blocked By** | None (all dependencies complete) |
| **Assigned** | - |
| **Created** | February 5, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 7 |
| **Target Worktree** | `vmcp-gateway` |

---

## Validation Mapping

| Validates | Reference |
|-----------|-----------|
| **Demo 5** | Unified Audit - Every tool call logged with full attribution |
| **User Journey Step** | Step 8-10: Agent executes tool → All actions logged → Sarah reviews |
| **MP4 Dependency** | E3 completion enables MP4 (Complete System) |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] E2 (Audit logger service) is complete - provides `/api/v1/audit/events` endpoint ✅
- [x] C6 (Delegation validator) is complete - provides `AgentContext`
- [x] C7 (Credential injection) is complete - full execution path works
- [x] B7 (tools/call handler) is complete - handles tool execution

---

## Task Description

Implement **audit middleware** in the Gateway that logs every `tools/call` request to the Control Plane's audit service. This middleware intercepts tool calls, measures execution time, and sends structured audit events.

### Context

This is **Steps 8-10 of Sarah's journey** and the core of **Demo 5 (Unified Audit)**:
- Every tool call the agent makes is logged with full attribution
- Audit captures: who (agent), on whose behalf (Sarah), what (tool + args), when (timestamp), outcome (success/error)
- Events are sent asynchronously to not block tool execution
- Both successful calls and permission denials are logged

### Key Requirements

1. **Every tools/call logged**: Both successful and failed calls
2. **Full attribution**: agent_id, on_behalf_of (user), tool, arguments
3. **Performance data**: Capture execution duration
4. **Non-blocking**: Don't slow down tool execution
5. **Fail-open for audit**: If audit fails, don't block the tool call

### Integration Flow

```
MCP Request: tools/call
         │
         ├── JWT Validation (C3) → AgentContext
         │
         ├── Permission Check (C5, C6)
         │        │
         │        ├── If denied → Log PERMISSION_DENIED event
         │        │
         │        └── If allowed → Continue
         │
         ├── Credential Injection (C7)
         │
         ├── Backend Execution (D3-D6)
         │        │
         │        └── Get result/error
         │
         └── Audit Middleware (E3) ← THIS TASK
                  │
                  ├── Capture: agent, user, tool, args, result, duration
                  │
                  └── POST to Control Plane /api/v1/audit/events
                           │
                           └── AuditLoggerService (E2)
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/middleware/audit.py` | **CREATE** | Audit middleware class |
| `deeptrail-gateway/app/middleware/__init__.py` | **MODIFY** | Export AuditMiddleware |
| `deeptrail-gateway/app/mcp/handlers/tools_call.py` | **MODIFY** | Integrate audit middleware |
| `deeptrail-gateway/tests/middleware/test_audit.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. AuditMiddleware Class

```python
"""
Audit Middleware for MCP tool calls.

Logs every tools/call request to the Control Plane's audit service.
This is the Gateway-side component of the unified audit trail.

This implements:
- Demo 5: Unified Audit
- Steps 8-10 of Sarah's Journey

Security Principles:
- Full attribution: Every call includes agent and user context
- Non-blocking: Audit failures don't block tool execution
- Complete capture: Both successes and failures logged
- Sensitive data redacted: Passwords/tokens not logged

Usage:
    from app.middleware.audit import AuditMiddleware
    
    middleware = AuditMiddleware(control_plane_url="http://localhost:8000")
    
    # In tools/call handler, after execution:
    await middleware.log_tool_call(
        agent_context=context,
        tool_name="notion.search_pages",
        arguments={"query": "meeting"},
        result=result,
        duration_ms=150,
    )
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import httpx

from .jwt_validation import AgentContext

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""
    MCP_TOOL_CALL = "mcp_tool_call"
    PERMISSION_DENIED = "permission_denied"
    CREDENTIAL_ERROR = "credential_error"
    TOOL_ERROR = "tool_error"


@dataclass
class AuditEvent:
    """
    Structured audit event for logging.
    
    Captures all information needed for the unified audit trail.
    """
    event_type: AuditEventType
    agent_id: str
    on_behalf_of: str
    tool: str
    arguments: dict[str, Any] | None = None
    result_summary: str | None = None
    error: str | None = None
    duration_ms: int | None = None
    organization_id: str | None = None
    extra_data: dict[str, Any] | None = None


class AuditMiddleware:
    """
    Middleware for logging MCP tool calls to the audit service.
    
    Responsibilities:
    1. Capture tool call details with full attribution
    2. Send events to Control Plane asynchronously
    3. Redact sensitive data before logging
    4. Handle audit failures gracefully (fail-open)
    
    Non-blocking:
    - Audit is sent in background task
    - Tool response returned immediately
    - Audit failure doesn't affect tool execution
    """
    
    def __init__(
        self,
        control_plane_url: str | None = None,
        timeout_seconds: float = 5.0,
        enabled: bool = True,
    ):
        """
        Initialize the audit middleware.
        
        Args:
            control_plane_url: URL to Control Plane audit endpoint
            timeout_seconds: Timeout for audit requests
            enabled: Whether audit logging is enabled
        """
        self.control_plane_url = control_plane_url
        self.timeout_seconds = timeout_seconds
        self.enabled = enabled
        self._pending_tasks: set[asyncio.Task] = set()
    
    async def log_tool_call(
        self,
        agent_context: AgentContext,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any] | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """
        Log a successful tool call.
        
        Args:
            agent_context: Agent context from JWT validation
            tool_name: Namespaced tool name (e.g., "notion.search_pages")
            arguments: Tool arguments
            result: Tool result (optional)
            error: Error message if failed (optional)
            duration_ms: Execution duration in milliseconds
        """
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_type=AuditEventType.MCP_TOOL_CALL if not error else AuditEventType.TOOL_ERROR,
            agent_id=agent_context.agent_id,
            on_behalf_of=agent_context.on_behalf_of or "unknown",
            tool=tool_name,
            arguments=self._redact_sensitive(arguments),
            result_summary=self._summarize_result(result) if result else None,
            error=error,
            duration_ms=duration_ms,
            organization_id=agent_context.organization_id,
        )
        
        # Send asynchronously - don't block tool response
        await self._send_event_async(event)
    
    async def log_permission_denied(
        self,
        agent_context: AgentContext,
        tool_name: str,
        required_permission: str,
        denial_reason: str,
    ) -> None:
        """
        Log a permission denied event.
        
        Args:
            agent_context: Agent context from JWT validation
            tool_name: Tool that was denied
            required_permission: Permission that was required
            denial_reason: Reason for denial
        """
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_type=AuditEventType.PERMISSION_DENIED,
            agent_id=agent_context.agent_id,
            on_behalf_of=agent_context.on_behalf_of or "unknown",
            tool=tool_name,
            error=f"Permission denied: {required_permission}",
            organization_id=agent_context.organization_id,
            extra_data={
                "required_permission": required_permission,
                "denial_reason": denial_reason,
            },
        )
        
        await self._send_event_async(event)
    
    async def log_credential_error(
        self,
        agent_context: AgentContext,
        tool_name: str,
        error_message: str,
    ) -> None:
        """
        Log a credential injection error.
        
        Args:
            agent_context: Agent context
            tool_name: Tool that failed
            error_message: Error description
        """
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_type=AuditEventType.CREDENTIAL_ERROR,
            agent_id=agent_context.agent_id,
            on_behalf_of=agent_context.on_behalf_of or "unknown",
            tool=tool_name,
            error=error_message,
            organization_id=agent_context.organization_id,
        )
        
        await self._send_event_async(event)
    
    async def _send_event_async(self, event: AuditEvent) -> None:
        """
        Send audit event asynchronously.
        
        Creates a background task to send the event.
        Task is tracked to prevent garbage collection.
        
        Args:
            event: The audit event to send
        """
        task = asyncio.create_task(self._send_event(event))
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)
    
    async def _send_event(self, event: AuditEvent) -> bool:
        """
        Send audit event to Control Plane.
        
        Args:
            event: The audit event to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.control_plane_url:
            # No URL configured - log locally instead
            logger.info(
                "AUDIT [%s] agent=%s user=%s tool=%s duration=%sms error=%s",
                event.event_type.value,
                event.agent_id,
                event.on_behalf_of,
                event.tool,
                event.duration_ms,
                event.error,
            )
            return True
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.control_plane_url}/api/v1/audit/events",
                    json={
                        "event_type": event.event_type.value,
                        "agent_id": event.agent_id,
                        "on_behalf_of": event.on_behalf_of,
                        "tool": event.tool,
                        "arguments": event.arguments,
                        "result_summary": event.result_summary,
                        "error": event.error,
                        "duration_ms": event.duration_ms,
                        "organization_id": event.organization_id,
                        "extra_data": event.extra_data,
                    },
                    timeout=self.timeout_seconds,
                )
                
                if response.status_code == 200:
                    logger.debug("Audit event sent: %s", event.tool)
                    return True
                else:
                    logger.warning(
                        "Audit send failed: %d - %s",
                        response.status_code,
                        response.text[:100],
                    )
                    return False
                    
        except Exception as e:
            # Fail-open: Don't block tool execution if audit fails
            logger.error("Audit send error: %s", str(e))
            return False
    
    def _redact_sensitive(self, data: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        Redact sensitive fields from audit data.
        
        Removes passwords, tokens, and other secrets.
        
        Args:
            data: The data to redact
            
        Returns:
            Redacted copy of the data
        """
        if not data:
            return data
        
        sensitive_keys = {
            "password", "secret", "token", "api_key", "apikey",
            "access_token", "refresh_token", "authorization",
            "credential", "private_key", "secret_key"
        }
        
        def redact_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: "[REDACTED]" if k.lower() in sensitive_keys else redact_recursive(v)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [redact_recursive(item) for item in obj]
            return obj
        
        return redact_recursive(data)
    
    def _summarize_result(self, result: dict[str, Any]) -> str:
        """
        Create a brief summary of the tool result.
        
        Truncates long results to avoid bloating audit logs.
        
        Args:
            result: The tool result
            
        Returns:
            Brief summary string
        """
        if not result:
            return "No result"
        
        # For MCP results, extract content summary
        if "content" in result:
            content = result["content"]
            if isinstance(content, list) and len(content) > 0:
                first_item = content[0]
                if isinstance(first_item, dict) and "text" in first_item:
                    text = first_item["text"]
                    if len(text) > 100:
                        return f"{text[:100]}..."
                    return text
        
        # Generic summary
        is_error = result.get("isError", False)
        return f"Error response" if is_error else "Success"
    
    async def flush(self) -> None:
        """
        Wait for all pending audit events to be sent.
        
        Call this during graceful shutdown.
        """
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)


# =============================================================================
# Singleton Instance
# =============================================================================

_audit_middleware: AuditMiddleware | None = None


def get_audit_middleware() -> AuditMiddleware:
    """Get the configured audit middleware instance."""
    global _audit_middleware
    if _audit_middleware is None:
        _audit_middleware = AuditMiddleware()
    return _audit_middleware


def configure_audit_middleware(
    control_plane_url: str | None = None,
    enabled: bool = True,
) -> AuditMiddleware:
    """
    Configure and return the audit middleware.
    
    Args:
        control_plane_url: URL to Control Plane
        enabled: Whether audit is enabled
        
    Returns:
        Configured AuditMiddleware instance
    """
    global _audit_middleware
    _audit_middleware = AuditMiddleware(
        control_plane_url=control_plane_url,
        enabled=enabled,
    )
    return _audit_middleware
```

### 2. Integration with tools_call Handler

Modify `tools_call.py` to use audit middleware:

```python
from app.middleware.audit import get_audit_middleware, AuditMiddleware

async def handle_tools_call(request: MCPRequest, context: dict) -> MCPResponse:
    """Handle tools/call with audit logging."""
    start_time = time.time()
    audit = get_audit_middleware()
    agent_context = context.get("agent_context")
    
    tool_name = request.params.get("name")
    arguments = request.params.get("arguments", {})
    
    try:
        # Permission validation (C6)
        validation_result = await validator.validate_tool_call(
            tool_name=tool_name,
            agent_context=agent_context,
        )
        
        if not validation_result.allowed:
            # Log permission denied
            await audit.log_permission_denied(
                agent_context=agent_context,
                tool_name=tool_name,
                required_permission=validation_result.required_permission,
                denial_reason=validation_result.denial_reason.value,
            )
            raise MCPError(...)
        
        # Execute tool (C7, D3-D6)
        result = await execute_tool(tool_name, arguments, agent_context)
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log successful call
        await audit.log_tool_call(
            agent_context=agent_context,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
        )
        
        return MCPResponse(result=result)
        
    except MCPError as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log error
        await audit.log_tool_call(
            agent_context=agent_context,
            tool_name=tool_name,
            arguments=arguments,
            error=str(e),
            duration_ms=duration_ms,
        )
        raise
```

### 3. Key Behaviors

| Scenario | Behavior |
|----------|----------|
| Successful tool call | Log MCP_TOOL_CALL with result summary |
| Permission denied | Log PERMISSION_DENIED with required permission |
| Credential error | Log CREDENTIAL_ERROR |
| Tool execution error | Log TOOL_ERROR with error message |
| Audit service down | Fail-open, log locally, don't block tool |
| Sensitive data in args | Automatically redacted before logging |

---

## Acceptance Criteria

### Protocol Criteria
- [ ] Every `tools/call` request is logged
- [ ] Audit event sent to Control Plane `/api/v1/audit/events`
- [ ] Events include: agent_id, on_behalf_of, tool, arguments, duration_ms

### Security Criteria
- [ ] **Full attribution**: Every event has agent_id and on_behalf_of
- [ ] **Sensitive data redacted**: Passwords, tokens never logged
- [ ] **Fail-open**: Audit failure doesn't block tool execution
- [ ] **Permission denials logged**: All denied requests captured

### Integration Criteria
- [ ] Uses `AgentContext` from C3 (JWT validation)
- [ ] Sends to E2 (AuditLoggerService) endpoint
- [ ] Works with existing tools/call handler (B7)
- [ ] Enables MP4 (Complete System)

### Demo 5 Metric
- [ ] Can demonstrate: All tool calls visible in audit log
- [ ] Can demonstrate: Query "What did agent X do?" returns events
- [ ] Can demonstrate: Both success and denial events logged

---

## Test Cases

### Unit Tests (`test_audit.py`)

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.middleware.audit import (
    AuditMiddleware,
    AuditEvent,
    AuditEventType,
)
from app.middleware.jwt_validation import AgentContext


class TestAuditMiddleware:
    """Tests for E3: Audit Middleware"""
    
    @pytest.fixture
    def agent_context(self):
        return AgentContext(
            agent_id="agent-123",
            on_behalf_of="sarah@acme.com",
            delegated_permissions=["notion:*"],
            organization_id="org-456",
        )
    
    @pytest.fixture
    def middleware(self):
        return AuditMiddleware(enabled=True)
    
    @pytest.mark.asyncio
    async def test_log_tool_call_creates_event(self, middleware, agent_context):
        """E3: Should create audit event for tool call"""
        with patch.object(middleware, '_send_event', new_callable=AsyncMock) as mock_send:
            await middleware.log_tool_call(
                agent_context=agent_context,
                tool_name="notion.search_pages",
                arguments={"query": "test"},
                result={"content": [{"type": "text", "text": "Found 5 results"}]},
                duration_ms=150,
            )
            
            # Give async task time to complete
            await middleware.flush()
            
            mock_send.assert_called_once()
            event = mock_send.call_args[0][0]
            assert event.event_type == AuditEventType.MCP_TOOL_CALL
            assert event.agent_id == "agent-123"
            assert event.on_behalf_of == "sarah@acme.com"
            assert event.tool == "notion.search_pages"
            assert event.duration_ms == 150
    
    @pytest.mark.asyncio
    async def test_log_permission_denied(self, middleware, agent_context):
        """E3: Should log permission denied events"""
        with patch.object(middleware, '_send_event', new_callable=AsyncMock) as mock_send:
            await middleware.log_permission_denied(
                agent_context=agent_context,
                tool_name="slack.post_message",
                required_permission="slack:messages:post",
                denial_reason="permission_not_delegated",
            )
            
            await middleware.flush()
            
            event = mock_send.call_args[0][0]
            assert event.event_type == AuditEventType.PERMISSION_DENIED
            assert "required_permission" in event.extra_data
    
    def test_redact_sensitive_data(self, middleware):
        """E3 Security: Should redact sensitive fields"""
        data = {
            "query": "test",
            "password": "secret123",
            "api_key": "key123",
        }
        
        redacted = middleware._redact_sensitive(data)
        
        assert redacted["query"] == "test"
        assert redacted["password"] == "[REDACTED]"
        assert redacted["api_key"] == "[REDACTED]"
    
    @pytest.mark.asyncio
    async def test_disabled_middleware_no_logging(self, agent_context):
        """E3: Disabled middleware should not log"""
        middleware = AuditMiddleware(enabled=False)
        
        with patch.object(middleware, '_send_event', new_callable=AsyncMock) as mock_send:
            await middleware.log_tool_call(
                agent_context=agent_context,
                tool_name="notion.search_pages",
                arguments={},
            )
            
            mock_send.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_fail_open_on_send_error(self, middleware, agent_context):
        """E3 Security: Should fail-open if audit send fails"""
        middleware.control_plane_url = "http://localhost:9999"  # Non-existent
        
        # Should not raise exception
        await middleware.log_tool_call(
            agent_context=agent_context,
            tool_name="notion.search_pages",
            arguments={},
        )
        
        await middleware.flush()
        # Test passes if no exception raised


class TestResultSummarization:
    """Tests for result summarization"""
    
    def test_summarize_mcp_result(self):
        """E3: Should summarize MCP result content"""
        middleware = AuditMiddleware()
        
        result = {
            "content": [{"type": "text", "text": "Found 5 results for query"}],
            "isError": False,
        }
        
        summary = middleware._summarize_result(result)
        assert "Found 5 results" in summary
    
    def test_summarize_long_result_truncated(self):
        """E3: Should truncate long results"""
        middleware = AuditMiddleware()
        
        long_text = "x" * 500
        result = {
            "content": [{"type": "text", "text": long_text}],
        }
        
        summary = middleware._summarize_result(result)
        assert len(summary) <= 103  # 100 + "..."
```

### Integration Tests

```python
@pytest.mark.integration
async def test_audit_to_control_plane(gateway_client, control_plane_url):
    """E3 Demo 5: Tool calls should be logged to Control Plane"""
    # Execute a tool call
    response = await gateway_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "notion.search_pages",
                "arguments": {"query": "test"}
            }
        },
        headers={"Authorization": f"Bearer {agent_jwt}"},
    )
    
    assert response.status_code == 200
    
    # Query audit log from Control Plane
    audit_response = await httpx.get(
        f"{control_plane_url}/api/v1/audit/events",
        params={"agent_id": "test-agent", "limit": 1},
    )
    
    assert audit_response.status_code == 200
    events = audit_response.json()["events"]
    assert len(events) >= 1
    assert events[0]["tool"] == "notion.search_pages"
```

---

## Post-Conditions

After completing this task:

1. Every `tools/call` is logged to Control Plane
2. Audit events include full attribution
3. Sensitive data is redacted
4. MP4 (Complete System) is unblocked

---

## Unblocks

| Task | Name | Notes |
|------|------|-------|
| **F1** | Sarah's Journey E2E Test | Can verify complete audit trail |
| **F5** | Demo 4: Permission Enforcement | Denied attempts are logged |
| **F6** | Demo 5: Unified Audit | Full audit trail working |
| **MP4** | Complete System | E3 + backends enables final merge |

---

## References

- **Design Doc**: Section 2.9 (Audit Event Structure), Section 2.10 (Audit Queries)
- **E2 Implementation**: `deeptrail-control/app/services/audit_logger_service.py`
- **C6 Implementation**: `deeptrail-gateway/app/middleware/delegation_validator.py`
- **B7 Handler**: `deeptrail-gateway/app/mcp/handlers/tools_call.py`

---

## Notes

- Audit is sent asynchronously to avoid blocking tool execution
- Failed audit sends are logged locally but don't block the response
- Result summarization prevents bloating audit logs with large responses
- Flush method provided for graceful shutdown
- Future: Add batching for high-volume scenarios
- Future: Add retry logic for transient failures
