# Task: WS-E2 Implement Audit Logger Service

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-E: Audit & Security |
| **Dependencies** | E1 (Audit event model) ✅ |
| **Blocked By** | None (E1 complete) |
| **Assigned** | - |
| **Created** | February 5, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 7 |
| **Target Worktree** | `vmcp-control` |

---

## Validation Mapping

| Validates | Reference |
|-----------|-----------|
| **Demo 5** | Unified Audit - All actions logged with attribution |
| **User Journey Step** | Step 10: Sarah Reviews Audit Trail |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] E1 (Audit event model) is complete - provides `AuditEvent` and `AuditEventType`
- [x] Database migrations for `audit_events` table exist
- [x] Existing service patterns established (see `user_session_service.py`, `delegation_service.py`)

---

## Task Description

Implement the **AuditLoggerService** in the Control Plane that persists audit events to the database and provides efficient query capabilities. This service is called by the Gateway's audit middleware (E3) to log all MCP tool calls.

### Context

This is **Step 10 of Sarah's journey** (Sarah Reviews Audit Trail) and the core of **Demo 5 (Unified Audit)**:
- Every tool call the agent makes is logged with full attribution
- Sarah can query: "What did my agent do?"
- Audit events capture: who (agent), on whose behalf (Sarah), what (tool), when (timestamp)
- Gateway sends audit events to Control Plane for centralized storage

### Key Requirements

1. **Persistent Storage**: Save audit events to PostgreSQL via SQLAlchemy
2. **High-Performance Logging**: Async write, don't block tool execution
3. **Query Support**: Query by agent_id, user_id, time range, event_type
4. **Immutability**: Audit events cannot be modified once written
5. **Efficient Indexing**: Use composite indexes from E1 model

### Integration Flow

