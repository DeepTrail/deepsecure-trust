"""Cross-mapper consistency tests.

Validates alignment across the four sources of truth for tool/permission
definitions:

1. ScopeMapper (control plane) — maps OAuth scopes to permission strings
2. PermissionMapper (gateway) — maps tool names to permission strings
3. tool_definitions.py (gateway) — defines tool schemas (CachedTool)
4. Backend clients (gateway) — implement tool execution

Any drift between these four creates discrepancies visible in the UI:
tools that can be delegated but not executed, tools with degraded schemas,
or permissions that map to nothing.
"""

import importlib
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = ROOT / "deeptrail-gateway"
CONTROL = ROOT / "deeptrail-control"

for p in (GATEWAY, CONTROL):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _import_permission_mapper():
    mod = importlib.import_module("app.mcp.permission_mapper")
    return mod.PermissionMapper


def _import_tool_definitions():
    return importlib.import_module("app.mcp.tool_definitions")


def _import_scope_mapper():
    mod = importlib.import_module("app.services.scope_mapper")
    return mod.ScopeMapper


KNOWN_REST_SERVICES = {"notion", "slack", "gdrive", "gcalendar", "gmail", "github"}

PERMISSION_FORMAT = re.compile(r"^[a-z]+:[a-z_]+:[a-z_]+$")


class TestPermissionMapperToolDefsAlignment:
    """Every tool in PermissionMapper must have a schema in tool_definitions.py."""

    def test_every_mapped_tool_has_schema(self):
        PM = _import_permission_mapper()
        td = _import_tool_definitions()

        all_defs = td.get_all_tool_definitions()
        tool_names_in_defs = set()
        for backend_id, tools in all_defs.items():
            for tool in tools:
                tool_names_in_defs.add(f"{backend_id}.{tool.name}")

        for tool_name in PM.get_all_tools():
            backend = tool_name.split(".")[0]
            if backend not in KNOWN_REST_SERVICES:
                continue
            assert tool_name in tool_names_in_defs, (
                f"Tool '{tool_name}' is in PermissionMapper but has no schema "
                f"in tool_definitions.py — this creates a 'dark tool' with degraded schema"
            )

    def test_every_defined_tool_has_permission_mapping(self):
        PM = _import_permission_mapper()
        td = _import_tool_definitions()

        all_defs = td.get_all_tool_definitions()
        for backend_id, tools in all_defs.items():
            for tool in tools:
                namespaced = f"{backend_id}.{tool.name}"
                perm = PM.get_permission(namespaced)
                assert perm is not None, (
                    f"Tool '{namespaced}' is in tool_definitions.py but has no "
                    f"permission mapping — agents cannot be granted access"
                )


class TestScopeMapperPermissionMapperAlignment:
    """Every REST permission in PermissionMapper should be reachable via ScopeMapper."""

    def test_rest_permissions_reachable_from_scopes(self):
        PM = _import_permission_mapper()
        SM = _import_scope_mapper()

        all_scope_perms = SM.get_all_known_permissions()

        for tool_name, perm in PM.TOOL_TO_PERMISSION.items():
            backend = tool_name.split(".")[0]
            if backend not in KNOWN_REST_SERVICES:
                continue
            assert perm in all_scope_perms, (
                f"Permission '{perm}' (for tool '{tool_name}') is not reachable "
                f"from any OAuth scope in ScopeMapper — users cannot delegate this tool"
            )


class TestPermissionStringFormat:
    """All permission strings should follow {service}:{resource}:{action} format."""

    def test_permission_mapper_format(self):
        PM = _import_permission_mapper()
        for tool_name, perm in PM.TOOL_TO_PERMISSION.items():
            assert PERMISSION_FORMAT.match(perm), (
                f"Permission '{perm}' (for tool '{tool_name}') does not follow "
                f"the canonical format {{service}}:{{resource}}:{{action}}"
            )

    def test_scope_mapper_format(self):
        SM = _import_scope_mapper()
        for perm in SM.get_all_known_permissions():
            assert PERMISSION_FORMAT.match(perm), (
                f"Permission '{perm}' in ScopeMapper does not follow "
                f"the canonical format {{service}}:{{resource}}:{{action}}"
            )


class TestToolDefinitionPermissions:
    """CachedTool.permission should match PermissionMapper entries."""

    def test_tool_permission_matches_mapper(self):
        PM = _import_permission_mapper()
        td = _import_tool_definitions()

        all_defs = td.get_all_tool_definitions()
        for backend_id, tools in all_defs.items():
            for tool in tools:
                if tool.permission is None:
                    continue
                namespaced = f"{backend_id}.{tool.name}"
                mapper_perm = PM.get_permission(namespaced)
                if mapper_perm is not None:
                    assert tool.permission == mapper_perm, (
                        f"Tool '{namespaced}' has permission='{tool.permission}' "
                        f"but PermissionMapper says '{mapper_perm}' — these must match"
                    )


class TestBackendClientDispatchers:
    """Tool names in backend client dispatchers should match tool_definitions."""

    @pytest.mark.parametrize("backend_id,module_name,class_name", [
        ("notion", "app.backends.notion_client", "NotionDirectClient"),
        ("slack", "app.backends.slack_client", "SlackDirectClient"),
        ("gdrive", "app.backends.gdrive_client", "GDriveDirectClient"),
        ("gcalendar", "app.backends.gcalendar_client", "GCalendarDirectClient"),
        ("gmail", "app.backends.gmail_client", "GmailDirectClient"),
        ("github", "app.backends.github_client", "GitHubDirectClient"),
    ])
    def test_client_handles_all_defined_tools(self, backend_id, module_name, class_name):
        td = _import_tool_definitions()

        all_defs = td.get_all_tool_definitions()
        if backend_id not in all_defs:
            pytest.skip(f"No tool definitions for {backend_id}")

        try:
            mod = importlib.import_module(module_name)
        except ImportError:
            pytest.skip(f"Client module {module_name} not found")

        client_cls = getattr(mod, class_name)
        source = importlib.import_module(module_name).__file__
        if source is None:
            pytest.skip(f"Cannot read source for {module_name}")

        source_text = Path(source).read_text()

        for tool in all_defs[backend_id]:
            assert tool.name in source_text, (
                f"Tool '{tool.name}' is defined in tool_definitions[{backend_id}] but "
                f"not found in {module_name} — the client cannot execute this tool"
            )
