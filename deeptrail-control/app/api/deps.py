"""API endpoint dependencies.

Functions defined here can be used with FastAPI's dependency injection system
to provide shared logic or resources (like database sessions) to endpoints.
"""

# Placeholder for dependency injection functions
# Example:
# from app.db.session import SessionLocal
#
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from typing import Annotated, Generator
from sqlalchemy.orm import Session
import logging # Import logging

from app.core.config import settings
from app.db.session import SessionLocal # Import the session factory
from app.core import security
from app import crud, models


logger = logging.getLogger(__name__) # Define logger for this module

# --- Database Dependency ---

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DbDep = Annotated[Session, Depends(get_db)]

# --- Authentication Dependency (API Key) ---

# Define the header scheme
api_key_header_scheme = APIKeyHeader(name="Authorization", auto_error=False) # auto_error=False to handle missing header manually

def verify_api_key(api_key_header: str = Depends(api_key_header_scheme)):
    """Dependency to verify the static API key in the Authorization header.

    Expects header format: "Authorization: Bearer <YOUR_STATIC_TOKEN>"
    """
    if not api_key_header or not api_key_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Authorization header (Bearer token expected)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = api_key_header.split(" ")[1]

    # Temporary debug logging (disabled)
    # logger.info(f"[AUTH_DEBUG] Token received by deeptrail-control: '{token}'")
    # logger.info(f"[AUTH_DEBUG] Token expected by deeptrail-control (settings.BACKEND_API_TOKEN): '{settings.BACKEND_API_TOKEN}'")

    if token != settings.BACKEND_API_TOKEN:
        # logger.warning(f"[AUTH_DEBUG] Token mismatch: Received '{token}' vs Expected '{settings.BACKEND_API_TOKEN}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # logger.info(f"[AUTH_DEBUG] Token validation successful for: '{token}'")
    return

# Type alias for the dependency
APIKeyDep = Depends(verify_api_key)

# --- END Authentication Dependencies ---

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/token")

def get_current_active_agent(
    db: DbDep, token: str = Depends(oauth2_scheme)
) -> models.Agent:
    """
    Dependency to get the current authenticated agent from a JWT token.
    
    1. Decodes the JWT token from the Authorization header.
    2. Validates the token's signature and expiration.
    3. Fetches the agent from the database based on the 'agent_id' claim.
    4. Returns the active agent object.
    
    Raises HTTPException for any validation failures.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = security.decode_token(token)
    if payload is None:
        raise credentials_exception
        
    agent_id = payload.get("agent_id")
    if agent_id is None:
        raise credentials_exception
        
    agent = crud.agent.get(db, id=agent_id)
    if agent is None:
        raise credentials_exception
        
    # TODO: Add check for agent.is_active if you have such a field
    # if not agent.is_active:
    #     raise HTTPException(status_code=400, detail="Inactive agent")
        
    return agent


# (Removed commented out OAuth2 code)

# --- Agent JWT Claims Dependency ---

# OAuth2 scheme for agent JWTs (no auto_error to handle manually)
agent_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/agent/verify", auto_error=False)


def get_current_agent_claims(
    token: str = Depends(agent_oauth2_scheme),
) -> dict:
    """Extract and validate claims from an Agent Session JWT.

    This dependency decodes the Agent JWT issued during challenge-response
    authentication and returns the claims dict containing:
    - sub: Agent ID
    - owner: User ID (e.g., sarah@acme.com) - the delegator
    - delegated_permissions: List of permissions delegated to the agent
    - session_id: Session identifier
    - delegation_id: Reference to the delegation

    Used by endpoints that need to verify agent permissions without
    fetching the agent from the database.

    Returns:
        dict: JWT claims with user_id (from 'owner') and delegated_permissions

    Raises:
        HTTPException 401: If JWT is missing, invalid, or expired
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Missing authorization token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = security.decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Invalid or expired token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate required claims for agent JWT or task token
    # Agent JWTs use 'owner' for user_id and 'sub' for agent_id
    # Task tokens use 'owner' for user_id and 'agent_id' directly
    # NOTE: 'sub' is agent_id, NOT user_id - do not confuse them
    user_id = payload.get("owner")
    token_type = payload.get("token_type", "agent_session")

    if token_type == "task_token":
        scoped = payload.get("scoped_permissions", [])
        delegated_permissions = [
            p["urn"] for p in scoped if isinstance(p, dict) and "urn" in p
        ]
        agent_id = payload.get("agent_id")
    else:
        delegated_permissions = payload.get("delegated_permissions", [])
        agent_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Invalid token: missing user identity"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Return normalized claims
    return {
        "user_id": user_id,
        "agent_id": agent_id,
        "delegated_permissions": delegated_permissions,
        "session_id": payload.get("session_id") or payload.get("task_id"),
        "delegation_id": payload.get("delegation_id"),
    }


# Type alias for agent claims dependency
AgentClaimsDep = Annotated[dict, Depends(get_current_agent_claims)]


# --- Internal Token Authentication (Gateway-to-Control) ---

# Header scheme for internal API token
internal_token_header_scheme = APIKeyHeader(name="Authorization", auto_error=False)


def verify_internal_token(
    authorization: str = Depends(internal_token_header_scheme),
) -> str:
    """Verify internal API token for gateway-to-control calls.

    This is used for internal service-to-service communication where
    the gateway needs to call control plane endpoints on behalf of users.
    The user identity is passed via X-User-ID header, not extracted from
    a JWT.

    Args:
        authorization: Authorization header value (Bearer token).

    Returns:
        The validated token string.

    Raises:
        HTTPException 401: If token is missing or invalid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Invalid or missing internal token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1]

    # Validate against configured internal token
    if token != settings.GATEWAY_INTERNAL_API_TOKEN:
        logger.warning("Invalid internal API token received")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Invalid internal token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


# Type alias for internal token dependency
InternalTokenDep = Annotated[str, Depends(verify_internal_token)]


# You can add more dependencies here later, e.g., for role checks
# def get_current_active_admin(...): ... 