```
Gateway (E3 Audit Middleware)
         │
         ├── Tool call happens
         │
         └── HTTP POST to Control Plane
                  │
                  └── AuditLoggerService.log_event() ← THIS TASK
                           │
                           ├── Validate event
                           ├── Persist to DB
                           └── Return event_id

Sarah (Dashboard)
         │
         └── GET /api/v1/audit/events?agent_id=...
                  │
                  └── AuditLoggerService.query_events() ← THIS TASK
                           │
                           └── Return filtered events
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/services/audit_logger_service.py` | **CREATE** | AuditLoggerService class |
| `deeptrail-control/app/services/__init__.py` | **MODIFY** | Export AuditLoggerService |
| `deeptrail-control/app/api/v1/endpoints/audit.py` | **CREATE** | API endpoints for logging and querying |
| `deeptrail-control/app/api/v1/endpoints/__init__.py` | **MODIFY** | Register audit router |
| `deeptrail-control/tests/services/test_audit_logger_service.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. AuditLoggerService Class

```python
"""
Audit Logger Service for the Virtual MCP Server.

This service persists audit events to the database and provides query capabilities.
It is the central point for all audit logging in the system.

This implements:
- Demo 5: Unified Audit
- Step 10 of Sarah's Journey

Usage:
    from app.services.audit_logger_service import AuditLoggerService
    
    service = AuditLoggerService(db_session)
    
    # Log an event
    event_id = await service.log_event(
        event_type=AuditEventType.MCP_TOOL_CALL,
        agent_id="agent-123",
        on_behalf_of="sarah@acme.com",
        tool="notion.search_pages",
        arguments={"query": "meeting notes"},
        result_summary="Found 5 results"
    )
    
    # Query events
    events = await service.query_events(
        agent_id="agent-123",
        start_time=datetime.now() - timedelta(hours=1),
        limit=100
    )
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.audit_event import AuditEvent, AuditEventType, generate_event_id

logger = logging.getLogger(__name__)


class AuditLoggerService:
    """
    Service for logging and querying audit events.
    
    Responsibilities:
    1. Persist audit events to the database
    2. Provide efficient query capabilities
    3. Ensure audit event immutability
    4. Support high-volume event logging
    
    Security:
    - Events are immutable once written
    - Sensitive data can be redacted before logging
    - No update or delete operations exposed
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize the audit logger service.
        
        Args:
            db: SQLAlchemy async session
        """
        self.db = db
    
    async def log_event(
        self,
        event_type: AuditEventType | str,
        on_behalf_of: str,
        agent_id: str | None = None,
        organization_id: str | None = None,
        tool: str | None = None,
        arguments: dict[str, Any] | None = None,
        result_summary: str | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> str:
        """
        Log an audit event to the database.
        
        Args:
            event_type: Type of event (e.g., MCP_TOOL_CALL, PERMISSION_DENIED)
            on_behalf_of: User on whose behalf the action was taken
            agent_id: Agent that performed the action (optional)
            organization_id: Organization context (optional)
            tool: Tool that was called (for tool call events)
            arguments: Arguments passed to the tool
            result_summary: Summary of the result (for successful calls)
            error: Error message (for failed calls)
            duration_ms: Duration of the operation in milliseconds
            extra_data: Additional context data
            
        Returns:
            The event ID of the logged event
            
        Security:
            - Arguments may be redacted for sensitive data
            - Event is immutable once written
        """
        # Convert string event_type to enum if needed
        if isinstance(event_type, str):
            event_type = AuditEventType(event_type)
        
        # Generate unique event ID
        event_id = generate_event_id()
        
        # Redact sensitive arguments (e.g., passwords, tokens)
        safe_arguments = self._redact_sensitive_data(arguments) if arguments else None
        
        # Create the audit event
        event = AuditEvent(
            id=event_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type.value,
            agent_id=agent_id,
            on_behalf_of=on_behalf_of,
            organization_id=organization_id,
            tool=tool,
            arguments=safe_arguments,
            result_summary=result_summary,
            error=error,
            duration_ms=duration_ms,
            extra_data=extra_data,
        )
        
        # Persist to database
        self.db.add(event)
        await self.db.commit()
        
        logger.debug(
            "Audit event logged: %s (type=%s, agent=%s, user=%s)",
            event_id, event_type.value, agent_id, on_behalf_of
        )
        
        return event_id
    
    async def log_tool_call(
        self,
        agent_id: str,
        on_behalf_of: str,
        tool: str,
        arguments: dict[str, Any],
        result_summary: str | None = None,
        duration_ms: int | None = None,
        organization_id: str | None = None,
    ) -> str:
        """
        Convenience method for logging MCP tool calls.
        
        Args:
            agent_id: Agent that made the call
            on_behalf_of: User on whose behalf
            tool: Namespaced tool name (e.g., "notion.search_pages")
            arguments: Tool arguments
            result_summary: Optional summary of result
            duration_ms: Optional duration
            organization_id: Optional org context
            
        Returns:
            Event ID
        """
        return await self.log_event(
            event_type=AuditEventType.MCP_TOOL_CALL,
            agent_id=agent_id,
            on_behalf_of=on_behalf_of,
            tool=tool,
            arguments=arguments,
            result_summary=result_summary,
            duration_ms=duration_ms,
            organization_id=organization_id,
        )
    
    async def log_permission_denied(
        self,
        agent_id: str,
        on_behalf_of: str,
        tool: str,
        required_permission: str,
        organization_id: str | None = None,
    ) -> str:
        """
        Log a permission denied event.
        
        Args:
            agent_id: Agent that attempted the action
            on_behalf_of: User context
            tool: Tool that was denied
            required_permission: Permission that was required
            organization_id: Optional org context
            
        Returns:
            Event ID
        """
        return await self.log_event(
            event_type=AuditEventType.PERMISSION_DENIED,
            agent_id=agent_id,
            on_behalf_of=on_behalf_of,
            tool=tool,
            error=f"Permission denied: {required_permission} required",
            extra_data={"required_permission": required_permission},
            organization_id=organization_id,
        )
    
    async def query_events(
        self,
        agent_id: str | None = None,
        on_behalf_of: str | None = None,
        organization_id: str | None = None,
        event_type: AuditEventType | str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        tool: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """
        Query audit events with filters.
        
        Args:
            agent_id: Filter by agent ID
            on_behalf_of: Filter by user (e.g., "sarah@acme.com")
            organization_id: Filter by organization
            event_type: Filter by event type
            start_time: Filter events after this time
            end_time: Filter events before this time
            tool: Filter by tool name
            limit: Maximum events to return (default 100, max 1000)
            offset: Pagination offset
            
        Returns:
            List of matching audit events, ordered by timestamp descending
        """
        # Build query
        query = select(AuditEvent)
        
        # Apply filters
        conditions = []
        
        if agent_id:
            conditions.append(AuditEvent.agent_id == agent_id)
        
        if on_behalf_of:
            conditions.append(AuditEvent.on_behalf_of == on_behalf_of)
        
        if organization_id:
            conditions.append(AuditEvent.organization_id == organization_id)
        
        if event_type:
            if isinstance(event_type, AuditEventType):
                event_type = event_type.value
            conditions.append(AuditEvent.event_type == event_type)
        
        if start_time:
            conditions.append(AuditEvent.timestamp >= start_time)
        
        if end_time:
            conditions.append(AuditEvent.timestamp <= end_time)
        
        if tool:
            conditions.append(AuditEvent.tool == tool)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Order by timestamp descending (most recent first)
        query = query.order_by(desc(AuditEvent.timestamp))
        
        # Apply pagination
        limit = min(limit, 1000)  # Cap at 1000
        query = query.limit(limit).offset(offset)
        
        # Execute query
        result = await self.db.execute(query)
        events = result.scalars().all()
        
        return list(events)
    
    async def get_event(self, event_id: str) -> AuditEvent | None:
        """
        Get a single audit event by ID.
        
        Args:
            event_id: The event ID to retrieve
            
        Returns:
            The audit event or None if not found
        """
        result = await self.db.execute(
            select(AuditEvent).where(AuditEvent.id == event_id)
        )
        return result.scalar_one_or_none()
    
    async def count_events(
        self,
        agent_id: str | None = None,
        on_behalf_of: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """
        Count audit events matching filters.
        
        Useful for pagination and dashboards.
        
        Args:
            agent_id: Filter by agent
            on_behalf_of: Filter by user
            start_time: Filter after this time
            end_time: Filter before this time
            
        Returns:
            Count of matching events
        """
        from sqlalchemy import func
        
        query = select(func.count(AuditEvent.id))
        
        conditions = []
        if agent_id:
            conditions.append(AuditEvent.agent_id == agent_id)
        if on_behalf_of:
            conditions.append(AuditEvent.on_behalf_of == on_behalf_of)
        if start_time:
            conditions.append(AuditEvent.timestamp >= start_time)
        if end_time:
            conditions.append(AuditEvent.timestamp <= end_time)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.db.execute(query)
        return result.scalar_one()
    
    def _redact_sensitive_data(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Redact sensitive fields from audit data.
        
        Fields like passwords, tokens, and secrets are replaced with "[REDACTED]".
        
        Args:
            data: The data to redact
            
        Returns:
            Redacted copy of the data
        """
        sensitive_keys = {
            "password", "secret", "token", "api_key", "apikey",
            "access_token", "refresh_token", "authorization",
            "credential", "private_key", "secret_key"
        }
        
        def redact_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: "[REDACTED]" if k.lower() in sensitive_keys else redact_recursive(v)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [redact_recursive(item) for item in obj]
            return obj
        
        return redact_recursive(data)


