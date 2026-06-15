"""
DeepTrail Gateway - Main Application

This is the main FastAPI application that serves as the central proxy gateway
for all outbound agent traffic, providing authentication, policy enforcement,
and secret injection capabilities.

Core PEP Functionality:
- JWT validation middleware
- Basic policy enforcement
- HTTP request proxying
- Simple secret injection

For Future - Enterprise Grade:
- Advanced security middleware
- Comprehensive logging and audit
- Sophisticated sanitization
- Performance monitoring
- Rate limiting and throttling
"""

import asyncio
import logging
import os
import json
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any
from urllib.parse import urlparse

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel

from .proxy import proxy_handler
from .core.proxy_config import config, get_project_version
from .core.http_client import close_http_client
from .core.request_validator import ValidationError
from .core.request_logger import LoggingConfig, configure_request_logging
from .core.share_storage import ShareStorageManager

# For Future - Enterprise Grade: Advanced middleware imports
# from .middleware.logging import setup_logging_middleware, get_logging_stats
# from .middleware.security import SecurityMiddleware, SecurityHeadersMiddleware
# from .middleware.sanitization import SanitizationMiddleware, ContentValidationMiddleware

# Core PEP: Essential middleware imports
from .middleware.correlation import CorrelationMiddleware, get_request_id
from .middleware.jwt_validation import (
    JWTValidationMiddleware,
    build_insufficient_scope_body,
    build_insufficient_scope_header,
)
from .middleware.oauth_validation import configure_oauth_validator
from .security.session_revocation import configure_session_revocation_checker
from .middleware.policy_enforcement import PolicyEnforcementMiddleware
from .middleware.secret_injection import SecretInjectionMiddleware

# MCP Protocol imports
from .mcp.protocol import MCPProtocolHandler, JsonRpcErrorCode, MCPMethod
from .mcp.handlers import (
    handle_initialize, 
    handle_tools_list, 
    handle_tools_call,
    handle_discover,
    configure_initialize_handler,
    configure_tools_list_handler,
    configure_tools_call_handler,
)
from .mcp.session_manager import MCPSessionManager
from .mcp.tool_cache import ToolCache
from .security.fail_closed import configure_health_checker
from .middleware.audit import configure_audit_middleware
from .middleware.result_filter import configure_result_filter
from .security.prompt_injection import configure_prompt_injection_detector
from .security.token_exchange import configure_token_exchange_client, TokenExchangeConfig
from .middleware.credential_injection import get_credential_injector, configure_credential_injector
from .middleware.result_filter import configure_result_filter
from .security.prompt_injection import configure_prompt_injection_detector
from .security.token_exchange import configure_token_exchange_client, TokenExchangeConfig
from .backends.adapter import create_backend_adapter
from .backends.dynamic_registry import DynamicBackendLoader
from .core.config import get_settings
from .services.cache_subscriber import start_cache_subscriber, stop_cache_subscriber

# C6: Protected Resource Metadata (RFC 9728)
from .api.well_known import router as well_known_router

