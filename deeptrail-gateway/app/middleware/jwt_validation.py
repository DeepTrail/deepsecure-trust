"""
JWT Validation Middleware for DeepTrail Gateway

Validates Bearer tokens from two issuers:
  1. DeepSecure Agent Session JWTs (HS256, Layer 3) — issued by Control Plane
  2. OAuth 2.1 tokens from Keycloak (RS256) — external authorization server

Token routing uses a header-inspection heuristic: RS256/RS384/RS512 tokens
are delegated to the OAuthTokenValidator; HS256 tokens are validated locally.

Key Features:
- Dual-token detection via JWT header algorithm
- Validates JWT signature (HS256 with shared secret - MVP)
- Validates issuer (deeptrail-control) and audience (deeptrail-gateway)
- Extracts delegated_permissions for downstream permission filtering
- Stores validated claims in request.state for middleware chain
- Fail-closed: denies access if validation fails

JWT Claims (Layer 3 — DeepSecure):
- sub: Agent ID
- owner: Delegator email
- delegated_permissions: Array of permission strings
- delegation_id: Reference to active delegation
- session_id: Unique session identifier
- iss: deeptrail-control
- aud: deeptrail-gateway

JWT Claims (OAuth 2.1 — Keycloak):
- sub: User/client ID
- scope: Space-separated scopes (mcp_tools, mcp_resources, etc.)
- iss: Keycloak realm URL
- aud: mcp-gateway
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import Request, status
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from ..core.proxy_config import config

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AgentContext:
    """
    Validated agent context extracted from JWT.

    Stored in request.state.agent_context for downstream middleware.

    Attributes:
        agent_id: Agent identifier from 'sub' claim
        owner: Delegator email from 'owner' claim
        delegation_id: Active delegation reference
        session_id: Unique session identifier
        delegated_permissions: List of permission strings
        groups: Group memberships for ABAC
        party_type: first_party or third_party
        idp_issuer: Original IdP that authenticated the owner
    """

    agent_id: str
    owner: str
    delegation_id: str | None
    session_id: str
    delegated_permissions: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    party_type: str = "first_party"
    idp_issuer: str | None = None
    organization_id: str | None = None
    token_type: str = "agent_session"
    task_id: str | None = None
    scoped_permissions: list[dict] | None = None

    @classmethod
    def from_jwt_payload(cls, payload: dict[str, Any]) -> "AgentContext":
        """Create AgentContext from validated JWT payload.

        Handles both Layer 3 (agent session) and Layer 4 (task token) JWTs.
        """
        token_type = payload.get("token_type", "agent_session")

        if token_type == "task_token":
            scoped = payload.get("scoped_permissions", [])
            perm_urns = [
                p["urn"] for p in scoped if isinstance(p, dict) and "urn" in p
            ]
            return cls(
                agent_id=payload.get("agent_id", ""),
                owner=payload.get("owner", ""),
                delegation_id=None,
                session_id=payload.get("task_id", ""),
                delegated_permissions=perm_urns,
                organization_id=payload.get("organization_id"),
                token_type="task_token",
                task_id=payload.get("task_id"),
                scoped_permissions=scoped,
            )

        return cls(
            agent_id=payload.get("sub", ""),
            owner=payload.get("owner", ""),
            delegation_id=payload.get("delegation_id", ""),
            session_id=payload.get("session_id", ""),
            delegated_permissions=payload.get("delegated_permissions", []),
            groups=payload.get("groups", []),
            party_type=payload.get("party_type", "first_party"),
            idp_issuer=payload.get("idp_issuer"),
            organization_id=payload.get("organization_id"),
        )

    def has_permission(self, permission: str) -> bool:
        """
        Check if agent has a specific permission.

        Args:
            permission: Permission string (e.g., "notion:pages:search")

        Returns:
            True if agent has the permission
        """
        return permission in self.delegated_permissions

    def has_any_permission(self, permissions: list[str]) -> bool:
        """
        Check if agent has any of the specified permissions.

        Args:
            permissions: List of permission strings

        Returns:
            True if agent has at least one of the permissions
        """
        return any(p in self.delegated_permissions for p in permissions)

    def has_all_permissions(self, permissions: list[str]) -> bool:
        """
        Check if agent has all of the specified permissions.

        Args:
            permissions: List of permission strings

        Returns:
            True if agent has all of the permissions
        """
        return all(p in self.delegated_permissions for p in permissions)


# =============================================================================
# Exceptions
# =============================================================================


class JWTValidationError(Exception):
    """Custom exception for JWT validation errors."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str = "jwt_invalid",
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        self.headers = headers or {}
        super().__init__(detail)


