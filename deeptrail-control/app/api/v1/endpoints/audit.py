"""Audit API endpoints for logging and querying events.

This module implements the audit trail endpoints for the Virtual MCP Server:
- POST /api/v1/audit/events - Log an event (called by Gateway)
- GET /api/v1/audit/events - Query events (called by Dashboard)
- GET /api/v1/audit/events/{event_id} - Get single event

These endpoints support:
- Demo 5: Unified Audit
- Step 10 of Sarah's Journey: Sarah Reviews Audit Trail
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import SessionLocal
from app.models.audit_event import AuditEvent
from app.services.audit_logger_service import AuditLoggerService

router = APIRouter()


# Request/Response Models


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
    session_id: Optional[str] = Field(None, description="User session ID")
    agent_session_id: Optional[str] = Field(None, description="Agent session ID")
    mcp_session_id: Optional[str] = Field(None, description="MCP session ID")
    delegation_id: Optional[str] = Field(None, description="Delegation ID")
    success: Optional[bool] = Field(None, description="Whether the action succeeded")
    extra_data: Optional[dict[str, Any]] = Field(None, description="Extra context")

    model_config = {"json_schema_extra": {"example": {
        "event_type": "mcp_tool_call",
        "on_behalf_of": "sarah@acme.com",
        "agent_id": "agent-123",
        "tool": "notion.search_pages",
        "arguments": {"query": "meeting notes"},
        "result_summary": "Found 5 results",
        "duration_ms": 250,
    }}}


class LogEventResponse(BaseModel):
    """Response after logging an event."""

    event_id: str = Field(..., description="Unique event ID")
    timestamp: datetime = Field(..., description="When the event was logged")

    model_config = {"json_schema_extra": {"example": {
        "event_id": "evt-abc123",
        "timestamp": "2026-02-06T10:30:00Z",
    }}}


class AuditEventResponse(BaseModel):
    """Response for a single audit event."""

    id: str
    timestamp: datetime
    event_type: str
    agent_id: Optional[str]
    on_behalf_of: str
    organization_id: Optional[str]
    tool: Optional[str]
    success: Optional[bool] = None
    arguments: Optional[dict[str, Any]]
    result_summary: Optional[str]
    reason: Optional[str]
    attempted_tool: Optional[str] = None
    required_permission: Optional[str] = None
    session_id: Optional[str]
    agent_session_id: Optional[str]
    mcp_session_id: Optional[str]
    delegation_id: Optional[str]
    extra_data: Optional[dict[str, Any]]
    duration_ms: Optional[int] = None

    model_config = {"from_attributes": True}


class QueryEventsResponse(BaseModel):
    """Response for querying events."""

    events: list[AuditEventResponse]
    total: int = Field(..., description="Total matching events")
    limit: int = Field(..., description="Limit applied")
    offset: int = Field(..., description="Offset applied")


class AuditSummaryResponse(BaseModel):
    """Response for audit summary statistics."""

    total_events: int = Field(..., description="Total number of events")
    by_event_type: dict[str, int] = Field(
        ..., description="Event counts by type (mcp_tool_call, permission_denied, etc.)"
    )
    by_tool: dict[str, int] = Field(
        ..., description="Event counts by tool (notion.search_pages, etc.)"
    )
    by_agent: dict[str, int] = Field(
        ..., description="Event counts by agent ID"
    )
    time_range: dict[str, str] = Field(
        default_factory=dict, description="Time range filter applied"
    )

    model_config = {"json_schema_extra": {"example": {
        "total_events": 150,
        "by_event_type": {"mcp_tool_call": 145, "permission_denied": 5},
        "by_tool": {"notion.search_pages": 50, "slack.post_message": 30},
        "by_agent": {"agent-sdr-001": 100, "agent-researcher-002": 50},
        "time_range": {"start": "2026-02-05T00:00:00Z", "end": "2026-02-06T00:00:00Z"},
    }}}


class AuditError(BaseModel):
    """Error response for audit operations."""

    error: str
    detail: Optional[str] = None


# Dependencies


def get_audit_logger_service(db: deps.DbDep) -> AuditLoggerService:
    """Get an AuditLoggerService instance."""
    return AuditLoggerService(db)


AuditLoggerServiceDep = Annotated[
    AuditLoggerService,
    Depends(get_audit_logger_service),
]


# Endpoints


@router.post(
    "/events",
    response_model=LogEventResponse,
    responses={
        400: {"model": AuditError, "description": "Invalid event type"},
    },
    summary="Log an audit event",
    description="Log an audit event. Called by the Gateway's audit middleware.",
)
def log_event(
    request: LogEventRequest,
    db: Session = Depends(deps.get_db),
) -> LogEventResponse:
    """Log an audit event.

    Called by the Gateway's audit middleware to log tool calls.
    """
    event_id = f"evt-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    extra = dict(request.extra_data) if request.extra_data else {}
    if request.duration_ms is not None:
        extra["duration_ms"] = request.duration_ms
    if request.error is not None:
        extra["error"] = request.error

    audit_event = AuditEvent(
        id=event_id,
        timestamp=now,
        event_type=request.event_type,
        on_behalf_of=request.on_behalf_of,
        agent_id=request.agent_id,
        organization_id=request.organization_id,
        tool=request.tool,
        arguments=request.arguments,
        result_summary=request.result_summary,
        reason=request.error,
        session_id=request.session_id,
        agent_session_id=request.agent_session_id,
        mcp_session_id=request.mcp_session_id,
        delegation_id=request.delegation_id,
        success=request.success,
        extra_data=extra or None,
    )
    db.add(audit_event)
    db.commit()

    return LogEventResponse(
        event_id=event_id,
        timestamp=now,
    )


@router.get(
    "/events",
    response_model=QueryEventsResponse,
    summary="Query audit events",
    description="Query audit events with filters. Used by the dashboard to display audit trails.",
)
def query_events(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    on_behalf_of: Optional[str] = Query(None, description="Filter by user"),
    organization_id: Optional[str] = Query(None, description="Filter by org"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start_time: Optional[datetime] = Query(None, alias="from_date", description="Events after this time"),
    end_time: Optional[datetime] = Query(None, alias="to_date", description="Events before this time"),
    tool: Optional[str] = Query(None, description="Filter by tool name"),
    delegation_id: Optional[str] = Query(None, description="Filter by delegation ID"),
    token_layer: Optional[str] = Query(None, description="Filter by token layer (e.g., delegation, agent_session, task)"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(deps.get_db),
) -> QueryEventsResponse:
    """Query audit events.

    Used by the dashboard to display Sarah's audit trail.
    """
    query = db.query(AuditEvent)

    if agent_id:
        query = query.filter(AuditEvent.agent_id == agent_id)
    if on_behalf_of:
        query = query.filter(AuditEvent.on_behalf_of == on_behalf_of)
    if event_type:
        query = query.filter(AuditEvent.event_type == event_type)
    if tool:
        query = query.filter(AuditEvent.tool == tool)
    if organization_id:
        query = query.filter(AuditEvent.organization_id == organization_id)
    if delegation_id:
        query = query.filter(AuditEvent.delegation_id == delegation_id)
    if token_layer:
        if token_layer == "delegation":
            query = query.filter(AuditEvent.delegation_id.isnot(None))
        elif token_layer == "agent_session":
            query = query.filter(AuditEvent.agent_session_id.isnot(None))
        elif token_layer == "task":
            query = query.filter(AuditEvent.event_type.contains("task"))
    if start_time:
        query = query.filter(AuditEvent.timestamp >= start_time)
    if end_time:
        query = query.filter(AuditEvent.timestamp <= end_time)

    total = query.count()

    rows = (
        query.order_by(AuditEvent.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    events = []
    for e in rows:
        duration_ms = (e.extra_data or {}).get("duration_ms") if e.extra_data else None
        events.append(AuditEventResponse(
            id=e.id,
            timestamp=e.timestamp,
            event_type=e.event_type,
            agent_id=e.agent_id,
            on_behalf_of=e.on_behalf_of,
            organization_id=e.organization_id,
            tool=e.tool,
            success=e.success,
            arguments=e.arguments,
            result_summary=e.result_summary,
            reason=e.reason,
            attempted_tool=e.attempted_tool,
            required_permission=e.required_permission,
            session_id=e.session_id,
            agent_session_id=e.agent_session_id,
            mcp_session_id=e.mcp_session_id,
            delegation_id=e.delegation_id,
            extra_data=e.extra_data,
            duration_ms=duration_ms,
        ))

    return QueryEventsResponse(
        events=events,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/events/stream",
    summary="Stream audit events in real-time via SSE",
    description="Server-Sent Events endpoint for real-time audit event streaming.",
)
async def stream_audit_events(
    agent_id: Optional[str] = Query(None),
    on_behalf_of: Optional[str] = Query(None),
) -> StreamingResponse:
    """Stream audit events in real-time via Server-Sent Events.

    Polls the database every 2 seconds for new events, tracking the last
    seen event ID as a cursor.
    """

    async def event_generator():
        last_id: Optional[str] = None
        while True:
            db = SessionLocal()
            try:
                query = db.query(AuditEvent).order_by(AuditEvent.timestamp.asc())
                if last_id is not None:
                    last_event = db.query(AuditEvent).filter(AuditEvent.id == last_id).first()
                    if last_event:
                        query = query.filter(AuditEvent.timestamp > last_event.timestamp)
                if agent_id:
                    query = query.filter(AuditEvent.agent_id == agent_id)
                if on_behalf_of:
                    query = query.filter(AuditEvent.on_behalf_of == on_behalf_of)

                new_events = query.limit(50).all()
                for event in new_events:
                    duration_ms = (event.extra_data or {}).get("duration_ms") if event.extra_data else None
                    resp = AuditEventResponse(
                        id=event.id,
                        timestamp=event.timestamp,
                        event_type=event.event_type,
                        agent_id=event.agent_id,
                        on_behalf_of=event.on_behalf_of,
                        organization_id=event.organization_id,
                        tool=event.tool,
                        success=event.success,
                        arguments=event.arguments,
                        result_summary=event.result_summary,
                        reason=event.reason,
                        attempted_tool=event.attempted_tool,
                        required_permission=event.required_permission,
                        session_id=event.session_id,
                        agent_session_id=event.agent_session_id,
                        mcp_session_id=event.mcp_session_id,
                        delegation_id=event.delegation_id,
                        extra_data=event.extra_data,
                        duration_ms=duration_ms,
                    )
                    yield f"data: {resp.model_dump_json()}\n\n"
                    last_id = event.id
            finally:
                db.close()
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get(
    "/events/{event_id}",
    response_model=AuditEventResponse,
    responses={
        404: {"model": AuditError, "description": "Event not found"},
    },
    summary="Get audit event by ID",
    description="Retrieve a single audit event by its ID.",
)
def get_event(
    event_id: str,
    service: AuditLoggerServiceDep,
) -> AuditEventResponse:
    """Get a single audit event by ID."""
    event = service.get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    return AuditEventResponse.model_validate(event)


@router.get(
    "/summary",
    response_model=AuditSummaryResponse,
    summary="Get audit summary statistics",
    description=(
        "Get aggregate statistics for audit events. "
        "Returns counts by event type, tool, and agent."
    ),
)
def get_summary(
    service: AuditLoggerServiceDep,
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    on_behalf_of: Optional[str] = Query(
        None,
        description="Filter by user email",
        alias="user_email",
    ),
    organization_id: Optional[str] = Query(None, description="Filter by org"),
    start_time: Optional[datetime] = Query(None, description="Events after this time"),
    end_time: Optional[datetime] = Query(None, description="Events before this time"),
) -> AuditSummaryResponse:
    """Get summary statistics for audit events.

    Useful for dashboards and quick overview of agent activity.

    Examples:
    - /api/v1/audit/summary?agent_id=agent-sdr-001
    - /api/v1/audit/summary?user_email=sarah@acme.com
    - /api/v1/audit/summary?start_time=2026-02-06T00:00:00Z
    """
    summary = service.get_summary(
        agent_id=agent_id,
        on_behalf_of=on_behalf_of,
        organization_id=organization_id,
        start_time=start_time,
        end_time=end_time,
    )

    return AuditSummaryResponse(
        total_events=summary["total_events"],
        by_event_type=summary["by_event_type"],
        by_tool=summary["by_tool"],
        by_agent=summary["by_agent"],
        time_range=summary["time_range"],
    )