# Configure basic logging
logging.basicConfig(
    level=getattr(logging, config.logging.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def _health_report_loop(loader: DynamicBackendLoader, interval: int) -> None:
    """Periodically probe backends and report health to Control Plane."""
    while True:
        await asyncio.sleep(interval)
        try:
            await loader.report_health()
        except Exception as e:
            logger.error("Health report loop error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown tasks.
    """
    # Startup
    logger.info("Starting DeepTrail Gateway...")
    logger.info(f"Configuration: {config.proxy_type} on {config.host}:{config.port}")
    logger.info(f"Target header: {config.routing.target_header}")
    logger.info(f"Path prefix: {config.routing.path_prefix}")

    # Start cache invalidation subscriber
    if config.redis_url:
        try:
            injector = get_credential_injector()
            await start_cache_subscriber(
                redis_url=config.redis_url,
                on_token_invalidate=injector.invalidate_credential,
                on_user_service_invalidate=injector.invalidate_user_service,
                on_clear_all=injector.clear_cache,
            )
            logger.info("Cache invalidation subscriber started")
        except Exception as e:
            logger.warning(f"Failed to start cache subscriber: {e}")
    else:
        logger.info("REDIS_URL not set, cache invalidation subscriber disabled")

    # Dynamic backend registry loader — loads service catalog from Control Plane
    from .backends.connection_manager import BackendConnectionManager
    from .core.config import get_settings
    gw_settings = get_settings()
    mcp_connection_manager = BackendConnectionManager()
    backend_client.set_connection_manager(mcp_connection_manager)
    dynamic_loader = DynamicBackendLoader(
        adapter=backend_client,
        connection_manager=mcp_connection_manager,
        tool_cache=mcp_tool_cache,
        control_plane_url=gw_settings.control_plane_url,
        internal_api_token=gw_settings.gateway_internal_api_token,
        refresh_interval_seconds=gw_settings.registry_refresh_interval,
    )
    count = await dynamic_loader.initial_load()
    logger.info("Dynamic registry: %d backends loaded from Control Plane", count)

    refresh_task = asyncio.create_task(dynamic_loader.run_refresh_loop())
    health_task = asyncio.create_task(_health_report_loop(dynamic_loader, gw_settings.registry_health_report_interval))

    yield

    # Shutdown
    logger.info("Shutting down DeepTrail Gateway...")
    dynamic_loader.stop()
    refresh_task.cancel()
    health_task.cancel()
    await stop_cache_subscriber()
    await close_http_client()
    logger.info("DeepTrail Gateway stopped")


# Create FastAPI application
app = FastAPI(
    title="DeepTrail Gateway",
    description="Secure proxy gateway for AI agent outbound traffic",
    version=get_project_version(),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# C6: Mount .well-known routes (no JWT required — public discovery endpoints)
app.include_router(well_known_router)

_cors_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
if _cors_env:
    _allowed_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    _allowed_origins = []

if not _allowed_origins:
    logger.warning(
        "CORS_ALLOWED_ORIGINS is empty — no cross-origin requests will be allowed. "
        "Set CORS_ALLOWED_ORIGINS to a comma-separated list of permitted origins."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["POST", "GET", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Mcp-Session-Id", "MCP-Protocol-Version", "Mcp-Method", "Mcp-Name", "X-Request-ID"],
)

# Configure basic logging (not enterprise-grade structured logging)
logging_config = LoggingConfig(
    enabled=True,
    log_level="INFO",
    log_headers=False,  # For Future - Enterprise Grade
    log_body=False,     # For Future - Enterprise Grade
    log_response_body=False,  # For Future - Enterprise Grade
    audit_mode=False    # For Future - Enterprise Grade
)

# Configure global request logging
configure_request_logging(logging_config)

# For Future - Enterprise Grade: Advanced middleware stack
# app = setup_logging_middleware(app, logging_config)
# app.add_middleware(SecurityHeadersMiddleware)
# app.add_middleware(SecurityMiddleware, config=config)
# app.add_middleware(ContentValidationMiddleware)
# app.add_middleware(SanitizationMiddleware, config=config)

# TODO: Add JWT validation middleware (essential for core PEP)
# TODO: Add basic policy enforcement middleware (essential for core PEP)

# Core PEP: Essential middleware stack
# Order matters: Correlation -> JWT validation -> Policy enforcement -> Secret injection
app.add_middleware(SecretInjectionMiddleware, control_plane_url=config.control_plane_url)
app.add_middleware(PolicyEnforcementMiddleware, enforcement_mode=config.policy.enforcement_mode)
app.add_middleware(JWTValidationMiddleware, control_plane_url=config.control_plane_url)
app.add_middleware(CorrelationMiddleware)

configure_oauth_validator()
logger.info("OAuth token validator configured for Keycloak MCP realm")

configure_session_revocation_checker(redis_url=config.redis_url)
logger.info("Session revocation checker configured (Redis)")

# =============================================================================
# MCP Protocol Handler Setup
# =============================================================================

# Configure fail-closed security with control plane health checks
configure_health_checker(
    control_plane_url=config.control_plane_url,
    timeout_seconds=5.0,
    circuit_breaker_threshold=5,
    circuit_breaker_reset_seconds=30.0,
)
logger.info(f"Health checker configured with control plane URL: {config.control_plane_url}")

# =============================================================================
# Audit Middleware Configuration
# =============================================================================

# Configure audit middleware to dispatch events to Control Plane
configure_audit_middleware(
    control_plane_url=config.control_plane_url,
    timeout_seconds=5.0,
    enabled=True,
)
logger.info(f"Audit middleware configured: control_plane_url={config.control_plane_url}")

# =============================================================================
# Result Filter Configuration (J4: PII Masking)
# =============================================================================

configure_result_filter(enabled=True)
logger.info("Result filter configured: PII masking enabled")

# =============================================================================
# Prompt Injection Detection Configuration (J5)
# =============================================================================

configure_prompt_injection_detector()
logger.info("Prompt injection detector configured: argument scanning enabled")

# =============================================================================
# Token Exchange Configuration (J6: Keycloak RFC 8693)
# =============================================================================

_keycloak_url = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")
_keycloak_realm = os.environ.get("KEYCLOAK_REALM", "deepsecure")
_keycloak_client_id = os.environ.get("KEYCLOAK_GATEWAY_CLIENT_ID", "gateway")
_keycloak_client_secret = os.environ.get("KEYCLOAK_GATEWAY_CLIENT_SECRET", "")

configure_token_exchange_client(
    TokenExchangeConfig(
        enabled=bool(_keycloak_client_secret),
        keycloak_url=_keycloak_url,
        realm=_keycloak_realm,
        client_id=_keycloak_client_id,
        client_secret=_keycloak_client_secret,
    )
)
logger.info(
    "Token exchange client configured: enabled=%s",
    bool(_keycloak_client_secret),
)

# Initialize MCP Session Manager and Tool Cache
mcp_session_manager = MCPSessionManager()

# Get the global tool cache and populate it with proper tool definitions
# The tools_list handler uses get_tool_cache() internally, so we must use the same instance
from .mcp.tool_cache import get_tool_cache
from .mcp.tool_definitions import populate_tool_cache
mcp_tool_cache = get_tool_cache()
populate_tool_cache(mcp_tool_cache)
logger.info("Tool cache populated with backend tool definitions")

from .mcp.permission_mapper import PermissionMapper
_auto_mapped = PermissionMapper.build_from_tool_cache(mcp_tool_cache)
logger.info("PermissionMapper auto-built %d mappings from tool cache", _auto_mapped)

# Configure credential injector with Control Plane URL
# This enables real vault token retrieval instead of mock tokens
configure_credential_injector(
    control_plane_url=config.control_plane_url,
    cache_ttl_seconds=60,
    internal_api_token=getattr(config, 'internal_api_token', None),
)
logger.info(f"Credential injector configured with Control Plane URL: {config.control_plane_url}")

# Configure MCP method handlers with dependencies
configure_initialize_handler(
    session_manager=mcp_session_manager,
)
configure_tools_list_handler(
    session_manager=mcp_session_manager,
    tool_cache=mcp_tool_cache,
)
# =============================================================================
# Backend Client Configuration
# =============================================================================
_gw_settings = get_settings()
backend_client = create_backend_adapter(
    include_builtin=_gw_settings.registry_mode != "dynamic_only",
)
logger.info(
    "Backend client adapter configured (registry_mode=%s, backends=%s)",
    _gw_settings.registry_mode,
    backend_client.registered_backends,
)

configure_tools_call_handler(
    session_manager=mcp_session_manager,
    backend_client=backend_client,  # Production: Real backend calls via adapter
    audit_logger=None,  # MVP: Basic audit logging
)

# Initialize MCP Protocol Handler for Virtual MCP Server
mcp_protocol_handler = MCPProtocolHandler()

# Register MCP method handlers
mcp_protocol_handler.register_handler(MCPMethod.INITIALIZE, handle_initialize)
mcp_protocol_handler.register_handler(MCPMethod.TOOLS_LIST, handle_tools_list)
mcp_protocol_handler.register_handler(MCPMethod.TOOLS_CALL, handle_tools_call)
mcp_protocol_handler.register_handler(MCPMethod.DISCOVER, handle_discover)

# Global exception handlers
@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle request validation errors."""
    logger.warning(f"Validation error: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Validation Error",
            "message": exc.message,
            "type": "validation_error"
        }
    )

@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError):
    """Handle FastAPI request validation errors."""
    logger.warning(f"Request validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "Request Validation Error",
            "message": str(exc),
            "type": "request_validation_error"
        }
    )

