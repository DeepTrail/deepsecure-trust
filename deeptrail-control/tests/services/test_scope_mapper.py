"""Unit tests for ScopeMapper.

Tests the mapping of OAuth scopes to DeepSecure permission strings.
"""

import pytest

from app.services.scope_mapper import ScopeMapper


class TestGetPermissionsForScope:
    """Test single scope → permissions."""
    
    def test_notion_read_pages(self):
        """Notion read_pages scope grants read, search, and blocks:read permissions."""
        perms = ScopeMapper.get_permissions_for_scope("notion", "read_pages")
        assert "notion:pages:read" in perms
        assert "notion:pages:search" in perms
        assert "notion:blocks:read" in perms
        assert len(perms) == 3
    
    def test_notion_read_content(self):
        """Notion read_content scope grants multiple permissions."""
        perms = ScopeMapper.get_permissions_for_scope("notion", "read_content")
        assert "notion:pages:read" in perms
        assert "notion:pages:search" in perms
        assert "notion:databases:list" in perms
        assert "notion:databases:query" in perms
    
    def test_notion_write_pages(self):
        """Notion write_pages scope grants create and update permissions."""
        perms = ScopeMapper.get_permissions_for_scope("notion", "write_pages")
        assert "notion:pages:create" in perms
        assert "notion:pages:update" in perms
    
    def test_slack_channels_read(self):
        """Slack channels:read scope grants list channels permission."""
        perms = ScopeMapper.get_permissions_for_scope("slack", "channels:read")
        assert perms == ["slack:channels:list"]
    
    def test_slack_chat_write(self):
        """Slack chat:write scope grants send messages permission."""
        perms = ScopeMapper.get_permissions_for_scope("slack", "chat:write")
        assert perms == ["slack:messages:send"]
    
    def test_unknown_scope_returns_empty(self):
        """Unknown scope returns empty list."""
        perms = ScopeMapper.get_permissions_for_scope("notion", "unknown_scope")
        assert perms == []
    
    def test_unknown_service_returns_empty(self):
        """Unknown service returns empty list."""
        perms = ScopeMapper.get_permissions_for_scope("unknown_service", "read_pages")
        assert perms == []
    
    def test_case_insensitive_service_id(self):
        """Service ID should be case-insensitive."""
        perms_lower = ScopeMapper.get_permissions_for_scope("notion", "read_pages")
        perms_upper = ScopeMapper.get_permissions_for_scope("NOTION", "read_pages")
        perms_mixed = ScopeMapper.get_permissions_for_scope("Notion", "read_pages")
        
        assert perms_lower == perms_upper == perms_mixed


class TestGetPermissionsForScopes:
    """Test multiple scopes → permissions."""
    
    def test_multiple_scopes_combined(self):
        """Multiple scopes combine their permissions."""
        perms = ScopeMapper.get_permissions_for_scopes(
            "notion", ["read_pages", "write_pages"]
        )
        # From read_pages
        assert "notion:pages:read" in perms
        assert "notion:pages:search" in perms
        # From write_pages
        assert "notion:pages:create" in perms
        assert "notion:pages:update" in perms
    
    def test_deduplication(self):
        """Overlapping permissions are deduplicated."""
        perms = ScopeMapper.get_permissions_for_scopes(
            "notion", ["read_pages", "search_content"]
        )
        # Both scopes grant notion:pages:search; read_pages also grants blocks:read
        assert "notion:pages:search" in perms
        assert "notion:pages:read" in perms
        assert "notion:blocks:read" in perms
        assert len(perms) == 3
    
    def test_empty_scopes(self):
        """Empty scope list returns empty set."""
        perms = ScopeMapper.get_permissions_for_scopes("notion", [])
        assert perms == set()
    
    def test_all_unknown_scopes(self):
        """All unknown scopes returns empty set."""
        perms = ScopeMapper.get_permissions_for_scopes(
            "notion", ["unknown1", "unknown2"]
        )
        assert perms == set()
    
    def test_mixed_known_unknown_scopes(self):
        """Mix of known and unknown scopes returns only known permissions."""
        perms = ScopeMapper.get_permissions_for_scopes(
            "notion", ["read_pages", "unknown_scope"]
        )
        assert "notion:pages:read" in perms
        assert "notion:pages:search" in perms
        assert "notion:blocks:read" in perms
        assert len(perms) == 3


