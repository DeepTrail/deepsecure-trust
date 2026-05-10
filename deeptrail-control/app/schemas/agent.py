"""Pydantic schemas for Agent related API operations."""

import logging
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo
from typing import Optional, Any, List
from datetime import datetime
import base64
import binascii # For b64decode error catching

# Setup logger
logger = logging.getLogger(__name__)

# Test keys for reference
VALID_SSH_PUB_KEY_B64_1 = "AAAAC3NzaC1lZDI1NTE5AAAAIDAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
VALID_SSH_PUB_KEY_B64_2 = "AAAAC3NzaC1lZDI1NTE5AAAAIGBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB="
VALID_SSH_PUB_KEY_B64_3 = "AAAAC3NzaC1lZDI1NTE5AAAAIGCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC="

# Map of test keys - for each agent_id, return the appropriate test key
TEST_KEY_MAP = {
    "test-agent-001": VALID_SSH_PUB_KEY_B64_1,
    "test-agent-002": VALID_SSH_PUB_KEY_B64_2,
    "test-agent-003": VALID_SSH_PUB_KEY_B64_3,
}

# --- Base Schemas --- #
class AgentBase(BaseModel):
    name: Optional[str] = Field(None, max_length=255, json_schema_extra={"example": "MyAwesomeAgent"})
    description: Optional[str] = Field(None, json_schema_extra={"example": "Agent for processing order data."})

class AgentCreate(AgentBase):
    agent_id: Optional[str] = Field(None, description="Optional agent ID. If not provided, one will be generated.")
    public_key: Optional[bytes] = Field(None, description="Base64-encoded Ed25519 public key. If omitted, backend generates a keypair.")
    
    @field_validator('public_key', mode='before')
    @classmethod
    def validate_public_key_from_str_input(cls, v: Any) -> Optional[bytes]:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("Input public_key must be a base64 encoded string.")
        try:
            key_bytes = base64.b64decode(v, validate=True)
            if len(key_bytes) != 32:
                raise ValueError("Decoded public key must be 32 bytes long for Ed25519.")
            return key_bytes
        except (binascii.Error, ValueError) as e:
            raise ValueError(f"Invalid base64 encoded public key: {e}")

class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255, json_schema_extra={"example": "MyRenamedAgent"})
    description: Optional[str] = Field(None, json_schema_extra={"example": "Updated agent description."})
    status: Optional[str] = Field(None, max_length=50, json_schema_extra={"example": "inactive"})

# --- Schemas for Database Interaction (usually includes all model fields) --- #
class AgentInDBBase(AgentBase):
    agent_id: str = Field(json_schema_extra={"example": "agent_f3b4c1a9-0123-4567-89ab-cdef01234567"})
    public_key: bytes # Field name matches SQLAlchemy model, stores raw bytes from DB
    status: str = Field(json_schema_extra={"example": "active"})
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

# --- Schemas for API Responses --- #
class Agent(AgentInDBBase): # Inherits fields from AgentInDBBase, including public_key: bytes
    
    # Override the public_key field to return a base64 string instead of bytes
    public_key: str = Field(serialization_alias="publicKey")

    # Lifecycle fields (populated by LifecycleService, not stored in DB)
    lifecycle_state: Optional[str] = Field(None, description="Computed lifecycle state: registered, delegated, authenticated, active")
    last_authenticated_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    session_count: Optional[int] = Field(None, description="Total sessions for this agent")
    delegation_count: Optional[int] = Field(None, description="Active delegation count")

    @field_validator('public_key', mode='before')
    @classmethod
    def encode_public_key_bytes(cls, v: Any) -> str:
        """Convert public key bytes from database to base64 string for JSON response."""
        if isinstance(v, bytes):
            return base64.b64encode(v).decode('utf-8')
        elif isinstance(v, str):
            return v  # Already encoded
        else:
            logger.error(f"[AGENT_SCHEMA] Unexpected public key type: {type(v)}, value: {v}")
            return ""  # Return empty string instead of None to avoid null issues

    model_config = {
        "from_attributes": True,
        "populate_by_name": True, # Allows using serialization_alias "publicKey"
    }

# For listing multiple agents
class AgentList(BaseModel):
    agents: List[Agent]
    total: int


class AgentSessionSummary(BaseModel):
    """Summary of an agent session for the sessions endpoint."""
    session_id: str
    agent_id: str
    delegation_id: str
    is_active: bool
    source_ip: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    last_activity_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AgentSessionList(BaseModel):
    """Response schema for GET /agents/{agent_id}/sessions."""
    sessions: List[AgentSessionSummary]
    total: int

# Schema for agent public key rotation request (if needed as separate endpoint)
class AgentRotateKeyRequest(BaseModel):
    new_public_key: str = Field(..., description="New base64 encoded raw Ed25519 public key (32 bytes).")
    @field_validator('new_public_key', mode='before')
    @classmethod
    def validate_new_public_key(cls, v: Any) -> bytes:
        return AgentCreate.validate_public_key_from_str_input(v)

# Schema for agent rotation request
class AgentRotateRequest(BaseModel):
    """Schema for the request body when rotating an agent's identity key."""
    new_public_key: str = Field(..., description="Base64 encoded raw Ed25519 public key bytes (32 bytes).", example="Base64EncodedEd25519PublicKeyBytes")

# --- Schemas for Challenge-Response Auth ---

class AgentCreateResponse(BaseModel):
    """Response schema for agent creation, includes private_key when backend generates keypair."""

    agent_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    public_key: str = Field(description="Base64-encoded Ed25519 public key")
    status: str = "active"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    private_key: Optional[str] = Field(None, description="Base64-encoded Ed25519 private key (only present when backend generates keypair)")
    private_key_warning: Optional[str] = Field(None, description="Warning about private key storage")

    model_config = {"from_attributes": True}


class AgentToolInfo(BaseModel):
    """Schema for a single tool available to an agent."""

    name: str = Field(description="Tool name (e.g., notion.search_pages)")
    backend: str = Field(description="Backend service (e.g., notion)")
    permission: str = Field(description="Required permission string")
    available: bool = Field(description="Whether the agent has this permission delegated")
    reason: Optional[str] = Field(None, description="Reason if not available")


class AgentToolsResponse(BaseModel):
    """Response schema for GET /agents/{id}/tools."""

    agent_id: str
    tools: List[AgentToolInfo]


class ChallengeRequest(BaseModel):
    """Schema for requesting a new challenge nonce."""
    agent_id: str = Field(..., description="The ID of the agent requesting the challenge.")

class ChallengeResponse(BaseModel):
    """Schema for returning a new challenge nonce."""
    nonce: str = Field(..., description="The single-use nonce for the agent to sign.") 