@app.exception_handler(HTTPException)
async def fastapi_http_exception_handler(request: Request, exc: HTTPException):
    """Handle FastAPI HTTP exceptions."""
    logger.info(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "message": exc.detail,
            "type": "http_error"
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    logger.error(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "message": exc.detail,
            "type": "http_error"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "type": "internal_error"
        }
    )


# Health check endpoints
@app.get("/")
async def root():
    """
    Root endpoint for basic health checks.
    """
    return {
        "message": "DeepTrail Gateway is running",
        "status": "healthy",
        "version": config.version,
        "proxy_type": config.proxy_type
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    """
    # Check control plane connectivity
    control_plane_status = "connected"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{config.control_plane_url}/health")
            if response.status_code != 200:
                control_plane_status = "disconnected"
    except Exception as e:
        logger.error(f"Control plane health check failed: {e}")
        control_plane_status = "disconnected"
    
    # Check Redis connectivity
    redis_status = "connected"
    try:
        # Parse Redis URL from config
        redis_url = getattr(config, 'redis_url', 'redis://redis:6379')
        parsed = urlparse(redis_url)
        
        redis_client = redis.Redis(
            host=parsed.hostname or 'redis',
            port=parsed.port or 6379,
            decode_responses=True
        )
        
        # Test connection with ping
        await redis_client.ping()
        await redis_client.aclose()
        
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_status = "disconnected"
    
    return {
        "service": "DeepSecure Gateway",
        "version": config.version,
        "status": "ok",
        "dependencies": {
            "control_plane": control_plane_status,
            "redis": redis_status
        }
    }


@app.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint for Kubernetes and container orchestrators.
    """
    try:
        # Check if all components are ready
        health_status = await proxy_handler.health_check()
        
        if health_status.get("status") == "healthy":
            return {
                "status": "ready",
                "message": "Gateway is ready to accept requests"
            }
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "message": "Gateway is not ready to accept requests"
                }
            )
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "error": str(e),
                "message": "Gateway is not ready to accept requests"
            }
        )


