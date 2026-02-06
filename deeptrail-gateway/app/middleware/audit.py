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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx

from .jwt_validation import AgentContext

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class AuditEventType(str, Enum):
    """
    Types of audit events.
    
    Used for categorizing events in the audit log.
    """
    MCP_TOOL_CALL = "mcp_tool_call"
    PERMISSION_DENIED = "permission_denied"
    CREDENTIAL_ERROR = "credential_error"
    TOOL_ERROR = "tool_error"
    DELEGATION_REVOKED = "delegation_revoked"


@dataclass
class AuditEvent:
    """
    Structured audit event for logging.
    
    Captures all information needed for the unified audit trail.
    Designed to be serializable to JSON for Control Plane API.
    
    Attributes:
        event_type: Type of audit event
        agent_id: Agent that made the request
        on_behalf_of: User who delegated permissions
        tool: Namespaced tool name
        timestamp: When the event occurred
        arguments: Tool arguments (redacted of sensitive data)
        result_summary: Brief summary of result
        error: Error message if failed
        duration_ms: Execution duration in milliseconds
        organization_id: Organization context
        extra_data: Additional metadata
    """
    event_type: AuditEventType
    agent_id: str
    on_behalf_of: str
    tool: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    arguments: dict[str, Any] | None = None
    result_summary: str | None = None
    error: str | None = None
    duration_ms: int | None = None
    delegation_id: str | None = None
    session_id: str | None = None
    organization_id: str | None = None
    extra_data: dict[str, Any] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_type": self.event_type.value,
            "agent_id": self.agent_id,
            "on_behalf_of": self.on_behalf_of,
            "tool": self.tool,
            "timestamp": self.timestamp,
            "arguments": self.arguments,
            "result_summary": self.result_summary,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "delegation_id": self.delegation_id,
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "extra_data": self.extra_data,
        }