# Dependency injection helper
def get_audit_logger_service(db: AsyncSession) -> AuditLoggerService:
    """Get an instance of AuditLoggerService with the given session."""
    return AuditLoggerService(db)
```

### 2. API Endpoints

```python
"""
Audit API endpoints for logging and querying events.

Endpoints:
- POST /api/v1/audit/events - Log an event (called by Gateway)
- GET /api/v1/audit/events - Query events (called by Dashboard)
- GET /api/v1/audit/events/{event_id} - Get single event
"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.audit_event import AuditEventType
from app.services.audit_logger_service import AuditLoggerService

router = APIRouter(prefix="/audit", tags=["audit"])


class LogEventRequest(BaseModel):
    """Request body for logging an audit event."""
    event_type: str = Field(..., description="Event type (e.g., mcp_tool_call)")
    on_behalf_of: str = Field(..., description="User on whose behalf")
    agent_id: Optional[str] = Field(None, description="Agent ID")
    organization_id: Optional[str] = Field(None, description="Organization ID")
    tool: Optional[str] = Field(None, description="Tool name")
    arguments: Optional[dict[str, Any]] = Field(None, description="Tool arguments")
    result_summary: Optional[str] = Field(None, description="Result summary")
    error: Optional[str] = Field(None, description="Error message")
    duration_ms: Optional[int] = Field(None, description="Duration in ms")
    extra_data: Optional[dict[str, Any]] = Field(None, description="Extra context")


class LogEventResponse(BaseModel):
    """Response after logging an event."""
    event_id: str
    timestamp: datetime


class AuditEventResponse(BaseModel):
    """Response for a single audit event."""
    id: str
    timestamp: datetime
    event_type: str
    agent_id: Optional[str]
    on_behalf_of: str
    organization_id: Optional[str]
    tool: Optional[str]
    arguments: Optional[dict[str, Any]]
    result_summary: Optional[str]
    error: Optional[str]
    duration_ms: Optional[int]
    extra_data: Optional[dict[str, Any]]
    
    class Config:
        from_attributes = True


class QueryEventsResponse(BaseModel):
    """Response for querying events."""
    events: list[AuditEventResponse]
    total: int
    limit: int
    offset: int


@router.post("/events", response_model=LogEventResponse)
async def log_event(
    request: LogEventRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Log an audit event.
    
    Called by the Gateway's audit middleware to log tool calls.
    """
    service = AuditLoggerService(db)
    
    try:
        event_id = await service.log_event(
            event_type=request.event_type,
            on_behalf_of=request.on_behalf_of,
            agent_id=request.agent_id,
            organization_id=request.organization_id,
            tool=request.tool,
            arguments=request.arguments,
            result_summary=request.result_summary,
            error=request.error,
            duration_ms=request.duration_ms,
            extra_data=request.extra_data,
        )
        
        return LogEventResponse(
            event_id=event_id,
            timestamp=datetime.utcnow(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/events", response_model=QueryEventsResponse)
async def query_events(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    on_behalf_of: Optional[str] = Query(None, description="Filter by user"),
    organization_id: Optional[str] = Query(None, description="Filter by org"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start_time: Optional[datetime] = Query(None, description="Events after this time"),
    end_time: Optional[datetime] = Query(None, description="Events before this time"),
    tool: Optional[str] = Query(None, description="Filter by tool name"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
):
    """
    Query audit events.
    
    Used by the dashboard to display Sarah's audit trail.
    """
    service = AuditLoggerService(db)
    
    events = await service.query_events(
        agent_id=agent_id,
        on_behalf_of=on_behalf_of,
        organization_id=organization_id,
        event_type=event_type,
        start_time=start_time,
        end_time=end_time,
        tool=tool,
        limit=limit,
        offset=offset,
    )
    
    # Get total count for pagination
    total = await service.count_events(
        agent_id=agent_id,
        on_behalf_of=on_behalf_of,
        start_time=start_time,
        end_time=end_time,
    )
    
    return QueryEventsResponse(
        events=[AuditEventResponse.model_validate(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/events/{event_id}", response_model=AuditEventResponse)
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single audit event by ID."""
    service = AuditLoggerService(db)
    
    event = await service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return AuditEventResponse.model_validate(event)
```

### 3. Key Behaviors

| Operation | Behavior |
|-----------|----------|
| `log_event()` | Persists event, returns event_id immediately |
| `log_tool_call()` | Convenience method for MCP_TOOL_CALL events |
| `log_permission_denied()` | Convenience method for PERMISSION_DENIED events |
| `query_events()` | Paginated query with filters, max 1000 results |
| `count_events()` | Count for pagination |
| Sensitive data | Automatically redacted (passwords, tokens, etc.) |

---

## Acceptance Criteria

### Protocol Criteria
- [ ] `POST /api/v1/audit/events` logs event and returns event_id
- [ ] `GET /api/v1/audit/events` returns paginated results
- [ ] Query supports: agent_id, on_behalf_of, time range, event_type, tool

### Security Criteria
- [ ] **Immutability**: No update or delete operations exposed
- [ ] **Redaction**: Sensitive fields automatically redacted
- [ ] **Authorization**: Query endpoint requires authentication (future)

### Integration Criteria
- [ ] Uses `AuditEvent` model from E1
- [ ] Follows existing service patterns (`delegation_service.py`, etc.)
- [ ] Gateway (E3) can call logging endpoint
- [ ] Unblocks E3 (Audit middleware) and E6 (Audit query API)

### Demo 5 Metric
- [ ] Can demonstrate: All tool calls logged with full attribution
- [ ] Can demonstrate: Query returns events for a specific agent
- [ ] Can demonstrate: Query returns events for a specific user

---

## Test Cases

### Unit Tests (`test_audit_logger_service.py`)

```python
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.audit_event import AuditEvent, AuditEventType
from app.services.audit_logger_service import AuditLoggerService


class TestAuditLoggerService:
    """Tests for E2: Audit Logger Service"""
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.fixture
    def service(self, mock_db):
        return AuditLoggerService(mock_db)
    
    @pytest.mark.asyncio
    async def test_log_event_returns_event_id(self, service, mock_db):
        """E2: Should return event ID after logging"""
        event_id = await service.log_event(
            event_type=AuditEventType.MCP_TOOL_CALL,
            on_behalf_of="sarah@acme.com",
            agent_id="agent-123",
            tool="notion.search_pages",
        )
        
        assert event_id.startswith("evt-")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_log_tool_call_convenience_method(self, service, mock_db):
        """E2: Should have convenience method for tool calls"""
        event_id = await service.log_tool_call(
            agent_id="agent-123",
            on_behalf_of="sarah@acme.com",
            tool="notion.search_pages",
            arguments={"query": "meeting"},
        )
        
        assert event_id.startswith("evt-")
        
        # Verify the event was created with correct type
        call_args = mock_db.add.call_args[0][0]
        assert call_args.event_type == AuditEventType.MCP_TOOL_CALL.value
    
    @pytest.mark.asyncio
    async def test_log_permission_denied(self, service, mock_db):
        """E2: Should log permission denied events"""
        event_id = await service.log_permission_denied(
            agent_id="agent-123",
            on_behalf_of="sarah@acme.com",
            tool="slack.post_message",
            required_permission="slack:messages:post",
        )
        
        call_args = mock_db.add.call_args[0][0]
        assert call_args.event_type == AuditEventType.PERMISSION_DENIED.value
        assert "required_permission" in call_args.extra_data
    
    def test_redact_sensitive_data(self, service):
        """E2 Security: Should redact sensitive fields"""
        data = {
            "query": "test",
            "password": "secret123",
            "api_key": "key123",
            "nested": {
                "token": "abc",
                "safe_field": "visible"
            }
        }
        
        redacted = service._redact_sensitive_data(data)
        
        assert redacted["query"] == "test"
        assert redacted["password"] == "[REDACTED]"
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["nested"]["token"] == "[REDACTED]"
        assert redacted["nested"]["safe_field"] == "visible"


class TestQueryEvents:
    """Tests for querying audit events"""
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db
    
    @pytest.fixture
    def service(self, mock_db):
        return AuditLoggerService(mock_db)
    
    @pytest.mark.asyncio
    async def test_query_with_agent_filter(self, service, mock_db):
        """E2: Should filter by agent_id"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        
        await service.query_events(agent_id="agent-123")
        
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_query_limit_capped(self, service, mock_db):
        """E2: Should cap limit at 1000"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        
        # Request 5000, should be capped to 1000
        await service.query_events(limit=5000)
        
        # Verify the query was executed (limit is applied in SQL)
        mock_db.execute.assert_called_once()


class TestAuditEventImmutability:
    """Tests to ensure audit events are immutable"""
    
    def test_no_update_method(self):
        """E2 Security: Service should not expose update method"""
        assert not hasattr(AuditLoggerService, "update_event")
    
    def test_no_delete_method(self):
        """E2 Security: Service should not expose delete method"""
        assert not hasattr(AuditLoggerService, "delete_event")
```

### Integration Tests

```python
@pytest.mark.integration
async def test_log_and_query_flow(db_session):
    """E2 Demo 5: Log events and query them back"""
    service = AuditLoggerService(db_session)
    
    # Log several events
    event1 = await service.log_tool_call(
        agent_id="agent-123",
        on_behalf_of="sarah@acme.com",
        tool="notion.search_pages",
        arguments={"query": "test"},
    )
    
    event2 = await service.log_tool_call(
        agent_id="agent-123",
        on_behalf_of="sarah@acme.com",
        tool="slack.post_message",
        arguments={"channel": "#general"},
    )
    
    # Query by agent
    events = await service.query_events(agent_id="agent-123")
    
    assert len(events) >= 2
    assert any(e.id == event1 for e in events)
    assert any(e.id == event2 for e in events)


@pytest.mark.integration
async def test_api_log_endpoint(client, db_session):
    """E2: POST /api/v1/audit/events should log event"""
    response = await client.post(
        "/api/v1/audit/events",
        json={
            "event_type": "mcp_tool_call",
            "on_behalf_of": "sarah@acme.com",
            "agent_id": "agent-123",
            "tool": "notion.search_pages",
            "arguments": {"query": "test"},
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "event_id" in data
    assert data["event_id"].startswith("evt-")


@pytest.mark.integration
async def test_api_query_endpoint(client, db_session):
    """E2: GET /api/v1/audit/events should return events"""
    response = await client.get(
        "/api/v1/audit/events",
        params={"agent_id": "agent-123", "limit": 10}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert "total" in data
```

---

## Post-Conditions

After completing this task:

1. `AuditLoggerService` is available in `deeptrail-control/app/services/`
2. API endpoints available at `/api/v1/audit/events`
3. Gateway can POST events to Control Plane
4. Dashboard can query events for a user

---

## Unblocks

| Task | Name | Notes |
|------|------|-------|
| **E3** | Audit Middleware | Gateway can now send events to Control Plane |
| **E6** | Audit Query API | Query capabilities implemented here |

---

## References

- **Design Doc**: Section 2.9 (Audit Event Structure), Section 2.10 (Audit Queries)
- **E1 Implementation**: `deeptrail-control/app/models/audit_event.py`
- **E1 Completion Report**: `docs/workstreams/virtual-mcp-server-mvp/reports/WS-E1-completion.md`
- **Existing Services**: `delegation_service.py`, `user_session_service.py` (patterns)

---

## Notes

- Sensitive data redaction happens at log time, not query time
- Query results are capped at 1000 for performance
- Event immutability is enforced by not exposing update/delete
- Future: Add authentication to query endpoint (currently open for MVP)
- Future: Add rate limiting for logging endpoint
- Future: Add batch logging for high-volume scenarios