# For Future - Enterprise Grade: Advanced monitoring endpoints
@app.get("/metrics")
async def metrics():
    """
    For Future - Enterprise Grade: Metrics endpoint for Prometheus monitoring.
    
    Current Implementation: Basic metrics only.
    """
    try:
        health_status = await proxy_handler.health_check()
        
        # Basic metrics only (not full Prometheus format)
        return {
            "requests_processed": health_status.get('requests_processed', 0),
            "gateway_status": 1 if health_status.get('status') == 'healthy' else 0,
            "version": config.version,
            "proxy_type": config.proxy_type
        }
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Error collecting metrics"}
        )


# For Future - Enterprise Grade: Advanced configuration endpoint
@app.get("/config")
async def get_configuration():
    """
    For Future - Enterprise Grade: Get current gateway configuration.
    
    Current Implementation: Basic configuration only.
    """
    return {
        "proxy_type": config.proxy_type,
        "routing": {
            "target_header": config.routing.target_header,
            "path_prefix": config.routing.path_prefix
        },
        "authentication": {
            "jwt_validation": config.authentication.jwt_validation
        },
        "logging": {
            "enable_request_logging": config.logging.enable_request_logging,
            "log_level": config.logging.log_level
        }
    }


# For Future - Enterprise Grade: Advanced logging endpoints
@app.get("/logging/stats")
async def get_logging_stats():
    """For Future - Enterprise Grade: Get logging statistics."""
    return {"message": "For Future - Enterprise Grade"}

@app.get("/logging/config")
async def get_logging_config():
    """For Future - Enterprise Grade: Get logging configuration."""
    return {"message": "For Future - Enterprise Grade"}

@app.get("/logging/active")
async def get_active_requests():
    """For Future - Enterprise Grade: Get active request information."""
    return {"message": "For Future - Enterprise Grade"}


# =============================================================================
# MCP Protocol Endpoint - Virtual MCP Server Entry Point
# =============================================================================


