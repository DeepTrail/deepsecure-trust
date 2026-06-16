#!/usr/bin/env python3
"""
Demo 5: Unified Audit Trail

Demonstrates that a single API query can answer:
"What did agent X do today?"

Value Proposition:
- All agent activity logged in one place
- Sub-second query response (< 1 second)
- Filter by agent, user, tool, status, time
- Complete audit trail for compliance

Usage:
    # With mock mode (no services required)
    python demo_05_unified_audit.py --mock
    
    # With real services (requires Control Plane with E6 API)
    python demo_05_unified_audit.py

Reference:
    Design Doc Section 5.5 - Demo 5: Unified Audit Trail
"""

import argparse
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class DemoConfig:
    """Configuration for the unified audit demo."""
    CONTROL_PLANE_URL: str = "http://localhost:8000"
    AGENT_ID: str = "agent-sdr-001"
    AGENT_NAME: str = "SDR-Assistant"
    USER_EMAIL: str = "sarah@acme.com"
    USER_ID: str = "user-sarah-123"


# Global config instance
CONFIG = DemoConfig()


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AuditEvent:
    """Represents a single audit event."""
    timestamp: datetime
    agent_id: str
    on_behalf_of: str
    tool: str
    status: str
    duration_ms: int
    backend: str = ""
    request_id: str = ""


@dataclass
class AuditQueryResult:
    """Result of an audit query."""
    events: list[AuditEvent]
    query_time_ms: float
    total_count: int
    filters_applied: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditSummary:
    """Summary statistics for audit events."""
    total_events: int
    success_count: int
    denied_count: int
    error_count: int
    tool_counts: dict[str, int]
    backend_counts: dict[str, int]
    avg_duration_ms: float


@dataclass
class DemoResult:
    """Result of running the demo."""
    success: bool
    query_time_ms: float
    events_found: int
    under_one_second: bool
    error: str | None = None


# =============================================================================
# Mock Data
# =============================================================================


def get_mock_events() -> list[AuditEvent]:
    """Get mock audit events for demo."""
    now = datetime.now(timezone.utc)
    
    return [
        AuditEvent(
            timestamp=now - timedelta(hours=2, minutes=15),
            agent_id=CONFIG.AGENT_ID,
            on_behalf_of=CONFIG.USER_EMAIL,
            tool="notion.search_pages",
            status="success",
            duration_ms=145,
            backend="notion",
            request_id="req-001",
        ),
        AuditEvent(
            timestamp=now - timedelta(hours=2, minutes=14),
            agent_id=CONFIG.AGENT_ID,
            on_behalf_of=CONFIG.USER_EMAIL,
            tool="notion.read_page",
            status="success",
            duration_ms=89,
            backend="notion",
            request_id="req-002",
        ),
        AuditEvent(
            timestamp=now - timedelta(hours=2, minutes=13),
            agent_id=CONFIG.AGENT_ID,
            on_behalf_of=CONFIG.USER_EMAIL,
            tool="notion.create_page",
            status="denied",
            duration_ms=12,
            backend="notion",
            request_id="req-003",
        ),
        AuditEvent(
            timestamp=now - timedelta(hours=1, minutes=45),
            agent_id=CONFIG.AGENT_ID,
            on_behalf_of=CONFIG.USER_EMAIL,
            tool="slack.search_messages",
            status="success",
            duration_ms=234,
            backend="slack",
            request_id="req-004",
        ),
        AuditEvent(
            timestamp=now - timedelta(hours=1, minutes=30),
            agent_id=CONFIG.AGENT_ID,
            on_behalf_of=CONFIG.USER_EMAIL,
            tool="slack.list_channels",
            status="success",
            duration_ms=67,
            backend="slack",
            request_id="req-005",
        ),
        AuditEvent(
            timestamp=now - timedelta(minutes=45),
            agent_id=CONFIG.AGENT_ID,
            on_behalf_of=CONFIG.USER_EMAIL,
            tool="gmail.search_messages",
            status="success",
            duration_ms=178,
            backend="gmail",
            request_id="req-006",
        ),
        AuditEvent(
            timestamp=now - timedelta(minutes=30),
            agent_id=CONFIG.AGENT_ID,
            on_behalf_of=CONFIG.USER_EMAIL,
            tool="gmail.list_messages",
            status="success",
            duration_ms=156,
            backend="gmail",
            request_id="req-007",
        ),
        AuditEvent(
            timestamp=now - timedelta(minutes=15),
            agent_id=CONFIG.AGENT_ID,
            on_behalf_of=CONFIG.USER_EMAIL,
            tool="notion.search_pages",
            status="success",
            duration_ms=112,
            backend="notion",
            request_id="req-008",
        ),
    ]


