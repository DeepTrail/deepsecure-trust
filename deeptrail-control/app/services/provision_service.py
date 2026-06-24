"""Composite agent provisioning service with atomic rollback.

Handles the full provisioning flow in a single transaction:
  1. Register agent (insert into agents table)
  2. Set agent config (tagged_prompts, operational params)
  3. Create delegation template
  4. Resume Cloud Scheduler (if slot-based, best-effort)

If any step except scheduler resume fails, the entire transaction rolls back.
Scheduler resume failure is non-fatal: the agent is created but paused.
"""

import json
import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import Agent
from app.models.delegation_template import DelegationTemplate

logger = logging.getLogger(__name__)


class ProvisionError(Exception):
    """Raised when provisioning fails (triggers rollback)."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AgentProvisionService:
    def __init__(self, db: Session):
        self.db = db

    def provision(
        self,
        agent_name: str,
        agent_description: Optional[str],
        platform: str,
        selector: str,
        config: dict,
        template_max_permissions: list[str],
        template_default_ttl_days: int = 7,
        template_available_to_roles: Optional[list[str]] = None,
        admin_email: str = "",
    ) -> dict:
        """Atomically provision an agent: register + config + template.

        Returns dict with keys: agent, config, delegation_template, scheduler_resumed, warning.
        Raises ProvisionError on validation/integrity failure (auto-rolls back).
        """
        if template_available_to_roles is None:
            template_available_to_roles = ["all"]

        existing = self.db.query(Agent).filter(Agent.selector == selector).first()
        if existing:
            raise ProvisionError(
                f"Agent with selector '{selector}' already exists (agent_id={existing.agent_id})",
                status_code=409,
            )

        try:
            agent_id = f"agent-{uuid.uuid4().hex[:12]}"
            agent = Agent(
                agent_id=agent_id,
                name=agent_name,
                description=agent_description,
                platform=platform,
                selector=selector,
                config=config,
                created_by=admin_email,
                owner_user_id=admin_email,
            )
            self.db.add(agent)
            self.db.flush()

            template = DelegationTemplate(
                agent_id=agent_id,
                max_permissions=template_max_permissions,
                default_ttl_days=template_default_ttl_days,
                available_to_roles=template_available_to_roles,
                created_by=admin_email,
            )
            self.db.add(template)
            self.db.flush()

            scheduler_resumed = self._resume_scheduler(selector)
            warning = None
            if not scheduler_resumed and self._is_known_slot(selector):
                warning = "Agent created but scheduler could not be resumed. Check IAM permissions."

            self.db.commit()
            self.db.refresh(agent)
            self.db.refresh(template)

            return {
                "agent": {
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "description": agent.description,
                    "platform": agent.platform,
                    "selector": agent.selector,
                    "created_by": agent.created_by,
                    "created_at": agent.created_at.isoformat() if agent.created_at else None,
                },
                "config": config,
                "delegation_template": {
                    "id": str(template.id),
                    "agent_id": template.agent_id,
                    "max_permissions": template.max_permissions,
                    "default_ttl_days": template.default_ttl_days,
                    "available_to_roles": template.available_to_roles,
                    "created_by": template.created_by,
                },
                "scheduler_resumed": scheduler_resumed,
                "warning": warning,
            }

        except ProvisionError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            logger.error("Provision failed: %s", exc, exc_info=True)
            raise ProvisionError(f"Provisioning failed: {exc}", status_code=500) from exc

    def _get_slots(self) -> list[dict]:
        raw = settings.AGENT_SLOTS_JSON
        try:
            return json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            return []

    def _is_known_slot(self, selector: str) -> bool:
        return any(s.get("sa_email") == selector for s in self._get_slots())

    def _resume_scheduler(self, selector: str) -> bool:
        """Resume the paused Cloud Scheduler for a slot matching this selector."""
        slots = self._get_slots()
        slot = next((s for s in slots if s.get("sa_email") == selector), None)
        if not slot:
            return False

        try:
            from google.cloud import scheduler_v1

            client = scheduler_v1.CloudSchedulerClient()
            name = (
                f"projects/{settings.GCP_PROJECT}"
                f"/locations/{settings.GCP_REGION}"
                f"/jobs/{slot['scheduler_name']}"
            )
            client.resume_job(name=name)
            logger.info("Resumed scheduler: %s", slot["scheduler_name"])
            return True
        except ImportError:
            logger.warning("google-cloud-scheduler not installed — skipping resume")
            return False
        except Exception as exc:
            logger.warning("Scheduler resume failed for %s: %s", slot.get("scheduler_name"), exc)
            return False