@app.post("/mcp", summary="MCP JSON-RPC 2.0 endpoint")
async def mcp_endpoint(request: Request):
    """
    MCP (Model Context Protocol) JSON-RPC 2.0 endpoint.
    
    This is the entry point for AI agents connecting to the Virtual MCP Server.
    The endpoint handles JSON-RPC 2.0 requests for MCP methods:
    
    - `initialize`: Establish MCP session handshake
    - `tools/list`: List available tools (filtered by agent permissions)
    - `tools/call`: Execute a tool with automatic credential injection
    
    Authentication:
        Requires Bearer token in Authorization header (agent session JWT).
        JWT validation is handled by JWTValidationMiddleware.
    
    Request Format (JSON-RPC 2.0):
        ```json
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "MyAgent", "version": "1.0.0"}
            }
        }
        ```
    
    Response Format (JSON-RPC 2.0):
        Success:
        ```json
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": true}},
                "serverInfo": {"name": "DeepTrail Virtual MCP Server", "version": "0.1.0"}
            }
        }
        ```
        
        Error:
        ```json
        {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32601, "message": "Method not found"}
        }
        ```
    """
    try:
        # Read raw request body
        raw_body = await request.body()
        
        # Phase 1: Diagnostic logging for MCP Streamable HTTP debugging
        try:
            parsed_body = json.loads(raw_body)
            req_method = parsed_body.get("method", "?") if isinstance(parsed_body, dict) else "batch"
        except (json.JSONDecodeError, UnicodeDecodeError):
            req_method = "<invalid>"
        
        mcp_headers = {
            k: (v[:20] + "..." if k.lower() == "authorization" else v)
            for k, v in request.headers.items()
            if k.lower() in ("accept", "content-type", "mcp-session-id", "authorization")
        }
        logger.info("MCP IN: method=%s headers=%s", req_method, mcp_headers)

        # B4: Read and validate MCP headers (MCP 2026-07-28)
        mcp_protocol_version = request.headers.get("MCP-Protocol-Version")
        mcp_method_header = request.headers.get("Mcp-Method")
        mcp_name_header = request.headers.get("Mcp-Name")

        # B4: Reject Mcp-Method / JSON-RPC body mismatches with HTTP 400
        if isinstance(parsed_body, dict):
            from .mcp.header_validation import mcp_method_header_mismatch

            if mcp_method_header_mismatch(mcp_method_header, req_method):
                logger.warning(
                    "Mcp-Method mismatch: header=%s body=%s",
                    mcp_method_header,
                    req_method,
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": "Mcp-Method header does not match JSON-RPC method",
                        "error_code": "header_body_mismatch",
                        "mcp_method_header": mcp_method_header,
                        "jsonrpc_method": req_method,
                    },
                )
        
        # Extract context from request state (populated by JWTValidationMiddleware)
        agent_context = getattr(request.state, "agent_context", None)
        
        # Build context for MCP handlers
        context = {
            "request_id": get_request_id(request),
            "mcp_protocol_version": mcp_protocol_version,
            "mcp_method": mcp_method_header,
            "mcp_name": mcp_name_header,
        }
        
        # Accept Mcp-Session-Id from client (stateless — JWT is source of truth)
        client_session_id = request.headers.get("Mcp-Session-Id")
        if client_session_id:
            context["mcp_session_id"] = client_session_id
        
        # Map agent context to handler-expected fields
        if agent_context:
            context.update({
                "agent_session_id": agent_context.session_id,
                "agent_id": agent_context.agent_id,
                "delegator": agent_context.owner,
                "delegated_permissions": agent_context.delegated_permissions,
                "delegation_id": agent_context.delegation_id,
                "organization_id": agent_context.organization_id,
                "constraints": {},  # MVP: No constraints enforcement yet
                "agent_jwt_token": getattr(request.state, "agent_jwt_token", None),
            })
        
        # Handle the MCP request
        response = await mcp_protocol_handler.handle_request(raw_body, context=context)
        
        # Handle different response types
        if response is None:
            # Notification — per MCP Streamable HTTP spec: return 202 Accepted
            logger.info("MCP OUT: 202 Accepted (notification: %s)", req_method)
            return Response(status_code=202)
        
        if isinstance(response, list):
            # Batch response
            logger.info("MCP OUT: 200 batch (%d responses)", len(response))
            return JSONResponse(
                content=[r.model_dump() for r in response],
                media_type="application/json"
            )
        
        # E2: Permission denied → HTTP 403 with scope challenge (not JSON-RPC 200)
        if (
            response.error
            and response.error.code == JsonRpcErrorCode.PERMISSION_DENIED
        ):
            required_perm = None
            if response.error.data and isinstance(response.error.data, dict):
                required_perm = response.error.data.get("required_permission")
            required_perms = [required_perm] if required_perm else []
            req_id = get_request_id(request)
            return JSONResponse(
                status_code=403,
                content=build_insufficient_scope_body(
                    required_perms,
                    response.error.message,
                    request_id=req_id,
                ),
                headers={
                    "WWW-Authenticate": build_insufficient_scope_header(required_perms),
                    "X-Request-ID": req_id,
                    "MCP-Protocol-Version": mcp_protocol_version or "2025-11-25",
                },
            )

        # Single response — build JSONResponse
        response_obj = JSONResponse(
            content=response.model_dump(),
            media_type="application/json"
        )
        response_obj.headers["X-Request-ID"] = get_request_id(request)
        
        # B5: Set MCP-Protocol-Version response header (2026-07-28 spec)
        negotiated_version = mcp_protocol_version or "2025-11-25"
        if response.result and isinstance(response.result, dict):
            negotiated_version = response.result.get("protocolVersion", negotiated_version)
        response_obj.headers["MCP-Protocol-Version"] = negotiated_version
        
        # Echo Mcp-Session-Id on InitializeResult per Streamable HTTP spec
        if req_method == "initialize" and agent_context and agent_context.session_id:
            response_obj.headers["Mcp-Session-Id"] = agent_context.session_id
            logger.info(
                "MCP OUT: 200 initialize (Mcp-Session-Id: %s, protocol: %s)",
                agent_context.session_id,
                negotiated_version,
            )
        else:
            logger.info("MCP OUT: 200 %s (protocol: %s)", req_method, negotiated_version)
        
        return response_obj
        
    except Exception as e:
        logger.error(f"Unexpected error in MCP endpoint: {e}", exc_info=True)
        # Return JSON-RPC internal error
        error_response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": JsonRpcErrorCode.INTERNAL_ERROR,
                "message": "Internal error"
            }
        }
        return JSONResponse(content=error_response, status_code=500)


