"""Admin role management endpoints.

POST /api/v1/admin/users/{user_id}/role — Set a user's role
GET  /api/v1/admin/users/me — Get current admin's profile (with role)

Protected by require_admin middleware.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.middleware.admin_auth import require_admin
from app.models.user_session import UserSession

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_ROLES = {"employee", "admin", "security"}


class SetRoleRequest(BaseModel):
    role: str = Field(..., description="New role: 'employee', 'admin', or 'security'")


class SetRoleResponse(BaseModel):
    user_id: str
    role: str
    message: str


class AdminProfileResponse(BaseModel):
    user_id: str
    role: str
    session_id: str


@router.post(
    "/users/{user_id}/role",
    response_model=SetRoleResponse,
    dependencies=[Depends(require_admin)],
)
def set_user_role(
    user_id: str,
    body: SetRoleRequest,
    db: Session = Depends(get_db),
) -> SetRoleResponse:
    """Set the role for a specific user.

    Only admins can change roles. Valid roles: employee, admin, security.
    Updates the most recent active session for the user.
    """
    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{body.role}'. Must be one of: {sorted(VALID_ROLES)}",
        )

    session = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        .order_by(UserSession.created_at.desc())
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active session found for user '{user_id}'",
        )

    session.role = body.role
    db.commit()

    logger.info("Role updated: user=%s role=%s", user_id, body.role)
    return SetRoleResponse(
        user_id=user_id,
        role=body.role,
        message=f"Role updated to '{body.role}'",
    )


@router.get(
    "/users/me",
    response_model=AdminProfileResponse,
)
def get_admin_profile(
    claims: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminProfileResponse:
    """Get the current admin user's profile with role information."""
    user_id = claims.get("sub", "")
    session = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        .order_by(UserSession.created_at.desc())
        .first()
    )

    role = "admin"
    session_id = ""
    if session:
        role = getattr(session, "role", "admin")
        session_id = session.session_id

    return AdminProfileResponse(
        user_id=user_id,
        role=role,
        session_id=session_id,
    )
