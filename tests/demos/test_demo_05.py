"""
Unit tests for Demo 5: Unified Audit Trail (demo_05_unified_audit.py)

Tests the audit query functionality that answers:
"What did agent X do today?"
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Add demos directory to path for imports
demos_dir = Path(__file__).parent.parent.parent / "demos"
sys.path.insert(0, str(demos_dir))

from demo_05_unified_audit import (  # noqa: E402
    CONFIG,
    DemoConfig,
    AuditEvent,
    AuditQueryResult,
    AuditSummary,
    DemoResult,
    get_mock_events,
    calculate_summary,
    is_query_fast,
    calculate_speedup,
    run_demo,
)


# =============================================================================
# Configuration Tests
# =============================================================================


class TestDemoConfig:
    """Tests for DemoConfig dataclass."""
    
    def test_config_has_control_plane_url(self):
        """Config includes Control Plane URL."""
        config = DemoConfig()
        assert config.CONTROL_PLANE_URL is not None
        assert "localhost" in config.CONTROL_PLANE_URL or "http" in config.CONTROL_PLANE_URL
    
    def test_config_has_agent_id(self):
        """Config includes agent ID."""
        config = DemoConfig()
        assert config.AGENT_ID is not None
        assert len(config.AGENT_ID) > 0
    
    def test_config_has_agent_name(self):
        """Config includes agent name."""
        config = DemoConfig()
        assert config.AGENT_NAME is not None
        assert len(config.AGENT_NAME) > 0
    
    def test_config_has_user_email(self):
        """Config includes user email."""
        config = DemoConfig()
        assert config.USER_EMAIL is not None
        assert "@" in config.USER_EMAIL
    
    def test_config_has_user_id(self):
        """Config includes user ID."""
        config = DemoConfig()
        assert config.USER_ID is not None
        assert len(config.USER_ID) > 0
    
    def test_global_config_exists(self):
        """Global CONFIG instance exists."""
        assert CONFIG is not None
        assert isinstance(CONFIG, DemoConfig)


# =============================================================================
# AuditEvent Tests
# =============================================================================


class TestAuditEvent:
    """Tests for AuditEvent dataclass."""
    
    def test_audit_event_creation(self):
        """Can create an AuditEvent."""
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            agent_id="agent-001",
            on_behalf_of="user@example.com",
            tool="notion.search_pages",
            status="success",
            duration_ms=100,
        )
        assert event.agent_id == "agent-001"
        assert event.tool == "notion.search_pages"
        assert event.status == "success"
    
    def test_audit_event_with_backend(self):
        """AuditEvent can include backend."""
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            agent_id="agent-001",
            on_behalf_of="user@example.com",
            tool="notion.search_pages",
            status="success",
            duration_ms=100,
            backend="notion",
        )
        assert event.backend == "notion"
    
    def test_audit_event_with_request_id(self):
        """AuditEvent can include request ID."""
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc),
            agent_id="agent-001",
            on_behalf_of="user@example.com",
            tool="notion.search_pages",
            status="success",
            duration_ms=100,
            request_id="req-123",
        )
        assert event.request_id == "req-123"


# =============================================================================
# AuditQueryResult Tests
# =============================================================================


class TestAuditQueryResult:
    """Tests for AuditQueryResult dataclass."""
    
    def test_query_result_creation(self):
        """Can create an AuditQueryResult."""
        result = AuditQueryResult(
            events=[],
            query_time_ms=50.0,
            total_count=0,
        )
        assert result.query_time_ms == 50.0
        assert result.total_count == 0
    
    def test_query_result_with_filters(self):
        """AuditQueryResult can include filters."""
        result = AuditQueryResult(
            events=[],
            query_time_ms=50.0,
            total_count=0,
            filters_applied={"agent_id": "agent-001"},
        )
        assert result.filters_applied["agent_id"] == "agent-001"


# =============================================================================
# AuditSummary Tests
# =============================================================================


class TestAuditSummary:
    """Tests for AuditSummary dataclass."""
    
    def test_summary_creation(self):
        """Can create an AuditSummary."""
        summary = AuditSummary(
            total_events=10,
            success_count=8,
            denied_count=1,
            error_count=1,
            tool_counts={"notion.search_pages": 5},
            backend_counts={"notion": 5},
            avg_duration_ms=100.0,
        )
        assert summary.total_events == 10
        assert summary.success_count == 8
        assert summary.denied_count == 1


# =============================================================================
# DemoResult Tests
# =============================================================================


class TestDemoResult:
    """Tests for DemoResult dataclass."""
    
    def test_demo_result_success(self):
        """Can create a successful DemoResult."""
        result = DemoResult(
            success=True,
            query_time_ms=50.0,
            events_found=8,
            under_one_second=True,
        )
        assert result.success is True
        assert result.under_one_second is True
        assert result.error is None
    
    def test_demo_result_failure(self):
        """Can create a failed DemoResult."""
        result = DemoResult(
            success=False,
            query_time_ms=0.0,
            events_found=0,
            under_one_second=False,
            error="Connection failed",
        )
        assert result.success is False
        assert result.error == "Connection failed"


# =============================================================================
# Mock Events Tests
# =============================================================================


class TestMockEvents:
    """Tests for mock event data."""
    
    def test_mock_events_exist(self):
        """Mock events are defined."""
        events = get_mock_events()
        assert len(events) >= 5
    
    def test_mock_events_have_required_fields(self):
        """Mock events have all required fields."""
        events = get_mock_events()
        for event in events:
            assert event.timestamp is not None
            assert event.agent_id is not None
            assert event.on_behalf_of is not None
            assert event.tool is not None
            assert event.status in ["success", "denied", "error"]
            assert event.duration_ms >= 0
    
    def test_mock_events_include_denied(self):
        """Mock events include at least one denied status."""
        events = get_mock_events()
        denied_events = [e for e in events if e.status == "denied"]
        assert len(denied_events) >= 1
    
    def test_mock_events_are_recent(self):
        """Mock events are within the last day."""
        events = get_mock_events()
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        for event in events:
            assert event.timestamp >= one_day_ago
    
    def test_mock_events_have_multiple_backends(self):
        """Mock events span multiple backends."""
        events = get_mock_events()
        backends = set(e.backend for e in events if e.backend)
        assert len(backends) >= 2
    
    def test_mock_events_have_multiple_tools(self):
        """Mock events include multiple different tools."""
        events = get_mock_events()
        tools = set(e.tool for e in events)
        assert len(tools) >= 3
    
    def test_mock_events_have_consistent_agent(self):
        """All mock events are from the same agent."""
        events = get_mock_events()
        agent_ids = set(e.agent_id for e in events)
        assert len(agent_ids) == 1
        assert CONFIG.AGENT_ID in agent_ids


# =============================================================================
# Summary Calculation Tests
# =============================================================================


class TestSummaryCalculation:
    """Tests for summary calculation functions."""
    
    def test_calculate_summary_empty(self):
        """Can calculate summary for empty events."""
        summary = calculate_summary([])
        assert summary.total_events == 0
        assert summary.success_count == 0
        assert summary.avg_duration_ms == 0.0
    
    def test_calculate_summary_counts_status(self):
        """Summary correctly counts by status."""
        events = get_mock_events()
        summary = calculate_summary(events)
        
        assert summary.total_events == len(events)
        assert summary.success_count + summary.denied_count + summary.error_count == len(events)
    
    def test_calculate_summary_counts_tools(self):
        """Summary correctly counts by tool."""
        events = get_mock_events()
        summary = calculate_summary(events)
        
        total_tool_count = sum(summary.tool_counts.values())
        assert total_tool_count == len(events)
    
    def test_calculate_summary_counts_backends(self):
        """Summary correctly counts by backend."""
        events = get_mock_events()
        summary = calculate_summary(events)
        
        # Only events with backend are counted
        events_with_backend = [e for e in events if e.backend]
        total_backend_count = sum(summary.backend_counts.values())
        assert total_backend_count == len(events_with_backend)
    
    def test_calculate_summary_avg_duration(self):
        """Summary correctly calculates average duration."""
        events = get_mock_events()
        summary = calculate_summary(events)
        
        expected_avg = sum(e.duration_ms for e in events) / len(events)
        assert abs(summary.avg_duration_ms - expected_avg) < 0.01


# =============================================================================
# Query Speed Tests
# =============================================================================


class TestQuerySpeed:
    """Tests for query speed functions."""
    
    def test_is_query_fast_under_threshold(self):
        """Query under 1 second is fast."""
        assert is_query_fast(50.0) is True
        assert is_query_fast(500.0) is True
        assert is_query_fast(999.0) is True
    
    def test_is_query_fast_over_threshold(self):
        """Query over 1 second is not fast."""
        assert is_query_fast(1000.0) is False
        assert is_query_fast(1001.0) is False
        assert is_query_fast(5000.0) is False
    
    def test_calculate_speedup(self):
        """Speedup calculation is correct."""
        # 4 hours = 14,400,000 ms
        speedup = calculate_speedup(100.0)
        expected = (4 * 60 * 60 * 1000) / 100.0  # 144,000x
        assert abs(speedup - expected) < 1.0
    
    def test_calculate_speedup_zero_time(self):
        """Speedup handles zero time."""
        speedup = calculate_speedup(0.0)
        assert speedup == 0


# =============================================================================
# Demo Execution Tests
# =============================================================================


class TestDemoExecution:
    """Tests for demo execution."""
    
    @pytest.mark.asyncio
    async def test_demo_runs_in_mock_mode(self):
        """Demo runs successfully in mock mode."""
        result = await run_demo(mock_mode=True)
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_demo_finds_events(self):
        """Demo finds audit events."""
        result = await run_demo(mock_mode=True)
        assert result.events_found > 0
    
    @pytest.mark.asyncio
    async def test_demo_query_is_fast(self):
        """Demo query completes under 1 second."""
        result = await run_demo(mock_mode=True)
        assert result.under_one_second is True
    
    @pytest.mark.asyncio
    async def test_demo_no_errors_in_mock_mode(self):
        """No errors in mock mode."""
        result = await run_demo(mock_mode=True)
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_demo_query_time_is_positive(self):
        """Query time is positive."""
        result = await run_demo(mock_mode=True)
        assert result.query_time_ms > 0


# =============================================================================
# Value Proposition Tests
# =============================================================================


class TestValueProposition:
    """Tests that verify the demo's value proposition."""
    
    def test_traditional_approach_time(self):
        """Traditional approach takes ~4 hours."""
        # 4 hours in milliseconds
        traditional_time_ms = 4 * 60 * 60 * 1000
        assert traditional_time_ms == 14_400_000
    
    def test_sub_second_query_possible(self):
        """Sub-second query is achievable in mock mode."""
        # Mock events should be returned instantly
        events = get_mock_events()
        assert len(events) > 0
    
    def test_filter_by_agent_possible(self):
        """Events can be filtered by agent."""
        events = get_mock_events()
        agent_id = CONFIG.AGENT_ID
        filtered = [e for e in events if e.agent_id == agent_id]
        assert len(filtered) == len(events)  # All mock events are same agent
    
    def test_filter_by_status_possible(self):
        """Events can be filtered by status."""
        events = get_mock_events()
        success_events = [e for e in events if e.status == "success"]
        denied_events = [e for e in events if e.status == "denied"]
        assert len(success_events) > 0
        assert len(denied_events) > 0
    
    def test_filter_by_tool_possible(self):
        """Events can be filtered by tool."""
        events = get_mock_events()
        notion_events = [e for e in events if "notion" in e.tool]
        assert len(notion_events) > 0
    
    def test_filter_by_backend_possible(self):
        """Events can be filtered by backend."""
        events = get_mock_events()
        notion_events = [e for e in events if e.backend == "notion"]
        slack_events = [e for e in events if e.backend == "slack"]
        assert len(notion_events) > 0
        assert len(slack_events) > 0
    
    def test_complete_audit_trail(self):
        """Each event has complete audit information."""
        events = get_mock_events()
        for event in events:
            # Required for audit trail
            assert event.timestamp is not None
            assert event.agent_id is not None
            assert event.on_behalf_of is not None  # User attribution
            assert event.tool is not None
            assert event.status is not None
            assert event.duration_ms is not None


# =============================================================================
# Compliance Tests
# =============================================================================


class TestCompliance:
    """Tests for compliance-related features."""
    
    def test_user_attribution(self):
        """All events attribute action to user."""
        events = get_mock_events()
        for event in events:
            assert event.on_behalf_of is not None
            assert "@" in event.on_behalf_of  # Email format
    
    def test_timestamp_precision(self):
        """Events have precise timestamps."""
        events = get_mock_events()
        for event in events:
            assert isinstance(event.timestamp, datetime)
            # Timezone-aware
            assert event.timestamp.tzinfo is not None
    
    def test_request_tracking(self):
        """Events can include request IDs for correlation."""
        events = get_mock_events()
        events_with_request_id = [e for e in events if e.request_id]
        assert len(events_with_request_id) > 0
    
    def test_denied_actions_logged(self):
        """Denied actions are also logged."""
        events = get_mock_events()
        denied = [e for e in events if e.status == "denied"]
        assert len(denied) >= 1
        
        # Denied event has same required fields
        for event in denied:
            assert event.agent_id is not None
            assert event.tool is not None
            assert event.on_behalf_of is not None