# MCP Streamable HTTP spec: GET opens SSE stream for server-initiated messages
@app.get("/mcp", include_in_schema=False)
async def mcp_get_endpoint(request: Request):
    """SSE stream endpoint for server-to-client notifications. Returns minimal valid stream."""
    from starlette.responses import StreamingResponse
    import asyncio

    session_id = request.headers.get("Mcp-Session-Id", "")
    logger.info("MCP GET: SSE stream requested (session=%s)", session_id)

    async def event_generator():
        yield ": keepalive\n\n"
        await asyncio.sleep(30)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# MCP Streamable HTTP spec: DELETE terminates session (no-op for stateless gateway)
@app.delete("/mcp", include_in_schema=False)
async def mcp_delete_endpoint(request: Request):
    """Acknowledge session termination request. Stateless — JWT expiry handles cleanup."""
    session_id = request.headers.get("Mcp-Session-Id", "none")
    logger.info("MCP DELETE: session termination requested (session=%s)", session_id)
    return Response(status_code=200)


# Internal endpoint models for share storage
class InternalShareIn(BaseModel):
    secret_name: str
    share_value: Any  # Can be string or list [index, hex_string]
    prime_mod: str | None = None  # Prime modulus as hex string for Shamir reassembly
    metadata: Dict[str, Any] | None = None


