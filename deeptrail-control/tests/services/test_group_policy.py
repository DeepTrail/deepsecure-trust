"""Tests for GroupPolicyMapper.

Covers:
- GroupPolicy / GroupPolicyResult dataclass contracts
- YAML loading (valid, missing, malformed)
- resolve() with empty, single, multiple, unknown, and mixed groups
- Deduplication of roles and permissions
"""

import textwrap
from pathlib import Path

import pytest
import yaml

from app.services.group_policy import GroupPolicy, GroupPolicyMapper, GroupPolicyResult


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def sample_policies() -> list[GroupPolicy]:
    return [
        GroupPolicy(
            group="engineering@deeptrail.com",
            role="engineer",
            default_permissions=["github:repos:read", "jira:issues:read", "gdrive:files:read"],
        ),
        GroupPolicy(
            group="sales@deeptrail.com",
            role="sales",
            default_permissions=["notion:pages:search", "notion:pages:read", "slack:channels:list"],
        ),
        GroupPolicy(
            group="acme-org",
            role="user",
            default_permissions=["notion:pages:search", "notion:pages:read"],
        ),
    ]


@pytest.fixture()
def mapper(sample_policies: list[GroupPolicy]) -> GroupPolicyMapper:
    return GroupPolicyMapper(sample_policies)


@pytest.fixture()
def yaml_file(tmp_path: Path) -> Path:
    content = textwrap.dedent("""\
        policies:
          - group: "eng@corp.com"
            role: "engineer"
            default_permissions:
              - "github:repos:read"
          - group: "ops@corp.com"
            role: "ops"
            default_permissions:
              - "aws:ec2:list"
    """)
    p = tmp_path / "policies.yaml"
    p.write_text(content)
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Test: GroupPolicy dataclass
# ─────────────────────────────────────────────────────────────────────────────


class TestGroupPolicyDataclass:

    def test_required_fields(self):
        policy = GroupPolicy(group="g1", role="admin")
        assert policy.group == "g1"
        assert policy.role == "admin"

    def test_default_permissions_empty(self):
        policy = GroupPolicy(group="g1", role="admin")
        assert policy.default_permissions == []

    def test_max_delegatable_defaults_to_none(self):
        policy = GroupPolicy(group="g1", role="admin")
        assert policy.max_delegatable is None

    def test_max_delegatable_set(self):
        policy = GroupPolicy(
            group="g1",
            role="admin",
            max_delegatable=["notion:pages:read"],
        )
        assert policy.max_delegatable == ["notion:pages:read"]

    def test_frozen(self):
        policy = GroupPolicy(group="g1", role="admin")
        with pytest.raises(AttributeError):
            policy.group = "g2"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Test: GroupPolicyResult dataclass
# ─────────────────────────────────────────────────────────────────────────────


class TestGroupPolicyResultDataclass:

    def test_defaults_empty(self):
        result = GroupPolicyResult()
        assert result.roles == []
        assert result.default_permissions == []
        assert result.matched_groups == []

    def test_custom_values(self):
        result = GroupPolicyResult(
            roles=["admin"],
            default_permissions=["a:b:c"],
            matched_groups=["g1"],
        )
        assert result.roles == ["admin"]
        assert result.default_permissions == ["a:b:c"]
        assert result.matched_groups == ["g1"]


# ─────────────────────────────────────────────────────────────────────────────
# Test: from_yaml
# ─────────────────────────────────────────────────────────────────────────────


