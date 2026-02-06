# Task: WS-E6 Implement Audit Query API

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-E: Audit & Security |
| **Code Dependencies** | E2 (Audit logger service) ✅ |
| **Runtime Dependencies** | Database (PostgreSQL) |
| **Blocked By** | None |
| **Assigned** | - |
| **Created** | February 6, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 9 |
| **Target Worktree** | `vmcp-control` |

---

## Dependencies

### Code Dependencies (must complete before starting)

| Task | What We Need | Status |
|------|--------------|--------|
| E2 | Audit logger service with database storage | ✅ |

### Runtime Dependencies (must be deployed for integration testing)

| Service | Endpoint | Required For |
|---------|----------|--------------|
| PostgreSQL | `localhost:5434` | Storing and querying audit events |
| Control Plane | `http://localhost:8000` | Hosting the query API |

### Development Mode

When runtime dependencies are unavailable:

- [x] **Fallback behavior**: In-memory audit storage for testing
- [x] **Local testing**: Unit tests with mocked database
- [x] **Integration testing**: Requires database for query performance tests

---

## Pre-Conditions

Before starting this task, ensure:

- [x] E2 (Audit logger service) is complete ✅
- [x] Audit event model is defined
- [x] Database schema for audit_events table exists

---

## Task Description

Implement an **Audit Query API** in the Control Plane that allows querying audit events to answer questions like "What did agent X do today?"

### Context

From the design doc (Section 5.5 - Demo 5: Unified Audit Trail):
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

The API should support:
1. Filter by agent_id
2. Filter by user (on_behalf_of)
3. Filter by time range
4. Filter by tool/action
5. Filter by result status (success, denied, error)
6. Pagination for large result sets

---

## Acceptance Criteria

- [ ] `GET /api/v1/audit/events` endpoint with query parameters
- [ ] Filter by agent_id, user_email, tool, status, time range
- [ ] Pagination support (limit, offset, cursor)
- [ ] Response time < 100ms for typical queries
- [ ] Proper authorization (only admins/users can query their agents)
- [ ] Unit tests for query logic
- [ ] Integration tests with database
- [ ] No new linting errors introduced

---

## Files to Modify/Create

### Files to Create

- `deeptrail-control/app/api/routes/audit.py` - Audit query endpoints
- `deeptrail-control/app/services/audit_query.py` - Query service logic
- `deeptrail-control/app/schemas/audit_query.py` - Query/response schemas

### Files to Modify

- `deeptrail-control/app/api/__init__.py` - Register audit routes
- `deeptrail-control/app/api/routes/__init__.py` - Add audit router

### Tests to Add

- `deeptrail-control/tests/api/test_audit_query.py` - API endpoint tests
- `deeptrail-control/tests/services/test_audit_query_service.py` - Service tests

---

## Implementation Details

### API Endpoint

```python
# deeptrail-control/app/api/routes/audit.py

from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta
from typing import Optional, List

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

@router.get("/events")
async def query_audit_events(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    user_email: Optional[str] = Query(None, description="Filter by user email"),
    tool: Optional[str] = Query(None, description="Filter by tool name"),
    status: Optional[str] = Query(None, description="Filter by status: success, denied, error"),
    start_time: Optional[datetime] = Query(None, description="Start of time range"),
    end_time: Optional[datetime] = Query(None, description="End of time range"),
    limit: int = Query(50, ge=1, le=1000, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    audit_service: AuditQueryService = Depends(get_audit_query_service)
) -> AuditQueryResponse:
    """
    Query audit events with filtering and pagination.
    
    Examples:
    - /api/v1/audit/events?agent_id=agent-sdr-001
    - /api/v1/audit/events?user_email=sarah@acme.com&status=denied
    - /api/v1/audit/events?tool=notion.search_pages&start_time=2026-02-06T00:00:00Z
    """
    filters = AuditQueryFilters(
        agent_id=agent_id,
        user_email=user_email,
        tool=tool,
        status=status,
        start_time=start_time or datetime.utcnow() - timedelta(days=1),
        end_time=end_time or datetime.utcnow(),
    )
    
    return await audit_service.query_events(
        filters=filters,
        limit=limit,
        offset=offset
    )


@router.get("/events/{event_id}")
async def get_audit_event(
    event_id: str,
    audit_service: AuditQueryService = Depends(get_audit_query_service)
) -> AuditEvent:
    """Get a single audit event by ID."""
    event = await audit_service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/summary")
async def get_audit_summary(
    agent_id: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    audit_service: AuditQueryService = Depends(get_audit_query_service)
) -> AuditSummary:
    """
    Get summary statistics for audit events.
    
    Returns:
    - Total events
    - Events by status (success, denied, error)
    - Events by tool
    - Events by agent
    """
    filters = AuditQueryFilters(
        agent_id=agent_id,
        user_email=user_email,
        start_time=start_time or datetime.utcnow() - timedelta(days=1),
        end_time=end_time or datetime.utcnow(),
    )
    
    return await audit_service.get_summary(filters)
```