class TestGetAllAllowedPermissions:
    """Test all allowed permissions across services."""
    
    def test_single_service(self):
        """Single service with single scope."""
        allowed = ScopeMapper.get_all_allowed_permissions([
            ("notion", ["read_pages"])
        ])
        assert "notion:pages:read" in allowed
        assert "notion:pages:search" in allowed
    
    def test_multiple_services(self):
        """Multiple services combine permissions."""
        allowed = ScopeMapper.get_all_allowed_permissions([
            ("notion", ["read_pages"]),
            ("slack", ["channels:read"]),
        ])
        assert "notion:pages:read" in allowed
        assert "notion:pages:search" in allowed
        assert "slack:channels:list" in allowed
    
    def test_empty_connected_services(self):
        """No connected services returns empty set."""
        allowed = ScopeMapper.get_all_allowed_permissions([])
        assert allowed == set()


class TestValidatePermissions:
    """Test permission validation."""
    
    def test_valid_permissions(self):
        """All requested permissions are valid."""
        is_valid, invalid = ScopeMapper.validate_permissions(
            ["notion:pages:search"],
            [("notion", ["read_pages"])],
        )
        assert is_valid is True
        assert invalid == []
    
    def test_invalid_permission(self):
        """Single invalid permission detected."""
        is_valid, invalid = ScopeMapper.validate_permissions(
            ["notion:pages:create"],  # Requires write scope
            [("notion", ["read_pages"])],  # Only read scope
        )
        assert is_valid is False
        assert "notion:pages:create" in invalid
    
    def test_mixed_valid_invalid(self):
        """Mix of valid and invalid returns only invalid ones."""
        is_valid, invalid = ScopeMapper.validate_permissions(
            ["notion:pages:search", "notion:pages:create"],
            [("notion", ["read_pages"])],
        )
        assert is_valid is False
        assert invalid == ["notion:pages:create"]
        assert "notion:pages:search" not in invalid
    
    def test_multiple_invalid_permissions(self):
        """Multiple invalid permissions all returned."""
        is_valid, invalid = ScopeMapper.validate_permissions(
            ["notion:pages:create", "notion:pages:delete", "slack:messages:send"],
            [("notion", ["read_pages"])],  # No write permissions, no Slack
        )
        assert is_valid is False
        assert len(invalid) == 3
        assert "notion:pages:create" in invalid
        assert "notion:pages:delete" in invalid
        assert "slack:messages:send" in invalid
    
    def test_cross_service_validation(self):
        """Validation works across multiple services."""
        is_valid, invalid = ScopeMapper.validate_permissions(
            ["notion:pages:search", "slack:channels:list"],
            [("notion", ["read_pages"]), ("slack", ["channels:read"])],
        )
        assert is_valid is True
        assert invalid == []
    
    def test_empty_requested_permissions(self):
        """Empty requested permissions are valid."""
        is_valid, invalid = ScopeMapper.validate_permissions(
            [],
            [("notion", ["read_pages"])],
        )
        assert is_valid is True
        assert invalid == []
    
    def test_no_connected_services(self):
        """All permissions invalid when no services connected."""
        is_valid, invalid = ScopeMapper.validate_permissions(
            ["notion:pages:search"],
            [],
        )
        assert is_valid is False
        assert invalid == ["notion:pages:search"]


