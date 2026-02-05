"""Unit tests for the ConnectedService model."""

import uuid
from datetime import datetime, timedelta, timezone

from app.models.connected_service import ConnectedService, generate_connection_id


class TestConnectionIdGeneration:
    """Tests for connection ID generation."""

    def test_generate_connection_id_format(self):
        """Connection ID should have correct prefix format."""
        conn_id = generate_connection_id()
        assert conn_id.startswith("conn-")

    def test_generate_connection_id_uniqueness(self):
        """Each generated connection ID should be unique."""
        ids = [generate_connection_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generate_connection_id_contains_uuid(self):
        """Connection ID should contain a valid UUID after the prefix."""
        conn_id = generate_connection_id()
        uuid_part = conn_id.replace("conn-", "")
        # Should not raise
        uuid.UUID(uuid_part)


class TestConnectedServiceModel:
    """Tests for ConnectedService model instantiation."""

    def test_create_basic_connection(self):
        """Create a connection with required fields."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://sarah-notion-oauth-abc123",
            scopes_granted=["read_content", "search"],
        )

        assert conn.user_id == "sarah@acme.com"
        assert conn.service_id == "notion"
        assert conn.oauth_token_ref == "vault://sarah-notion-oauth-abc123"
        assert conn.scopes_granted == ["read_content", "search"]

    def test_default_id_generated(self):
        """Connection ID should be auto-generated if not provided."""
        # Verify that a default generator is configured for the id column
        assert ConnectedService.id.default is not None
        assert callable(ConnectedService.id.default.arg)

    def test_optional_fields(self):
        """Optional fields should be None by default."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=[],
        )

        assert conn.service_name is None
        assert conn.organization_id is None
        assert conn.disconnected_at is None
        assert conn.last_used_at is None

    def test_with_optional_fields(self):
        """Connection can be created with all optional fields."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            service_name="Notion",
            oauth_token_ref="vault://test",
            scopes_granted=["read", "write"],
            organization_id="org-acme-123",
        )

        assert conn.service_name == "Notion"
        assert conn.organization_id == "org-acme-123"

    def test_scopes_as_list(self):
        """Scopes should be stored as a list."""
        scopes = ["read_content", "search", "create_pages"]
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=scopes,
        )

        assert isinstance(conn.scopes_granted, list)
        assert len(conn.scopes_granted) == 3
        assert "read_content" in conn.scopes_granted

    def test_empty_scopes(self):
        """Connection can have empty scopes list."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=[],
        )

        assert conn.scopes_granted == []


class TestConnectedServiceTablename:
    """Tests for table configuration."""

    def test_tablename(self):
        """Model should have correct table name."""
        assert ConnectedService.__tablename__ == "connected_services"


class TestConnectedServiceIsActive:
    """Tests for is_active hybrid property."""

    def test_is_active_when_connected(self):
        """New connection should be active."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=[],
        )

        assert conn.is_active is True

    def test_is_active_when_disconnected(self):
        """Disconnected connection should not be active."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=[],
            disconnected_at=datetime.now(timezone.utc),
        )

        assert conn.is_active is False


class TestConnectedServiceHasScope:
    """Tests for has_scope method."""

    def test_has_scope_present(self):
        """has_scope returns True when scope is present."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=["read_content", "search", "create_pages"],
        )

        assert conn.has_scope("read_content") is True
        assert conn.has_scope("search") is True

    def test_has_scope_absent(self):
        """has_scope returns False when scope is absent."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=["read_content"],
        )

        assert conn.has_scope("write") is False
        assert conn.has_scope("delete") is False

    def test_has_scope_empty_list(self):
        """has_scope handles empty scopes list."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=[],
        )

        assert conn.has_scope("anything") is False

    def test_has_scope_none(self):
        """has_scope handles None scopes."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=None,
        )

        assert conn.has_scope("anything") is False


class TestConnectedServiceHasAllScopes:
    """Tests for has_all_scopes method."""

    def test_has_all_scopes_when_present(self):
        """has_all_scopes returns True when all scopes are present."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=["read", "write", "delete"],
        )

        assert conn.has_all_scopes(["read", "write"]) is True
        assert conn.has_all_scopes(["read"]) is True

    def test_has_all_scopes_when_missing_one(self):
        """has_all_scopes returns False when any scope is missing."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=["read", "write"],
        )

        assert conn.has_all_scopes(["read", "delete"]) is False

    def test_has_all_scopes_empty_request(self):
        """has_all_scopes returns True for empty request list."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=["read"],
        )

        assert conn.has_all_scopes([]) is True


class TestConnectedServiceHasAnyScope:
    """Tests for has_any_scope method."""

    def test_has_any_scope_when_present(self):
        """has_any_scope returns True when any scope is present."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=["read"],
        )

        assert conn.has_any_scope(["read", "write"]) is True

    def test_has_any_scope_when_none_present(self):
        """has_any_scope returns False when no scopes are present."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=["read"],
        )

        assert conn.has_any_scope(["write", "delete"]) is False

    def test_has_any_scope_empty_request(self):
        """has_any_scope returns False for empty request list."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=["read"],
        )

        assert conn.has_any_scope([]) is False


