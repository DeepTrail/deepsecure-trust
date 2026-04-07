"""
MCP tools/call Request Handler for Virtual MCP Server.

Handles the MCP `tools/call` method by:
1. Parsing namespaced tool name to extract backend and tool
2. Validating permission against agent's delegation (C6: DelegationValidator)
3. Validating constraints (rate limits, quotas) - placeholder for MVP
4. Getting backend session and credential reference
5. Forwarding to backend MCP server with injected credentials
6. Logging audit event for every call (success or failure)
7. Returning result to agent

This is the core handler demonstrating:
- Demo 3: Delegation Execution
- Demo 4: Permission Enforcement
- Step 8-9 of Sarah's Journey

Security principles:
- Fail-closed: Deny if any validation fails
- Unknown tools denied by default (via DelegationValidator)
- Every call logged for audit
- Agent never sees OAuth tokens

MCP Specification Reference:
https://spec.modelcontextprotocol.io/specification/server/tools/

Usage:
    from app.mcp.handlers import handle_tools_call
    from app.mcp.protocol import MCPProtocolHandler, MCPMethod
    
    handler = MCPProtocolHandler()
    handler.register_handler(MCPMethod.TOOLS_CALL, handle_tools_call)

Request Format:
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "notion.search_pages",
            "arguments": {"query": "competitor analysis"}
        }
    }

Success Response:
    {
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "content": [{"type": "text", "text": "Found 3 pages: ..."}]
        }
    }

Error Response:
    {
        "jsonrpc": "2.0",
        "id": 3,
        "error": {
            "code": -32001,
            "message": "Permission denied: notion:pages:create not delegated"
        }
    }
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..namespace import NamespaceError, unprefix_tool_name
from ..protocol import JsonRpcErrorCode, MCPError
from ..session_manager import BackendMCPSession, MCPSessionManager
from ...middleware.audit import get_audit_middleware
from ...middleware.credential_injection import get_credential_injector
from ...middleware.delegation_validator import get_delegation_validator
from ...middleware.jwt_validation import AgentContext
from ...middleware.result_filter import get_result_filter
from ...security.fail_closed import FailClosedError, enforce_fail_closed
from ...security.constraint_checker import get_constraint_checker
from ...security.prompt_injection import get_prompt_injection_detector

logger = logging.getLogger(__name__)


# =============================================================================
# MCP Error Codes (extensions for tools/call)
# =============================================================================


class ToolsCallErrorCode:
    """
    MCP error codes for tools/call method.
    
    Uses reserved range -32000 to -32099 for MCP-specific errors.
    """
    # From protocol.py
    PERMISSION_DENIED = JsonRpcErrorCode.PERMISSION_DENIED  # -32001
    SESSION_INVALID = JsonRpcErrorCode.SESSION_INVALID  # -32002
    CREDENTIAL_ERROR = JsonRpcErrorCode.CREDENTIAL_ERROR  # -32003
    
    # tools/call specific
    INVALID_TOOL_NAME = -32010  # Invalid tool name format
    BACKEND_UNAVAILABLE = -32011  # Backend not connected
    CONSTRAINT_VIOLATED = -32012  # Rate limit, quota exceeded
    TOOL_EXECUTION_ERROR = -32013  # Backend returned error


# =============================================================================
# Request/Response Models
# =============================================================================


class ToolsCallParams(BaseModel):
    """
    Parameters for the MCP tools/call request.
    
    Attributes:
        name: Namespaced tool name (e.g., "notion.search_pages")
        arguments: Tool arguments to pass to the backend
    """
    name: str = Field(..., description="Namespaced tool name")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the tool"
    )
    
    model_config = {"extra": "allow"}


class ToolCallContent(BaseModel):
    """
    Content item in tool call result.
    
    MCP tools/call result contains a content array with typed items.
    """
    type: str = Field(..., description="Content type (text, image, etc.)")
    text: str | None = Field(default=None, description="Text content")
    data: str | None = Field(default=None, description="Base64 encoded data")
    mimeType: str | None = Field(default=None, alias="mimeType", description="MIME type for data")
    
    model_config = {"populate_by_name": True}


class ToolsCallResult(BaseModel):
    """
    Result for the MCP tools/call response.
    
    Attributes:
        content: Array of content items returned by the tool
        isError: Whether the tool execution resulted in an error
    """
    content: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Content returned by the tool"
    )
    isError: bool = Field(
        default=False,
        alias="isError",
        description="Whether the tool execution resulted in an error"
    )
    
    model_config = {"populate_by_name": True}


# =============================================================================
# Audit Event Models
# =============================================================================


class AuditEvent(BaseModel):
    """
    Audit event for tool calls.
    
    Every tool call (success or failure) generates an audit event.
    Enhanced for C6 DelegationValidator integration.
    """
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    event_type: str = Field(..., description="Event type (mcp_tool_call, permission_denied, etc.)")
    agent_id: str | None = Field(default=None, description="Agent identifier")
    on_behalf_of: str | None = Field(default=None, description="User who delegated access")
    session_id: str | None = Field(default=None, description="Agent session ID")
    tool: str = Field(..., description="Tool name that was called")
    backend: str | None = Field(default=None, description="Backend server ID")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    success: bool = Field(..., description="Whether the call succeeded")
    result_summary: str | None = Field(default=None, description="Brief summary of result")
    error: str | None = Field(default=None, description="Error message if failed")
    required_permission: str | None = Field(default=None, description="Permission that was checked")
    denial_reason: str | None = Field(default=None, description="C6: DelegationValidator denial reason")


# =============================================================================
# Handler Dependencies
# =============================================================================


# Global instances - will be set during app initialization
_session_manager: MCPSessionManager | None = None
_backend_client: Any | None = None  # For production backend forwarding
_audit_logger: Any | None = None  # For production audit logging


def configure_tools_call_handler(
    session_manager: MCPSessionManager,
    backend_client: Any | None = None,
    audit_logger: Any | None = None,
) -> None:
    """
    Configure the tools/call handler with required dependencies.
    
    Must be called during app initialization before handling requests.
    
    Args:
        session_manager: MCP session manager instance
        backend_client: Optional backend client for forwarding (mock for MVP)
        audit_logger: Optional audit logger (uses logging if None)
    """
    global _session_manager, _backend_client, _audit_logger
    _session_manager = session_manager
    _backend_client = backend_client
    _audit_logger = audit_logger
    logger.info("tools/call handler configured")


def get_session_manager() -> MCPSessionManager:
    """Get the configured session manager."""
    if _session_manager is None:
        raise RuntimeError("tools/call handler not configured. Call configure_tools_call_handler() first.")
    return _session_manager


# =============================================================================
# Handler Implementation
# =============================================================================


async def handle_tools_call(params: dict[str, Any]) -> dict[str, Any]:
    """
    Handle MCP tools/call request.
    
    Routes tool calls to backend MCP servers with credential injection and
    permission validation. This is the core handler demonstrating:
    - Delegation execution (agent acts on behalf of user)
    - Permission enforcement (only delegated tools allowed)
    - Audit trail (every call logged)
    
    Args:
        params: Request parameters (may include _context from middleware):
            - name: Namespaced tool name (e.g., "notion.search_pages")
            - arguments: Tool arguments
            - _context: Request context from middleware containing:
                - agent_session_id: Agent's session ID
                - delegated_permissions: List of permission strings
    
    Returns:
        tools/call result containing:
            - content: Array of content items from tool execution
            - isError: Whether execution resulted in error
    
    Raises:
        MCPError: If validation fails or backend unavailable
    
    Example:
        >>> await handle_tools_call({
        ...     "name": "notion.search_pages",
        ...     "arguments": {"query": "test"},
        ...     "_context": {
        ...         "agent_session_id": "agent-123",
        ...         "delegated_permissions": ["notion:pages:search"]
        ...     }
        ... })
        {
            "content": [{"type": "text", "text": "Found 5 pages..."}],
            "isError": false
        }
    """
    # Extract context (passed by middleware/protocol handler)
    context = params.pop("_context", {})
    agent_session_id = context.get("agent_session_id")
    agent_id = context.get("agent_id", agent_session_id)
    delegated_permissions = context.get("delegated_permissions", [])
    delegation_id = context.get("delegation_id")
    constraints = context.get("constraints", {})  # E5: Delegation constraints
    agent_jwt_token = context.get("agent_jwt_token")  # H1: Raw JWT for vault API calls

    # Build AgentContext for C6 DelegationValidator
    agent_context: AgentContext | None = None
    if agent_session_id and delegated_permissions:
        agent_context = AgentContext(
            agent_id=agent_id or "",
            owner=context.get("delegator", ""),
            delegation_id=delegation_id or "",
            session_id=agent_session_id or "",
            delegated_permissions=delegated_permissions,
        )
    
    # E4: Fail-closed security - deny if Control Plane unreachable
    try:
        await enforce_fail_closed()
    except FailClosedError as e:
        logger.warning(f"FAIL-CLOSED: tools/call denied - {e.reason}")
        raise MCPError(
            JsonRpcErrorCode.PERMISSION_DENIED,
            f"Security denial: Cannot verify permissions - {e.reason}"
        )
    
    # Parse and validate params
    try:
        call_params = ToolsCallParams(**params)
    except Exception as e:
        logger.warning(f"Invalid tools/call params: {e}")
        raise MCPError(
            JsonRpcErrorCode.INVALID_PARAMS,
            f"Invalid parameters: {e}"
        )
    
    tool_name = call_params.name
    arguments = call_params.arguments
    
    logger.debug(f"tools/call request: tool={tool_name}, session={agent_session_id}")
    
    # Get audit middleware (E3)
    audit_middleware = get_audit_middleware()
    
    # Start timing for duration measurement
    start_time = time.perf_counter()
    
    # Get session manager
    try:
        session_manager = get_session_manager()
    except RuntimeError as e:
        logger.error(f"Handler not configured: {e}")
        raise MCPError(
            JsonRpcErrorCode.INTERNAL_ERROR,
            "Server configuration error"
        )
    
    # Get agent session
    if not agent_session_id:
        # E3: Log audit (minimal context since no session)
        await _log_audit(
            None, tool_name, arguments,
            success=False,
            error="No agent session"
        )
        raise MCPError(
            ToolsCallErrorCode.SESSION_INVALID,
            "No agent session. Call initialize first."
        )
    
    agent_session = session_manager.get_agent_session(agent_session_id)
    if not agent_session:
        await _log_audit(
            None, tool_name, arguments,
            success=False,
            error="Session not found"
        )
        raise MCPError(
            ToolsCallErrorCode.SESSION_INVALID,
            "Session not found. Call initialize first."
        )
    
    # Step 1: Parse namespace
    try:
        backend_id, original_tool = unprefix_tool_name(tool_name)
    except NamespaceError as e:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        if agent_context:
            # E3: Use audit middleware
            await audit_middleware.log_tool_call(
                agent_context=agent_context,
                tool_name=tool_name,
                arguments=arguments,
                error=f"Invalid tool name: {e}",
                duration_ms=duration_ms,
            )
        else:
            await _log_audit(
                agent_session, tool_name, arguments,
                success=False,
                error=f"Invalid tool name: {e}"
            )
        raise MCPError(
            ToolsCallErrorCode.INVALID_TOOL_NAME,
            f"Invalid tool name format: {tool_name}"
        )
    
    logger.debug(f"Parsed namespace: backend={backend_id}, tool={original_tool}")
    
    # Step 2: Validate permission using C6 DelegationValidator
    validator = get_delegation_validator()
    validation_result = await validator.validate_tool_call(
        tool_name=tool_name,
        agent_context=agent_context,
    )
    
    if not validation_result.allowed:
        required_perm = validation_result.required_permission
        error_message = validation_result.error_message or f"Permission denied: {required_perm}"
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        
        if agent_context:
            # E3: Use audit middleware for permission denied
            denial_reason = validation_result.denial_reason.value if validation_result.denial_reason else "unknown"
            await audit_middleware.log_permission_denied(
                agent_context=agent_context,
                tool_name=tool_name,
                required_permission=required_perm or "",
                denial_reason=denial_reason,
            )
        else:
            await _log_audit(
                agent_session, tool_name, arguments,
                success=False,
                error=error_message,
                required_permission=required_perm,
                backend=backend_id,
                denial_reason=validation_result.denial_reason.value if validation_result.denial_reason else None,
            )
        raise MCPError(
            ToolsCallErrorCode.PERMISSION_DENIED,
            error_message,
            data={
                "tool": tool_name,
                "required_permission": required_perm,
                "delegated_permissions": agent_context.delegated_permissions if agent_context else []
            }
        )
    
    logger.debug(f"Permission validated: {validation_result.required_permission}")
    
    # Step 3: Validate and increment constraints (E5: ConstraintChecker)
    constraint_checker = get_constraint_checker()
    constraint_violation = await constraint_checker.check_and_increment(
        agent_id=agent_id or "",
        delegation_id=delegation_id or "",
        session_id=agent_session_id,
        constraints=constraints,
    )
    
    if constraint_violation:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        error_msg = f"Constraint violated: {constraint_violation.message}"
        if agent_context:
            await audit_middleware.log_tool_call(
                agent_context=agent_context,
                tool_name=tool_name,
                arguments=arguments,
                error=error_msg,
                duration_ms=duration_ms,
            )
        else:
            await _log_audit(
                agent_session, tool_name, arguments,
                success=False,
                error=error_msg,
                backend=backend_id
            )
        raise MCPError(
            ToolsCallErrorCode.CONSTRAINT_VIOLATED,
            error_msg,
            data={
                "constraint": constraint_violation.constraint_name,
                "current": constraint_violation.current_value,
                "limit": constraint_violation.limit_value,
            }
        )
    
    # Step 3.5: Scan arguments for prompt injection (J5)
    injection_detector = get_prompt_injection_detector()
    if injection_detector:
        scan_result = injection_detector.scan_arguments(
            arguments=arguments,
            tool_name=tool_name,
        )
        if scan_result.is_blocked:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning(
                "Prompt injection blocked",
                extra={
                    "tool": tool_name,
                    "threat_level": scan_result.threat_level.value,
                    "detections": scan_result.detection_count,
                    "categories": [
                        d.category.value for d in scan_result.detections if d.category
                    ],
                },
            )
            if agent_context:
                await audit_middleware.log_tool_call(
                    agent_context=agent_context,
                    tool_name=tool_name,
                    arguments=arguments,
                    error=f"Prompt injection blocked: threat_level={scan_result.threat_level.value}",
                    duration_ms=duration_ms,
                )
            raise MCPError(
                JsonRpcErrorCode.INVALID_PARAMS,
                "Request blocked: potentially malicious content detected in arguments",
                data={
                    "threat_level": scan_result.threat_level.value,
                    "blocked_fields": scan_result.scanned_fields,
                },
            )

    # Step 4: Get backend session and credentials
    backend_session = session_manager.get_backend_session(agent_session_id, backend_id)
    
    if not backend_session:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        if agent_context:
            await audit_middleware.log_tool_call(
                agent_context=agent_context,
                tool_name=tool_name,
                arguments=arguments,
                error=f"Backend {backend_id} not connected",
                duration_ms=duration_ms,
            )
        else:
            await _log_audit(
                agent_session, tool_name, arguments,
                success=False,
                error=f"Backend {backend_id} not connected",
                backend=backend_id
            )
        raise MCPError(
            ToolsCallErrorCode.BACKEND_UNAVAILABLE,
            f"Backend '{backend_id}' not connected for this session"
        )
    
    # Step 5: Forward to backend with credential injection
    try:
        result = await _forward_to_backend(
            backend_id=backend_id,
            backend_session=backend_session,
            tool_name=original_tool,
            arguments=arguments,
            agent_context=agent_context,  # E3: Pass context for credential error auditing
            agent_jwt_token=agent_jwt_token,  # H1: Raw JWT for vault API calls
        )
    except MCPError:
        # Re-raise MCP errors (already logged by _forward_to_backend if credential error)
        raise
    except Exception as e:
        logger.error(f"Backend call failed: {e}", exc_info=True)
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        if agent_context:
            await audit_middleware.log_tool_call(
                agent_context=agent_context,
                tool_name=tool_name,
                arguments=arguments,
                error=f"Backend error: {e}",
                duration_ms=duration_ms,
            )
        else:
            await _log_audit(
                agent_session, tool_name, arguments,
                success=False,
                error=f"Backend error: {e}",
                backend=backend_id
            )
        raise MCPError(
            ToolsCallErrorCode.TOOL_EXECUTION_ERROR,
            f"Tool execution failed: {e}"
        )
    
    # Step 5.5: Apply PII result filter (J4) before audit/return
    result_filter = get_result_filter()
    if result_filter and result_filter.enabled:
        filter_result = result_filter.filter_response(
            content=result,
            backend_id=backend_id,
            tool_name=tool_name,
        )
        result = filter_result.filtered_content
        if filter_result.masks_applied > 0:
            logger.info(
                "PII masked in response",
                extra={
                    "tool": tool_name,
                    "backend": backend_id,
                    "masks_applied": filter_result.masks_applied,
                    "pii_types": [t.value for t in filter_result.pii_types_found],
                },
            )

    # Step 6: Log successful call using E3 AuditMiddleware
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    if agent_context:
        await audit_middleware.log_tool_call(
            agent_context=agent_context,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
        )
    else:
        result_summary = _summarize_result(result)
        await _log_audit(
            agent_session, tool_name, arguments,
            success=True,
            result_summary=result_summary,
            backend=backend_id
        )
    
    logger.info(
        f"tools/call success: tool={tool_name}, agent={agent_session.agent_session_id}, "
        f"on_behalf_of={agent_session.delegator}"
    )
    
    # Step 7: Return result
    return ToolsCallResult(**result).model_dump(by_alias=True)


# =============================================================================
# Validation Functions
# =============================================================================


# NOTE: _validate_permission has been replaced by C6 DelegationValidator
# The DelegationValidator provides:
# - Structured ValidationResult with DenialReason enum
# - Support for delegation revocation checking
# - Better audit logging integration
# - Wildcard permission support (notion:*, *:*)
# See: app/middleware/delegation_validator.py


# NOTE: _validate_constraints has been replaced by E5 ConstraintChecker
# The ConstraintChecker provides:
# - max_actions_per_day constraint enforcement
# - max_actions_per_session constraint enforcement
# - Proper counter management with ConstraintStore
# - Support for Redis-backed persistent counters
# See: app/security/constraint_checker.py


# =============================================================================
# Backend Forwarding
# =============================================================================


async def _forward_to_backend(
    backend_id: str,
    backend_session: BackendMCPSession,
    tool_name: str,
    arguments: dict[str, Any],
    agent_context: AgentContext | None = None,
    agent_jwt_token: str | None = None,
) -> dict[str, Any]:
    """
    Forward tool call to backend MCP server with credential injection (C7).
    
    MVP: Returns mock response. Production uses backend_client.
    
    Security (C7):
    - Injects OAuth credentials server-side
    - Agent never sees the actual token
    - Fail-closed: No credential = request denied
    
    Args:
        backend_id: Backend identifier (e.g., "notion")
        backend_session: Backend session with credential reference
        tool_name: Original tool name (without namespace)
        arguments: Tool arguments
        agent_context: Agent context for E3 audit logging
    
    Returns:
        Backend response with content array
        
    Raises:
        MCPError: If credential injection fails (CREDENTIAL_ERROR)
    """
    global _backend_client
    
    # Get credential reference from session
    cred_ref = None
    if backend_session.credential_ref:
        cred_ref = backend_session.credential_ref.ref
    
    # C7: Inject credentials - get authorization headers from vault
    injector = get_credential_injector()
    injection_result = await injector.inject_credentials(
        credential_ref=cred_ref,
        backend_id=backend_id,
        agent_jwt_token=agent_jwt_token,
        user_id=agent_context.owner if agent_context else None,
    )
    
    if not injection_result.success:
        # C7 Fail-closed: No credential = request denied
        error_msg = injection_result.error_message or "Credential error"
        logger.warning(
            "Credential injection failed for backend %s: %s",
            backend_id,
            injection_result.error.value if injection_result.error else "unknown",
        )
        
        # E3: Log credential error to audit
        if agent_context:
            audit_middleware = get_audit_middleware()
            await audit_middleware.log_credential_error(
                agent_context=agent_context,
                tool_name=f"{backend_id}.{tool_name}",
                error_message=error_msg,
            )
        
        raise MCPError(
            ToolsCallErrorCode.CREDENTIAL_ERROR,
            error_msg
        )
    
    # C7: Get auth headers (agent never sees these)
    auth_headers = injection_result.headers
    
    if _backend_client is not None:
        # Production: Use configured backend client with injected credentials
        return await _backend_client.call_tool(
            backend_id=backend_id,
            tool_name=tool_name,
            arguments=arguments,
            auth_headers=auth_headers,  # C7: Pass injected headers
            mcp_session_id=backend_session.mcp_session_id
        )
    
    # MVP: Mock response (credentials were validated but mock doesn't use them)
    # Log that credentials were injected without exposing token
    logger.info(
        "MVP Mock: Forwarding %s to %s (credentials injected: %s)",
        tool_name,
        backend_id,
        bool(auth_headers),
    )
    
    # Update backend session activity
    backend_session.update_activity()
    
    # Generate mock response based on tool
    mock_text = _generate_mock_response(backend_id, tool_name, arguments)
    
    return {
        "content": [
            {
                "type": "text",
                "text": mock_text
            }
        ],
        "isError": False
    }


def _generate_mock_response(
    backend_id: str,
    tool_name: str,
    arguments: dict[str, Any]
) -> str:
    """Generate mock response text for MVP testing."""
    backend_display = backend_id.replace("_", " ").title()
    
    # Generate contextual mock responses
    if "search" in tool_name.lower():
        query = arguments.get("query", "items")
        return f"[{backend_display}] Found 5 results for '{query}'"
    
    if "list" in tool_name.lower():
        return f"[{backend_display}] Retrieved 10 items"
    
    if "create" in tool_name.lower():
        return f"[{backend_display}] Successfully created new item"
    
    if "update" in tool_name.lower():
        return f"[{backend_display}] Successfully updated item"
    
    if "delete" in tool_name.lower():
        return f"[{backend_display}] Successfully deleted item"
    
    if "read" in tool_name.lower() or "get" in tool_name.lower():
        return f"[{backend_display}] Retrieved item details"
    
    if "send" in tool_name.lower():
        return f"[{backend_display}] Message sent successfully"
    
    # Generic response
    return f"[{backend_display}] Tool {tool_name} executed successfully"


# =============================================================================
# Audit Logging
# =============================================================================


async def _log_audit(
    agent_session: Any | None,
    tool_name: str,
    arguments: dict[str, Any],
    success: bool,
    result_summary: str | None = None,
    error: str | None = None,
    required_permission: str | None = None,
    backend: str | None = None,
    denial_reason: str | None = None,
) -> None:
    """
    Log audit event for tool call.
    
    Every tool call generates an audit event, regardless of success/failure.
    Enhanced for C6 DelegationValidator integration.
    
    Args:
        agent_session: Agent's session (may be None if session lookup failed)
        tool_name: Tool that was called
        arguments: Tool arguments
        success: Whether call succeeded
        result_summary: Summary of result (if success)
        error: Error message (if failed)
        required_permission: Permission that was checked
        backend: Backend server ID
        denial_reason: C6 DelegationValidator denial reason
    """
    global _audit_logger
    
    # Determine event type (enhanced for C6 denial reasons)
    if success:
        event_type = "mcp_tool_call"
    elif denial_reason:
        # Use C6 DelegationValidator denial reason for event type
        event_type = f"delegation_{denial_reason}"
    elif error and "Permission denied" in error:
        event_type = "permission_denied"
    elif error and "constraint" in error.lower():
        event_type = "constraint_violated"
    else:
        event_type = "tool_call_error"
    
    event = AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        event_type=event_type,
        agent_id=agent_session.agent_session_id if agent_session else None,
        on_behalf_of=agent_session.delegator if agent_session else None,
        session_id=agent_session.agent_session_id if agent_session else None,
        tool=tool_name,
        backend=backend,
        arguments=arguments,
        success=success,
        result_summary=result_summary,
        error=error,
        required_permission=required_permission,
        denial_reason=denial_reason,
    )
    
    if _audit_logger is not None:
        await _audit_logger.log(event.model_dump())
    else:
        # Use standard logging for MVP
        if success:
            logger.info(f"AUDIT: {event.model_dump()}")
        else:
            logger.warning(f"AUDIT: {event.model_dump()}")


def _summarize_result(result: dict[str, Any]) -> str:
    """
    Create a summary of the tool result for audit log.
    
    Args:
        result: Backend response
    
    Returns:
        Brief summary string (max 100 chars)
    """
    content = result.get("content", [])
    if not content:
        return "No content"
    
    first_item = content[0]
    if isinstance(first_item, dict):
        if first_item.get("type") == "text":
            text = first_item.get("text", "")
            return text[:100] + "..." if len(text) > 100 else text
    
    return f"Response with {len(content)} content item(s)"


# =============================================================================
# Standalone Handler (for testing)
# =============================================================================


async def handle_tools_call_standalone(
    params: dict[str, Any],
    session_manager: MCPSessionManager,
    backend_client: Any | None = None,
    audit_logger: Any | None = None,
) -> dict[str, Any]:
    """
    Handle tools/call with explicit dependencies (for testing).
    
    This is an alternative to the global-configured handler,
    allowing explicit dependency injection for tests.
    
    Args:
        params: Request parameters
        session_manager: Session manager instance
        backend_client: Optional backend client
        audit_logger: Optional audit logger
    
    Returns:
        tools/call result
    """
    global _session_manager, _backend_client, _audit_logger
    
    # Temporarily configure globals
    old_sm = _session_manager
    old_bc = _backend_client
    old_al = _audit_logger
    
    configure_tools_call_handler(session_manager, backend_client, audit_logger)
    
    try:
        return await handle_tools_call(params)
    finally:
        # Restore globals
        _session_manager = old_sm
        _backend_client = old_bc
        _audit_logger = old_al
