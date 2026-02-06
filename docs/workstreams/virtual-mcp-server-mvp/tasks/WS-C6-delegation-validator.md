# Task: WS-C6 Implement Delegation Validator

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-C: Auth & Permissions |
| **Dependencies** | C3 (JWT validation middleware) ✅, A6 (DelegationService) ✅ |
| **Blocked By** | None (C3, A6 complete) |
| **Assigned** | - |
| **Created** | February 5, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 6 |
| **Target Worktree** | `vmcp-gateway` |

---

## Validation Mapping

| Validates | Reference |
|-----------|-----------|
| **Demo 4** | Permission Enforcement - Unauthorized blocked at gateway |
| **User Journey Step** | Step 8: Agent executes tool with valid delegation |
| **User Journey Step** | Step 9: Permission denied for non-delegated tools |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] C3 (JWT validation middleware) is complete - provides `request.state.agent_context` with `delegation_id` and `delegated_permissions`
- [x] A6 (DelegationService) is complete - can validate delegation status via Control Plane
- [x] B7 (tools/call handler) is complete - has basic permission validation to refactor
- [x] C4 (Permission mapper) is complete - maps tool names to permission strings

---

## Task Description

Implement a **delegation validator** that validates tool execution requests against the agent's active delegation before allowing `tools/call` to proceed.

### Context

This is **Step 8-9 of Sarah's journey**:
- Step 8: Agent executes a delegated tool successfully
- Step 9: Agent attempts non-delegated tool and is denied

The delegation validator sits in the execution path for `tools/call` and:
1. Extracts `delegation_id` and `delegated_permissions` from `AgentContext` (set by C3)
2. Uses `PermissionMapper` (C4) to determine required permission for the tool
3. Validates the permission is in `delegated_permissions`
4. Optionally validates delegation is still active with Control Plane (for revocation checks)
5. Returns appropriate error if validation fails

### Key Security Requirements

1. **Fail-closed behavior**: If validation cannot complete, deny the request
2. **Defense in depth**: Even though tools/list filters, tools/call must also validate
3. **Real-time revocation**: Can check delegation status with Control Plane
4. **Audit logging**: Log all permission denials

### Existing Code Integration

The `tools_call.py` handler already has `_validate_permission()`. This task:
1. Extracts permission validation into a reusable `DelegationValidator` class
2. Adds delegation status checking (is it revoked?)
3. Adds constraint validation support (for E5)
4. Creates proper middleware pattern for future enhancements

### Integration Point

