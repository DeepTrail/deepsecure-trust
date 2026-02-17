from typing import List, Optional
import uuid as uuid_module
from pydantic import BaseModel, field_validator

# Shared properties
class PolicyBase(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    effect: str = "allow"
    actions: Optional[List[str]] = None
    resources: Optional[List[str]] = None
    agent_id: Optional[str] = None  # String to match agents.agent_id format

# Properties to receive on item creation
class PolicyCreate(PolicyBase):
    name: str
    actions: List[str]
    resources: List[str]
    agent_id: str  # String format: either "agent-uuid" or just "uuid"

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is not empty."""
        if not v or not v.strip():
            raise ValueError('name cannot be empty')
        return v

    @field_validator('agent_id')
    @classmethod
    def validate_agent_id(cls, v: str) -> str:
        """Validate agent_id is a valid UUID or agent-prefixed UUID."""
        if not v:
            raise ValueError('agent_id cannot be empty')
        # Support both "agent-uuid" and plain "uuid" formats
        uuid_part = v.replace('agent-', '') if v.startswith('agent-') else v
        try:
            uuid_module.UUID(uuid_part)
        except ValueError:
            raise ValueError(f'agent_id must be a valid UUID format, got: {v}')
        return v

    @field_validator('actions')
    @classmethod
    def validate_actions(cls, v: List[str]) -> List[str]:
        """Validate actions list is not empty."""
        if not v:
            raise ValueError('actions list cannot be empty')
        return v

    @field_validator('resources')
    @classmethod
    def validate_resources(cls, v: List[str]) -> List[str]:
        """Validate resources list is not empty."""
        if not v:
            raise ValueError('resources list cannot be empty')
        return v

# Properties to receive on item update
class PolicyUpdate(PolicyBase):
    pass

# Properties shared by models stored in DB
class PolicyInDBBase(PolicyBase):
    id: uuid_module.UUID
    name: str
    agent_id: str  # String format to match agents.agent_id
    actions: List[str]
    resources: List[str]

    class Config:
        from_attributes = True

# Properties to return to client
class Policy(PolicyInDBBase):
    pass

# Properties properties stored in DB
class PolicyInDB(PolicyInDBBase):
    pass 