# =============================================================================
# Audit Summary Calculation
# =============================================================================


def calculate_summary(events: list[AuditEvent]) -> AuditSummary:
    """Calculate summary statistics from audit events."""
    if not events:
        return AuditSummary(
            total_events=0,
            success_count=0,
            denied_count=0,
            error_count=0,
            tool_counts={},
            backend_counts={},
            avg_duration_ms=0.0,
        )
    
    success_count = sum(1 for e in events if e.status == "success")
    denied_count = sum(1 for e in events if e.status == "denied")
    error_count = sum(1 for e in events if e.status == "error")
    
    tool_counts: dict[str, int] = {}
    backend_counts: dict[str, int] = {}
    
    for event in events:
        tool_counts[event.tool] = tool_counts.get(event.tool, 0) + 1
        if event.backend:
            backend_counts[event.backend] = backend_counts.get(event.backend, 0) + 1
    
    avg_duration = sum(e.duration_ms for e in events) / len(events)
    
    return AuditSummary(
        total_events=len(events),
        success_count=success_count,
        denied_count=denied_count,
        error_count=error_count,
        tool_counts=tool_counts,
        backend_counts=backend_counts,
        avg_duration_ms=avg_duration,
    )


def is_query_fast(query_time_ms: float) -> bool:
    """Check if query completed under 1 second threshold."""
    return query_time_ms < 1000


def calculate_speedup(query_time_ms: float) -> float:
    """Calculate speedup vs traditional 4-hour approach."""
    traditional_time_ms = 4 * 60 * 60 * 1000  # 4 hours in ms
    return traditional_time_ms / query_time_ms if query_time_ms > 0 else 0


# =============================================================================
# Display Functions
# =============================================================================


def print_banner() -> None:
    """Print demo banner."""
    print()
    print("=" * 70)
    print("  DEMO 5: UNIFIED AUDIT TRAIL")
    print("=" * 70)
    print()
    print("  Value Proposition:")
    print("  • Answer 'What did agent X do?' in < 1 second")
    print("  • All agent activity logged in one place")
    print("  • Filter by agent, user, tool, status, time")
    print("  • Complete audit trail for compliance")
    print()
    print("-" * 70)


def print_section(title: str, icon: str = "📋") -> None:
    """Print section header."""
    print()
    print(f"{icon} {title}")
    print("-" * 50)


def print_query_info(agent_id: str, time_range: str) -> None:
    """Print query information."""
    print_section("AUDIT QUERY", "🔍")
    
    print()
    print(f"   Question: 'What did agent {agent_id} do today?'")
    print()
    print("   API Request:")
    print(f"   GET {CONFIG.CONTROL_PLANE_URL}/api/v1/audit/events")
    print(f"       ?agent_id={agent_id}")
    print(f"       &start_time={time_range}")
    print()
    print("   Filters Available:")
    print("   • agent_id - Filter by specific agent")
    print("   • user_id - Filter by delegating user")
    print("   • tool - Filter by tool name")
    print("   • status - Filter by success/denied/error")
    print("   • start_time/end_time - Time range")


