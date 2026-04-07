"""
Security components for DeepTrail Gateway.

This package provides:
- Fail-closed security (E4) - Denies requests when Control Plane unavailable
- Circuit breaker pattern - Prevents overwhelming failing services
- Constraint checking (E5) - Enforces delegation constraints (rate limits, quotas)
- Prompt injection detection (J5) - Blocks malicious tool arguments (OWASP LLM01)
- Token exchange (J6) - RFC 8693 Keycloak token exchange for backend OAuth tokens
"""

from .fail_closed import (
    ControlPlaneHealthChecker,
    FailClosedError,
    enforce_fail_closed,
    get_health_checker,
    configure_health_checker,
    reset_health_checker,
)

from .constraint_store import (
    ConstraintStore,
    InMemoryConstraintStore,
    RedisConstraintStore,
    get_constraint_store,
    configure_constraint_store,
    reset_constraint_store,
)

from .constraint_checker import (
    ConstraintChecker,
    ConstraintType,
    ConstraintViolation,
    ConstraintStatus,
    get_constraint_checker,
    configure_constraint_checker,
    reset_constraint_checker,
)

from .token_exchange import (
    TokenExchangeClient,
    TokenExchangeConfig,
    ExchangedToken,
    TokenExchangeError,
    TokenExchangeUnavailableError,
    TokenExchangeDeniedError,
    get_token_exchange_client,
    configure_token_exchange_client,
    reset_token_exchange_client,
)

from .prompt_injection import (
    PromptInjectionDetector,
    PromptInjectionConfig,
    ThreatLevel,
    DetectionCategory,
    DetectionResult,
    ScanResult,
    get_prompt_injection_detector,
    configure_prompt_injection_detector,
    reset_prompt_injection_detector,
)

__all__ = [
    # Fail-closed security (E4)
    "ControlPlaneHealthChecker",
    "FailClosedError",
    "enforce_fail_closed",
    "get_health_checker",
    "configure_health_checker",
    "reset_health_checker",
    # Constraint storage (E5)
    "ConstraintStore",
    "InMemoryConstraintStore",
    "RedisConstraintStore",
    "get_constraint_store",
    "configure_constraint_store",
    "reset_constraint_store",
    # Constraint checking (E5)
    "ConstraintChecker",
    "ConstraintType",
    "ConstraintViolation",
    "ConstraintStatus",
    "get_constraint_checker",
    "configure_constraint_checker",
    "reset_constraint_checker",
    # Prompt injection detection (J5)
    "PromptInjectionDetector",
    "PromptInjectionConfig",
    "ThreatLevel",
    "DetectionCategory",
    "DetectionResult",
    "ScanResult",
    "get_prompt_injection_detector",
    "configure_prompt_injection_detector",
    "reset_prompt_injection_detector",
    # Token exchange (J6)
    "TokenExchangeClient",
    "TokenExchangeConfig",
    "ExchangedToken",
    "TokenExchangeError",
    "TokenExchangeUnavailableError",
    "TokenExchangeDeniedError",
    "get_token_exchange_client",
    "configure_token_exchange_client",
    "reset_token_exchange_client",
]
