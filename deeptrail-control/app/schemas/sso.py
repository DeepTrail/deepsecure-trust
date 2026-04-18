"""Pydantic schemas for SSO (OIDC) authentication endpoints."""

from typing import Optional

from pydantic import BaseModel, Field


class SSOAuthorizeResponse(BaseModel):
    """Response from SSO authorize endpoint."""

    authorization_url: str
    state: str
    expires_in: int = Field(default=300, description="State validity in seconds")


class SSOUserInfo(BaseModel):
    """User info returned after SSO login."""

    user_id: str
    email: str
    name: Optional[str] = None
    organization_id: Optional[str] = None
    is_new_user: bool = False


class SSOCallbackResponse(BaseModel):
    """Response from SSO callback (login success)."""

    token: str
    user: SSOUserInfo
    expires_in: int
    idp: str
    refresh_available: bool = False


class SSORefreshResponse(BaseModel):
    """Response from SSO session refresh."""

    token: str
    expires_in: int
    idp: str
    refreshed_at: str


class SSOLogoutRequest(BaseModel):
    """Optional request body for logout."""

    post_logout_redirect_uri: Optional[str] = None


class SSOLogoutResponse(BaseModel):
    """Response from SSO logout."""

    logout_url: Optional[str] = None
    message: str
