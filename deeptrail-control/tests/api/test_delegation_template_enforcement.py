"""Tests for delegation template ceiling enforcement.

Verifies that create_delegation rejects permissions that exceed
the admin-configured template ceiling or are explicitly blocked.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.delegation_template import DelegationTemplate
from app.services.delegation_service import DelegationService, PermissionValidationError


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def delegation_service(mock_db):
    return DelegationService(mock_db)


def _make_template(
    agent_id: str,
    max_permissions: list[str],
    blocked_permissions: list[str] | None = None,
) -> DelegationTemplate:
    t = DelegationTemplate()
    t.id = str(uuid.uuid4())
    t.agent_id = agent_id
    t.max_permissions = max_permissions
    t.blocked_permissions = blocked_permissions or []
    t.default_ttl_days = 7
    t.available_to_roles = ["all"]
    t.created_at = datetime.now(timezone.utc)
    t.updated_at = datetime.now(timezone.utc)
    return t


class TestTemplateCeilingEnforcement:
    """Template enforcement in create_delegation."""

    def test_rejects_over_ceiling_permissions(self, delegation_service, mock_db):
        """Permissions outside max_permissions are rejected."""
        agent_id = "agent-ceiling"
        template = _make_template(
            agent_id, ["notion:pages:read", "notion:pages:search"]
        )

        # Mock the template query
        query = MagicMock()
        query.filter.return_value.first.return_value = template
        mock_db.query.return_value = query

        # Also mock permission validation to pass
        with patch.object(
            delegation_service,
            "_validate_permissions_subset",
            return_value=(True, None, [], []),
        ):
            with pytest.raises(PermissionValidationError) as exc_info:
                delegation_service.create_delegation(
                    delegator="user@acme.com",
                    agent_id=agent_id,
                    permissions=["notion:pages:read", "notion:pages:write"],
                )
            assert "exceed" in str(exc_info.value).lower() or "ceiling" in str(
                exc_info.value
            ).lower()
            assert "notion:pages:write" in str(exc_info.value)

    def test_rejects_blocked_permissions(self, delegation_service, mock_db):
        """Explicitly blocked permissions are rejected."""
        agent_id = "agent-blocked"
        template = _make_template(
            agent_id,
            ["notion:pages:read", "notion:pages:delete"],
            blocked_permissions=["notion:pages:delete"],
        )

        query = MagicMock()
        query.filter.return_value.first.return_value = template
        mock_db.query.return_value = query

        with patch.object(
            delegation_service,
            "_validate_permissions_subset",
            return_value=(True, None, [], []),
        ):
            with pytest.raises(PermissionValidationError) as exc_info:
                delegation_service.create_delegation(
                    delegator="user@acme.com",
                    agent_id=agent_id,
                    permissions=["notion:pages:delete"],
                )
            assert "blocked" in str(exc_info.value).lower()

    def test_allows_within_ceiling(self, delegation_service, mock_db):
        """Permissions within ceiling are accepted."""
        agent_id = "agent-allowed"
        template = _make_template(
            agent_id, ["notion:pages:read", "notion:pages:search"]
        )

        query = MagicMock()
        query.filter.return_value.first.return_value = template
        mock_db.query.return_value = query

        with patch.object(
            delegation_service,
            "_validate_permissions_subset",
            return_value=(True, None, [], []),
        ), patch.object(
            delegation_service, "get_active_delegation", return_value=None
        ):
            delegation = delegation_service.create_delegation(
                delegator="user@acme.com",
                agent_id=agent_id,
                permissions=["notion:pages:read"],
            )
            assert delegation is not None

    def test_no_template_allows_all(self, delegation_service, mock_db):
        """Without a template, all valid permissions are allowed."""
        agent_id = "agent-no-template"

        query = MagicMock()
        query.filter.return_value.first.return_value = None
        mock_db.query.return_value = query

        with patch.object(
            delegation_service,
            "_validate_permissions_subset",
            return_value=(True, None, [], []),
        ), patch.object(
            delegation_service, "get_active_delegation", return_value=None
        ):
            delegation = delegation_service.create_delegation(
                delegator="user@acme.com",
                agent_id=agent_id,
                permissions=["anything:goes:here"],
            )
            assert delegation is not None