def print_events_table(events: list[AuditEvent], query_time_ms: float) -> None:
    """Print events in table format."""
    print_section(f"QUERY RESULTS ({len(events)} events)", "📊")
    
    print()
    print(f"   Query completed in: {query_time_ms:.1f}ms")
    
    if is_query_fast(query_time_ms):
        print("   ✓ Under 1 second threshold!")
    else:
        print("   ⚠ Query exceeded 1 second threshold")
    
    print()
    
    # Table header
    print("   " + "-" * 70)
    print(f"   {'Timestamp':<12} {'Tool':<28} {'Status':<10} {'Duration':<10} {'Backend':<10}")
    print("   " + "-" * 70)
    
    # Table rows
    for event in events:
        ts = event.timestamp.strftime("%H:%M:%S")
        status_icon = "✓" if event.status == "success" else "✗"
        duration_str = f"{event.duration_ms}ms"
        print(f"   {ts:<12} {event.tool:<28} {status_icon} {event.status:<7} {duration_str:<10} {event.backend:<10}")
    
    print("   " + "-" * 70)
    
    if events:
        print(f"   Agent: {events[0].agent_id}")
        print(f"   On behalf of: {events[0].on_behalf_of}")


def print_summary(summary: AuditSummary) -> None:
    """Print summary statistics."""
    print_section("AUDIT SUMMARY", "📈")
    
    print()
    print(f"   Total Events: {summary.total_events}")
    print()
    print("   By Status:")
    print(f"   ✓ Success: {summary.success_count}")
    print(f"   ✗ Denied:  {summary.denied_count}")
    print(f"   ⚠ Error:   {summary.error_count}")
    
    if summary.tool_counts:
        print()
        print("   By Tool:")
        for tool, count in sorted(summary.tool_counts.items(), key=lambda x: -x[1]):
            print(f"   • {tool}: {count}")
    
    if summary.backend_counts:
        print()
        print("   By Backend:")
        for backend, count in sorted(summary.backend_counts.items(), key=lambda x: -x[1]):
            print(f"   • {backend}: {count}")
    
    print()
    print(f"   Average Duration: {summary.avg_duration_ms:.1f}ms")


def print_comparison() -> None:
    """Print comparison between traditional and DeepSecure approaches."""
    print_section("COMPARISON: Traditional vs DeepSecure", "⚖️")
    
    print("""
   ┌─────────────────────────────────────────────────────────────────┐
   │                    TRADITIONAL APPROACH                         │
   ├─────────────────────────────────────────────────────────────────┤
   │                                                                 │
   │  To answer "What did agent X do today?":                        │
   │                                                                 │
   │  1. Check Notion audit logs              → 30 min               │
   │  2. Check Slack audit logs               → 30 min               │
   │  3. Check Google Drive audit logs          → 30 min               │
   │  4. Cross-reference agent identity       → 60 min               │
   │  5. Correlate timestamps                 → 60 min               │
   │  6. Compile report                       → 60 min               │
   │                                                                 │
   │  Total time: ~4 HOURS                                           │
   │                                                                 │
   └─────────────────────────────────────────────────────────────────┘
   
   ┌─────────────────────────────────────────────────────────────────┐
   │                    DEEPSECURE APPROACH                          │
   ├─────────────────────────────────────────────────────────────────┤
   │                                                                 │
   │  To answer "What did agent X do today?":                        │
   │                                                                 │
   │  GET /api/v1/audit/events?agent_id=agent-sdr-001                │
   │                                                                 │
   │  Total time: < 1 SECOND                                         │
   │                                                                 │
   │  Why? All activity flows through gateway, logged centrally.     │
   │                                                                 │
   └─────────────────────────────────────────────────────────────────┘
""")


def print_sql_example() -> None:
    """Print SQL query example from design doc."""
    print_section("EQUIVALENT SQL QUERY", "💾")
    
    print("""
   -- Query audit logs (what the API does internally)
   SELECT timestamp, tool, result, on_behalf_of
   FROM audit_logs
   WHERE agent_id = 'agent-sdr-001'
     AND timestamp > NOW() - INTERVAL '1 day';

   -- Result:
   -- 10:15:32 | notion.search_pages   | success | sarah@acme.com
   -- 10:16:45 | notion.create_page    | denied  | sarah@acme.com
   -- 10:17:12 | slack.search_messages | success | sarah@acme.com
""")


