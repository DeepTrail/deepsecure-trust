# Task: WS-C3 Implement JWT Validation Middleware

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `completed` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-C: Auth & Permissions |
| **Dependencies** | C2 (Agent Verify Endpoint) ✅ |
| **Blocked By** | None (C2 complete) |
| **Assigned** | - |
| **Created** | February 4, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 5 |
| **Target Worktree** | `vmcp-gateway` |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 4: Permission Enforcement, Demo 6: Fail-Closed |
| **Validates User Journey Step** | Step 6: Agent Connects to Virtual MCP |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] C2 (Agent Verify Endpoint) is complete
- [x] C1 (Agent Challenge Endpoint) is complete  
- [x] A8 (AgentSessionService) is complete - issues the JWT
- [x] Existing `jwt_validation.py` middleware exists in gateway
- [x] Understand the Layer 3 JWT format from C2

---

## Task Description

Enhance the existing JWT validation middleware to validate **Agent Session JWTs (Layer 3)** issued by the Control Plane. This enables Step 6 of Sarah's journey: Agent Connects to Virtual MCP.

### Context

From the MVP design (Section 2.6 - Step 6: Agent Connects to Virtual MCP):

```
Agent connects to Gateway with Layer 3 JWT:

Authorization: Bearer <agent-session-jwt>

The Gateway middleware must validate:
1. JWT signature (HS256 with shared secret for MVP)
2. JWT issuer (iss: deeptrail-control)
3. JWT audience (aud: deeptrail-gateway)
4. JWT expiration (exp)
5. Required claims presence

LAYER 3: AGENT SESSION JWT (from C2)
{
  "sub": "agent-sdr-001",              // Agent ID
  "owner": "sarah@acme.com",           // Delegator
  "idp_issuer": "https://acme.okta.com",
  "party_type": "first_party",
  "delegated_permissions": [           // Scoped permissions
    "notion:pages:search",
    "notion:pages:read",
    "slack:messages:search",
    "slack:channels:list"
  ],
  "delegation_id": "del-sarah-sdr-001",
  "groups": ["sales"],
  "session_id": "asess-sdr-001-ghi789",
  "iss": "deeptrail-control",
  "aud": "deeptrail-gateway",
  "iat": 1737900000,
  "exp": 1737936000                    // 8 hours
}

RESULT: Request state enriched with agent context for downstream middleware
```

### Current State

The gateway already has `jwt_validation.py` middleware that:
- Validates JWT signature with shared secret
- Validates `exp`, `iat`, `nbf` claims
- Extracts `agent_id` and `scope` claims

### Changes Required