# Internal endpoint: receive share_2 from control plane
@app.post("/internal/shares", status_code=201, include_in_schema=False)
async def receive_share(request: Request, body: InternalShareIn):
    """
    Receives a secret share from the control plane and stores it in Redis.
    This endpoint is for internal use only and requires API key authentication.
    """
    # Validate internal API token
    token = request.headers.get("X-Internal-API-Token")
    expected = getattr(config, "internal_api_token", None)
    if not token or not expected or token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing internal API key")

    try:
        # Initialize share storage manager
        redis_url = getattr(config, 'redis_url', 'redis://redis:6379')
        encryption_key = expected  # Use internal token as encryption key for dev
        storage = ShareStorageManager(redis_url=redis_url, encryption_key=encryption_key)

        ok = await storage.store_share(
            secret_name=body.secret_name,
            share_2=body.share_value,
            prime_mod_hex=body.prime_mod,  # Pass prime_mod for secret reassembly
            metadata=body.metadata or {}
        )
        if not ok:
            raise HTTPException(status_code=502, detail="Failed to persist share")

        logger.info(f"Successfully stored share_2 for secret '{body.secret_name}'")
        return {"status": "stored", "secret_name": body.secret_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing internal share: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error storing share")


# Internal endpoint: retrieve share_2 for secret reassembly
@app.get("/internal/shares/{secret_name}", status_code=200, include_in_schema=False)
async def get_share(request: Request, secret_name: str):
    """
    Retrieves a secret share from Redis for the gateway's secret injection.
    This endpoint is for internal use only and requires API key authentication.
    """
    # Validate internal API token
    token = request.headers.get("X-Internal-API-Token")
    expected = getattr(config, "internal_api_token", None)
    if not token or not expected or token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing internal API key")

    try:
        redis_url = getattr(config, 'redis_url', 'redis://redis:6379')
        encryption_key = expected
        storage = ShareStorageManager(redis_url=redis_url, encryption_key=encryption_key)

        share_data = await storage.retrieve_share(secret_name=secret_name)
        if share_data is None:
            raise HTTPException(status_code=404, detail=f"Share for '{secret_name}' not found")

        logger.info(f"Successfully retrieved share_2 for secret '{secret_name}'")
        return {"secret_name": secret_name, "share_2": share_data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving internal share: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error retrieving share")


# Internal endpoint: delete share_2 from Redis
@app.delete("/internal/shares/{secret_name}", status_code=200, include_in_schema=False)
async def delete_share(request: Request, secret_name: str):
    """
    Deletes a secret share from Redis.
    This endpoint is for internal use only and requires API key authentication.
    """
    # Validate internal API token
    token = request.headers.get("X-Internal-API-Token")
    expected = getattr(config, "internal_api_token", None)
    if not token or not expected or token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing internal API key")

    try:
        redis_url = getattr(config, 'redis_url', 'redis://redis:6379')
        encryption_key = expected
        storage = ShareStorageManager(redis_url=redis_url, encryption_key=encryption_key)

        deleted = await storage.delete_share(secret_name=secret_name)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Share for '{secret_name}' not found")

        logger.info(f"Successfully deleted share_2 for secret '{secret_name}'")
        return {"status": "deleted", "secret_name": secret_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting internal share: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error deleting share")


# Main proxy routes
@app.api_route(
    config.routing.path_prefix + "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    summary="Proxy requests to external services",
    description="Main proxy endpoint that forwards requests to external services based on the X-Target-Base-URL header"
)
async def proxy_request(request: Request, path: str = ""):
    """
    Main proxy endpoint that handles all HTTP methods and forwards requests
    to external services based on the X-Target-Base-URL header.
    
    Core PEP Functionality (Implemented):
    - JWT validation (✓ implemented via JWTValidationMiddleware)
    - Policy enforcement (✓ implemented via PolicyEnforcementMiddleware)
    - Request proxying (✓ implemented via proxy_handler)
    - Secret injection (✓ implemented via SecretInjectionMiddleware)
    
    Args:
        request: The incoming HTTP request
        path: The path component from the URL
        
    Returns:
        Response from the target service
        
    Raises:
        HTTPException: If the request fails validation or processing
    """
    try:
        # Core PEP functionality is handled by middleware:
        # 1. JWTValidationMiddleware validates the JWT token
        # 2. PolicyEnforcementMiddleware enforces access policies
        # 3. SecretInjectionMiddleware injects appropriate secrets
        # 4. proxy_handler forwards the request to the target service
        
        # Handle the proxy request
        response = await proxy_handler.handle_proxy_request(request, path)
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in proxy request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# Catch-all route for requests that don't match the proxy prefix
@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    include_in_schema=False
)
async def catch_all(request: Request, path: str):
    """
    Catch-all route for requests that don't match other endpoints.
    Provides helpful error messages for misconfigured requests.
    """
    if path.startswith("proxy/"):
        # Likely a misconfigured proxy request
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid proxy request",
                "message": f"Proxy requests must use the '{config.routing.path_prefix}' prefix",
                "correct_format": f"{config.routing.path_prefix}/your-path",
                "required_header": config.routing.target_header,
                "type": "configuration_error"
            }
        )
    
    # Regular 404 for other paths
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"Path '{path}' not found",
            "available_endpoints": [
                "/",
                "/health",
                "/ready", 
                "/metrics",
                "/config",
                f"{config.routing.path_prefix}/{{path:path}}"
            ],
            "type": "not_found"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.port,
        reload=True,
        log_level=config.logging.log_level.lower()
    )
