# Task: WS-F6 Create Demo 5: Unified Audit Trail

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `pending` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-F: Integration & Demos |
| **Code Dependencies** | E6 (Audit query API) ⬜ |
| **Runtime Dependencies** | Control Plane with audit API, Gateway |
| **Blocked By** | E6 (must complete first) |
| **Assigned** | - |
| **Created** | February 6, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 9 |
| **Target Worktree** | `vmcp-gateway` |

---

## Dependencies

### Code Dependencies (must complete before starting)

| Task | What We Need | Status |
|------|--------------|--------|
| E6 | Audit query API to retrieve events | ⬜ Pending |

### Runtime Dependencies (must be deployed for integration testing)

| Service | Endpoint | Required For |
|---------|----------|--------------|
| Control Plane | `http://localhost:8000` | Audit query API |
| Gateway | `http://localhost:8002` | Tool execution (generates events) |
| PostgreSQL | `localhost:5434` | Audit event storage |

### Development Mode

When runtime dependencies are unavailable:

- [x] **Fallback behavior**: Demo uses mocked audit data
- [x] **Local testing**: Unit tests verify demo script structure
- [x] **Integration testing**: Full demo requires E6 and database

---

## Pre-Conditions

Before starting this task, ensure:

- [ ] E6 (Audit query API) is complete
- [ ] `/api/v1/audit/events` endpoint is available
- [ ] Some audit events exist in database (from prior demos)

---

## Task Description

Create **Demo 5: Unified Audit Trail** - a demonstration script that shows a single query can answer "What did agent X do today?"

### Context

From the design doc (Section 5.5):
```sql
-- Query audit logs
SELECT timestamp, tool, result, on_behalf_of
FROM audit_logs
WHERE agent_id = 'agent-sdr-001'
  AND timestamp > NOW() - INTERVAL '1 day';

-- Result:
-- 10:15:32 | notion.search_pages   | success | sarah@acme.com
-- 10:16:45 | notion.create_page    | denied  | sarah@acme.com
-- 10:17:12 | slack.search_messages | success | sarah@acme.com
```

**Success Criteria**: Answer "what did agent X do?" in <1 second (not 4 hours).

### Technical Notes

The demo should:
1. Generate some agent activity (or use existing events)
2. Query the audit API with various filters
3. Display results in a human-readable format
4. Measure and report query latency

---

## Acceptance Criteria

- [ ] Demo queries audit events via API
- [ ] Demo shows results in table format
- [ ] Demo measures query latency (< 1 second)
- [ ] Demo supports filtering by agent, user, tool, time
- [ ] Demo shows summary statistics
- [ ] Includes both real and mock modes
- [ ] No new linting errors introduced

---

## Files to Modify/Create

### Files to Create

- `deeptrail-gateway/demos/demo_05_unified_audit.py` - Main demo script

### Files to Modify

- `deeptrail-gateway/demos/README.md` - Add Demo 5 instructions

### Tests to Add

- `deeptrail-gateway/tests/demos/test_demo_05.py` - Demo script validation

---

## Implementation Details

### Demo Script