def print_final_summary(query_time_ms: float, events_found: int) -> None:
    """Print final summary with key metrics."""
    print()
    print("=" * 70)
    print("  ✅ KEY INSIGHTS")
    print("=" * 70)
    print()
    print(f"   Query time:    {query_time_ms:.1f}ms")
    print(f"   Events found:  {events_found}")
    print()
    
    if is_query_fast(query_time_ms):
        speedup = calculate_speedup(query_time_ms)
        print("   ✓ SUCCESS: Query completed in under 1 second!")
        print()
        print("   Traditional approach: ~4 hours")
        print(f"   DeepSecure approach:  {query_time_ms:.0f}ms")
        print()
        print(f"   Speedup: {speedup:,.0f}x faster")
    else:
        print("   ⚠ Query took longer than 1 second - investigate!")
    
    print()
    print("   COMPLIANCE VALUE:")
    print("   ┌─────────────────────────────────────────────────────┐")
    print("   │ • Instant audit trail for any agent                 │")
    print("   │ • All actions attributed to delegating user         │")
    print("   │ • Complete history for incident investigation       │")
    print("   │ • Filter by time, tool, status, backend             │")
    print("   └─────────────────────────────────────────────────────┘")
    print()
    print("=" * 70)
    print()


# =============================================================================
# Main Demo Function
# =============================================================================


async def run_demo(mock_mode: bool = False) -> DemoResult:
    """
    Run the unified audit trail demo.
    
    Args:
        mock_mode: If True, use mock data instead of live API
        
    Returns:
        DemoResult with execution metrics
    """
    print_banner()
    
    if mock_mode:
        print("🎭 Running in MOCK MODE (no services required)")
    else:
        print("🔌 Running with LIVE SERVICES")
    print("-" * 70)
    
    try:
        # Query info
        time_range = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        print_query_info(CONFIG.AGENT_ID, time_range)
        
        # Execute query
        start_time = time.time()
        
        if mock_mode:
            # Simulate network latency
            await asyncio.sleep(0.05)
            events = get_mock_events()
        else:
            # Real API call
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{CONFIG.CONTROL_PLANE_URL}/api/v1/audit/events",
                        params={
                            "agent_id": CONFIG.AGENT_ID,
                            "start_time": time_range,
                        },
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    data = response.json()
                    events = [
                        AuditEvent(
                            timestamp=datetime.fromisoformat(e["timestamp"]),
                            agent_id=e["agent_id"],
                            on_behalf_of=e.get("on_behalf_of", ""),
                            tool=e["tool"],
                            status=e["status"],
                            duration_ms=e.get("duration_ms", 0),
                            backend=e.get("backend", ""),
                            request_id=e.get("request_id", ""),
                        )
                        for e in data.get("events", [])
                    ]
            except ImportError:
                print("\n   ⚠ httpx not available, falling back to mock data")
                await asyncio.sleep(0.05)
                events = get_mock_events()
            except Exception as e:
                print(f"\n   ⚠ API call failed: {e}")
                print("   Falling back to mock data...")
                await asyncio.sleep(0.05)
                events = get_mock_events()
        
        query_time_ms = (time.time() - start_time) * 1000
        
        # Display results
        print_events_table(events, query_time_ms)
        
        # Calculate and display summary
        summary = calculate_summary(events)
        print_summary(summary)
        
        # Show comparison
        print_comparison()
        
        # Show SQL example
        print_sql_example()
        
        # Final summary
        print_final_summary(query_time_ms, len(events))
        
        return DemoResult(
            success=True,
            query_time_ms=query_time_ms,
            events_found=len(events),
            under_one_second=is_query_fast(query_time_ms),
        )
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ Error: {error_msg}")
        
        return DemoResult(
            success=False,
            query_time_ms=0.0,
            events_found=0,
            under_one_second=False,
            error=error_msg,
        )


# =============================================================================
# CLI Entry Point
# =============================================================================


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Demo 5: Unified Audit Trail - "
                    "Answer 'What did agent X do?' in under 1 second",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with mock data
    python demo_05_unified_audit.py --mock
    
    # Run with live Control Plane
    python demo_05_unified_audit.py
        """,
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode (no services required)",
    )
    args = parser.parse_args()
    
    result = asyncio.run(run_demo(mock_mode=args.mock))
    
    return 0 if result.success else 1


if __name__ == "__main__":
    exit(main())
