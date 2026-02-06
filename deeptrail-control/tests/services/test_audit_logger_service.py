"""Tests for E2: Audit Logger Service.

Tests the AuditLoggerService that persists audit events to the database
and provides query capabilities for the unified audit trail.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.models.audit_event import AuditEvent, AuditEventType
from app.services.audit_logger_service import AuditLoggerService


def unique_id() -> str:
    """Generate a unique ID for test isolation."""
    return f"test-{uuid.uuid4().hex[:8]}"


class TestAuditLoggerService:
    """Tests for E2: Audit Logger Service"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create an AuditLoggerService instance."""
        return AuditLoggerService(mock_db)

    def test_log_event_returns_event_id(self, service, mock_db):
        """E2: Should return event ID after logging."""
        event_id = service.log_event(
            event_type=AuditEventType.MCP_TOOL_CALL,
            on_behalf_of="sarah@acme.com",
            agent_id="agent-123",
            tool="notion.search_pages",
        )

        assert event_id.startswith("evt-")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_log_event_with_string_event_type(self, service, mock_db):
        """E2: Should accept string event type."""
        event_id = service.log_event(
            event_type="mcp_tool_call",
            on_behalf_of="sarah@acme.com",
            agent_id="agent-123",
            tool="notion.search_pages",
        )

        assert event_id.startswith("evt-")
        call_args = mock_db.add.call_args[0][0]
        assert call_args.event_type == "mcp_tool_call"

    def test_log_event_with_all_fields(self, service, mock_db):
        """E2: Should persist all fields."""
        event_id = service.log_event(
            event_type=AuditEventType.MCP_TOOL_CALL,
            on_behalf_of="sarah@acme.com",
            agent_id="agent-123",
            organization_id="org-456",
            tool="notion.search_pages",
            arguments={"query": "meeting notes"},
            result_summary="Found 5 results",
            session_id="usess-789",
            agent_session_id="asess-abc",
            mcp_session_id="mcpsess-def",
            delegation_id="del-xyz",
            extra_data={"custom": "data"},
        )

        assert event_id.startswith("evt-")
        call_args = mock_db.add.call_args[0][0]
        assert call_args.on_behalf_of == "sarah@acme.com"
        assert call_args.agent_id == "agent-123"
        assert call_args.organization_id == "org-456"
        assert call_args.tool == "notion.search_pages"
        assert call_args.arguments == {"query": "meeting notes"}
        assert call_args.result_summary == "Found 5 results"
        assert call_args.session_id == "usess-789"
        assert call_args.agent_session_id == "asess-abc"
        assert call_args.mcp_session_id == "mcpsess-def"
        assert call_args.delegation_id == "del-xyz"
        assert call_args.extra_data == {"custom": "data"}

    def test_log_tool_call_convenience_method(self, service, mock_db):
        """E2: Should have convenience method for tool calls."""
        event_id = service.log_tool_call(
            agent_id="agent-123",
            on_behalf_of="sarah@acme.com",
            tool="notion.search_pages",
            arguments={"query": "meeting"},
        )

        assert event_id.startswith("evt-")

        # Verify the event was created with correct type
        call_args = mock_db.add.call_args[0][0]
        assert call_args.event_type == AuditEventType.MCP_TOOL_CALL.value

    def test_log_tool_call_with_all_optional_fields(self, service, mock_db):
        """E2: Should accept all optional fields in log_tool_call."""
        event_id = service.log_tool_call(
            agent_id="agent-123",
            on_behalf_of="sarah@acme.com",
            tool="notion.search_pages",
            arguments={"query": "meeting"},
            result_summary="Found 5 results",
            duration_ms=250,
            organization_id="org-456",
            session_id="usess-789",
            agent_session_id="asess-abc",
            mcp_session_id="mcpsess-def",
            delegation_id="del-xyz",
        )

        assert event_id.startswith("evt-")
        call_args = mock_db.add.call_args[0][0]
        assert call_args.extra_data == {"duration_ms": 250}

    def test_log_permission_denied(self, service, mock_db):
        """E2: Should log permission denied events."""
        service.log_permission_denied(
            agent_id="agent-123",
            on_behalf_of="sarah@acme.com",
            tool="slack.post_message",
            required_permission="slack:messages:post",
        )

        call_args = mock_db.add.call_args[0][0]
        assert call_args.event_type == AuditEventType.PERMISSION_DENIED.value
        assert call_args.reason == "Permission denied: slack:messages:post required"
        assert "required_permission" in call_args.extra_data

    def test_log_permission_denied_with_all_optional_fields(self, service, mock_db):
        """E2: Should accept all optional fields in log_permission_denied."""
        event_id = service.log_permission_denied(
            agent_id="agent-123",
            on_behalf_of="sarah@acme.com",
            tool="slack.post_message",
            required_permission="slack:messages:post",
            organization_id="org-456",
            session_id="usess-789",
            agent_session_id="asess-abc",
            delegation_id="del-xyz",
        )

        assert event_id.startswith("evt-")
        call_args = mock_db.add.call_args[0][0]
        assert call_args.organization_id == "org-456"
        assert call_args.session_id == "usess-789"
        assert call_args.agent_session_id == "asess-abc"
        assert call_args.delegation_id == "del-xyz"


