"""Delegation-based prompt validation for RBAC.

Validates that all service tags in a prompt are covered by the user's
active delegations to the target agent. Used by prompt CRUD endpoints
to enforce that employees can only add prompts for services they have
been delegated access to.
"""

from typing import List, Set, Tuple

from sqlalchemy.orm import Session

from app.models.delegation import DelegationToken


def get_user_delegations_for_agent(
    db: Session, user_email: str, agent_id: str
) -> List[DelegationToken]:
    """Fetch active (non-revoked, non-expired) delegations for a user+agent pair."""
    delegations = (
        db.query(DelegationToken)
        .filter(
            DelegationToken.agent_id == agent_id,
            DelegationToken.delegator == user_email,
            DelegationToken.revoked_at.is_(None),
        )
        .all()
    )
    return [d for d in delegations if d.is_valid]


def get_delegated_services(delegations: List[DelegationToken]) -> Set[str]:
    """Extract unique service IDs from delegation permissions."""
    services: Set[str] = set()
    for d in delegations:
        perms = d.delegated_permissions if isinstance(d.delegated_permissions, list) else []
        for perm in perms:
            if ":" in perm:
                services.add(perm.split(":")[0])
    return services


def validate_prompt_services(
    delegations: List[DelegationToken],
    prompt_services: str,
) -> Tuple[bool, Set[str]]:
    """Validate that all service tags in a prompt are covered by user's delegations.

    Args:
        delegations: Active delegations for the user+agent pair.
        prompt_services: Comma-separated service IDs from the prompt.

    Returns:
        Tuple of (is_valid, missing_services).
        is_valid is True when all requested services are covered.
    """
    required = {s.strip() for s in prompt_services.split(",") if s.strip()}
    delegated = get_delegated_services(delegations)
    missing = required - delegated
    return (len(missing) == 0, missing)