### Query Service

```python
# deeptrail-control/app/services/audit_query.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

@dataclass
class AuditQueryFilters:
    agent_id: Optional[str] = None
    user_email: Optional[str] = None
    tool: Optional[str] = None
    status: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class AuditQueryService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def query_events(
        self,
        filters: AuditQueryFilters,
        limit: int = 50,
        offset: int = 0
    ) -> AuditQueryResponse:
        """Query audit events with filters."""
        query = select(AuditEventModel)
        query = self._apply_filters(query, filters)
        query = query.order_by(AuditEventModel.timestamp.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        events = result.scalars().all()
        
        # Get total count
        count_query = select(func.count()).select_from(AuditEventModel)
        count_query = self._apply_filters(count_query, filters)
        total = await self.db.execute(count_query)
        
        return AuditQueryResponse(
            events=[self._to_schema(e) for e in events],
            total=total.scalar(),
            limit=limit,
            offset=offset
        )
    
    def _apply_filters(self, query, filters: AuditQueryFilters):
        """Apply filters to query."""
        conditions = []
        
        if filters.agent_id:
            conditions.append(AuditEventModel.agent_id == filters.agent_id)
        if filters.user_email:
            conditions.append(AuditEventModel.on_behalf_of == filters.user_email)
        if filters.tool:
            conditions.append(AuditEventModel.tool == filters.tool)
        if filters.status:
            conditions.append(AuditEventModel.status == filters.status)
        if filters.start_time:
            conditions.append(AuditEventModel.timestamp >= filters.start_time)
        if filters.end_time:
            conditions.append(AuditEventModel.timestamp <= filters.end_time)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        return query
    
    async def get_summary(self, filters: AuditQueryFilters) -> AuditSummary:
        """Get summary statistics."""
        # Count by status
        status_query = select(
            AuditEventModel.status,
            func.count().label("count")
        ).group_by(AuditEventModel.status)
        status_query = self._apply_filters(status_query, filters)
        
        # Count by tool
        tool_query = select(
            AuditEventModel.tool,
            func.count().label("count")
        ).group_by(AuditEventModel.tool)
        tool_query = self._apply_filters(tool_query, filters)
        
        status_result = await self.db.execute(status_query)
        tool_result = await self.db.execute(tool_query)
        
        return AuditSummary(
            by_status=dict(status_result.all()),
            by_tool=dict(tool_result.all())
        )
```

### Response Schemas

```python
# deeptrail-control/app/schemas/audit_query.py

from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Optional

class AuditEventResponse(BaseModel):
    event_id: str
    timestamp: datetime
    agent_id: str
    agent_name: Optional[str]
    on_behalf_of: str
    tool: str
    arguments: Dict
    status: str  # success, denied, error
    duration_ms: Optional[int]
    error_message: Optional[str]

class AuditQueryResponse(BaseModel):
    events: List[AuditEventResponse]
    total: int
    limit: int
    offset: int
    
    @property
    def has_more(self) -> bool:
        return self.offset + len(self.events) < self.total

class AuditSummary(BaseModel):
    total_events: int
    by_status: Dict[str, int]  # {"success": 45, "denied": 3, "error": 1}
    by_tool: Dict[str, int]    # {"notion.search_pages": 20, "slack.send_message": 15}
    time_range: Dict[str, datetime]  # {"start": ..., "end": ...}
```

---

## Test Cases

### Unit Tests