class TestSensitiveDataRedaction:
    """Tests for sensitive data redaction functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create an AuditLoggerService instance."""
        return AuditLoggerService(mock_db)

    def test_redact_sensitive_data_simple(self, service):
        """E2 Security: Should redact sensitive fields."""
        data = {
            "query": "test",
            "password": "secret123",
            "api_key": "key123",
        }

        redacted = service._redact_sensitive_data(data)

        assert redacted["query"] == "test"
        assert redacted["password"] == "[REDACTED]"
        assert redacted["api_key"] == "[REDACTED]"

    def test_redact_sensitive_data_nested(self, service):
        """E2 Security: Should redact nested sensitive fields."""
        data = {
            "query": "test",
            "nested": {
                "token": "abc",
                "safe_field": "visible",
            },
        }

        redacted = service._redact_sensitive_data(data)

        assert redacted["query"] == "test"
        assert redacted["nested"]["token"] == "[REDACTED]"
        assert redacted["nested"]["safe_field"] == "visible"

    def test_redact_sensitive_data_list(self, service):
        """E2 Security: Should redact sensitive fields in lists."""
        data = {
            "items": [
                {"name": "item1", "secret": "s1"},
                {"name": "item2", "secret": "s2"},
            ],
        }

        redacted = service._redact_sensitive_data(data)

        assert redacted["items"][0]["name"] == "item1"
        assert redacted["items"][0]["secret"] == "[REDACTED]"
        assert redacted["items"][1]["name"] == "item2"
        assert redacted["items"][1]["secret"] == "[REDACTED]"

    def test_redact_sensitive_data_all_sensitive_keys(self, service):
        """E2 Security: Should redact all known sensitive keys."""
        data = {
            "password": "p1",
            "secret": "s1",
            "token": "t1",
            "api_key": "k1",
            "apikey": "k2",
            "access_token": "at1",
            "refresh_token": "rt1",
            "authorization": "a1",
            "credential": "c1",
            "private_key": "pk1",
            "secret_key": "sk1",
        }

        redacted = service._redact_sensitive_data(data)

        for key in data:
            assert redacted[key] == "[REDACTED]"

    def test_redact_sensitive_data_case_insensitive(self, service):
        """E2 Security: Should redact regardless of case."""
        data = {
            "PASSWORD": "p1",
            "Password": "p2",
            "pAsSwOrD": "p3",
        }

        redacted = service._redact_sensitive_data(data)

        assert redacted["PASSWORD"] == "[REDACTED]"
        assert redacted["Password"] == "[REDACTED]"
        assert redacted["pAsSwOrD"] == "[REDACTED]"

    def test_log_event_redacts_arguments(self, service, mock_db):
        """E2 Security: Should redact arguments before persisting."""
        service.log_event(
            event_type=AuditEventType.MCP_TOOL_CALL,
            on_behalf_of="sarah@acme.com",
            arguments={"query": "test", "password": "secret123"},
        )

        call_args = mock_db.add.call_args[0][0]
        assert call_args.arguments["query"] == "test"
        assert call_args.arguments["password"] == "[REDACTED]"