class TestConnectedServiceDisconnect:
    """Tests for disconnect method."""

    def test_disconnect_sets_timestamp(self):
        """disconnect method sets disconnected_at timestamp."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=[],
        )

        assert conn.disconnected_at is None
        conn.disconnect()
        assert conn.disconnected_at is not None
        assert conn.is_active is False

    def test_disconnect_timestamp_is_recent(self):
        """disconnect sets a recent timestamp."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=[],
        )

        before = datetime.now(timezone.utc)
        conn.disconnect()
        after = datetime.now(timezone.utc)

        assert before <= conn.disconnected_at <= after


class TestConnectedServiceRecordUsage:
    """Tests for record_usage method."""

    def test_record_usage_sets_timestamp(self):
        """record_usage sets last_used_at timestamp."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=[],
        )

        assert conn.last_used_at is None
        conn.record_usage()
        assert conn.last_used_at is not None

    def test_record_usage_updates_timestamp(self):
        """record_usage updates existing timestamp."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=[],
            last_used_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        old_timestamp = conn.last_used_at
        conn.record_usage()

        assert conn.last_used_at > old_timestamp


class TestConnectedServiceCreateTokenRef:
    """Tests for create_token_ref class method."""

    def test_create_token_ref_format(self):
        """Token reference has correct format."""
        ref = ConnectedService.create_token_ref("sarah@acme.com", "notion")

        assert ref.startswith("vault://")
        assert "sarah" in ref
        assert "notion" in ref
        assert "oauth" in ref

    def test_create_token_ref_strips_email_domain(self):
        """Token reference uses only username part of email."""
        ref = ConnectedService.create_token_ref("sarah@acme.com", "notion")

        assert "sarah" in ref
        assert "acme.com" not in ref

    def test_create_token_ref_uniqueness(self):
        """Each call generates unique token reference."""
        refs = [
            ConnectedService.create_token_ref("sarah@acme.com", "notion")
            for _ in range(10)
        ]

        assert len(set(refs)) == 10

    def test_create_token_ref_different_services(self):
        """Different services produce different references."""
        ref_notion = ConnectedService.create_token_ref("sarah@acme.com", "notion")
        ref_slack = ConnectedService.create_token_ref("sarah@acme.com", "slack")

        assert "notion" in ref_notion
        assert "slack" in ref_slack
        assert ref_notion != ref_slack


class TestConnectedServiceRepr:
    """Tests for __repr__ method."""

    def test_repr_active(self):
        """Repr shows active status for connected service."""
        conn = ConnectedService(
            id="conn-test-123",
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=[],
        )

        repr_str = repr(conn)
        assert "conn-test-123" in repr_str
        assert "sarah@acme.com" in repr_str
        assert "notion" in repr_str
        assert "active" in repr_str

    def test_repr_disconnected(self):
        """Repr shows disconnected status."""
        conn = ConnectedService(
            id="conn-test-123",
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://test",
            scopes_granted=[],
            disconnected_at=datetime.now(timezone.utc),
        )

        repr_str = repr(conn)
        assert "disconnected" in repr_str


class TestConnectedServiceDesignDocCompliance:
    """Tests verifying compliance with design document examples."""

    def test_design_doc_example_structure(self):
        """Connection matches the structure from design doc Section 2.4."""
        # From the design doc:
        # {
        #   "user_id": "sarah@acme.com",
        #   "service_id": "notion",
        #   "oauth_token_ref": "vault://sarah-notion-oauth-xyz",
        #   "scopes_granted": ["read_content", "search", "create_pages"],
        #   "connected_at": "2026-01-21T10:05:00Z"
        # }
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_token_ref="vault://sarah-notion-oauth-xyz",
            scopes_granted=["read_content", "search", "create_pages"],
            connected_at=datetime(2026, 1, 21, 10, 5, 0, tzinfo=timezone.utc),
        )

        assert conn.user_id == "sarah@acme.com"
        assert conn.service_id == "notion"
        assert conn.oauth_token_ref == "vault://sarah-notion-oauth-xyz"
        assert "read_content" in conn.scopes_granted
        assert "search" in conn.scopes_granted
        assert "create_pages" in conn.scopes_granted
        assert conn.is_active is True

    def test_slack_connection_example(self):
        """Slack connection follows same pattern as Notion."""
        conn = ConnectedService(
            user_id="sarah@acme.com",
            service_id="slack",
            service_name="Slack",
            oauth_token_ref="vault://sarah-slack-oauth-xyz",
            scopes_granted=["channels:read", "chat:write", "users:read"],
        )

        assert conn.service_id == "slack"
        assert conn.service_name == "Slack"
        assert conn.has_scope("channels:read")
        assert conn.has_scope("chat:write")