```python
#!/usr/bin/env python3
"""
Demo 5: Unified Audit Trail

Demonstrates that a single API query can answer:
"What did agent X do today?"

Value Proposition:
- All agent activity in one place
- Sub-second query response
- Filter by agent, user, tool, status
- Complete audit trail for compliance

Usage:
    python demo_05_unified_audit.py --mock
"""

import asyncio
import argparse
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AuditEvent:
    """Represents a single audit event."""
    timestamp: datetime
    agent_id: str
    on_behalf_of: str
    tool: str
    status: str
    duration_ms: int


# Demo configuration
CONTROL_PLANE_URL = "http://localhost:8000"
AGENT_ID = "agent-sdr-001"
USER_EMAIL = "sarah@acme.com"

# Mock audit events for demo
MOCK_EVENTS = [
    AuditEvent(
        timestamp=datetime.now() - timedelta(hours=2, minutes=15),
        agent_id=AGENT_ID,
        on_behalf_of=USER_EMAIL,
        tool="notion.search_pages",
        status="success",
        duration_ms=145
    ),
    AuditEvent(
        timestamp=datetime.now() - timedelta(hours=2, minutes=14),
        agent_id=AGENT_ID,
        on_behalf_of=USER_EMAIL,
        tool="notion.read_page",
        status="success",
        duration_ms=89
    ),
    AuditEvent(
        timestamp=datetime.now() - timedelta(hours=2, minutes=13),
        agent_id=AGENT_ID,
        on_behalf_of=USER_EMAIL,
        tool="notion.create_page",
        status="denied",
        duration_ms=12
    ),
    AuditEvent(
        timestamp=datetime.now() - timedelta(hours=1, minutes=45),
        agent_id=AGENT_ID,
        on_behalf_of=USER_EMAIL,
        tool="slack.search_messages",
        status="success",
        duration_ms=234
    ),
    AuditEvent(
        timestamp=datetime.now() - timedelta(hours=1, minutes=30),
        agent_id=AGENT_ID,
        on_behalf_of=USER_EMAIL,
        tool="slack.list_channels",
        status="success",
        duration_ms=67
    ),
    AuditEvent(
        timestamp=datetime.now() - timedelta(minutes=45),
        agent_id=AGENT_ID,
        on_behalf_of=USER_EMAIL,
        tool="notion.search_pages",
        status="success",
        duration_ms=112
    ),
]


def print_banner():
    """Print demo banner."""
    print("\n" + "=" * 70)
    print(" DEMO 5: UNIFIED AUDIT TRAIL")
    print("=" * 70)
    print()
    print(" Value Proposition:")
    print(" • Answer 'What did agent X do?' in < 1 second")
    print(" • All agent activity logged in one place")
    print(" • Filter by agent, user, tool, status, time")
    print(" • Complete audit trail for compliance")
    print()
    print("-" * 70)


def print_section(title: str, icon: str = "📋"):
    """Print section header."""
    print(f"\n{icon} {title}")
    print("-" * 50)


def print_query_info(agent_id: str, time_range: str):
    """Print query information."""
    print_section("AUDIT QUERY", "🔍")
    
    print(f"\n   Question: 'What did agent {agent_id} do today?'")
    print()
    print("   API Request:")
    print(f"   GET {CONTROL_PLANE_URL}/api/v1/audit/events")
    print(f"       ?agent_id={agent_id}")
    print(f"       &start_time={time_range}")


def print_events_table(events: List[AuditEvent], query_time_ms: float):
    """Print events in table format."""
    print_section(f"QUERY RESULTS ({len(events)} events)", "📊")
    
    print(f"\n   Query completed in: {query_time_ms:.1f}ms")
    print()
    
    # Table header
    print("   " + "-" * 65)
    print(f"   {'Timestamp':<20} {'Tool':<25} {'Status':<10} {'Duration':<10}")
    print("   " + "-" * 65)
    
    # Table rows
    for event in events:
        ts = event.timestamp.strftime("%H:%M:%S")
        status_icon = "✓" if event.status == "success" else "✗"
        print(f"   {ts:<20} {event.tool:<25} {status_icon} {event.status:<7} {event.duration_ms}ms")
    
    print("   " + "-" * 65)
    print(f"   On behalf of: {events[0].on_behalf_of if events else 'N/A'}")


def print_summary(events: List[AuditEvent]):
    """Print summary statistics."""
    print_section("AUDIT SUMMARY", "📈")
    
    # Count by status
    success_count = sum(1 for e in events if e.status == "success")
    denied_count = sum(1 for e in events if e.status == "denied")
    error_count = sum(1 for e in events if e.status == "error")
    
    # Count by tool
    tool_counts: Dict[str, int] = {}
    for event in events:
        tool_counts[event.tool] = tool_counts.get(event.tool, 0) + 1
    
    print("\n   By Status:")
    print(f"   ✓ Success: {success_count}")
    print(f"   ✗ Denied:  {denied_count}")
    print(f"   ⚠ Error:   {error_count}")
    
    print("\n   By Tool:")
    for tool, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
        print(f"   • {tool}: {count}")
    
    # Average latency
    avg_latency = sum(e.duration_ms for e in events) / len(events) if events else 0
    print(f"\n   Average latency: {avg_latency:.1f}ms")


def compare_traditional_approach():
    """Compare with traditional audit approach."""
    print_section("COMPARISON: Traditional vs DeepSecure", "⚖️")
    
    print("""
   ┌─────────────────────────────────────────────────────────────────┐
   │                    TRADITIONAL APPROACH                         │
   ├─────────────────────────────────────────────────────────────────┤
   │                                                                  │
   │  To answer "What did agent X do today?":                        │
   │                                                                  │
   │  1. Check Notion audit logs              → 30 min               │
   │  2. Check Slack audit logs               → 30 min               │
   │  3. Check HubSpot audit logs             → 30 min               │
   │  4. Cross-reference agent identity       → 60 min               │
   │  5. Correlate timestamps                 → 60 min               │
   │  6. Compile report                       → 60 min               │
   │                                                                  │
   │  Total time: ~4 HOURS                                           │
   │                                                                  │
   └─────────────────────────────────────────────────────────────────┘
   
   ┌─────────────────────────────────────────────────────────────────┐
   │                    DEEPSECURE APPROACH                          │
   ├─────────────────────────────────────────────────────────────────┤
   │                                                                  │
   │  To answer "What did agent X do today?":                        │
   │                                                                  │
   │  GET /api/v1/audit/events?agent_id=agent-sdr-001               │
   │                                                                  │
   │  Total time: < 1 SECOND                                         │
   │                                                                  │
   │  Why? All activity flows through gateway, logged centrally.     │
   │                                                                  │
   └─────────────────────────────────────────────────────────────────┘
""")


def print_final_summary(query_time_ms: float):
    """Print final summary."""
    print("\n" + "=" * 70)
    print(" ✅ KEY INSIGHT")
    print("=" * 70)
    print()
    print(f"   Query time: {query_time_ms:.1f}ms")
    print()
    if query_time_ms < 1000:
        print("   ✓ SUCCESS: Query completed in under 1 second!")
        print()
        print("   Traditional approach: ~4 hours")
        print(f"   DeepSecure approach:  {query_time_ms:.0f}ms")
        print()
        speedup = (4 * 60 * 60 * 1000) / query_time_ms
        print(f"   Speedup: {speedup:,.0f}x faster")
    else:
        print("   ⚠ Query took longer than 1 second - investigate!")
    print()
    print("=" * 70)


async def run_demo(mock_mode: bool = False):
    """Run the demo."""
    print_banner()
    
    if mock_mode:
        print("🎭 Running in MOCK MODE")
    else:
        print("🔌 Running with LIVE SERVICES")
    print("-" * 70)
    
    # Query info
    time_range = (datetime.now() - timedelta(days=1)).isoformat()
    print_query_info(AGENT_ID, time_range)
    
    # Simulate query (or make real API call)
    start_time = time.time()
    
    if mock_mode:
        await asyncio.sleep(0.05)  # Simulate network latency
        events = MOCK_EVENTS
    else:
        # Real API call would go here
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CONTROL_PLANE_URL}/api/v1/audit/events",
                params={
                    "agent_id": AGENT_ID,
                    "start_time": time_range
                }
            )
            data = response.json()
            events = [AuditEvent(**e) for e in data.get("events", [])]
    
    query_time_ms = (time.time() - start_time) * 1000
    
    # Display results
    print_events_table(events, query_time_ms)
    print_summary(events)
    compare_traditional_approach()
    print_final_summary(query_time_ms)
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Demo 5: Unified Audit Trail"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode"
    )
    args = parser.parse_args()
    
    exit_code = asyncio.run(run_demo(mock_mode=args.mock))
    exit(exit_code)


if __name__ == "__main__":
    main()
```