```python
# tests/services/test_audit_query_service.py

import pytest
from datetime import datetime, timedelta
from app.services.audit_query import AuditQueryService, AuditQueryFilters

class TestAuditQueryService:
    
    @pytest.mark.asyncio
    async def test_query_by_agent_id(self, db_session, sample_events):
        """Query events filtered by agent ID."""
        service = AuditQueryService(db_session)
        
        result = await service.query_events(
            AuditQueryFilters(agent_id="agent-sdr-001")
        )
        
        assert all(e.agent_id == "agent-sdr-001" for e in result.events)
    
    @pytest.mark.asyncio
    async def test_query_by_time_range(self, db_session, sample_events):
        """Query events within time range."""
        service = AuditQueryService(db_session)
        now = datetime.utcnow()
        
        result = await service.query_events(
            AuditQueryFilters(
                start_time=now - timedelta(hours=1),
                end_time=now
            )
        )
        
        for event in result.events:
            assert now - timedelta(hours=1) <= event.timestamp <= now
    
    @pytest.mark.asyncio
    async def test_query_by_status(self, db_session, sample_events):
        """Query events filtered by status."""
        service = AuditQueryService(db_session)
        
        result = await service.query_events(
            AuditQueryFilters(status="denied")
        )
        
        assert all(e.status == "denied" for e in result.events)
    
    @pytest.mark.asyncio
    async def test_pagination(self, db_session, sample_events):
        """Pagination works correctly."""
        service = AuditQueryService(db_session)
        
        page1 = await service.query_events(
            AuditQueryFilters(), limit=10, offset=0
        )
        page2 = await service.query_events(
            AuditQueryFilters(), limit=10, offset=10
        )
        
        assert len(page1.events) == 10
        assert page1.events[0].event_id != page2.events[0].event_id
    
    @pytest.mark.asyncio
    async def test_summary_by_status(self, db_session, sample_events):
        """Summary returns correct counts by status."""
        service = AuditQueryService(db_session)
        
        summary = await service.get_summary(AuditQueryFilters())
        
        assert "success" in summary.by_status
        assert summary.by_status["success"] > 0
```

### API Tests

```python
# tests/api/test_audit_query.py

import pytest
from httpx import AsyncClient

class TestAuditQueryAPI:
    
    @pytest.mark.asyncio
    async def test_query_events_endpoint(self, client: AsyncClient):
        """Query events endpoint returns results."""
        response = await client.get("/api/v1/audit/events")
        
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "total" in data
    
    @pytest.mark.asyncio
    async def test_query_with_filters(self, client: AsyncClient):
        """Query with filters works."""
        response = await client.get(
            "/api/v1/audit/events",
            params={"agent_id": "agent-sdr-001", "status": "success"}
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_get_single_event(self, client: AsyncClient, sample_event):
        """Get single event by ID."""
        response = await client.get(f"/api/v1/audit/events/{sample_event.event_id}")
        
        assert response.status_code == 200
        assert response.json()["event_id"] == sample_event.event_id
    
    @pytest.mark.asyncio
    async def test_summary_endpoint(self, client: AsyncClient):
        """Summary endpoint returns statistics."""
        response = await client.get("/api/v1/audit/summary")
        
        assert response.status_code == 200
        data = response.json()
        assert "by_status" in data
        assert "by_tool" in data
```

---

## Post-Conditions

### Code Complete (enables dependent tasks to start)

- [ ] All acceptance criteria met
- [ ] Unit tests pass locally: `pytest deeptrail-control/tests/`
- [ ] Linting passes: `ruff check deeptrail-control/`
- [ ] Type checking passes: `mypy deeptrail-control/`
- [ ] API documented (OpenAPI/Swagger)
- [ ] Completion report created

### Integration Complete (validated at merge point)

- [ ] Integration tests pass with PostgreSQL
- [ ] Query performance < 100ms verified
- [ ] API accessible at `/api/v1/audit/events`

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| F6 | Code dependency satisfied | Demo 5: Unified Audit can proceed |

---

## References

- Design Doc: [Section 5.5 - Demo 5: Unified Audit Trail](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md#55-demo-5-unified-audit-trail)
- Related Code: `deeptrail-control/app/services/audit_logger.py` (E2)
- Related Code: `deeptrail-control/app/models/audit_event.py` (E1)

---

## Notes

- Consider adding database indexes for common query patterns (agent_id, timestamp)
- Future: Add support for cursor-based pagination for large datasets
- Future: Add export to CSV/JSON for compliance reporting

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
