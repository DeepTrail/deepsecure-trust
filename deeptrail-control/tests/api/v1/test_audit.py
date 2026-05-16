"""Tests for audit API endpoints.

Tests the audit endpoints:
- POST /api/v1/audit/events - Log an event
- GET /api/v1/audit/events - Query events
- GET /api/v1/audit/events/{event_id} - Get single event

These implement Demo 5: Unified Audit and Step 10 of Sarah's Journey.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.audit import get_audit_logger_service
from app.main import app


def unique_id() -> str:
    """Generate a unique ID for test isolation."""
    return f"test-{uuid.uuid4().hex[:8]}"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_audit_logger_service():
    """Create a mock AuditLoggerService."""
    mock_service = MagicMock()
    return mock_service


@pytest.fixture
def client_with_mock_service(db, mock_audit_logger_service):
    """Client with mocked AuditLoggerService dependency."""
    from app.api.deps import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_audit_logger_service():
        return mock_audit_logger_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_audit_logger_service] = override_audit_logger_service

    with TestClient(app) as c:
        yield c

    # Clean up
    del app.dependency_overrides[get_db]
    del app.dependency_overrides[get_audit_logger_service]


@pytest.fixture
def client(db):
    """Client with real AuditLoggerService (integration tests)."""
    from app.api.deps import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    # Clean up
    del app.dependency_overrides[get_db]


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/audit/events Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLogEvent:
    """Tests for POST /api/v1/audit/events endpoint."""

    def test_log_event_success(self, client_with_mock_service, mock_audit_logger_service):
        """E2: Should log event and return event_id."""
        response = client_with_mock_service.post(
            "/api/v1/audit/events",
            json={
                "event_type": "mcp_tool_call",
                "on_behalf_of": "sarah@acme.com",
                "agent_id": "agent-123",
                "tool": "notion.search_pages",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["event_id"].startswith("evt-")
        assert "timestamp" in data

    def test_log_event_with_all_fields(self, client_with_mock_service, mock_audit_logger_service):
        """E2: Should accept all optional fields."""
        mock_audit_logger_service.log_event.return_value = "evt-test-456"

        response = client_with_mock_service.post(
            "/api/v1/audit/events",
            json={
                "event_type": "mcp_tool_call",
                "on_behalf_of": "sarah@acme.com",
                "agent_id": "agent-123",
                "organization_id": "org-456",
                "tool": "notion.search_pages",
                "arguments": {"query": "meeting notes"},
                "result_summary": "Found 5 results",
                "duration_ms": 250,
                "session_id": "usess-789",
                "agent_session_id": "asess-abc",
                "mcp_session_id": "mcpsess-def",
                "delegation_id": "del-xyz",
                "extra_data": {"custom": "data"},
            },
        )

        assert response.status_code == 200

    def test_log_event_missing_required_field(self, client_with_mock_service):
        """E2: Should return 422 for missing required fields."""
        response = client_with_mock_service.post(
            "/api/v1/audit/events",
            json={
                "event_type": "mcp_tool_call",
                # Missing on_behalf_of
            },
        )

        assert response.status_code == 422

    def test_log_event_invalid_event_type(self, client_with_mock_service, mock_audit_logger_service):
        """E2: Endpoint accepts any event_type string (validation is not enforced at this layer)."""
        response = client_with_mock_service.post(
            "/api/v1/audit/events",
            json={
                "event_type": "invalid_type",
                "on_behalf_of": "sarah@acme.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["event_id"].startswith("evt-")


class TestLogEventIntegration:
    """Integration tests for logging events with real DB."""

    def test_log_and_retrieve_event(self, client):
        """E2 Integration: Should persist and retrieve event."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        # Log event
        response = client.post(
            "/api/v1/audit/events",
            json={
                "event_type": "mcp_tool_call",
                "on_behalf_of": unique_user,
                "agent_id": unique_agent,
                "tool": "notion.search_pages",
                "arguments": {"query": "test"},
            },
        )

        assert response.status_code == 200
        event_id = response.json()["event_id"]
        assert event_id.startswith("evt-")

        # Retrieve event
        response = client.get(f"/api/v1/audit/events/{event_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == event_id
        assert data["agent_id"] == unique_agent
        assert data["on_behalf_of"] == unique_user
        assert data["tool"] == "notion.search_pages"


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/audit/events Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestQueryEvents:
    """Tests for GET /api/v1/audit/events endpoint."""

    def test_query_events_no_filters(self, client_with_mock_service, mock_audit_logger_service):
        """E2: Should query events without filters."""
        mock_audit_logger_service.query_events.return_value = []
        mock_audit_logger_service.count_events.return_value = 0

        response = client_with_mock_service.get("/api/v1/audit/events")

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    def test_query_events_with_agent_filter(self, client_with_mock_service, mock_audit_logger_service):
        """E2: Should filter by agent_id."""
        client_with_mock_service.post(
            "/api/v1/audit/events",
            json={
                "event_type": "mcp_tool_call",
                "on_behalf_of": "sarah@acme.com",
                "agent_id": "agent-123",
                "tool": "notion.search_pages",
            },
        )

        response = client_with_mock_service.get(
            "/api/v1/audit/events",
            params={"agent_id": "agent-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert all(e["agent_id"] == "agent-123" for e in data["events"])

    def test_query_events_with_pagination(self, client_with_mock_service, mock_audit_logger_service):
        """E2: Should support pagination."""
        mock_audit_logger_service.query_events.return_value = []
        mock_audit_logger_service.count_events.return_value = 0

        response = client_with_mock_service.get(
            "/api/v1/audit/events",
            params={"limit": 10, "offset": 50},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 50

    def test_query_events_limit_validation(self, client_with_mock_service):
        """E2: Should validate limit is within bounds."""
        response = client_with_mock_service.get(
            "/api/v1/audit/events",
            params={"limit": 5000},  # Over max
        )

        assert response.status_code == 422

    def test_query_events_with_time_filter(self, client_with_mock_service, mock_audit_logger_service):
        """E2: Should filter by time range."""
        mock_audit_logger_service.query_events.return_value = []
        mock_audit_logger_service.count_events.return_value = 0

        response = client_with_mock_service.get(
            "/api/v1/audit/events",
            params={
                "start_time": "2026-02-01T00:00:00Z",
                "end_time": "2026-02-06T00:00:00Z",
            },
        )

        assert response.status_code == 200


class TestQueryEventsIntegration:
    """Integration tests for querying events with real DB."""

    def test_log_and_query_events(self, client):
        """E2 Integration: Should query logged events."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        # Log multiple events
        for i in range(3):
            client.post(
                "/api/v1/audit/events",
                json={
                    "event_type": "mcp_tool_call",
                    "on_behalf_of": unique_user,
                    "agent_id": unique_agent,
                    "tool": f"tool_{i}",
                    "arguments": {"index": i},
                },
            )

        # Query by agent
        response = client.get(
            "/api/v1/audit/events",
            params={"agent_id": unique_agent},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 3
        assert data["total"] == 3

    def test_query_by_user(self, client):
        """E2 Integration: Should filter by on_behalf_of."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        client.post(
            "/api/v1/audit/events",
            json={
                "event_type": "mcp_tool_call",
                "on_behalf_of": unique_user,
                "agent_id": unique_agent,
                "tool": "notion.search_pages",
                "arguments": {},
            },
        )

        response = client.get(
            "/api/v1/audit/events",
            params={"on_behalf_of": unique_user},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) >= 1
        assert all(e["on_behalf_of"] == unique_user for e in data["events"])


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/audit/events/{event_id} Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestGetEvent:
    """Tests for GET /api/v1/audit/events/{event_id} endpoint."""

    def test_get_event_success(self, client_with_mock_service, mock_audit_logger_service):
        """E2: Should return event when found."""
        mock_event = MagicMock()
        mock_event.id = "evt-123"
        mock_event.timestamp = datetime.now(timezone.utc)
        mock_event.event_type = "mcp_tool_call"
        mock_event.agent_id = "agent-123"
        mock_event.on_behalf_of = "sarah@acme.com"
        mock_event.organization_id = None
        mock_event.tool = "notion.search_pages"
        mock_event.arguments = {"query": "test"}
        mock_event.result_summary = None
        mock_event.reason = None
        mock_event.session_id = None
        mock_event.agent_session_id = None
        mock_event.mcp_session_id = None
        mock_event.delegation_id = None
        mock_event.extra_data = None

        mock_audit_logger_service.get_event.return_value = mock_event

        response = client_with_mock_service.get("/api/v1/audit/events/evt-123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "evt-123"
        assert data["event_type"] == "mcp_tool_call"

    def test_get_event_not_found(self, client_with_mock_service, mock_audit_logger_service):
        """E2: Should return 404 for non-existent event."""
        mock_audit_logger_service.get_event.return_value = None

        response = client_with_mock_service.get("/api/v1/audit/events/evt-nonexistent")

        assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# OpenAPI Documentation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestOpenAPIDocumentation:
    """Tests for OpenAPI schema documentation."""

    def test_audit_endpoints_in_openapi(self, client):
        """E2: Should include audit endpoints in OpenAPI schema."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        paths = schema["paths"]
        assert "/api/v1/audit/events" in paths
        assert "/api/v1/audit/events/{event_id}" in paths

    def test_log_event_endpoint_documented(self, client):
        """E2: POST /audit/events should be documented."""
        response = client.get("/openapi.json")
        schema = response.json()

        endpoint = schema["paths"]["/api/v1/audit/events"]
        assert "post" in endpoint
        assert "summary" in endpoint["post"]

    def test_query_events_endpoint_documented(self, client):
        """E2: GET /audit/events should be documented."""
        response = client.get("/openapi.json")
        schema = response.json()

        endpoint = schema["paths"]["/api/v1/audit/events"]
        assert "get" in endpoint
        assert "parameters" in endpoint["get"]

    def test_get_event_endpoint_documented(self, client):
        """E2: GET /audit/events/{event_id} should be documented."""
        response = client.get("/openapi.json")
        schema = response.json()

        endpoint = schema["paths"]["/api/v1/audit/events/{event_id}"]
        assert "get" in endpoint

    def test_audit_tag_exists(self, client):
        """E2: Should have 'audit' tag for organization."""
        response = client.get("/openapi.json")
        schema = response.json()

        # Check that audit endpoints use the audit tag
        endpoint = schema["paths"]["/api/v1/audit/events"]["post"]
        assert "audit" in endpoint.get("tags", [])

    def test_summary_endpoint_in_openapi(self, client):
        """E6: Summary endpoint should be in OpenAPI schema."""
        response = client.get("/openapi.json")
        schema = response.json()

        paths = schema["paths"]
        assert "/api/v1/audit/summary" in paths
        assert "get" in paths["/api/v1/audit/summary"]


# ─────────────────────────────────────────────────────────────────────────────
# Summary Endpoint Tests (E6)
# ─────────────────────────────────────────────────────────────────────────────


class TestGetSummary:
    """Tests for GET /api/v1/audit/summary endpoint."""

    def test_get_summary_success(self, client_with_mock_service, mock_audit_logger_service):
        """E6: Should return summary statistics."""
        mock_audit_logger_service.get_summary.return_value = {
            "total_events": 100,
            "by_event_type": {"mcp_tool_call": 95, "permission_denied": 5},
            "by_tool": {"notion.search_pages": 50, "slack.post_message": 30},
            "by_agent": {"agent-sdr-001": 60, "agent-researcher-002": 40},
            "time_range": {},
        }

        response = client_with_mock_service.get("/api/v1/audit/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 100
        assert "by_event_type" in data
        assert "by_tool" in data
        assert "by_agent" in data

    def test_get_summary_with_agent_filter(
        self, client_with_mock_service, mock_audit_logger_service
    ):
        """E6: Should accept agent_id filter."""
        mock_audit_logger_service.get_summary.return_value = {
            "total_events": 50,
            "by_event_type": {"mcp_tool_call": 48, "permission_denied": 2},
            "by_tool": {"notion.search_pages": 30},
            "by_agent": {"agent-sdr-001": 50},
            "time_range": {},
        }

        response = client_with_mock_service.get(
            "/api/v1/audit/summary",
            params={"agent_id": "agent-sdr-001"},
        )

        assert response.status_code == 200
        mock_audit_logger_service.get_summary.assert_called_once()

    def test_get_summary_with_user_email_filter(
        self, client_with_mock_service, mock_audit_logger_service
    ):
        """E6: Should accept user_email filter (alias for on_behalf_of)."""
        mock_audit_logger_service.get_summary.return_value = {
            "total_events": 30,
            "by_event_type": {"mcp_tool_call": 30},
            "by_tool": {"notion.search_pages": 20},
            "by_agent": {"agent-sdr-001": 30},
            "time_range": {},
        }

        response = client_with_mock_service.get(
            "/api/v1/audit/summary",
            params={"user_email": "sarah@acme.com"},
        )

        assert response.status_code == 200
        # Verify it was passed as on_behalf_of
        call_args = mock_audit_logger_service.get_summary.call_args
        assert call_args.kwargs.get("on_behalf_of") == "sarah@acme.com"

    def test_get_summary_with_time_range(
        self, client_with_mock_service, mock_audit_logger_service
    ):
        """E6: Should accept time range filters."""
        mock_audit_logger_service.get_summary.return_value = {
            "total_events": 20,
            "by_event_type": {"mcp_tool_call": 20},
            "by_tool": {"notion.search_pages": 10},
            "by_agent": {"agent-sdr-001": 20},
            "time_range": {"start": "2026-02-05T00:00:00Z", "end": "2026-02-06T00:00:00Z"},
        }

        response = client_with_mock_service.get(
            "/api/v1/audit/summary",
            params={
                "start_time": "2026-02-05T00:00:00Z",
                "end_time": "2026-02-06T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "time_range" in data


class TestGetSummaryIntegration:
    """Integration tests for summary endpoint with real DB."""

    def test_summary_returns_correct_totals(self, client):
        """E6 Integration: Should return correct totals."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        # Log several events
        for i in range(3):
            client.post(
                "/api/v1/audit/events",
                json={
                    "event_type": "mcp_tool_call",
                    "on_behalf_of": unique_user,
                    "agent_id": unique_agent,
                    "tool": "notion.search_pages",
                    "arguments": {"index": i},
                },
            )

        # Get summary for this agent
        response = client.get(
            "/api/v1/audit/summary",
            params={"agent_id": unique_agent},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] >= 3
        assert "mcp_tool_call" in data["by_event_type"]

    def test_summary_groups_by_tool_correctly(self, client):
        """E6 Integration: Should group by tool correctly."""
        unique_agent = unique_id()
        unique_user = f"{unique_id()}@acme.com"

        # Log events with different tools
        client.post(
            "/api/v1/audit/events",
            json={
                "event_type": "mcp_tool_call",
                "on_behalf_of": unique_user,
                "agent_id": unique_agent,
                "tool": "notion.search_pages",
                "arguments": {},
            },
        )
        client.post(
            "/api/v1/audit/events",
            json={
                "event_type": "mcp_tool_call",
                "on_behalf_of": unique_user,
                "agent_id": unique_agent,
                "tool": "slack.post_message",
                "arguments": {},
            },
        )

        # Get summary
        response = client.get(
            "/api/v1/audit/summary",
            params={"agent_id": unique_agent},
        )

        assert response.status_code == 200
        data = response.json()
        assert "notion.search_pages" in data["by_tool"]
        assert "slack.post_message" in data["by_tool"]