class TestGetAvailablePermissionsByService:
    """Test available permissions helper."""
    
    def test_grouped_by_service(self):
        """Permissions grouped by service."""
        result = ScopeMapper.get_available_permissions_by_service([
            ("notion", ["read_pages"]),
            ("slack", ["channels:read"]),
        ])
        
        assert "notion" in result
        assert "slack" in result
        assert "notion:pages:read" in result["notion"]
        assert "notion:pages:search" in result["notion"]
        assert "slack:channels:list" in result["slack"]
    
    def test_single_service(self):
        """Single service returns single key."""
        result = ScopeMapper.get_available_permissions_by_service([
            ("notion", ["read_pages"]),
        ])
        
        assert list(result.keys()) == ["notion"]
        assert "notion:pages:read" in result["notion"]
    
    def test_permissions_are_sorted(self):
        """Permissions are sorted alphabetically."""
        result = ScopeMapper.get_available_permissions_by_service([
            ("notion", ["full_access"]),
        ])
        
        perms = result["notion"]
        assert perms == sorted(perms)
    
    def test_empty_connected_services(self):
        """Empty connected services returns empty dict."""
        result = ScopeMapper.get_available_permissions_by_service([])
        assert result == {}
    
    def test_unknown_service_excluded(self):
        """Unknown services are excluded from result."""
        result = ScopeMapper.get_available_permissions_by_service([
            ("unknown_service", ["some_scope"]),
        ])
        assert result == {}


class TestGetSupportedServices:
    """Test supported services listing."""
    
    def test_returns_all_services(self):
        """Returns all configured services."""
        services = ScopeMapper.get_supported_services()
        assert "notion" in services
        assert "slack" in services
    
    def test_exactly_six_services(self):
        """Supports notion, slack, gdrive, gcalendar, gmail, github."""
        services = ScopeMapper.get_supported_services()
        assert len(services) == 6
        assert "github" in services


class TestGetSupportedScopes:
    """Test supported scopes listing."""
    
    def test_notion_scopes(self):
        """Notion has expected scopes."""
        scopes = ScopeMapper.get_supported_scopes("notion")
        assert "read_content" in scopes
        assert "read_pages" in scopes
        assert "write_pages" in scopes
    
    def test_slack_scopes(self):
        """Slack has expected scopes."""
        scopes = ScopeMapper.get_supported_scopes("slack")
        assert "channels:read" in scopes
        assert "chat:write" in scopes
        assert "search:read" in scopes
    
    def test_unknown_service_returns_empty(self):
        """Unknown service returns empty list."""
        scopes = ScopeMapper.get_supported_scopes("unknown_service")
        assert scopes == []
    
    def test_case_insensitive(self):
        """Service ID is case-insensitive."""
        scopes_lower = ScopeMapper.get_supported_scopes("notion")
        scopes_upper = ScopeMapper.get_supported_scopes("NOTION")
        assert scopes_lower == scopes_upper


class TestGetAllPermissionsForService:
    """Test getting all permissions for a service."""
    
    def test_notion_all_permissions(self):
        """Notion has all expected permissions."""
        perms = ScopeMapper.get_all_permissions_for_service("notion")
        assert "notion:pages:read" in perms
        assert "notion:pages:search" in perms
        assert "notion:pages:create" in perms
        assert "notion:pages:update" in perms
        assert "notion:pages:delete" in perms
        assert "notion:databases:list" in perms
        assert "notion:databases:query" in perms
    
    def test_slack_all_permissions(self):
        """Slack has all expected permissions."""
        perms = ScopeMapper.get_all_permissions_for_service("slack")
        assert "slack:channels:list" in perms
        assert "slack:messages:search" in perms
        assert "slack:messages:send" in perms
        assert "slack:users:list" in perms
        assert "slack:reactions:write" in perms
    
    def test_unknown_service_returns_empty(self):
        """Unknown service returns empty set."""
        perms = ScopeMapper.get_all_permissions_for_service("unknown")
        assert perms == set()