Enhance the middleware to:
1. **Validate new claims format**: `sub`, `owner`, `delegated_permissions`, `delegation_id`, `session_id`
2. **Validate issuer/audience**: `iss` = `deeptrail-control`, `aud` = `deeptrail-gateway`
3. **Support MCP endpoints**: Apply to `/mcp/*` endpoints (not just `/proxy/*`)
4. **Enrich request state**: Store all claims for downstream middleware (C5, C6, C7)
5. **Backward compatibility**: Support both old format (if needed) and new format

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/middleware/jwt_validation.py` | **MODIFY** | Enhance for Agent Session JWT |
| `deeptrail-gateway/tests/middleware/test_jwt_validation.py` | **CREATE** | Add comprehensive tests |

---

## Implementation Details

### 1. Enhanced JWT Validation Middleware

Update `deeptrail-gateway/app/middleware/jwt_validation.py`:

```python
"""
JWT Validation Middleware for DeepTrail Gateway

Validates Agent Session JWTs (Layer 3) issued by the Control Plane.
This is Step 6 of Sarah's journey: Agent Connects to Virtual MCP.

Key Features:
- Validates JWT signature (HS256 with shared secret - MVP)
- Validates issuer (deeptrail-control) and audience (deeptrail-gateway)
- Extracts delegated_permissions for downstream permission filtering
- Stores validated claims in request.state for middleware chain
- Fail-closed: denies access if validation fails

JWT Claims (Layer 3):
- sub: Agent ID
- owner: Delegator email
- delegated_permissions: Array of permission strings
- delegation_id: Reference to active delegation
- session_id: Unique session identifier
- iss: deeptrail-control
- aud: deeptrail-gateway
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from dataclasses import dataclass

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import JSONResponse
from jose import jwt, JWTError

from ..core.proxy_config import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AgentContext:
    """
    Validated agent context extracted from JWT.
    
    Stored in request.state.agent_context for downstream middleware.
    """
    agent_id: str
    owner: str
    delegation_id: str
    session_id: str
    delegated_permissions: List[str]
    groups: List[str]
    party_type: str
    idp_issuer: Optional[str] = None
    
    @classmethod
    def from_jwt_payload(cls, payload: Dict[str, Any]) -> "AgentContext":
        """Create AgentContext from validated JWT payload."""
        return cls(
            agent_id=payload.get("sub", ""),
            owner=payload.get("owner", ""),
            delegation_id=payload.get("delegation_id", ""),
            session_id=payload.get("session_id", ""),
            delegated_permissions=payload.get("delegated_permissions", []),
            groups=payload.get("groups", []),
            party_type=payload.get("party_type", "first_party"),
            idp_issuer=payload.get("idp_issuer"),
        )
    
    def has_permission(self, permission: str) -> bool:
        """Check if agent has a specific permission."""
        return permission in self.delegated_permissions


class JWTValidationError(Exception):
    """Custom exception for JWT validation errors."""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str = "jwt_invalid",
        headers: Optional[Dict[str, str]] = None
    ):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        self.headers = headers or {}
        super().__init__(detail)


# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────────────────


class JWTValidationMiddleware(BaseHTTPMiddleware):
    """
    JWT validation middleware for Agent Session JWTs (Layer 3).
    
    This middleware validates JWTs issued by the Control Plane and enriches
    the request state with agent context for downstream middleware.
    
    Security Features:
    - Signature verification with shared secret (HS256 - MVP)
    - Issuer and audience validation
    - Expiration and timing validation
    - Required claims validation
    - Fail-closed: denies access on any validation failure
    """
    
    # Expected JWT issuer (Control Plane)
    EXPECTED_ISSUER = "deeptrail-control"
    
    # Expected JWT audience (this Gateway)
    EXPECTED_AUDIENCE = "deeptrail-gateway"
    
    # Required claims in Agent Session JWT
    REQUIRED_CLAIMS = ["sub", "owner", "delegated_permissions", "delegation_id", "session_id"]
    
    def __init__(
        self,
        app: ASGIApp,
        control_plane_url: str = "http://deeptrail-control:8000",
    ):
        super().__init__(app)
        self.control_plane_url = control_plane_url
        
        # Paths that bypass JWT validation
        self.bypass_paths = {
            "/",
            "/health",
            "/ready",
            "/metrics",
            "/config",
            "/docs",
            "/redoc",
            "/openapi.json",
        }
        
        # Paths that require JWT validation
        # MCP endpoints + proxy endpoints
        self.protected_path_prefixes = ["/mcp", "/proxy", "/api/v1/tools"]
        
        # JWT configuration from proxy config
        self.jwt_secret_key = config.security.jwt_secret_key
        self.jwt_algorithm = config.security.jwt_algorithm
        
        logger.info("JWT validation middleware initialized")
        logger.info(f"Control plane URL: {control_plane_url}")
        logger.info(f"JWT algorithm: {self.jwt_algorithm}")
        logger.info(f"Expected issuer: {self.EXPECTED_ISSUER}")
        logger.info(f"Expected audience: {self.EXPECTED_AUDIENCE}")
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and validate JWT if required.
        
        Flow:
        1. Check if path requires authentication
        2. Extract and validate JWT token
        3. Enrich request.state with agent context
        4. Continue to next middleware/handler
        """
        # Skip JWT validation for bypass paths
        if request.url.path in self.bypass_paths:
            return await call_next(request)
        
        # Check if path requires JWT validation
        requires_auth = any(
            request.url.path.startswith(prefix)
            for prefix in self.protected_path_prefixes
        )
        
        if not requires_auth:
            return await call_next(request)
        
        # Extract JWT token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning(f"Missing Authorization header for {request.url.path}")
            return self._unauthorized_response(
                detail="Missing Authorization header",
                error_code="missing_authorization",
            )
        
        # Parse Bearer token
        try:
            scheme, token = auth_header.split(" ", 1)
            if scheme.lower() != "bearer":
                raise ValueError("Invalid scheme")
        except ValueError:
            logger.warning(f"Invalid Authorization header format for {request.url.path}")
            return self._unauthorized_response(
                detail="Invalid Authorization header format. Expected: Bearer <token>",
                error_code="invalid_header_format",
            )
        
        # Validate JWT token
        try:
            jwt_payload = await self._validate_jwt_token(token)
            
            # Create agent context from validated payload
            agent_context = AgentContext.from_jwt_payload(jwt_payload)
            
            # Store in request state for downstream middleware
            request.state.agent_context = agent_context
            request.state.jwt_payload = jwt_payload
            
            # Legacy compatibility: also set individual fields
            request.state.agent_id = agent_context.agent_id
            request.state.agent_permissions = agent_context.delegated_permissions
            request.state.delegation_id = agent_context.delegation_id
            request.state.session_id = agent_context.session_id
            
            logger.info(
                f"JWT validated for agent {agent_context.agent_id}, "
                f"session {agent_context.session_id}, "
                f"permissions: {len(agent_context.delegated_permissions)}"
            )
            
        except JWTValidationError as e:
            logger.warning(f"JWT validation failed: {e.detail}")
            return self._error_response(e)
            
        except Exception as e:
            logger.error(f"Unexpected JWT validation error: {e}")
            return self._unauthorized_response(
                detail="JWT validation failed",
                error_code="validation_error",
            )
        
        # Continue with request processing
        return await call_next(request)
    
    async def _validate_jwt_token(self, token: str) -> Dict[str, Any]:
        """
        Validate Agent Session JWT (Layer 3).
        
        Validates:
        1. Signature (HS256 with shared secret)
        2. Issuer (iss = deeptrail-control)
        3. Audience (aud = deeptrail-gateway)
        4. Expiration (exp)
        5. Required claims (sub, owner, delegated_permissions, etc.)
        
        Returns:
            Validated JWT payload
            
        Raises:
            JWTValidationError: If validation fails
        """
        try:
            # Decode and validate JWT token with signature verification
            # Note: jose library validates exp automatically
            payload = jwt.decode(
                token,
                self.jwt_secret_key,
                algorithms=[self.jwt_algorithm],
                audience=self.EXPECTED_AUDIENCE,
                issuer=self.EXPECTED_ISSUER,
            )
            
            # Validate required claims
            self._validate_required_claims(payload)
            
            # Validate timing claims
            self._validate_timing_claims(payload)
            
            # Validate permissions format
            self._validate_permissions(payload)
            
            logger.debug(
                f"JWT validated successfully for agent {payload.get('sub')}"
            )
            return payload
            
        except jwt.ExpiredSignatureError:
            raise JWTValidationError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT token has expired",
                error_code="token_expired",
            )
            
        except jwt.JWTClaimsError as e:
            error_msg = str(e).lower()
            if "audience" in error_msg:
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid JWT audience",
                    error_code="invalid_audience",
                )
            elif "issuer" in error_msg:
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid JWT issuer",
                    error_code="invalid_issuer",
                )
            else:
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"JWT claims validation failed: {e}",
                    error_code="claims_invalid",
                )
                
        except JWTError as e:
            error_msg = str(e).lower()
            if "signature" in error_msg:
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid JWT signature",
                    error_code="invalid_signature",
                )
            else:
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="JWT validation failed",
                    error_code="validation_failed",
                )
                
        except JWTValidationError:
            raise
            
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            raise JWTValidationError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid JWT token format",
                error_code="invalid_format",
            )
    
    def _validate_required_claims(self, payload: Dict[str, Any]) -> None:
        """Validate that all required claims are present."""
        missing_claims = [
            claim for claim in self.REQUIRED_CLAIMS
            if claim not in payload or payload[claim] is None
        ]
        
        if missing_claims:
            raise JWTValidationError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"JWT missing required claims: {', '.join(missing_claims)}",
                error_code="missing_claims",
            )
    
    def _validate_timing_claims(self, payload: Dict[str, Any]) -> None:
        """Validate timing claims (iat, nbf, exp)."""
        current_time = datetime.now(timezone.utc).timestamp()
        
        # Check issued at (iat) - should not be in the future
        if "iat" in payload:
            # Allow small clock skew (60 seconds)
            if payload["iat"] > current_time + 60:
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="JWT issued in the future",
                    error_code="invalid_iat",
                )
        
        # Check not before (nbf)
        if "nbf" in payload:
            if payload["nbf"] > current_time:
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="JWT not yet valid",
                    error_code="token_not_yet_valid",
                )
    
    def _validate_permissions(self, payload: Dict[str, Any]) -> None:
        """Validate permissions format."""
        permissions = payload.get("delegated_permissions", [])
        
        if not isinstance(permissions, list):
            raise JWTValidationError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="delegated_permissions must be a list",
                error_code="invalid_permissions_format",
            )
        
        # Validate permission string format (namespace:resource:action)
        for perm in permissions:
            if not isinstance(perm, str):
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Each permission must be a string",
                    error_code="invalid_permission_type",
                )
            
            # Basic format validation: should contain at least one colon
            if ":" not in perm:
                logger.warning(f"Permission '{perm}' doesn't follow namespace:resource:action format")
                # Don't fail - just warn for MVP
    
    def _unauthorized_response(
        self,
        detail: str,
        error_code: str = "unauthorized",
    ) -> JSONResponse:
        """Create a 401 Unauthorized response."""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": error_code,
                "detail": detail,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    def _error_response(self, error: JWTValidationError) -> JSONResponse:
        """Create an error response from JWTValidationError."""
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": error.error_code,
                "detail": error.detail,
            },
            headers=error.headers if error.headers else {"WWW-Authenticate": "Bearer"},
        )


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Dependency (Alternative to Middleware)
# ─────────────────────────────────────────────────────────────────────────────