# =============================================================================
# AuditMiddleware Class
# =============================================================================


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
    
    MVP Mode:
    - When control_plane_url is None, logs locally
    - Can be configured later to send to E2 (AuditLoggerService)
    
    Example:
        >>> middleware = AuditMiddleware()
        >>> await middleware.log_tool_call(
        ...     agent_context=context,
        ...     tool_name="notion.search_pages",
        ...     arguments={"query": "test"},
        ...     duration_ms=150,
        ... )
    """
    
    # Sensitive field names to redact
    SENSITIVE_KEYS = frozenset({
        "password", "secret", "token", "api_key", "apikey",
        "access_token", "refresh_token", "authorization",
        "credential", "private_key", "secret_key", "bearer",
        "auth", "key", "passwd", "pwd",
    })
    
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
        self._pending_tasks: set[asyncio.Task[bool]] = set()
    
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
        Log a tool call (successful or failed).
        
        This is the main entry point for logging tool executions.
        Sends audit event asynchronously to not block tool response.
        
        Args:
            agent_context: Agent context from JWT validation
            tool_name: Namespaced tool name (e.g., "notion.search_pages")
            arguments: Tool arguments
            result: Tool result (optional, for success)
            error: Error message (optional, for failure)
            duration_ms: Execution duration in milliseconds
        """
        if not self.enabled:
            return
        
        event_type = AuditEventType.TOOL_ERROR if error else AuditEventType.MCP_TOOL_CALL
        
        event = AuditEvent(
            event_type=event_type,
            agent_id=agent_context.agent_id,
            on_behalf_of=agent_context.owner,
            tool=tool_name,
            arguments=self._redact_sensitive(arguments),
            result_summary=self._summarize_result(result) if result else None,
            error=error,
            duration_ms=duration_ms,
            delegation_id=agent_context.delegation_id,
            session_id=agent_context.session_id,
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
        
        Called when DelegationValidator (C6) denies a request.
        
        Args:
            agent_context: Agent context from JWT validation
            tool_name: Tool that was denied
            required_permission: Permission that was required
            denial_reason: Reason for denial (from DenialReason enum)
        """
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_type=AuditEventType.PERMISSION_DENIED,
            agent_id=agent_context.agent_id,
            on_behalf_of=agent_context.owner,
            tool=tool_name,
            error=f"Permission denied: {required_permission}",
            delegation_id=agent_context.delegation_id,
            session_id=agent_context.session_id,
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
        
        Called when CredentialInjector (C7) fails.
        
        Args:
            agent_context: Agent context
            tool_name: Tool that failed
            error_message: Error description (without token details)
        """
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_type=AuditEventType.CREDENTIAL_ERROR,
            agent_id=agent_context.agent_id,
            on_behalf_of=agent_context.owner,
            tool=tool_name,
            error=error_message,
            delegation_id=agent_context.delegation_id,
            session_id=agent_context.session_id,
        )
        
        await self._send_event_async(event)
    
    async def log_delegation_revoked(
        self,
        agent_context: AgentContext,
        tool_name: str,
    ) -> None:
        """
        Log a delegation revoked event.
        
        Called when DelegationValidator detects revoked delegation.
        
        Args:
            agent_context: Agent context
            tool_name: Tool that was attempted
        """
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_type=AuditEventType.DELEGATION_REVOKED,
            agent_id=agent_context.agent_id,
            on_behalf_of=agent_context.owner,
            tool=tool_name,
            error="Delegation has been revoked",
            delegation_id=agent_context.delegation_id,
            session_id=agent_context.session_id,
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
        
        If no control_plane_url is configured (MVP mode),
        logs the event locally instead.
        
        Args:
            event: The audit event to send
            
        Returns:
            True if sent/logged successfully, False otherwise
        """
        if not self.control_plane_url:
            # MVP mode: Log locally
            self._log_event_locally(event)
            return True
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.control_plane_url}/api/v1/audit/events",
                    json=event.to_dict(),
                    timeout=self.timeout_seconds,
                )
                
                if response.status_code in (200, 201, 202):
                    logger.debug(
                        "Audit event sent: %s %s",
                        event.event_type.value,
                        event.tool,
                    )
                    return True
                else:
                    logger.warning(
                        "Audit send failed: %d for %s",
                        response.status_code,
                        event.tool,
                    )
                    # Fail-open: Log locally as fallback
                    self._log_event_locally(event)
                    return False
                    
        except httpx.TimeoutException:
            logger.warning("Audit send timeout for %s", event.tool)
            self._log_event_locally(event)
            return False
        except Exception as e:
            # Fail-open: Don't block tool execution if audit fails
            logger.error("Audit send error: %s", type(e).__name__)
            self._log_event_locally(event)
            return False
    
    def _log_event_locally(self, event: AuditEvent) -> None:
        """
        Log audit event locally.
        
        Used in MVP mode or as fallback when Control Plane is unavailable.
        
        Args:
            event: The audit event to log
        """
        log_level = logging.WARNING if event.error else logging.INFO
        
        logger.log(
            log_level,
            "AUDIT [%s] agent=%s user=%s tool=%s duration=%sms error=%s",
            event.event_type.value,
            event.agent_id,
            event.on_behalf_of,
            event.tool,
            event.duration_ms,
            event.error,
        )
    
    def _redact_sensitive(self, data: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        Redact sensitive fields from audit data.
        
        Removes passwords, tokens, and other secrets.
        Recursively processes nested dicts and lists.
        
        Args:
            data: The data to redact
            
        Returns:
            Redacted copy of the data
        """
        if not data:
            return data
        
        def redact_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: "[REDACTED]" if self._is_sensitive_key(k) else redact_recursive(v)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [redact_recursive(item) for item in obj]
            return obj
        
        return redact_recursive(data)
    
    def _is_sensitive_key(self, key: str) -> bool:
        """
        Check if a key name is sensitive.
        
        Args:
            key: The key name to check
            
        Returns:
            True if the key should be redacted
        """
        key_lower = key.lower()
        return any(sensitive in key_lower for sensitive in self.SENSITIVE_KEYS)
    
    def _summarize_result(self, result: dict[str, Any] | None) -> str:
        """
        Create a brief summary of the tool result.
        
        Truncates long results to avoid bloating audit logs.
        
        Args:
            result: The tool result
            
        Returns:
            Brief summary string (max 100 chars + ellipsis)
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
                elif isinstance(first_item, dict) and "type" in first_item:
                    return f"Content: {first_item['type']} ({len(content)} items)"
        
        # Check for error
        is_error = result.get("isError", False)
        if is_error:
            return "Error response"
        
        # Generic success
        return "Success"
    
    async def flush(self) -> None:
        """
        Wait for all pending audit events to be sent.
        
        Call this during graceful shutdown to ensure
        all audit events are delivered.
        """
        if self._pending_tasks:
            logger.debug("Flushing %d pending audit events", len(self._pending_tasks))
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
    
    def get_pending_count(self) -> int:
        """Get the number of pending audit events."""
        return len(self._pending_tasks)


# =============================================================================
# Module-Level Configuration
# =============================================================================


# Singleton instance
_audit_middleware: AuditMiddleware | None = None


def get_audit_middleware() -> AuditMiddleware:
    """
    Get the configured audit middleware instance.
    
    Returns the singleton middleware, creating it with
    defaults if not configured.
    
    Returns:
        AuditMiddleware instance
    """
    global _audit_middleware
    if _audit_middleware is None:
        _audit_middleware = AuditMiddleware()
    return _audit_middleware


def configure_audit_middleware(
    control_plane_url: str | None = None,
    timeout_seconds: float = 5.0,
    enabled: bool = True,
) -> AuditMiddleware:
    """
    Configure and return the audit middleware.
    
    Args:
        control_plane_url: URL to Control Plane audit endpoint
        timeout_seconds: Timeout for audit requests
        enabled: Whether audit is enabled
        
    Returns:
        Configured AuditMiddleware instance
    """
    global _audit_middleware
    _audit_middleware = AuditMiddleware(
        control_plane_url=control_plane_url,
        timeout_seconds=timeout_seconds,
        enabled=enabled,
    )
    logger.info(
        "Audit middleware configured: control_plane_url=%s, enabled=%s",
        control_plane_url or "None (local logging)",
        enabled,
    )
    return _audit_middleware


def reset_audit_middleware() -> None:
    """Reset the audit middleware (for testing)."""
    global _audit_middleware
    _audit_middleware = None


# =============================================================================
# Convenience Functions
# =============================================================================


async def log_tool_call(
    agent_context: AgentContext,
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any] | None = None,
    error: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """
    Convenience function to log a tool call.
    
    Uses the configured singleton middleware.
    """
    middleware = get_audit_middleware()
    await middleware.log_tool_call(
        agent_context=agent_context,
        tool_name=tool_name,
        arguments=arguments,
        result=result,
        error=error,
        duration_ms=duration_ms,
    )


async def log_permission_denied(
    agent_context: AgentContext,
    tool_name: str,
    required_permission: str,
    denial_reason: str,
) -> None:
    """
    Convenience function to log a permission denied event.
    """
    middleware = get_audit_middleware()
    await middleware.log_permission_denied(
        agent_context=agent_context,
        tool_name=tool_name,
        required_permission=required_permission,
        denial_reason=denial_reason,
    )