class TestGoogleScopeMappings:
    """Test Google API scope mappings (gdrive, gcalendar, gmail)."""

    def test_gdrive_drive_readonly(self):
        """gdrive drive.readonly scope grants 4 read permissions."""
        perms = ScopeMapper.get_permissions_for_scope("gdrive", "drive.readonly")
        assert len(perms) == 4
        assert "gdrive:files:search" in perms
        assert "gdrive:files:read" in perms
        assert "gdrive:files:list" in perms
        assert "gdrive:files:metadata" in perms

    def test_gdrive_drive_file(self):
        """gdrive drive.file scope grants identical read-only permissions (MVP)."""
        readonly = ScopeMapper.get_permissions_for_scope("gdrive", "drive.readonly")
        file_scope = ScopeMapper.get_permissions_for_scope("gdrive", "drive.file")
        assert readonly == file_scope

    def test_gcalendar_calendar_readonly(self):
        """gcalendar calendar.readonly scope grants 3 permissions."""
        perms = ScopeMapper.get_permissions_for_scope("gcalendar", "calendar.readonly")
        assert len(perms) == 3
        assert "gcalendar:calendars:list" in perms
        assert "gcalendar:events:list" in perms
        assert "gcalendar:events:read" in perms

    def test_gcalendar_events_readonly(self):
        """gcalendar calendar.events.readonly scope grants 3 permissions."""
        perms = ScopeMapper.get_permissions_for_scope("gcalendar", "calendar.events.readonly")
        assert len(perms) == 3
        assert "gcalendar:events:list" in perms
        assert "gcalendar:events:read" in perms
        assert "gcalendar:events:search" in perms

    def test_gmail_readonly(self):
        """gmail gmail.readonly scope grants 4 permissions."""
        perms = ScopeMapper.get_permissions_for_scope("gmail", "gmail.readonly")
        assert len(perms) == 4
        assert "gmail:messages:list" in perms
        assert "gmail:messages:read" in perms
        assert "gmail:messages:search" in perms
        assert "gmail:labels:list" in perms

    def test_gdrive_unknown_scope(self):
        """Unknown gdrive scope returns empty list."""
        perms = ScopeMapper.get_permissions_for_scope("gdrive", "unknown")
        assert perms == []

    def test_google_services_in_supported_list(self):
        """All Google services appear in supported services."""
        services = ScopeMapper.get_supported_services()
        assert "gdrive" in services
        assert "gcalendar" in services
        assert "gmail" in services

    def test_gdrive_scopes_list(self):
        """gdrive has expected scopes."""
        scopes = ScopeMapper.get_supported_scopes("gdrive")
        assert "drive.readonly" in scopes
        assert "drive.file" in scopes

    def test_gcalendar_scopes_list(self):
        """gcalendar has expected scopes."""
        scopes = ScopeMapper.get_supported_scopes("gcalendar")
        assert "calendar.readonly" in scopes
        assert "calendar.events.readonly" in scopes

    def test_gmail_scopes_list(self):
        """gmail has expected scopes."""
        scopes = ScopeMapper.get_supported_scopes("gmail")
        assert "gmail.readonly" in scopes

    def test_google_permissions_format(self):
        """All Google permission strings follow service:resource:action format."""
        import re
        pattern = re.compile(r"^[a-z]+:[a-z]+:[a-z]+$")
        for svc in ["gdrive", "gcalendar", "gmail"]:
            for perms in ScopeMapper.SCOPE_TO_PERMISSIONS[svc].values():
                for p in perms:
                    assert pattern.match(p), f"Bad format: {p}"

    def test_validate_google_permissions(self):
        """validate_permissions works with Google service permissions."""
        is_valid, invalid = ScopeMapper.validate_permissions(
            ["gdrive:files:read", "gcalendar:events:list"],
            [("gdrive", ["drive.readonly"]), ("gcalendar", ["calendar.readonly"])],
        )
        assert is_valid is True
        assert invalid == []

    def test_validate_google_permissions_invalid(self):
        """validate_permissions rejects Google permissions without matching scope."""
        is_valid, invalid = ScopeMapper.validate_permissions(
            ["gdrive:files:read"],
            [("gcalendar", ["calendar.readonly"])],
        )
        assert is_valid is False
        assert "gdrive:files:read" in invalid

    def test_no_write_permissions_in_mvp(self):
        """MVP Google scopes map only to read-only permissions (no write/create/update/delete)."""
        write_actions = {"write", "create", "update", "delete", "send"}
        for svc in ["gdrive", "gcalendar", "gmail"]:
            all_perms = ScopeMapper.get_all_permissions_for_service(svc)
            for p in all_perms:
                action = p.split(":")[-1]
                assert action not in write_actions, f"Write permission found: {p}"


