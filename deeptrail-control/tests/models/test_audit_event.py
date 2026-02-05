"""Unit tests for the AuditEvent model."""

import uuid
from datetime import datetime, timezone

from app.models.audit_event import (
    AuditEvent,
    AuditEventType,
    generate_event_id,
)


class TestGenerateEventId:
    """Tests for the event ID generation function."""

    def test_generates_string(self):
        """Event ID should be a string."""
        event_id = generate_event_id()
        assert isinstance(event_id, str)

    def test_has_correct_prefix(self):
        """Event ID should start with 'evt-' prefix."""
        event_id = generate_event_id()
        assert event_id.startswith("evt-")

    def test_contains_uuid(self):
        """Event ID should contain a valid UUID after the prefix."""
        event_id = generate_event_id()
        uuid_part = event_id.replace("evt-", "")
        # Should not raise ValueError if valid UUID
        uuid.UUID(uuid_part)

    def test_generates_unique_ids(self):
        """Each call should generate a unique event ID."""
        ids = [generate_event_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestAuditEventType:
    """Tests for the AuditEventType enum."""

    def test_mcp_tool_call_value(self):
        """MCP_TOOL_CALL should have correct value."""
        assert AuditEventType.MCP_TOOL_CALL.value == "mcp_tool_call"

    def test_permission_denied_value(self):
        """PERMISSION_DENIED should have correct value."""
        assert AuditEventType.PERMISSION_DENIED.value == "permission_denied"

    def test_session_created_value(self):
        """SESSION_CREATED should have correct value."""
        assert AuditEventType.SESSION_CREATED.value == "session_created"

    def test_session_expired_value(self):
        """SESSION_EXPIRED should have correct value."""
        assert AuditEventType.SESSION_EXPIRED.value == "session_expired"

    def test_delegation_created_value(self):
        """DELEGATION_CREATED should have correct value."""
        assert AuditEventType.DELEGATION_CREATED.value == "delegation_created"

    def test_delegation_revoked_value(self):
        """DELEGATION_REVOKED should have correct value."""
        assert AuditEventType.DELEGATION_REVOKED.value == "delegation_revoked"

    def test_is_string_enum(self):
        """AuditEventType should be a string enum."""
        assert isinstance(AuditEventType.MCP_TOOL_CALL, str)
        assert AuditEventType.MCP_TOOL_CALL == "mcp_tool_call"


class TestAuditEventModel:
    """Tests for the AuditEvent SQLAlchemy model."""

    def test_instantiation_with_required_fields(self):
        """AuditEvent can be instantiated with only required fields."""
        event = AuditEvent(
            event_type=AuditEventType.MCP_TOOL_CALL.value,
            on_behalf_of="sarah@acme.com",
        )

        assert event.event_type == "mcp_tool_call"
        assert event.on_behalf_of == "sarah@acme.com"

    def test_agent_id_optional(self):
        """Agent ID should be optional (None for user-direct actions)."""
        event = AuditEvent(
            event_type=AuditEventType.SESSION_CREATED.value,
            on_behalf_of="sarah@acme.com",
        )

        assert event.agent_id is None

    def test_agent_id_can_be_set(self):
        """Agent ID can be set for agent actions."""
        event = AuditEvent(
            event_type=AuditEventType.MCP_TOOL_CALL.value,
            on_behalf_of="sarah@acme.com",
            agent_id="agent-sdr-001",
        )

        assert event.agent_id == "agent-sdr-001"

    def test_tool_call_fields(self):
        """Tool call related fields should work correctly."""
        event = AuditEvent(
            event_type=AuditEventType.MCP_TOOL_CALL.value,
            on_behalf_of="sarah@acme.com",
            agent_id="agent-sdr-001",
            tool="notion.search_pages",
            arguments={"query": "competitor analysis", "limit": 5},
            result_summary="3 pages found",
        )

        assert event.tool == "notion.search_pages"
        assert event.arguments == {"query": "competitor analysis", "limit": 5}
        assert event.result_summary == "3 pages found"

    def test_permission_denied_fields(self):
        """Permission denied related fields should work correctly."""
        event = AuditEvent(
            event_type=AuditEventType.PERMISSION_DENIED.value,
            on_behalf_of="sarah@acme.com",
            agent_id="agent-sdr-001",
            attempted_tool="notion.create_page",
            required_permission="notion:pages:create",
            reason="Permission not in delegation",
        )

        assert event.attempted_tool == "notion.create_page"
        assert event.required_permission == "notion:pages:create"
        assert event.reason == "Permission not in delegation"

    def test_session_context_fields(self):
        """Session context fields should work correctly."""
        event = AuditEvent(
            event_type=AuditEventType.MCP_TOOL_CALL.value,
            on_behalf_of="sarah@acme.com",
            session_id="usess-abc123",
            agent_session_id="asess-sdr-001-ghi789",
            mcp_session_id="mcpsess-notion-jkl012",
            delegation_id="del-xyz789",
        )

        assert event.session_id == "usess-abc123"
        assert event.agent_session_id == "asess-sdr-001-ghi789"
        assert event.mcp_session_id == "mcpsess-notion-jkl012"
        assert event.delegation_id == "del-xyz789"

    def test_organization_id_optional(self):
        """Organization ID should be optional."""
        event = AuditEvent(
            event_type=AuditEventType.MCP_TOOL_CALL.value,
            on_behalf_of="sarah@acme.com",
        )

        assert event.organization_id is None

    def test_organization_id_can_be_set(self):
        """Organization ID can be set."""
        event = AuditEvent(
            event_type=AuditEventType.MCP_TOOL_CALL.value,
            on_behalf_of="sarah@acme.com",
            organization_id="org-acme-123",
        )

        assert event.organization_id == "org-acme-123"

    def test_extra_data_field(self):
        """Extra data field should accept JSON data."""
        event = AuditEvent(
            event_type=AuditEventType.MCP_TOOL_CALL.value,
            on_behalf_of="sarah@acme.com",
            extra_data={"ip_address": "192.168.1.1", "user_agent": "Mozilla/5.0"},
        )

        assert event.extra_data == {
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
        }

    def test_custom_timestamp(self):
        """Custom timestamp can be provided."""
        custom_time = datetime(2026, 1, 21, 10, 15, 32, tzinfo=timezone.utc)
        event = AuditEvent(
            event_type=AuditEventType.MCP_TOOL_CALL.value,
            on_behalf_of="sarah@acme.com",
            timestamp=custom_time,
        )

        assert event.timestamp == custom_time

    def test_repr(self):
        """String representation should include key fields."""
        event = AuditEvent(
            id="evt-test-123",
            event_type=AuditEventType.MCP_TOOL_CALL.value,
            on_behalf_of="sarah@acme.com",
            timestamp=datetime(2026, 1, 21, 10, 15, 32, tzinfo=timezone.utc),
        )

        repr_str = repr(event)
        assert "evt-test-123" in repr_str
        assert "mcp_tool_call" in repr_str
        assert "sarah@acme.com" in repr_str


class TestAuditEventFactoryMethods:
    """Tests for AuditEvent factory methods."""

    def test_create_tool_call_event(self):
        """Factory method should create tool call event with correct fields."""
        event = AuditEvent.create_tool_call_event(
            agent_id="agent-sdr-001",
            on_behalf_of="sarah@acme.com",
            tool="notion.search_pages",
            arguments={"query": "competitor analysis", "limit": 5},
            result_summary="3 pages found",
            session_id="usess-abc123",
            agent_session_id="asess-sdr-001-ghi789",
            mcp_session_id="mcpsess-notion-jkl012",
            delegation_id="del-xyz789",
            organization_id="org-acme-123",
        )

        assert event.event_type == AuditEventType.MCP_TOOL_CALL.value
        assert event.agent_id == "agent-sdr-001"
        assert event.on_behalf_of == "sarah@acme.com"
        assert event.tool == "notion.search_pages"
        assert event.arguments == {"query": "competitor analysis", "limit": 5}
        assert event.result_summary == "3 pages found"
        assert event.session_id == "usess-abc123"
        assert event.agent_session_id == "asess-sdr-001-ghi789"
        assert event.mcp_session_id == "mcpsess-notion-jkl012"
        assert event.delegation_id == "del-xyz789"
        assert event.organization_id == "org-acme-123"

    def test_create_tool_call_event_minimal(self):
        """Factory method should work with minimal required fields."""
        event = AuditEvent.create_tool_call_event(
            agent_id="agent-sdr-001",
            on_behalf_of="sarah@acme.com",
            tool="notion.search_pages",
        )

        assert event.event_type == AuditEventType.MCP_TOOL_CALL.value
        assert event.agent_id == "agent-sdr-001"
        assert event.on_behalf_of == "sarah@acme.com"
        assert event.tool == "notion.search_pages"
        assert event.arguments is None
        assert event.result_summary is None

    def test_create_permission_denied_event(self):
        """Factory method should create permission denied event with correct fields."""
        event = AuditEvent.create_permission_denied_event(
            agent_id="agent-sdr-001",
            on_behalf_of="sarah@acme.com",
            attempted_tool="notion.create_page",
            required_permission="notion:pages:create",
            reason="Permission not in delegation",
            session_id="usess-abc123",
            agent_session_id="asess-sdr-001-ghi789",
            delegation_id="del-xyz789",
            organization_id="org-acme-123",
        )

        assert event.event_type == AuditEventType.PERMISSION_DENIED.value
        assert event.agent_id == "agent-sdr-001"
        assert event.on_behalf_of == "sarah@acme.com"
        assert event.attempted_tool == "notion.create_page"
        assert event.required_permission == "notion:pages:create"
        assert event.reason == "Permission not in delegation"
        assert event.session_id == "usess-abc123"
        assert event.agent_session_id == "asess-sdr-001-ghi789"
        assert event.delegation_id == "del-xyz789"
        assert event.organization_id == "org-acme-123"

    def test_create_permission_denied_event_minimal(self):
        """Factory method should work with minimal required fields."""
        event = AuditEvent.create_permission_denied_event(
            agent_id="agent-sdr-001",
            on_behalf_of="sarah@acme.com",
            attempted_tool="notion.create_page",
            required_permission="notion:pages:create",
            reason="Permission not in delegation",
        )

        assert event.event_type == AuditEventType.PERMISSION_DENIED.value
        assert event.attempted_tool == "notion.create_page"
        assert event.session_id is None


class TestAuditEventTablename:
    """Tests for table configuration."""

    def test_tablename(self):
        """Table name should be 'audit_events'."""
        assert AuditEvent.__tablename__ == "audit_events"

    def test_has_composite_indexes(self):
        """Model should have composite indexes defined."""
        index_names = [idx.name for idx in AuditEvent.__table__.indexes]

        # Check for expected composite indexes
        assert "ix_audit_agent_time" in index_names
        assert "ix_audit_user_time" in index_names
        assert "ix_audit_org_time" in index_names
        assert "ix_audit_type_time" in index_names
        assert "ix_audit_delegation_time" in index_names


class TestAuditEventDesignCompliance:
    """Tests to verify compliance with the design document."""

    def test_step_8_audit_event_structure(self):
        """Event should match Step 8 audit log structure from design doc."""
        # From design doc Section 2.9 - Step 8
        event = AuditEvent(
            timestamp=datetime(2026, 1, 21, 10, 15, 32, tzinfo=timezone.utc),
            event_type="mcp_tool_call",
            agent_id="agent-sdr-001",
            on_behalf_of="sarah@acme.com",
            tool="notion.search_pages",
            arguments={"query": "competitor analysis", "limit": 5},
            result_summary="3 pages found",
            agent_session_id="asess-sdr-001-ghi789",
            mcp_session_id="mcpsess-notion-jkl012",
        )

        assert event.event_type == "mcp_tool_call"
        assert event.agent_id == "agent-sdr-001"
        assert event.on_behalf_of == "sarah@acme.com"
        assert event.tool == "notion.search_pages"
        assert event.arguments["query"] == "competitor analysis"
        assert event.result_summary == "3 pages found"

    def test_step_9_permission_denied_structure(self):
        """Event should match Step 9 permission denied structure from design doc."""
        # From design doc Section 2.10 - Step 9
        event = AuditEvent(
            timestamp=datetime(2026, 1, 21, 10, 16, 45, tzinfo=timezone.utc),
            event_type="permission_denied",
            agent_id="agent-sdr-001",
            on_behalf_of="sarah@acme.com",
            attempted_tool="notion.create_page",
            required_permission="notion:pages:create",
            reason="Permission not in delegation",
        )

        assert event.event_type == "permission_denied"
        assert event.agent_id == "agent-sdr-001"
        assert event.on_behalf_of == "sarah@acme.com"
        assert event.attempted_tool == "notion.create_page"
        assert event.required_permission == "notion:pages:create"
        assert event.reason == "Permission not in delegation"
