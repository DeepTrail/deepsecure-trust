"""Group-to-role policy mapper with YAML-driven configuration.

Maps IdP group names (from Keycloak ID tokens or Google Directory API)
to internal DeepTrail roles and default delegation permission templates.

Replaces the static ``_GROUP_TO_ROLE_MAP`` dict in ``idp_service.py`` with a
configurable, YAML-driven approach that also maps groups to default permissions.

Usage::

    mapper = GroupPolicyMapper.from_yaml("group_policies.yaml")
    result = mapper.resolve(["engineering@deeptrail.com", "sales@deeptrail.com"])
    # result.roles           -> ["engineer", "sales"]
    # result.default_permissions -> ["github:repos:read", "jira:issues:read", ...]
    # result.matched_groups  -> ["engineering@deeptrail.com", "sales@deeptrail.com"]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class GroupPolicy:
    """A single group-to-role-and-permissions mapping."""

    group: str
    role: str
    default_permissions: list[str] = field(default_factory=list)
    max_delegatable: list[str] | None = None


@dataclass
class GroupPolicyResult:
    """Merged result of resolving one or more groups against the policy set."""

    roles: list[str] = field(default_factory=list)
    default_permissions: list[str] = field(default_factory=list)
    matched_groups: list[str] = field(default_factory=list)


class GroupPolicyMapper:
    """Resolves IdP group names to DeepTrail roles and permissions.

    Policies are indexed by group name for O(1) lookup.
    """

    def __init__(self, policies: list[GroupPolicy]) -> None:
        self._policies: dict[str, GroupPolicy] = {p.group: p for p in policies}

    @classmethod
    def from_yaml(cls, path: str | Path) -> GroupPolicyMapper:
        """Load policies from a YAML configuration file.

        Raises:
            FileNotFoundError: If *path* does not exist.
            yaml.YAMLError: If *path* contains invalid YAML.
            KeyError: If required keys are missing from the YAML structure.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Group policy file not found: {path}")

        with open(path) as fh:
            data = yaml.safe_load(fh)

        raw_policies = data["policies"]
        policies = [
            GroupPolicy(
                group=entry["group"],
                role=entry["role"],
                default_permissions=entry.get("default_permissions", []),
                max_delegatable=entry.get("max_delegatable"),
            )
            for entry in raw_policies
        ]
        return cls(policies)

    def resolve(self, groups: list[str]) -> GroupPolicyResult:
        """Resolve a list of group names to merged roles and permissions.

        Unknown groups are silently ignored.  Roles and permissions are
        deduplicated while preserving insertion order.
        """
        seen_roles: dict[str, None] = {}
        seen_perms: dict[str, None] = {}
        matched: list[str] = []

        for group in groups:
            policy = self._policies.get(group)
            if policy is None:
                continue
            matched.append(group)
            if policy.role not in seen_roles:
                seen_roles[policy.role] = None
            for perm in policy.default_permissions:
                if perm not in seen_perms:
                    seen_perms[perm] = None

        return GroupPolicyResult(
            roles=list(seen_roles),
            default_permissions=list(seen_perms),
            matched_groups=matched,
        )
