"""Admin settings endpoints.

GET  /api/v1/admin/settings/delegation-policy — Get delegation policy
PUT  /api/v1/admin/settings/delegation-policy — Update delegation policy
GET  /api/v1/settings/delegation-policy         — Public read-only
"""

import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.middleware.admin_auth import require_admin
from app.models.org_settings import OrgSettings

logger = logging.getLogger(__name__)

router = APIRouter()
public_router = APIRouter()

DELEGATION_POLICY_KEY = "delegation_policy"
DEFAULT_DELEGATION_POLICY = {"allow_freeform": False}


class DelegationPolicyResponse(BaseModel):
    allow_freeform: bool


class DelegationPolicyUpdate(BaseModel):
    allow_freeform: bool


def _get_delegation_policy(db: Session) -> dict:
    row = db.query(OrgSettings).filter(OrgSettings.key == DELEGATION_POLICY_KEY).first()
    if row and row.value:
        return row.value
    return DEFAULT_DELEGATION_POLICY


@router.get(
    "/settings/delegation-policy",
    response_model=DelegationPolicyResponse,
    dependencies=[Depends(require_admin)],
)
def get_delegation_policy_admin(db: Session = Depends(get_db)):
    policy = _get_delegation_policy(db)
    return DelegationPolicyResponse(allow_freeform=policy.get("allow_freeform", False))


@router.put(
    "/settings/delegation-policy",
    response_model=DelegationPolicyResponse,
    dependencies=[Depends(require_admin)],
)
def update_delegation_policy(body: DelegationPolicyUpdate, db: Session = Depends(get_db)):
    row = db.query(OrgSettings).filter(OrgSettings.key == DELEGATION_POLICY_KEY).first()
    if row:
        row.value = {"allow_freeform": body.allow_freeform}
    else:
        row = OrgSettings(key=DELEGATION_POLICY_KEY, value={"allow_freeform": body.allow_freeform})
        db.add(row)
    db.commit()
    logger.info("Delegation policy updated: allow_freeform=%s", body.allow_freeform)
    return DelegationPolicyResponse(allow_freeform=body.allow_freeform)


@public_router.get(
    "/settings/delegation-policy",
    response_model=DelegationPolicyResponse,
)
def get_delegation_policy_public(db: Session = Depends(get_db)):
    """Read-only access to delegation policy for all authenticated users."""
    policy = _get_delegation_policy(db)
    return DelegationPolicyResponse(allow_freeform=policy.get("allow_freeform", False))