# =============================================================================
# Middleware
# =============================================================================


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

    # Required claims in Agent Session JWT (Layer 3)
    REQUIRED_CLAIMS = [
        "sub",
        "owner",
        "delegated_permissions",
        "delegation_id",
        "session_id",
    ]

    # Required claims in Task Token JWT (Layer 4)
    TASK_TOKEN_REQUIRED_CLAIMS = [
        "agent_id",
        "task_id",
        "scoped_permissions",
    ]

    # Legacy JWT fallback removed (MCP Auth Spec Compliance P0-B1/A1).
    # All tokens must now include iss/aud claims.

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

        # Path prefixes that require JWT validation
        # MCP endpoints + proxy endpoints + API tools endpoints
        self.protected_path_prefixes = ["/mcp", "/proxy", "/api/v1/tools"]

        # JWT configuration from proxy config
        self.jwt_secret_key = config.security.jwt_secret_key
        self.jwt_algorithm = config.security.jwt_algorithm
        self.jwt_access_token_expire_minutes = (
            config.security.jwt_access_token_expire_minutes
        )

        logger.info("JWT validation middleware initialized")
        logger.info("Control plane URL: %s", control_plane_url)
        logger.info("JWT algorithm: %s", self.jwt_algorithm)
        logger.info("Expected issuer: %s", self.EXPECTED_ISSUER)
        logger.info("Expected audience: %s", self.EXPECTED_AUDIENCE)
        logger.info("Protected path prefixes: %s", self.protected_path_prefixes)

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

        # MCP spec: DELETE /mcp (session termination) is a no-op for stateless gateway
        if request.url.path == "/mcp" and request.method == "DELETE":
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
            logger.warning("Missing Authorization header for %s", request.url.path)
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
            logger.warning(
                "Invalid Authorization header format for %s", request.url.path
            )
            return self._unauthorized_response(
                detail="Invalid Authorization header format. Expected: Bearer <token>",
                error_code="invalid_header_format",
            )

        # Route token to the correct validator based on algorithm + issuer
        try:
            from .oauth_validation import get_oauth_validator

            token_route = self._classify_token(token)

            if token_route == "oauth":
                oauth_validator = get_oauth_validator()
                if oauth_validator:
                    agent_context = await self._validate_oauth_token(
                        token, oauth_validator
                    )
                    request.state.token_type = "oauth"
                else:
                    jwt_payload = await self._validate_jwt_token(token)
                    agent_context = AgentContext.from_jwt_payload(jwt_payload)
                    request.state.jwt_payload = jwt_payload
                    request.state.token_type = "deepsecure"
            elif token_route == "deepsecure_rs256":
                jwt_payload = await self._validate_jwt_token_rs256(token)
                agent_context = AgentContext.from_jwt_payload(jwt_payload)
                request.state.jwt_payload = jwt_payload
                request.state.token_type = "deepsecure_rs256"
            else:
                jwt_payload = await self._validate_jwt_token(token)
                agent_context = AgentContext.from_jwt_payload(jwt_payload)
                request.state.jwt_payload = jwt_payload
                request.state.token_type = "deepsecure"

            # Store in request state for downstream middleware
            request.state.agent_context = agent_context
            request.state.agent_jwt_token = token

            # Legacy compatibility: also set individual fields
            request.state.agent_id = agent_context.agent_id
            request.state.agent_permissions = agent_context.delegated_permissions
            request.state.delegation_id = agent_context.delegation_id
            request.state.session_id = agent_context.session_id

            # D5: Reject revoked DeepSecure agent sessions (Redis marker from control)
            if request.state.token_type in ("deepsecure", "deepsecure_rs256"):
                from ..security.session_revocation import (
                    get_session_revocation_checker,
                )

                checker = get_session_revocation_checker()
                if checker and await checker.is_revoked(agent_context.session_id):
                    logger.warning(
                        "Rejected revoked session %s for agent %s",
                        agent_context.session_id,
                        agent_context.agent_id,
                    )
                    return self._unauthorized_response(
                        detail="Session revoked",
                        error_code="session_revoked",
                    )

            logger.info(
                "JWT validated [%s] for agent %s, session %s, permissions: %d",
                request.state.token_type,
                agent_context.agent_id,
                agent_context.session_id,
                len(agent_context.delegated_permissions),
            )

        except JWTValidationError as e:
            logger.warning("JWT validation failed: %s", e.detail)
            return self._error_response(e)

        except Exception as e:
            logger.error("Unexpected JWT validation error: %s", e)
            return self._unauthorized_response(
                detail="JWT validation failed",
                error_code="validation_error",
            )

        # Continue with request processing
        return await call_next(request)

    def _classify_token(self, token: str) -> str:
        """Classify a Bearer token for routing to the right validator.

        Returns one of: ``"deepsecure"`` (HS256), ``"deepsecure_rs256"``
        (RS256 from control plane), or ``"oauth"`` (RS256 from Keycloak).
        """
        try:
            header = jwt.get_unverified_header(token)
            alg = header.get("alg", "")
            if not alg.startswith("RS"):
                return "deepsecure"

            claims = jwt.get_unverified_claims(token)
            iss = claims.get("iss", "")
            if iss == self.EXPECTED_ISSUER:
                return "deepsecure_rs256"
            return "oauth"
        except Exception:
            return "deepsecure"

    async def _validate_jwt_token_rs256(self, token: str) -> dict[str, Any]:
        """Validate a DeepSecure RS256 JWT via the control plane's JWKS.

        Fetches ``/.well-known/jwks.json`` from the control plane,
        verifies the signature, and validates standard claims.
        """
        import httpx

        jwks_url = f"{self.control_plane_url}/.well-known/jwks.json"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(jwks_url)
                resp.raise_for_status()
                jwks = resp.json()
        except Exception as e:
            logger.warning("Cannot fetch control-plane JWKS from %s: %s", jwks_url, e)
            raise JWTValidationError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cannot verify RS256 token: JWKS unavailable",
                error_code="jwks_unavailable",
            )

        from jose import jwt as jose_jwt, JWTError as JoseJWTError

        try:
            payload = jose_jwt.decode(
                token,
                jwks,
                algorithms=["RS256", "RS384", "RS512"],
                audience=self.EXPECTED_AUDIENCE,
                issuer=self.EXPECTED_ISSUER,
            )
        except JoseJWTError as e:
            raise JWTValidationError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"RS256 token validation failed: {e}",
                error_code="rs256_validation_failed",
            )

        token_type = payload.get("token_type")
        if token_type == "task_token":
            self._validate_required_claims(payload, self.TASK_TOKEN_REQUIRED_CLAIMS)
        else:
            self._validate_required_claims(payload, self.REQUIRED_CLAIMS)

        self._validate_timing_claims(payload)

        if "delegated_permissions" in payload:
            self._validate_permissions(payload)

        return payload

    async def _validate_jwt_token(self, token: str) -> dict[str, Any]:
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
            payload = jwt.decode(
                token,
                self.jwt_secret_key,
                algorithms=[self.jwt_algorithm],
                audience=self.EXPECTED_AUDIENCE,
                issuer=self.EXPECTED_ISSUER,
            )

            token_type = payload.get("token_type")
            if token_type == "task_token":
                self._validate_required_claims(
                    payload, self.TASK_TOKEN_REQUIRED_CLAIMS
                )
            else:
                self._validate_required_claims(payload, self.REQUIRED_CLAIMS)

            # Validate timing claims
            self._validate_timing_claims(payload)

            # Validate permissions format if present
            if "delegated_permissions" in payload:
                self._validate_permissions(payload)

            logger.debug(
                "JWT validated successfully for agent %s", payload.get("sub")
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
            logger.error("JWT validation error: %s", e)
            raise JWTValidationError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid JWT token format",
                error_code="invalid_format",
            )

    async def _validate_oauth_token(
        self, token: str, validator: "OAuthTokenValidator"
    ) -> AgentContext:
        """Validate an OAuth 2.1 token and build an AgentContext from its claims.

        Maps OAuth scopes (e.g. ``mcp_tools``) to DeepSecure permission
        URNs so downstream middleware can reuse the same permission-checking
        logic regardless of token origin.
        """
        from .oauth_validation import OAuthValidationError

        try:
            claims = await validator.validate_token(token)
        except OAuthValidationError as e:
            raise JWTValidationError(
                status_code=401,
                detail=str(e),
                error_code="oauth_validation_failed",
            ) from e

        permissions = self._oauth_scopes_to_permissions(claims.scopes)

        return AgentContext(
            agent_id=claims.sub,
            owner=claims.preferred_username or claims.email or claims.sub,
            delegation_id=None,
            session_id=f"oauth-{claims.sub}",
            delegated_permissions=permissions,
            token_type="oauth",
            idp_issuer=claims.iss,
        )

    @staticmethod
    def _oauth_scopes_to_permissions(scopes: list[str]) -> list[str]:
        """Map OAuth scopes to DeepSecure permission strings.

        The mapping is intentionally broad — OAuth scopes grant capability
        categories, while DeepSecure permissions are fine-grained.  The
        gateway's PermissionMapper further restricts what tools are
        accessible within these categories.
        """
        scope_map: dict[str, list[str]] = {
            "mcp_tools": ["mcp:tools:list", "mcp:tools:call"],
            "mcp_resources": ["mcp:resources:list", "mcp:resources:read"],
            "mcp_prompts": ["mcp:prompts:list", "mcp:prompts:get"],
        }

        permissions: list[str] = []
        for scope in scopes:
            if scope in scope_map:
                permissions.extend(scope_map[scope])
        return permissions

    def _validate_required_claims(
        self, payload: dict[str, Any], required_claims: list[str]
    ) -> None:
        """Validate that all required claims are present."""
        missing_claims = [
            claim
            for claim in required_claims
            if claim not in payload or payload[claim] is None
        ]

        if missing_claims:
            raise JWTValidationError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"JWT missing required claims: {', '.join(missing_claims)}",
                error_code="missing_claims",
            )

    def _validate_timing_claims(self, payload: dict[str, Any]) -> None:
        """Validate timing claims (iat, nbf, exp)."""
        current_time = datetime.now(timezone.utc).timestamp()

        # Check issued at (iat) - should not be in the future
        # Allow small clock skew (60 seconds)
        if "iat" in payload:
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

        # Check expiration (exp) - jose library handles this,
        # but we add explicit check for better error messages
        if "exp" in payload:
            if payload["exp"] < current_time:
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="JWT token has expired",
                    error_code="token_expired",
                )

    def _validate_permissions(self, payload: dict[str, Any]) -> None:
        """Validate permissions format."""
        permissions = payload.get("delegated_permissions", [])

        if not isinstance(permissions, list):
            raise JWTValidationError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="delegated_permissions must be a list",
                error_code="invalid_permissions_format",
            )

        # Validate permission string format
        for perm in permissions:
            if not isinstance(perm, str):
                raise JWTValidationError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Each permission must be a string",
                    error_code="invalid_permission_type",
                )

            # Basic format validation: should contain at least one colon
            # for namespace:resource:action format
            if ":" not in perm:
                logger.warning(
                    "Permission '%s' doesn't follow namespace:resource:action format",
                    perm,
                )
                # Don't fail - just warn for MVP

    def _www_authenticate_header(self, error_code: str = "", error_description: str = "") -> str:
        """Build RFC 6750 §3 + RFC 9728 WWW-Authenticate header value.

        Includes ``resource_metadata`` pointing to the PRM endpoint so
        clients can discover how to obtain a valid token.
        """
        import os

        parts = ['Bearer realm="deeptrail-gateway"']
        if error_code:
            parts.append(f'error="{error_code}"')
        if error_description:
            safe_desc = error_description.replace('"', "'")
            parts.append(f'error_description="{safe_desc}"')

        gateway_url = os.environ.get(
            "GATEWAY_CANONICAL_URL", "https://gateway.deepsecure.one"
        )
        parts.append(
            f'resource_metadata="{gateway_url}/.well-known/oauth-protected-resource"'
        )
        return ", ".join(parts)

    def _build_error_body(
        self,
        error_code: str,
        detail: str,
        status_code: int,
    ) -> dict[str, Any]:
        """Build a structured RFC 9728-enriched error response body."""
        import os

        gateway_url = os.environ.get(
            "GATEWAY_CANONICAL_URL", "https://gateway.deepsecure.one"
        )
        body: dict[str, Any] = {
            "error": error_code,
            "detail": detail,
            "status": status_code,
            "resource_metadata": f"{gateway_url}/.well-known/oauth-protected-resource",
        }
        return body

    def _unauthorized_response(
        self,
        detail: str,
        error_code: str = "unauthorized",
    ) -> JSONResponse:
        """Create a 401 Unauthorized response."""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=self._build_error_body(error_code, detail, 401),
            headers={
                "WWW-Authenticate": self._www_authenticate_header(
                    error_code="invalid_token" if error_code != "missing_authorization" else "",
                    error_description=detail,
                )
            },
        )

    def _error_response(self, error: JWTValidationError) -> JSONResponse:
        """Create an error response from JWTValidationError."""
        status_code = error.status_code
        return JSONResponse(
            status_code=status_code,
            content=self._build_error_body(error.error_code, error.detail, status_code),
            headers=error.headers if error.headers else {
                "WWW-Authenticate": self._www_authenticate_header(
                    error_code="invalid_token",
                    error_description=error.detail,
                )
            },
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Methods for future enterprise enhancements
    # ─────────────────────────────────────────────────────────────────────────

    async def _fetch_public_key(self) -> str:
        """For Future - Enterprise Grade: Fetch public key from control plane."""
        # This would be used for RSA/ECDSA signature validation
        # with public key cryptography instead of shared secrets
        pass

    async def _validate_jwt_signature(self, token: str, public_key: str) -> bool:
        """For Future - Enterprise Grade: Validate JWT signature with public key."""
        # This would be used for RSA/ECDSA signature validation
        pass

    async def _check_token_revocation(self, token: str) -> bool:
        """For Future - Enterprise Grade: Check if token is revoked."""
        # This would check against a revocation list or cache
        pass

    async def _refresh_token_if_needed(self, token: str) -> str | None:
        """For Future - Enterprise Grade: Refresh token if it's about to expire."""
        # This would automatically refresh tokens that are close to expiration
        pass


# =============================================================================
# FastAPI Dependencies
# =============================================================================


async def get_agent_context(request: Request) -> AgentContext:
    """
    FastAPI dependency to get validated agent context.

    Usage in endpoints:
        @router.get("/tools")
        async def list_tools(agent: AgentContext = Depends(get_agent_context)):
            if agent.has_permission("notion:pages:search"):
                ...

    Args:
        request: FastAPI Request object

    Returns:
        AgentContext from validated JWT

    Raises:
        HTTPException: If agent context not available (JWT not validated)
    """
    from fastapi import HTTPException

    if not hasattr(request.state, "agent_context"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authenticated agent context",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return request.state.agent_context


def require_permission(permission: str) -> Callable:
    """
    FastAPI dependency factory to require a specific permission.

    Usage:
        @router.post("/tools/call")
        async def call_tool(
            tool_name: str,
            agent: AgentContext = Depends(require_permission("notion:pages:read"))
        ):
            ...

    Args:
        permission: Required permission string

    Returns:
        Dependency function that validates permission
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


def require_any_permission(*permissions: str) -> Callable:
    """
    FastAPI dependency factory to require any of the specified permissions.

    Usage:
        @router.get("/data")
        async def get_data(
            agent: AgentContext = Depends(require_any_permission(
                "notion:pages:read",
                "notion:pages:search"
            ))
        ):
            ...

    Args:
        permissions: Permission strings (at least one required)

    Returns:
        Dependency function that validates permissions
    """

    async def _check_permissions(request: Request) -> AgentContext:
        from fastapi import HTTPException

        agent = await get_agent_context(request)

        if not agent.has_any_permission(list(permissions)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires one of {permissions}",
            )

        return agent

    return _check_permissions
