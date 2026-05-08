"""Pydantic schemas for User-related API operations."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserUpdate(BaseModel):
    """Request schema for updating user profile via PATCH /users/me."""

    onboarding_completed: Optional[bool] = Field(
        None, description="Whether the user has completed onboarding"
    )


class UserResponse(BaseModel):
    """Response schema for user profile."""

    user_id: str
    email: Optional[str] = None
    onboarding_completed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
