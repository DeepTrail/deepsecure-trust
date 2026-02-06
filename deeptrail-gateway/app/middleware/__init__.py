# Middleware package for DeepTrail Gateway

"""
Middleware components for the DeepTrail Gateway.

This package provides middleware for:
- JWT validation (C3) - Validates Agent Session JWTs
- Permission filtering (C5) - Filters tools by delegated permissions
- Delegation validation (C6) - Validates tool calls against delegations
- Credential injection (C7) - Injects OAuth tokens into backend requests
- Policy enforcement - Enforces access policies
- Security - Request sanitization and security filters
- Logging - Request/response logging
"""

from .jwt_validation import (
    AgentContext,
    JWTValidationError,
    JWTValidationMiddleware,
    get_agent_context,
    require_permission,
    require_any_permission,
)
from .permission_filter import (
    PermissionFilter,
    filter_tools_for_agent,
    get_permitted_backends_for_agent,
)
from .delegation_validator import (
    DelegationValidator,
    DenialReason,
    ValidationResult,
    get_delegation_validator,
    configure_delegation_validator,
    validate_tool_call,
    is_tool_permitted,
)
from .credential_injection import (
    CredentialInjector,
    InjectionError,
    InjectionResult,
    get_credential_injector,
    configure_credential_injector,
    inject_credentials,
)
from .audit import (
    AuditMiddleware,
    AuditEvent,
    AuditEventType,
    get_audit_middleware,
    configure_audit_middleware,
    reset_audit_middleware,
    log_tool_call,
    log_permission_denied,
)

__all__ = [
    # JWT Validation (C3)
    "AgentContext",
    "JWTValidationError",
    "JWTValidationMiddleware",
    "get_agent_context",
    "require_permission",
    "require_any_permission",
    # Permission Filter (C5)
    "PermissionFilter",
    "filter_tools_for_agent",
    "get_permitted_backends_for_agent",
    # Delegation Validator (C6)
    "DelegationValidator",
    "DenialReason",
    "ValidationResult",
    "get_delegation_validator",
    "configure_delegation_validator",
    "validate_tool_call",
    "is_tool_permitted",
    # Credential Injection (C7)
    "CredentialInjector",
    "InjectionError",
    "InjectionResult",
    "get_credential_injector",
    "configure_credential_injector",
    "inject_credentials",
    # Audit Middleware (E3)
    "AuditMiddleware",
    "AuditEvent",
    "AuditEventType",
    "get_audit_middleware",
    "configure_audit_middleware",
    "reset_audit_middleware",
    "log_tool_call",
    "log_permission_denied",
]