class TestComputeAvailablePermissions:
    """Test compute_available_permissions class method."""

    def test_single_scope(self):
        """Single scope returns sorted permissions."""
        result = ScopeMapper.compute_available_permissions("notion", ["read_pages"])
        assert result == sorted(result)
        assert "notion:pages:read" in result
        assert "notion:pages:search" in result

    def test_multiple_scopes_deduplicates(self):
        """Multiple overlapping scopes produce a deduplicated sorted list."""
        result = ScopeMapper.compute_available_permissions(
            "notion", ["read_pages", "read_content"]
        )
        assert result == sorted(set(result))

    def test_empty_scopes(self):
        """Empty scopes returns empty list."""
        result = ScopeMapper.compute_available_permissions("notion", [])
        assert result == []

    def test_unknown_service(self):
        """Unknown service returns empty list."""
        result = ScopeMapper.compute_available_permissions("unknown", ["read_pages"])
        assert result == []

    def test_slack_full_access(self):
        """Slack full_access returns all Slack permissions sorted."""
        result = ScopeMapper.compute_available_permissions("slack", ["full_access"])
        all_perms = ScopeMapper.get_all_permissions_for_service("slack")
        assert set(result) == all_perms


class TestPermissionConsistency:
    """Test that permission strings are consistent with Gateway PermissionMapper."""
    
    # These are the permission strings used by Gateway's PermissionMapper
    # If these tests fail, the permission strings have drifted
    
    def test_notion_permissions_match_gateway(self):
        """Notion permissions match Gateway's PermissionMapper."""
        expected = {
            "notion:pages:search",
            "notion:pages:read",
            "notion:pages:create",
            "notion:pages:update",
            "notion:pages:delete",
            "notion:blocks:read",
            "notion:databases:list",
            "notion:databases:query",
        }
        actual = ScopeMapper.get_all_permissions_for_service("notion")
        assert expected == actual
    
    def test_slack_permissions_match_gateway(self):
        """Slack permissions match Gateway's PermissionMapper."""
        expected = {
            "slack:messages:search",
            "slack:messages:send",
            "slack:channels:list",
            "slack:channels:join",
            "slack:channels:history",
            "slack:reactions:write",
            "slack:users:list",
            "slack:users:search",
        }
        actual = ScopeMapper.get_all_permissions_for_service("slack")
        assert expected == actual
    
    def test_all_gateway_permissions_present_in_scope_mapper(self):
        """Every permission in Gateway's PermissionMapper exists in ScopeMapper (L1 golden-set)."""
        import importlib
        import sys
        import os

        gateway_perms_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "deeptrail-gateway"
        )
        sys.path.insert(0, gateway_perms_path)
        try:
            mod = importlib.import_module("app.mcp.permission_mapper")
            PermissionMapper = mod.PermissionMapper
        except (ImportError, ModuleNotFoundError, AttributeError):
            pytest.skip("Gateway PermissionMapper not importable (run from repo root)")
        finally:
            sys.path.pop(0)

        gateway_permissions = set(PermissionMapper.TOOL_TO_PERMISSION.values())
        scope_mapper_permissions: set[str] = set()
        for service_map in ScopeMapper.SCOPE_TO_PERMISSIONS.values():
            for perms in service_map.values():
                scope_mapper_permissions.update(perms)

        missing = gateway_permissions - scope_mapper_permissions
        assert missing == set(), (
            f"Gateway permissions missing from ScopeMapper: {sorted(missing)}"
        )