---

## Test Cases

### Unit Tests

```python
# tests/demos/test_demo_05.py

import pytest
from datetime import datetime, timedelta
from demos.demo_05_unified_audit import AuditEvent, MOCK_EVENTS

class TestDemo05:
    
    def test_mock_events_exist(self):
        """Mock events are defined."""
        assert len(MOCK_EVENTS) >= 5
    
    def test_mock_events_have_required_fields(self):
        """Mock events have all required fields."""
        for event in MOCK_EVENTS:
            assert event.timestamp is not None
            assert event.agent_id is not None
            assert event.on_behalf_of is not None
            assert event.tool is not None
            assert event.status in ["success", "denied", "error"]
    
    def test_mock_events_include_denied(self):
        """Mock events include at least one denied status."""
        denied_events = [e for e in MOCK_EVENTS if e.status == "denied"]
        assert len(denied_events) >= 1
    
    def test_events_are_recent(self):
        """Mock events are within the last day."""
        one_day_ago = datetime.now() - timedelta(days=1)
        for event in MOCK_EVENTS:
            assert event.timestamp >= one_day_ago
```

---

## Post-Conditions

### Code Complete (enables dependent tasks to start)

- [ ] All acceptance criteria met
- [ ] Unit tests pass locally: `pytest deeptrail-gateway/tests/demos/`
- [ ] Demo runs in mock mode
- [ ] Completion report created

### Integration Complete (validated at merge point)

- [ ] Demo runs with live E6 API
- [ ] Query latency < 1 second verified

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| - | - | Demo is leaf task |

---

## References

- Design Doc: [Section 5.5 - Demo 5: Unified Audit Trail](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md#55-demo-5-unified-audit-trail)
- Related Code: E6 audit query API

---

## Notes

- This demo is blocked by E6 - cannot run with live API until E6 is complete
- Mock mode works independently for demo development
- Key metric is query latency - must be under 1 second

---

## Execution Log

### Progress Updates

| Date | Update |
|------|--------|
| - | - |

### Blockers Encountered

| Date | Blocker | Resolution |
|------|---------|------------|
| - | - | - |