class TestQueryEvents:
    """Tests for querying audit events."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = []
        db.query.return_value = mock_query
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create an AuditLoggerService instance."""
        return AuditLoggerService(mock_db)

    def test_query_with_no_filters(self, service, mock_db):
        """E2: Should query without filters."""
        events = service.query_events()

        assert events == []
        mock_db.query.assert_called_once_with(AuditEvent)

    def test_query_with_agent_filter(self, service, mock_db):
        """E2: Should filter by agent_id."""
        service.query_events(agent_id="agent-123")

        mock_db.query.return_value.filter.assert_called()

    def test_query_with_on_behalf_of_filter(self, service, mock_db):
        """E2: Should filter by on_behalf_of."""
        service.query_events(on_behalf_of="sarah@acme.com")

        mock_db.query.return_value.filter.assert_called()

    def test_query_with_event_type_filter_enum(self, service, mock_db):
        """E2: Should filter by event_type enum."""
        service.query_events(event_type=AuditEventType.MCP_TOOL_CALL)

        mock_db.query.return_value.filter.assert_called()

    def test_query_with_event_type_filter_string(self, service, mock_db):
        """E2: Should filter by event_type string."""
        service.query_events(event_type="mcp_tool_call")

        mock_db.query.return_value.filter.assert_called()

    def test_query_with_time_range(self, service, mock_db):
        """E2: Should filter by time range."""
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        end = datetime.now(timezone.utc)

        service.query_events(start_time=start, end_time=end)

        mock_db.query.return_value.filter.assert_called()

    def test_query_with_tool_filter(self, service, mock_db):
        """E2: Should filter by tool."""
        service.query_events(tool="notion.search_pages")

        mock_db.query.return_value.filter.assert_called()

    def test_query_with_delegation_filter(self, service, mock_db):
        """E2: Should filter by delegation_id."""
        service.query_events(delegation_id="del-123")

        mock_db.query.return_value.filter.assert_called()

    def test_query_with_organization_filter(self, service, mock_db):
        """E2: Should filter by organization_id."""
        service.query_events(organization_id="org-456")

        mock_db.query.return_value.filter.assert_called()

    def test_query_limit_capped(self, service, mock_db):
        """E2: Should cap limit at 1000."""
        # Request 5000, should be capped to 1000
        service.query_events(limit=5000)

        mock_db.query.return_value.limit.assert_called_with(1000)

    def test_query_default_limit(self, service, mock_db):
        """E2: Should use default limit of 100."""
        service.query_events()

        mock_db.query.return_value.limit.assert_called_with(100)

    def test_query_with_offset(self, service, mock_db):
        """E2: Should apply offset for pagination."""
        service.query_events(offset=50)

        mock_db.query.return_value.offset.assert_called_with(50)


class TestGetEvent:
    """Tests for getting a single event by ID."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        db.query.return_value = mock_query
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create an AuditLoggerService instance."""
        return AuditLoggerService(mock_db)

    def test_get_event_not_found(self, service, mock_db):
        """E2: Should return None for non-existent event."""
        result = service.get_event("evt-nonexistent")

        assert result is None

    def test_get_event_found(self, service, mock_db):
        """E2: Should return event when found."""
        mock_event = MagicMock()
        mock_event.id = "evt-123"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_event

        result = service.get_event("evt-123")

        assert result == mock_event


class TestCountEvents:
    """Tests for counting events."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 42
        db.query.return_value = mock_query
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create an AuditLoggerService instance."""
        return AuditLoggerService(mock_db)

    def test_count_events_no_filters(self, service, mock_db):
        """E2: Should count all events."""
        count = service.count_events()

        assert count == 42

    def test_count_events_with_filters(self, service, mock_db):
        """E2: Should count with filters."""
        count = service.count_events(
            agent_id="agent-123",
            on_behalf_of="sarah@acme.com",
        )

        assert count == 42
        mock_db.query.return_value.filter.assert_called()

    def test_count_events_returns_zero(self, service, mock_db):
        """E2: Should return 0 for empty result."""
        mock_db.query.return_value.filter.return_value.scalar.return_value = None

        count = service.count_events(agent_id="agent-nonexistent")

        assert count == 0