class TestFromYaml:

    def test_loads_valid_file(self, yaml_file: Path):
        mapper = GroupPolicyMapper.from_yaml(yaml_file)
        assert len(mapper._policies) == 2

    def test_loaded_policies_correct(self, yaml_file: Path):
        mapper = GroupPolicyMapper.from_yaml(yaml_file)
        result = mapper.resolve(["eng@corp.com"])
        assert result.roles == ["engineer"]
        assert "github:repos:read" in result.default_permissions

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            GroupPolicyMapper.from_yaml("/nonexistent/path/policies.yaml")

    def test_invalid_yaml_raises(self, tmp_path: Path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("policies:\n  - [invalid: yaml: {{{")
        with pytest.raises(yaml.YAMLError):
            GroupPolicyMapper.from_yaml(bad)

    def test_accepts_string_path(self, yaml_file: Path):
        mapper = GroupPolicyMapper.from_yaml(str(yaml_file))
        assert len(mapper._policies) == 2

    def test_optional_fields_default(self, tmp_path: Path):
        content = textwrap.dedent("""\
            policies:
              - group: "minimal"
                role: "viewer"
        """)
        p = tmp_path / "minimal.yaml"
        p.write_text(content)
        mapper = GroupPolicyMapper.from_yaml(p)
        result = mapper.resolve(["minimal"])
        assert result.roles == ["viewer"]
        assert result.default_permissions == []


# ─────────────────────────────────────────────────────────────────────────────
# Test: resolve
# ─────────────────────────────────────────────────────────────────────────────


class TestResolve:

    def test_empty_groups(self, mapper: GroupPolicyMapper):
        result = mapper.resolve([])
        assert result.roles == []
        assert result.default_permissions == []
        assert result.matched_groups == []

    def test_unknown_group_returns_empty(self, mapper: GroupPolicyMapper):
        result = mapper.resolve(["nonexistent-group"])
        assert result.roles == []
        assert result.default_permissions == []
        assert result.matched_groups == []

    def test_single_keycloak_group(self, mapper: GroupPolicyMapper):
        result = mapper.resolve(["acme-org"])
        assert result.roles == ["user"]
        assert "notion:pages:search" in result.default_permissions
        assert "notion:pages:read" in result.default_permissions
        assert result.matched_groups == ["acme-org"]

    def test_single_google_group(self, mapper: GroupPolicyMapper):
        result = mapper.resolve(["engineering@deeptrail.com"])
        assert result.roles == ["engineer"]
        assert "github:repos:read" in result.default_permissions
        assert "jira:issues:read" in result.default_permissions
        assert "gdrive:files:read" in result.default_permissions
        assert result.matched_groups == ["engineering@deeptrail.com"]

    def test_multiple_groups_merged(self, mapper: GroupPolicyMapper):
        result = mapper.resolve(["engineering@deeptrail.com", "sales@deeptrail.com"])
        assert "engineer" in result.roles
        assert "sales" in result.roles
        assert "github:repos:read" in result.default_permissions
        assert "slack:channels:list" in result.default_permissions
        assert len(result.matched_groups) == 2

    def test_mixed_known_unknown_groups(self, mapper: GroupPolicyMapper):
        result = mapper.resolve(["acme-org", "nonexistent", "engineering@deeptrail.com"])
        assert len(result.matched_groups) == 2
        assert "acme-org" in result.matched_groups
        assert "engineering@deeptrail.com" in result.matched_groups
        assert "nonexistent" not in result.matched_groups

    def test_roles_deduplicated(self):
        policies = [
            GroupPolicy(group="g1", role="user", default_permissions=["a:b:c"]),
            GroupPolicy(group="g2", role="user", default_permissions=["d:e:f"]),
        ]
        mapper = GroupPolicyMapper(policies)
        result = mapper.resolve(["g1", "g2"])
        assert result.roles == ["user"]

    def test_permissions_deduplicated(self):
        policies = [
            GroupPolicy(group="g1", role="r1", default_permissions=["a:b:c", "d:e:f"]),
            GroupPolicy(group="g2", role="r2", default_permissions=["a:b:c", "x:y:z"]),
        ]
        mapper = GroupPolicyMapper(policies)
        result = mapper.resolve(["g1", "g2"])
        assert len(result.default_permissions) == 3
        assert "a:b:c" in result.default_permissions
        assert "d:e:f" in result.default_permissions
        assert "x:y:z" in result.default_permissions

    def test_insertion_order_preserved(self):
        policies = [
            GroupPolicy(group="g1", role="alpha", default_permissions=["z:z:z", "a:a:a"]),
            GroupPolicy(group="g2", role="beta", default_permissions=["m:m:m"]),
        ]
        mapper = GroupPolicyMapper(policies)
        result = mapper.resolve(["g1", "g2"])
        assert result.roles == ["alpha", "beta"]
        assert result.default_permissions == ["z:z:z", "a:a:a", "m:m:m"]


# ─────────────────────────────────────────────────────────────────────────────
# Test: Integration with shipped YAML
# ─────────────────────────────────────────────────────────────────────────────


class TestShippedYaml:
    """Verify the bundled group_policies.yaml loads correctly."""

    @pytest.fixture()
    def shipped_mapper(self) -> GroupPolicyMapper:
        yaml_path = Path(__file__).resolve().parents[2] / "group_policies.yaml"
        return GroupPolicyMapper.from_yaml(yaml_path)

    def test_loads_three_policies(self, shipped_mapper: GroupPolicyMapper):
        assert len(shipped_mapper._policies) == 3

    def test_engineering_group(self, shipped_mapper: GroupPolicyMapper):
        result = shipped_mapper.resolve(["engineering@deeptrail.com"])
        assert result.roles == ["engineer"]
        assert "gdrive:files:read" in result.default_permissions

    def test_sales_group(self, shipped_mapper: GroupPolicyMapper):
        result = shipped_mapper.resolve(["sales@deeptrail.com"])
        assert result.roles == ["sales"]
        assert "gcalendar:events:list" in result.default_permissions

    def test_acme_group(self, shipped_mapper: GroupPolicyMapper):
        result = shipped_mapper.resolve(["acme-org"])
        assert result.roles == ["user"]
