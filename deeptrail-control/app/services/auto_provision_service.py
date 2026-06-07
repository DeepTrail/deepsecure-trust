"""Auto-provision delegations from templates on SSO login."""

from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_event import AuditEventType
from app.models.delegation_template import DelegationTemplate
from app.services.audit_logger_service import AuditLoggerService
from app.services.available_to import AvailableToEvaluator
from app.services.delegation_service import DelegationService
from app.services.role_resolver import RoleResolver, UserContext

logger = logging.getLogger(__name__)


class AutoProvisionService:
    """Provision template delegations for eligible users at SSO login."""

    def __init__(self, db_session: Session):
        self._db = db_session
        self._delegation_service = DelegationService(db_session)
        self._evaluator = AvailableToEvaluator()
        self._role_resolver = RoleResolver()

    def provision_for_user(
        self,
        *,
        user_email: str,
        jwt_roles: List[str] | None = None,
        groups: List[str] | None = None,
    ) -> List[str]:
        """Create delegations for matching auto-provision templates.

        Returns list of created delegation IDs.
        """
        if not settings.DELEGATION_AUTO_PROVISION:
            return []

        user_ctx = self._role_resolver.resolve_context(
            sub=user_email,
            jwt_roles=jwt_roles or [],
            groups=groups or [],
            db=self._db,
        )

        templates = (
            self._db.query(DelegationTemplate)
            .filter(
                DelegationTemplate.auto_provision.is_(True),
                DelegationTemplate.provision_mode == "on_login",
            )
            .all()
        )

        created_ids: List[str] = []
        for template in templates:
            if not self._is_visible(template, user_ctx):
                continue

            delegation = self._delegation_service.create_template_delegation(
                user_email,
                template,
                source="template",
            )
            if delegation is None:
                continue

            created_ids.append(delegation.id)
            AuditLoggerService(self._db).log_event(
                event_type=AuditEventType.DELEGATION_AUTO_PROVISIONED,
                on_behalf_of=user_email,
                agent_id=template.agent_id,
                delegation_id=delegation.id,
                extra_data={
                    "template_id": str(template.id),
                    "permissions": delegation.delegated_permissions,
                },
            )

        if created_ids:
            self._db.commit()
            logger.info(
                "Auto-provisioned %d delegation(s) for %s",
                len(created_ids),
                user_email,
            )

        return created_ids

    def _is_visible(self, template: DelegationTemplate, user: UserContext) -> bool:
        return self._evaluator.is_visible(
            template.available_to_roles,
            getattr(template, "available_to_groups", None),
            getattr(template, "available_to_users", None),
            user,
        )
