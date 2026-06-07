"""Evaluate Available To visibility for catalog entries and templates."""

from __future__ import annotations

from app.services.role_resolver import UserContext


class AvailableToEvaluator:
    """CR-2: visible if role OR group OR user matches; empty all three = nobody."""

    def is_visible(
        self,
        available_to_roles: list[str] | None,
        available_to_groups: list[str] | None,
        available_to_users: list[str] | None,
        user: UserContext,
    ) -> bool:
        roles = [r.lower() for r in (available_to_roles or [])]
        groups = available_to_groups or []
        users = available_to_users or []

        if not roles and not groups and not users:
            return False

        if "all" in roles:
            return True

        user_roles = {r.lower() for r in user.roles}
        if roles and user_roles.intersection(roles):
            return True

        user_groups = set(user.groups)
        if groups and user_groups.intersection(groups):
            return True

        if users and user.sub in users:
            return True

        return False
