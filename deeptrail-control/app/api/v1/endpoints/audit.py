"""Audit API endpoints for logging and querying events.

This module implements the audit trail endpoints for the Virtual MCP Server:
- POST /api/v1/audit/events - Log an event (called by Gateway)
- GET /api/v1/audit/events - Query events (called by Dashboard)
- GET /api/v1/audit/events/{event_id} - Get single event

These endpoints support:
- Demo 5: Unified Audit
- Step 10 of Sarah's Journey: Sarah Reviews Audit Trail
"""

from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api import deps
from app.services.audit_logger_service import AuditLoggerService

router = APIRouter()


# =============================================================================
# MVP In-memory audit storage (bypasses database)
# =============================================================================

_mvp_audit_events: list[dict[str, Any]] = []


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
    arguments: Optional[dict[str, Any]]
    result_summary: Optional[str]
    reason: Optional[str]
    session_id: Optional[str]
    agent_session_id: Optional[str]
    mcp_session_id: Optional[str]
    delegation_id: Optional[str]
    extra_data: Optional[dict[str, Any]]

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
) -> LogEventResponse:
    """Log an audit event.

    Called by the Gateway's audit middleware to log tool calls.
    MVP: Uses in-memory storage instead of database.
    """
    import uuid
    
    # Generate event ID
    event_id = f"evt-{uuid.uuid4().hex[:12]}"
    timestamp = datetime.now(timezone.utc)
    
    # Store event in memory
    event = {
        "id": event_id,
        "timestamp": timestamp.isoformat(),
        "event_type": request.event_type,
        "on_behalf_of": request.on_behalf_of,
        "agent_id": request.agent_id,
        "organization_id": request.organization_id,
        "tool": request.tool,
        "arguments": request.arguments,
        "result_summary": request.result_summary,
        "error": request.error,
        "duration_ms": request.duration_ms,
        "session_id": request.session_id,
        "agent_session_id": request.agent_session_id,
        "mcp_session_id": request.mcp_session_id,
        "delegation_id": request.delegation_id,
        "extra_data": request.extra_data,
    }
    
    _mvp_audit_events.append(event)
    
    return LogEventResponse(
        event_id=event_id,
        timestamp=timestamp,
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
    start_time: Optional[datetime] = Query(None, description="Events after this time"),
    end_time: Optional[datetime] = Query(None, description="Events before this time"),
    tool: Optional[str] = Query(None, description="Filter by tool name"),
    delegation_id: Optional[str] = Query(None, description="Filter by delegation ID"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> QueryEventsResponse:
    """Query audit events.

    Used by the dashboard to display Sarah's audit trail.
    MVP: Uses in-memory storage instead of database.
    """
    # MVP: Use in-memory storage instead of database
    filtered_events = _mvp_audit_events.copy()
    
    # Apply filters
    if agent_id:
        filtered_events = [e for e in filtered_events if e.get("agent_id") == agent_id]
    if on_behalf_of:
        filtered_events = [e for e in filtered_events if e.get("on_behalf_of") == on_behalf_of]
    if event_type:
        filtered_events = [e for e in filtered_events if e.get("event_type") == event_type]
    if tool:
        filtered_events = [e for e in filtered_events if e.get("tool") == tool]
    
    # Sort by timestamp descending
    filtered_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    
    # Apply pagination
    total = len(filtered_events)
    paginated = filtered_events[offset:offset + limit]
    
    # Convert to response format
    events = []
    for e in paginated:
        events.append(AuditEventResponse(
            id=e.get("id", "unknown"),
            timestamp=datetime.fromisoformat(e.get("timestamp", datetime.now(timezone.utc).isoformat())),
            event_type=e.get("event_type", "unknown"),
            agent_id=e.get("agent_id"),
            on_behalf_of=e.get("on_behalf_of", "unknown"),
            organization_id=e.get("organization_id"),
            tool=e.get("tool"),
            arguments=e.get("arguments"),
            result_summary=e.get("result_summary"),
            reason=e.get("reason"),
            session_id=e.get("session_id"),
            agent_session_id=e.get("agent_session_id"),
            mcp_session_id=e.get("mcp_session_id"),
            delegation_id=e.get("delegation_id"),
            extra_data=e.get("extra_data"),
        ))

    return QueryEventsResponse(
        events=events,
        total=total,
        limit=limit,
        offset=offset,
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