class TestAuditEventImmutability:
    """Tests to ensure audit events are immutable."""

    def test_no_update_method(self):
        """E2 Security: Service should not expose update method."""
        assert not hasattr(AuditLoggerService, "update_event")

    def test_no_delete_method(self):
        """E2 Security: Service should not expose delete method."""
        assert not hasattr(AuditLoggerService, "delete_event")


class TestIntegrationWithDB:
    """Integration tests with actual database session."""

    @pytest.fixture
    def service(self, db):
        """Create an AuditLoggerService with real DB."""
        return AuditLoggerService(db)

    def test_log_and_retrieve_event(self, service, db):
        """E2 Integration: Should persist and retrieve event."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        event_id = service.log_event(
            event_type=AuditEventType.MCP_TOOL_CALL,
            on_behalf_of=unique_user,
            agent_id=unique_agent,
            tool="notion.search_pages",
            arguments={"query": "test"},
        )

        # Retrieve the event
        event = service.get_event(event_id)

        assert event is not None
        assert event.id == event_id
        assert event.event_type == AuditEventType.MCP_TOOL_CALL.value
        assert event.agent_id == unique_agent
        assert event.on_behalf_of == unique_user
        assert event.tool == "notion.search_pages"

    def test_log_and_query_events(self, service, db):
        """E2 Integration: Should query logged events."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        # Log several events
        event1 = service.log_tool_call(
            agent_id=unique_agent,
            on_behalf_of=unique_user,
            tool="notion.search_pages",
            arguments={"query": "test"},
        )

        event2 = service.log_tool_call(
            agent_id=unique_agent,
            on_behalf_of=unique_user,
            tool="slack.post_message",
            arguments={"channel": "#general"},
        )

        # Query by agent
        events = service.query_events(agent_id=unique_agent)

        assert len(events) >= 2
        event_ids = [e.id for e in events]
        assert event1 in event_ids
        assert event2 in event_ids

    def test_query_by_user(self, service, db):
        """E2 Integration: Should filter by user."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        service.log_tool_call(
            agent_id=unique_agent,
            on_behalf_of=unique_user,
            tool="notion.search_pages",
            arguments={"query": "test"},
        )

        events = service.query_events(on_behalf_of=unique_user)

        assert len(events) >= 1
        assert all(e.on_behalf_of == unique_user for e in events)

    def test_query_by_event_type(self, service, db):
        """E2 Integration: Should filter by event type."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        service.log_tool_call(
            agent_id=unique_agent,
            on_behalf_of=unique_user,
            tool="notion.search_pages",
            arguments={"query": "test"},
        )

        events = service.query_events(
            agent_id=unique_agent,
            event_type=AuditEventType.MCP_TOOL_CALL,
        )

        assert len(events) >= 1
        assert all(e.event_type == AuditEventType.MCP_TOOL_CALL.value for e in events)

    def test_count_events(self, service, db):
        """E2 Integration: Should count events."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        # Log events
        service.log_tool_call(
            agent_id=unique_agent,
            on_behalf_of=unique_user,
            tool="notion.search_pages",
            arguments={"query": "test"},
        )
        service.log_tool_call(
            agent_id=unique_agent,
            on_behalf_of=unique_user,
            tool="slack.post_message",
            arguments={"channel": "#general"},
        )

        count = service.count_events(agent_id=unique_agent)

        assert count >= 2

    def test_query_pagination(self, service, db):
        """E2 Integration: Should support pagination."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        # Log 5 events
        for i in range(5):
            service.log_tool_call(
                agent_id=unique_agent,
                on_behalf_of=unique_user,
                tool=f"tool_{i}",
                arguments={"index": i},
            )

        # Query with limit
        events_page1 = service.query_events(agent_id=unique_agent, limit=2, offset=0)
        events_page2 = service.query_events(agent_id=unique_agent, limit=2, offset=2)

        assert len(events_page1) == 2
        assert len(events_page2) == 2
        # Pages should have different events
        page1_ids = {e.id for e in events_page1}
        page2_ids = {e.id for e in events_page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_events_ordered_by_timestamp_desc(self, service, db):
        """E2 Integration: Should return events in timestamp descending order."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        # Log events
        for i in range(3):
            service.log_tool_call(
                agent_id=unique_agent,
                on_behalf_of=unique_user,
                tool=f"tool_{i}",
                arguments={"index": i},
            )

        events = service.query_events(agent_id=unique_agent)

        # Check descending order
        for i in range(len(events) - 1):
            assert events[i].timestamp >= events[i + 1].timestamp


class TestGetSummary:
    """Tests for E6: Audit summary statistics."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.scalar.return_value = 100
        mock_query.all.return_value = []
        db.query.return_value = mock_query
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create an AuditLoggerService instance."""
        return AuditLoggerService(mock_db)

    def test_get_summary_returns_structure(self, service, mock_db):
        """E6: Should return summary with correct structure."""
        summary = service.get_summary()

        assert "total_events" in summary
        assert "by_event_type" in summary
        assert "by_tool" in summary
        assert "by_agent" in summary
        assert "time_range" in summary

    def test_get_summary_with_filters(self, service, mock_db):
        """E6: Should accept filters."""
        summary = service.get_summary(
            agent_id="agent-123",
            on_behalf_of="sarah@acme.com",
        )

        assert summary is not None
        mock_db.query.return_value.filter.assert_called()


class TestGetSummaryIntegration:
    """Integration tests for audit summary."""

    @pytest.fixture
    def service(self, db):
        """Create an AuditLoggerService with real DB."""
        return AuditLoggerService(db)

    def test_summary_counts_events(self, service, db):
        """E6 Integration: Should count events correctly."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        # Log tool call events
        for i in range(3):
            service.log_tool_call(
                agent_id=unique_agent,
                on_behalf_of=unique_user,
                tool="notion.search_pages",
                arguments={"index": i},
            )

        # Log permission denied event
        service.log_permission_denied(
            agent_id=unique_agent,
            on_behalf_of=unique_user,
            tool="slack.post_message",
            required_permission="slack:messages:post",
        )

        summary = service.get_summary(agent_id=unique_agent)

        assert summary["total_events"] >= 4

    def test_summary_groups_by_event_type(self, service, db):
        """E6 Integration: Should group by event type."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        # Log different event types
        service.log_tool_call(
            agent_id=unique_agent,
            on_behalf_of=unique_user,
            tool="notion.search_pages",
            arguments={},
        )
        service.log_permission_denied(
            agent_id=unique_agent,
            on_behalf_of=unique_user,
            tool="slack.post_message",
            required_permission="slack:messages:post",
        )

        summary = service.get_summary(agent_id=unique_agent)

        assert "mcp_tool_call" in summary["by_event_type"]
        assert "permission_denied" in summary["by_event_type"]

    def test_summary_groups_by_tool(self, service, db):
        """E6 Integration: Should group by tool."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        # Log events with different tools
        service.log_tool_call(
            agent_id=unique_agent,
            on_behalf_of=unique_user,
            tool="notion.search_pages",
            arguments={},
        )
        service.log_tool_call(
            agent_id=unique_agent,
            on_behalf_of=unique_user,
            tool="slack.post_message",
            arguments={},
        )

        summary = service.get_summary(agent_id=unique_agent)

        assert "notion.search_pages" in summary["by_tool"]
        assert "slack.post_message" in summary["by_tool"]

    def test_summary_groups_by_agent(self, service, db):
        """E6 Integration: Should group by agent."""
        unique_user = f"{unique_id()}@acme.com"
        agent1 = unique_id()
        agent2 = unique_id()

        # Log events with different agents
        service.log_tool_call(
            agent_id=agent1,
            on_behalf_of=unique_user,
            tool="notion.search_pages",
            arguments={},
        )
        service.log_tool_call(
            agent_id=agent2,
            on_behalf_of=unique_user,
            tool="notion.search_pages",
            arguments={},
        )

        summary = service.get_summary(on_behalf_of=unique_user)

        assert agent1 in summary["by_agent"]
        assert agent2 in summary["by_agent"]

    def test_summary_with_time_range(self, service, db):
        """E6 Integration: Should include time range in response."""
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=1)

        summary = service.get_summary(start_time=start, end_time=now)

        assert "start" in summary["time_range"]
        assert "end" in summary["time_range"]