async def get_agent_context(request: Request) -> AgentContext:
    """
    FastAPI dependency to get validated agent context.
    
    Usage in endpoints:
        @router.get("/tools")
        async def list_tools(agent: AgentContext = Depends(get_agent_context)):
            if agent.has_permission("notion:pages:search"):
                ...
    
    Raises:
        HTTPException: If agent context not available (JWT not validated)
    """
    from fastapi import HTTPException
    
    if not hasattr(request.state, "agent_context"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authenticated agent context",
        )
    
    return request.state.agent_context


def require_permission(permission: str):
    """
    FastAPI dependency factory to require a specific permission.
    
    Usage:
        @router.post("/tools/call")
        async def call_tool(
            tool_name: str,
            agent: AgentContext = Depends(require_permission("notion:pages:read"))
        ):
            ...
    """
    async def _check_permission(request: Request) -> AgentContext:
        from fastapi import HTTPException
        
        agent = await get_agent_context(request)
        
        if not agent.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
        
        return agent
    
    return _check_permission
```

### 2. Register Middleware in Main App

Ensure the middleware is registered in `deeptrail-gateway/app/main.py`:

```python
from app.middleware.jwt_validation import JWTValidationMiddleware

# Add middleware (order matters - JWT validation should be early)
app.add_middleware(
    JWTValidationMiddleware,
    control_plane_url=settings.CONTROL_PLANE_URL,
)
```

---

## Acceptance Criteria

### JWT Validation Criteria

- [x] Validates JWT signature with shared secret (HS256)
- [x] Validates `iss` claim equals `deeptrail-control`
- [x] Validates `aud` claim equals `deeptrail-gateway`
- [x] Validates `exp` claim (rejects expired tokens)
- [x] Validates required claims: `sub`, `owner`, `delegated_permissions`, `delegation_id`, `session_id`
- [x] Returns 401 with `token_expired` for expired tokens
- [x] Returns 401 with `invalid_signature` for bad signatures
- [x] Returns 401 with `invalid_issuer` for wrong issuer
- [x] Returns 401 with `invalid_audience` for wrong audience
- [x] Returns 401 with `missing_claims` for incomplete tokens

### Request State Criteria

- [x] Stores `AgentContext` in `request.state.agent_context`
- [x] `AgentContext.agent_id` populated from `sub` claim
- [x] `AgentContext.owner` populated from `owner` claim
- [x] `AgentContext.delegated_permissions` populated as list
- [x] `AgentContext.delegation_id` populated
- [x] `AgentContext.session_id` populated
- [x] Legacy compatibility: `request.state.agent_id` also set

### Path Protection Criteria

- [x] Protects `/mcp/*` endpoints
- [x] Protects `/proxy/*` endpoints
- [x] Bypasses `/health`, `/ready`, `/metrics`, `/docs`
- [x] Bypasses `/openapi.json`

### Security Criteria

- [x] Fail-closed: denies access on any validation failure
- [x] No token information leaked in error messages
- [x] Logs validation failures at WARNING level
- [x] Logs successful validations at INFO level

### Test Criteria

- [x] Test successful validation with valid Agent Session JWT
- [x] Test 401 for expired token
- [x] Test 401 for invalid signature
- [x] Test 401 for wrong issuer
- [x] Test 401 for wrong audience
- [x] Test 401 for missing required claims
- [x] Test bypass paths don't require auth
- [x] Test AgentContext populated correctly
- [x] All tests pass with `pytest tests/middleware/test_jwt_validation.py`

---

## Test Cases

Create `deeptrail-gateway/tests/middleware/test_jwt_validation.py`:

```python
"""Tests for JWT validation middleware (C3)."""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.jwt_validation import (
    JWTValidationMiddleware,
    AgentContext,
    JWTValidationError,
)


# Test configuration
TEST_SECRET = "test-secret-key-for-jwt-validation"
TEST_ALGORITHM = "HS256"


@pytest.fixture
def valid_jwt_payload():
    """Create a valid Agent Session JWT payload."""
    return {
        "sub": "agent-sdr-001",
        "owner": "sarah@acme.com",
        "idp_issuer": "https://acme.okta.com",
        "party_type": "first_party",
        "delegated_permissions": [
            "notion:pages:search",
            "notion:pages:read",
            "slack:messages:search",
        ],
        "delegation_id": "del-sarah-sdr-001",
        "groups": ["sales"],
        "session_id": "asess-sdr-001-abc123",
        "iss": "deeptrail-control",
        "aud": "deeptrail-gateway",
        "iat": datetime.now(timezone.utc).timestamp(),
        "exp": (datetime.now(timezone.utc) + timedelta(hours=8)).timestamp(),
    }


@pytest.fixture
def valid_token(valid_jwt_payload):
    """Create a valid JWT token."""
    return jwt.encode(valid_jwt_payload, TEST_SECRET, algorithm=TEST_ALGORITHM)


@pytest.fixture
def app_with_middleware():
    """Create FastAPI app with JWT middleware."""
    app = FastAPI()
    
    # Mock the config
    with patch("app.middleware.jwt_validation.config") as mock_config:
        mock_config.security.jwt_secret_key = TEST_SECRET
        mock_config.security.jwt_algorithm = TEST_ALGORITHM
        
        app.add_middleware(JWTValidationMiddleware)
    
    @app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    @app.get("/mcp/tools")
    async def list_tools(request):
        return {
            "agent_id": request.state.agent_id,
            "permissions": request.state.agent_permissions,
        }
    
    return app


@pytest.fixture
def client(app_with_middleware):
    """Create test client."""
    return TestClient(app_with_middleware)


class TestJWTValidation:
    """Tests for JWT validation."""
    
    def test_valid_token_accepted(self, client, valid_token):
        """Test that valid tokens are accepted."""
        response = client.get(
            "/mcp/tools",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent-sdr-001"
        assert "notion:pages:search" in data["permissions"]
    
    def test_missing_authorization_header(self, client):
        """Test 401 for missing Authorization header."""
        response = client.get("/mcp/tools")
        
        assert response.status_code == 401
        assert response.json()["error"] == "missing_authorization"
    
    def test_invalid_authorization_format(self, client):
        """Test 401 for invalid Authorization format."""
        response = client.get(
            "/mcp/tools",
            headers={"Authorization": "InvalidFormat"}
        )
        
        assert response.status_code == 401
        assert response.json()["error"] == "invalid_header_format"
    
    def test_expired_token(self, client, valid_jwt_payload):
        """Test 401 for expired token."""
        # Create expired token
        valid_jwt_payload["exp"] = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).timestamp()
        expired_token = jwt.encode(
            valid_jwt_payload, TEST_SECRET, algorithm=TEST_ALGORITHM
        )
        
        response = client.get(
            "/mcp/tools",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == 401
        assert response.json()["error"] == "token_expired"
    
    def test_invalid_signature(self, client, valid_jwt_payload):
        """Test 401 for invalid signature."""
        # Create token with wrong secret
        bad_token = jwt.encode(
            valid_jwt_payload, "wrong-secret", algorithm=TEST_ALGORITHM
        )
        
        response = client.get(
            "/mcp/tools",
            headers={"Authorization": f"Bearer {bad_token}"}
        )
        
        assert response.status_code == 401
        assert response.json()["error"] == "invalid_signature"
    
    def test_wrong_issuer(self, client, valid_jwt_payload):
        """Test 401 for wrong issuer."""
        valid_jwt_payload["iss"] = "wrong-issuer"
        bad_token = jwt.encode(
            valid_jwt_payload, TEST_SECRET, algorithm=TEST_ALGORITHM
        )
        
        response = client.get(
            "/mcp/tools",
            headers={"Authorization": f"Bearer {bad_token}"}
        )
        
        assert response.status_code == 401
        assert response.json()["error"] == "invalid_issuer"
    
    def test_wrong_audience(self, client, valid_jwt_payload):
        """Test 401 for wrong audience."""
        valid_jwt_payload["aud"] = "wrong-audience"
        bad_token = jwt.encode(
            valid_jwt_payload, TEST_SECRET, algorithm=TEST_ALGORITHM
        )
        
        response = client.get(
            "/mcp/tools",
            headers={"Authorization": f"Bearer {bad_token}"}
        )
        
        assert response.status_code == 401
        assert response.json()["error"] == "invalid_audience"
    
    def test_missing_required_claims(self, client, valid_jwt_payload):
        """Test 401 for missing required claims."""
        # Remove required claim
        del valid_jwt_payload["delegation_id"]
        incomplete_token = jwt.encode(
            valid_jwt_payload, TEST_SECRET, algorithm=TEST_ALGORITHM
        )
        
        response = client.get(
            "/mcp/tools",
            headers={"Authorization": f"Bearer {incomplete_token}"}
        )
        
        assert response.status_code == 401
        assert response.json()["error"] == "missing_claims"
    
    def test_bypass_paths_no_auth(self, client):
        """Test that bypass paths don't require auth."""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestAgentContext:
    """Tests for AgentContext dataclass."""
    
    def test_from_jwt_payload(self, valid_jwt_payload):
        """Test creating AgentContext from JWT payload."""
        context = AgentContext.from_jwt_payload(valid_jwt_payload)
        
        assert context.agent_id == "agent-sdr-001"
        assert context.owner == "sarah@acme.com"
        assert context.delegation_id == "del-sarah-sdr-001"
        assert context.session_id == "asess-sdr-001-abc123"
        assert len(context.delegated_permissions) == 3
        assert context.groups == ["sales"]
        assert context.party_type == "first_party"
    
    def test_has_permission(self, valid_jwt_payload):
        """Test permission checking."""
        context = AgentContext.from_jwt_payload(valid_jwt_payload)
        
        assert context.has_permission("notion:pages:search") is True
        assert context.has_permission("notion:pages:read") is True
        assert context.has_permission("notion:pages:delete") is False
    
    def test_empty_permissions(self):
        """Test context with empty permissions."""
        payload = {
            "sub": "agent-001",
            "owner": "user@example.com",
            "delegation_id": "del-001",
            "session_id": "sess-001",
            "delegated_permissions": [],
        }
        
        context = AgentContext.from_jwt_payload(payload)
        
        assert context.delegated_permissions == []
        assert context.has_permission("any:permission") is False
```

---

## Post-Conditions

After completing this task:

- [x] Gateway validates Agent Session JWTs from Control Plane
- [x] Protected endpoints require valid JWT
- [x] Request state contains agent context for downstream middleware
- [x] C5 (Permission Filter) can access `agent_context.delegated_permissions`
- [x] C6 (Delegation Validator) can access `agent_context.delegation_id`
- [x] All unit tests pass

---

## Files Modified

| File | Lines | Description |
|------|-------|-------------|
| `deeptrail-gateway/app/middleware/jwt_validation.py` | 505 | Enhanced with AgentContext, Layer 3 validation, dependencies |

## Files Created

| File | Lines | Description |
|------|-------|-------------|
| `deeptrail-gateway/tests/middleware/__init__.py` | 1 | Test package init |
| `deeptrail-gateway/tests/middleware/test_jwt_validation.py` | 760 | 40 comprehensive unit tests |

---

## Execution Log

**Date**: 2026-01-30
**Duration**: ~20 minutes
**Tests Added**: 40 new tests
**Total MCP + Backends + Middleware Tests**: 571 (all passing)
**Lint Status**: All checks passed

---

## References

- **Design Doc Section**: 2.6 Step 6: Agent Connects to Virtual MCP
- **Token Architecture**: Section 4.1 (Three-Layer Token Model - Layer 3)
- **Upstream Tasks**:
  - [WS-C2: Agent Verify Endpoint](./WS-C2-agent-verify-endpoint.md) - Issues the JWT
- **Downstream Tasks**:
  - [WS-C5: Permission Filter](./WS-C5-permission-filter.md) - Uses permissions from JWT
  - [WS-C6: Delegation Validator](./WS-C6-delegation-validator.md) - Uses delegation_id
  - [WS-C7: Credential Injection](./WS-C7-credential-injection.md) - Uses owner claim
- **Existing Code**:
  - `deeptrail-gateway/app/middleware/jwt_validation.py` - Current implementation to enhance

---

## Notes

- This task enhances existing middleware rather than creating new file
- The `AgentContext` dataclass provides a clean interface for downstream middleware
- `require_permission` dependency enables declarative permission checks in endpoints
- In production, would migrate from HS256 to RS256/ES256 with public key verification
- The middleware is fail-closed: any validation failure results in 401
- Permission format validation is lenient for MVP (warns but doesn't fail)