```
Agent → Gateway
         │
         ├── JWTValidationMiddleware (C3) → sets request.state.agent_context
         │
         ├── tools/call handler (B7)
         │       │
         │       └── DelegationValidator (C6) → validates permission + delegation
         │               │
         │               ├── Uses PermissionMapper (C4)
         │               │
         │               └── (Optional) Calls Control Plane to verify delegation status
         │
         └── CredentialInjection (C7) → injects OAuth token [depends on C6]
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/middleware/delegation_validator.py` | **CREATE** | Delegation validator class |
| `deeptrail-gateway/app/mcp/handlers/tools_call.py` | **MODIFY** | Use DelegationValidator instead of inline validation |
| `deeptrail-gateway/tests/middleware/test_delegation_validator.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. DelegationValidator Class

```python
"""
Delegation Validator for tools/call requests.

Validates that the agent has permission to execute a tool based on their
active delegation. This is a critical security component implementing:
- Demo 4: Permission Enforcement
- Step 8-9 of Sarah's Journey

Security Principles:
- Fail-closed: Deny if validation cannot complete
- Defense in depth: Validates even if tools/list filtered
- Real-time revocation support: Can check Control Plane
- Audit trail: Logs all denials

Usage:
    from app.middleware.delegation_validator import DelegationValidator
    from app.middleware.jwt_validation import AgentContext
    
    validator = DelegationValidator(control_plane_url="http://deeptrail-control:8000")
    
    result = await validator.validate_tool_call(
        tool_name="notion.search_pages",
        agent_context=agent_context,
    )
    
    if not result.allowed:
        raise PermissionDenied(result.error_message)
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from app.middleware.jwt_validation import AgentContext
from app.mcp.permission_mapper import PermissionMapper

logger = logging.getLogger(__name__)


class DenialReason(Enum):
    """Reasons for denying a tool call."""
    NO_CONTEXT = "no_agent_context"
    UNKNOWN_TOOL = "unknown_tool"
    PERMISSION_NOT_DELEGATED = "permission_not_delegated"
    DELEGATION_REVOKED = "delegation_revoked"
    DELEGATION_EXPIRED = "delegation_expired"
    CONSTRAINT_VIOLATED = "constraint_violated"
    VALIDATION_ERROR = "validation_error"


@dataclass
class ValidationResult:
    """Result of delegation validation."""
    allowed: bool
    required_permission: str | None = None
    denial_reason: DenialReason | None = None
    error_message: str | None = None
    
    @classmethod
    def allow(cls, permission: str) -> "ValidationResult":
        return cls(allowed=True, required_permission=permission)
    
    @classmethod
    def deny(
        cls, 
        reason: DenialReason, 
        permission: str | None = None,
        message: str | None = None
    ) -> "ValidationResult":
        return cls(
            allowed=False,
            required_permission=permission,
            denial_reason=reason,
            error_message=message or f"Permission denied: {reason.value}"
        )


class DelegationValidator:
    """
    Validates tool calls against agent's delegation.
    
    Responsibilities:
    1. Map tool name to required permission (via PermissionMapper)
    2. Check permission is in delegated_permissions
    3. (Optional) Verify delegation is still active with Control Plane
    4. Support wildcard permissions (e.g., "notion:*")
    
    Security:
    - Fail-closed: Returns deny if any validation fails
    - Unknown tools are denied by default
    - All denials are logged for audit
    """
    
    def __init__(
        self,
        control_plane_url: str | None = None,
        check_revocation: bool = False,  # MVP: disabled, enable in production
        cache_ttl_seconds: int = 60,  # Cache delegation status
    ):
        """
        Initialize the delegation validator.
        
        Args:
            control_plane_url: URL to Control Plane for revocation checks
            check_revocation: Whether to check delegation status with Control Plane
            cache_ttl_seconds: How long to cache delegation status
        """
        self.control_plane_url = control_plane_url
        self.check_revocation = check_revocation
        self.cache_ttl_seconds = cache_ttl_seconds
        self._status_cache: dict[str, tuple[bool, float]] = {}
    
    async def validate_tool_call(
        self,
        tool_name: str,
        agent_context: AgentContext | None,
    ) -> ValidationResult:
        """
        Validate a tool call against the agent's delegation.
        
        Args:
            tool_name: Namespaced tool name (e.g., "notion.search_pages")
            agent_context: Agent context from JWT validation (C3)
            
        Returns:
            ValidationResult indicating whether call is allowed
        """
        # Step 1: Check agent context exists
        if agent_context is None:
            logger.warning("Delegation validation failed: no agent context")
            return ValidationResult.deny(
                DenialReason.NO_CONTEXT,
                message="No agent context. Authentication required."
            )
        
        # Step 2: Get required permission for tool
        required_permission = PermissionMapper.get_permission(tool_name)
        
        if required_permission is None:
            # Try to infer for better error message
            inferred = PermissionMapper.infer_permission(tool_name)
            logger.warning(
                f"Unknown tool {tool_name}, agent {agent_context.agent_id}"
            )
            return ValidationResult.deny(
                DenialReason.UNKNOWN_TOOL,
                permission=inferred,
                message=f"Unknown tool: {tool_name}"
            )
        
        # Step 3: Check permission in delegated_permissions
        if not self._check_permission(
            required_permission, 
            agent_context.delegated_permissions
        ):
            logger.info(
                f"Permission denied for {tool_name}: "
                f"{required_permission} not in delegation for agent {agent_context.agent_id}"
            )
            return ValidationResult.deny(
                DenialReason.PERMISSION_NOT_DELEGATED,
                permission=required_permission,
                message=f"Permission denied: {required_permission} not delegated"
            )
        
        # Step 4: (Optional) Check delegation is still active
        if self.check_revocation and agent_context.delegation_id:
            is_active = await self._check_delegation_active(
                agent_context.delegation_id
            )
            if not is_active:
                logger.warning(
                    f"Delegation {agent_context.delegation_id} is revoked/expired"
                )
                return ValidationResult.deny(
                    DenialReason.DELEGATION_REVOKED,
                    permission=required_permission,
                    message="Delegation has been revoked or expired"
                )
        
        # All checks passed
        logger.debug(
            f"Delegation validated: tool={tool_name}, "
            f"permission={required_permission}, agent={agent_context.agent_id}"
        )
        return ValidationResult.allow(required_permission)
    
    def _check_permission(
        self,
        required_permission: str,
        delegated_permissions: list[str],
    ) -> bool:
        """
        Check if required permission is in delegated permissions.
        
        Supports:
        - Exact match: "notion:pages:search" in permissions
        - Backend wildcard: "notion:*" matches any notion permission
        - Full wildcard: "*:*" matches anything (admin/testing)
        
        Args:
            required_permission: Permission string needed for tool
            delegated_permissions: Agent's delegated permissions
            
        Returns:
            True if permission is granted
        """
        # Exact match
        if required_permission in delegated_permissions:
            return True
        
        # Parse permission for wildcard checks
        parts = required_permission.split(":")
        if len(parts) < 1:
            return False
        
        backend = parts[0]
        
        # Check backend wildcard (e.g., "notion:*")
        if f"{backend}:*" in delegated_permissions:
            return True
        
        # Check resource wildcard (e.g., "notion:pages:*")
        if len(parts) >= 2:
            resource = parts[1]
            if f"{backend}:{resource}:*" in delegated_permissions:
                return True
        
        # Check full wildcard (admin/testing only)
        if "*:*" in delegated_permissions:
            return True
        
        return False
    
    async def _check_delegation_active(
        self,
        delegation_id: str,
    ) -> bool:
        """
        Check if delegation is still active with Control Plane.
        
        MVP: Always returns True (no Control Plane call)
        Production: Calls Control Plane with caching
        
        Args:
            delegation_id: Delegation ID from JWT
            
        Returns:
            True if delegation is active, False if revoked/expired
        """
        if not self.control_plane_url:
            # MVP: No Control Plane configured, assume active
            return True
        
        # Check cache first
        import time
        now = time.time()
        if delegation_id in self._status_cache:
            is_active, cached_at = self._status_cache[delegation_id]
            if now - cached_at < self.cache_ttl_seconds:
                return is_active
        
        # Call Control Plane
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.control_plane_url}/api/v1/delegations/{delegation_id}/status",
                    timeout=5.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    is_active = data.get("status") == "active"
                elif response.status_code == 404:
                    is_active = False
                else:
                    # Fail-closed: assume inactive on error
                    logger.error(
                        f"Control Plane returned {response.status_code} for delegation {delegation_id}"
                    )
                    is_active = False
                
                # Cache result
                self._status_cache[delegation_id] = (is_active, now)
                return is_active
                
        except Exception as e:
            logger.error(f"Failed to check delegation status: {e}")
            # Fail-closed: assume inactive on network error
            return False
    
    def clear_cache(self) -> None:
        """Clear the delegation status cache."""
        self._status_cache.clear()


# Singleton instance for handler use
_validator: DelegationValidator | None = None


def get_delegation_validator() -> DelegationValidator:
    """Get the configured delegation validator."""
    global _validator
    if _validator is None:
        _validator = DelegationValidator()
    return _validator


def configure_delegation_validator(
    control_plane_url: str | None = None,
    check_revocation: bool = False,
) -> DelegationValidator:
    """Configure and return the delegation validator."""
    global _validator
    _validator = DelegationValidator(
        control_plane_url=control_plane_url,
        check_revocation=check_revocation,
    )
    return _validator
```

### 2. Integration with tools_call Handler

Modify `tools_call.py` to use `DelegationValidator`:

```python
from app.middleware.delegation_validator import (
    DelegationValidator,
    get_delegation_validator,
    ValidationResult,
)
from app.middleware.jwt_validation import AgentContext

async def handle_tools_call(params: dict[str, Any]) -> dict[str, Any]:
    """Handle MCP tools/call with delegation validation."""
    
    # ... existing param parsing ...
    
    # Get agent context from request state (set by C3)
    agent_context = context.get("_agent_context")
    
    # Validate delegation using C6 validator
    validator = get_delegation_validator()
    validation_result = await validator.validate_tool_call(
        tool_name=tool_name,
        agent_context=agent_context,
    )
    
    if not validation_result.allowed:
        await _log_audit(
            agent_session, tool_name, arguments,
            success=False,
            error=validation_result.error_message,
            required_permission=validation_result.required_permission,
            backend=backend_id
        )
        raise MCPError(
            ToolsCallErrorCode.PERMISSION_DENIED,
            validation_result.error_message
        )
    
    # ... continue with backend forwarding ...
```

### 3. Key Behaviors

| Scenario | Behavior |
|----------|----------|
| No agent context | Deny with `NO_CONTEXT` |
| Unknown tool | Deny with `UNKNOWN_TOOL` |
| Permission not in delegation | Deny with `PERMISSION_NOT_DELEGATED` |
| Backend wildcard (notion:*) | Allow any notion permission |
| Delegation revoked | Deny with `DELEGATION_REVOKED` (if revocation check enabled) |
| Validation error | Deny with `VALIDATION_ERROR` (fail-closed) |

---

## Acceptance Criteria

### Protocol Criteria
- [ ] `tools/call` validates permission before execution
- [ ] Returns proper MCP error code (-32001) for permission denied
- [ ] Error message includes the required permission string

### Security Criteria
- [ ] **Fail-closed**: Unknown tools are denied
- [ ] **Defense in depth**: Validates even if tools/list filtered
- [ ] All permission denials logged for audit
- [ ] Supports wildcard permissions (notion:*, *:*)

### Integration Criteria
- [ ] Uses `AgentContext` from C3 (jwt_validation.py)
- [ ] Uses `PermissionMapper` from C4
- [ ] Integrates with B7 tools/call handler
- [ ] Unblocks C7 (credential injection)

### Demo 4 Metric
- [ ] Can demonstrate permission enforcement: agent with limited delegation gets denied for non-delegated tools

---

## Test Cases

### Unit Tests (`test_delegation_validator.py`)

```python
import pytest
from app.middleware.delegation_validator import (
    DelegationValidator,
    ValidationResult,
    DenialReason,
)
from app.middleware.jwt_validation import AgentContext


class TestDelegationValidator:
    """Tests for C6: Delegation Validator"""
    
    @pytest.fixture
    def validator(self):
        return DelegationValidator(check_revocation=False)
    
    @pytest.fixture
    def agent_with_limited_perms(self):
        return AgentContext(
            agent_id="agent-123",
            owner="sarah@example.com",
            delegation_id="del-456",
            session_id="sess-789",
            delegated_permissions=[
                "notion:pages:search",
                "slack:messages:send",
            ],
        )
    
    @pytest.fixture
    def agent_with_wildcard(self):
        return AgentContext(
            agent_id="agent-admin",
            owner="admin@example.com",
            delegation_id="del-admin",
            session_id="sess-admin",
            delegated_permissions=["notion:*"],
        )
    
    @pytest.mark.asyncio
    async def test_allows_delegated_tool(
        self, validator, agent_with_limited_perms
    ):
        """C6: Should allow tool with delegated permission"""
        result = await validator.validate_tool_call(
            tool_name="notion.search_pages",
            agent_context=agent_with_limited_perms,
        )
        
        assert result.allowed is True
        assert result.required_permission == "notion:pages:search"
    
    @pytest.mark.asyncio
    async def test_denies_non_delegated_tool(
        self, validator, agent_with_limited_perms
    ):
        """C6 Demo 4: Should deny tool without delegation"""
        result = await validator.validate_tool_call(
            tool_name="notion.create_page",
            agent_context=agent_with_limited_perms,
        )
        
        assert result.allowed is False
        assert result.denial_reason == DenialReason.PERMISSION_NOT_DELEGATED
        assert result.required_permission == "notion:pages:create"
        assert "not delegated" in result.error_message
    
    @pytest.mark.asyncio
    async def test_denies_without_context(self, validator):
        """C6 Fail-closed: Should deny when no agent context"""
        result = await validator.validate_tool_call(
            tool_name="notion.search_pages",
            agent_context=None,
        )
        
        assert result.allowed is False
        assert result.denial_reason == DenialReason.NO_CONTEXT
    
    @pytest.mark.asyncio
    async def test_denies_unknown_tool(
        self, validator, agent_with_limited_perms
    ):
        """C6 Fail-closed: Should deny unknown tools"""
        result = await validator.validate_tool_call(
            tool_name="unknown.mystery_tool",
            agent_context=agent_with_limited_perms,
        )
        
        assert result.allowed is False
        assert result.denial_reason == DenialReason.UNKNOWN_TOOL
    
    @pytest.mark.asyncio
    async def test_allows_backend_wildcard(
        self, validator, agent_with_wildcard
    ):
        """C6: Backend wildcard should allow any tool in backend"""
        # notion:* should allow notion:pages:create
        result = await validator.validate_tool_call(
            tool_name="notion.create_page",
            agent_context=agent_with_wildcard,
        )
        
        assert result.allowed is True
    
    @pytest.mark.asyncio
    async def test_wildcard_does_not_cross_backends(
        self, validator, agent_with_wildcard
    ):
        """C6: Backend wildcard should not allow other backends"""
        # notion:* should NOT allow slack:messages:send
        result = await validator.validate_tool_call(
            tool_name="slack.send_message",
            agent_context=agent_with_wildcard,
        )
        
        assert result.allowed is False
        assert result.denial_reason == DenialReason.PERMISSION_NOT_DELEGATED


class TestDelegationValidatorRevocationCheck:
    """Tests for delegation revocation checking (production feature)"""
    
    @pytest.fixture
    def validator_with_revocation(self):
        return DelegationValidator(
            control_plane_url="http://localhost:8000",
            check_revocation=True,
        )
    
    @pytest.mark.asyncio
    async def test_denies_revoked_delegation(
        self, validator_with_revocation, httpx_mock
    ):
        """C6: Should deny if delegation is revoked"""
        # Mock Control Plane response
        httpx_mock.add_response(
            url="http://localhost:8000/api/v1/delegations/del-revoked/status",
            json={"status": "revoked"},
        )
        
        agent = AgentContext(
            agent_id="agent-123",
            owner="sarah@example.com",
            delegation_id="del-revoked",
            session_id="sess-789",
            delegated_permissions=["notion:pages:search"],
        )
        
        result = await validator_with_revocation.validate_tool_call(
            tool_name="notion.search_pages",
            agent_context=agent,
        )
        
        assert result.allowed is False
        assert result.denial_reason == DenialReason.DELEGATION_REVOKED
```

### Integration Tests

```python
@pytest.mark.integration
async def test_tools_call_denied_for_non_delegated(
    gateway_client, agent_jwt_limited_perms
):
    """C6 Demo 4: tools/call should deny non-delegated tool"""
    response = await gateway_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "notion.create_page",  # Not in delegation
                "arguments": {"title": "Test"}
            }
        },
        headers={"Authorization": f"Bearer {agent_jwt_limited_perms}"},
    )
    
    assert response.status_code == 200
    result = response.json()
    assert "error" in result
    assert result["error"]["code"] == -32001  # Permission denied
    assert "notion:pages:create" in result["error"]["message"]


@pytest.mark.integration
async def test_tools_call_allowed_for_delegated(
    gateway_client, agent_jwt_limited_perms
):
    """C6 Step 8: tools/call should allow delegated tool"""
    response = await gateway_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "notion.search_pages",  # In delegation
                "arguments": {"query": "test"}
            }
        },
        headers={"Authorization": f"Bearer {agent_jwt_limited_perms}"},
    )
    
    assert response.status_code == 200
    result = response.json()
    assert "result" in result  # Success
    assert "content" in result["result"]
```

---

## Post-Conditions

After completing this task:

1. `tools/call` validates permissions using `DelegationValidator`
2. Permission denials include the required permission string
3. All denials are logged for audit
4. C7 (credential injection) can proceed knowing permission is valid

---

## Unblocks

| Task | Name | Notes |
|------|------|-------|
| **C7** | Credential Injection | Depends on C6 for permission validation |
| **E5** | Constraint Checker | Can build on C6's constraint validation hooks |
| **F5** | Demo 4: Permission Enforcement | Requires C6 to demonstrate enforcement |

---

## References

- **Design Doc**: Section "Step 8: Agent executes a delegated tool" and "Step 9: Permission denied"
- **C3 Implementation**: `deeptrail-gateway/app/middleware/jwt_validation.py`
- **C4 Implementation**: `deeptrail-gateway/app/mcp/permission_mapper.py`
- **B7 Handler**: `deeptrail-gateway/app/mcp/handlers/tools_call.py`
- **A6 Service**: `deeptrail-control/app/services/delegation_service.py`

---

## Notes

- MVP: Revocation checking is disabled by default (no Control Plane calls)
- Production: Enable `check_revocation=True` and configure `control_plane_url`
- The validator caches delegation status to reduce Control Plane calls
- Wildcard permissions are useful for admin/testing but should be used sparingly
