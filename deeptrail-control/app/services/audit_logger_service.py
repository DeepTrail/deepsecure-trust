"""Audit Logger Service for the Virtual MCP Server.

This service persists audit events to the database and provides query capabilities.
It is the central point for all audit logging in the system.

This implements:
- Demo 5: Unified Audit
- Step 10 of Sarah's Journey

Usage:
    from app.services.audit_logger_service import AuditLoggerService

    service = AuditLoggerService(db_session)

    # Log an event
    event_id = service.log_event(
        event_type=AuditEventType.MCP_TOOL_CALL,
        agent_id="agent-123",
        on_behalf_of="sarah@acme.com",
        tool="notion.search_pages",
        arguments={"query": "meeting notes"},
        result_summary="Found 5 results"
    )

    # Query events
    events = service.query_events(
        agent_id="agent-123",
        start_time=datetime.now() - timedelta(hours=1),
        limit=100
    )
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent, AuditEventType, generate_event_id

logger = logging.getLogger(__name__)


class AuditLoggerService:
    """Service for logging and querying audit events.

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

    def __init__(self, db: Session):
        """Initialize the audit logger service.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def log_event(
        self,
        event_type: AuditEventType | str,
        on_behalf_of: str,
        agent_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        tool: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        result_summary: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None,
        session_id: Optional[str] = None,
        agent_session_id: Optional[str] = None,
        mcp_session_id: Optional[str] = None,
        delegation_id: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log an audit event to the database.

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
            session_id: User session ID
            agent_session_id: Agent session ID
            mcp_session_id: MCP session ID
            delegation_id: Delegation that authorized the action
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
            reason=error,  # Map error to reason field
            session_id=session_id,
            agent_session_id=agent_session_id,
            mcp_session_id=mcp_session_id,
            delegation_id=delegation_id,
            extra_data=extra_data,
        )

        # Persist to database
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        logger.debug(
            "Audit event logged: %s (type=%s, agent=%s, user=%s)",
            event_id,
            event_type.value,
            agent_id,
            on_behalf_of,
        )

        return event_id

    def log_tool_call(
        self,
        agent_id: str,
        on_behalf_of: str,
        tool: str,
        arguments: Dict[str, Any],
        result_summary: Optional[str] = None,
        duration_ms: Optional[int] = None,
        organization_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_session_id: Optional[str] = None,
        mcp_session_id: Optional[str] = None,
        delegation_id: Optional[str] = None,
    ) -> str:
        """Convenience method for logging MCP tool calls.

        Args:
            agent_id: Agent that made the call
            on_behalf_of: User on whose behalf
            tool: Namespaced tool name (e.g., "notion.search_pages")
            arguments: Tool arguments
            result_summary: Optional summary of result
            duration_ms: Optional duration
            organization_id: Optional org context
            session_id: User session ID
            agent_session_id: Agent session ID
            mcp_session_id: MCP session ID
            delegation_id: Delegation ID

        Returns:
            Event ID
        """
        return self.log_event(
            event_type=AuditEventType.MCP_TOOL_CALL,
            agent_id=agent_id,
            on_behalf_of=on_behalf_of,
            tool=tool,
            arguments=arguments,
            result_summary=result_summary,
            extra_data={"duration_ms": duration_ms} if duration_ms else None,
            organization_id=organization_id,
            session_id=session_id,
            agent_session_id=agent_session_id,
            mcp_session_id=mcp_session_id,
            delegation_id=delegation_id,
        )

    def log_permission_denied(
        self,
        agent_id: str,
        on_behalf_of: str,
        tool: str,
        required_permission: str,
        organization_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_session_id: Optional[str] = None,
        delegation_id: Optional[str] = None,
    ) -> str:
        """Log a permission denied event.

        Args:
            agent_id: Agent that attempted the action
            on_behalf_of: User context
            tool: Tool that was denied
            required_permission: Permission that was required
            organization_id: Optional org context
            session_id: User session ID
            agent_session_id: Agent session ID
            delegation_id: Delegation ID

        Returns:
            Event ID
        """
        return self.log_event(
            event_type=AuditEventType.PERMISSION_DENIED,
            agent_id=agent_id,
            on_behalf_of=on_behalf_of,
            tool=tool,
            error=f"Permission denied: {required_permission} required",
            extra_data={"required_permission": required_permission},
            organization_id=organization_id,
            session_id=session_id,
            agent_session_id=agent_session_id,
            delegation_id=delegation_id,
        )

    def query_events(
        self,
        agent_id: Optional[str] = None,
        on_behalf_of: Optional[str] = None,
        organization_id: Optional[str] = None,
        event_type: Optional[AuditEventType | str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tool: Optional[str] = None,
        delegation_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """Query audit events with filters.

        Args:
            agent_id: Filter by agent ID
            on_behalf_of: Filter by user (e.g., "sarah@acme.com")
            organization_id: Filter by organization
            event_type: Filter by event type
            start_time: Filter events after this time
            end_time: Filter events before this time
            tool: Filter by tool name
            delegation_id: Filter by delegation ID
            limit: Maximum events to return (default 100, max 1000)
            offset: Pagination offset

        Returns:
            List of matching audit events, ordered by timestamp descending
        """
        # Build query
        query = self.db.query(AuditEvent)

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

        if delegation_id:
            conditions.append(AuditEvent.delegation_id == delegation_id)

        if conditions:
            query = query.filter(and_(*conditions))

        # Order by timestamp descending (most recent first)
        query = query.order_by(desc(AuditEvent.timestamp))

        # Apply pagination
        limit = min(limit, 1000)  # Cap at 1000
        query = query.limit(limit).offset(offset)

        # Execute query
        events = query.all()

        return list(events)

    def get_event(self, event_id: str) -> Optional[AuditEvent]:
        """Get a single audit event by ID.

        Args:
            event_id: The event ID to retrieve

        Returns:
            The audit event or None if not found
        """
        return (
            self.db.query(AuditEvent).filter(AuditEvent.id == event_id).first()
        )

    def count_events(
        self,
        agent_id: Optional[str] = None,
        on_behalf_of: Optional[str] = None,
        organization_id: Optional[str] = None,
        event_type: Optional[AuditEventType | str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """Count audit events matching filters.

        Useful for pagination and dashboards.

        Args:
            agent_id: Filter by agent
            on_behalf_of: Filter by user
            organization_id: Filter by organization
            event_type: Filter by event type
            start_time: Filter after this time
            end_time: Filter before this time

        Returns:
            Count of matching events
        """
        query = self.db.query(func.count(AuditEvent.id))

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

        if conditions:
            query = query.filter(and_(*conditions))

        result = query.scalar()
        return result or 0

    def get_summary(
        self,
        agent_id: Optional[str] = None,
        on_behalf_of: Optional[str] = None,
        organization_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get summary statistics for audit events.

        Returns aggregate statistics useful for dashboards:
        - Total events count
        - Events by event_type (mcp_tool_call, permission_denied, etc.)
        - Events by tool (notion.search_pages, slack.post_message, etc.)
        - Events by agent

        Args:
            agent_id: Filter by agent
            on_behalf_of: Filter by user
            organization_id: Filter by organization
            start_time: Filter after this time
            end_time: Filter before this time

        Returns:
            Dictionary with summary statistics
        """
        # Build base conditions
        conditions = []
        if agent_id:
            conditions.append(AuditEvent.agent_id == agent_id)
        if on_behalf_of:
            conditions.append(AuditEvent.on_behalf_of == on_behalf_of)
        if organization_id:
            conditions.append(AuditEvent.organization_id == organization_id)
        if start_time:
            conditions.append(AuditEvent.timestamp >= start_time)
        if end_time:
            conditions.append(AuditEvent.timestamp <= end_time)

        # Total count
        total_query = self.db.query(func.count(AuditEvent.id))
        if conditions:
            total_query = total_query.filter(and_(*conditions))
        total_events = total_query.scalar() or 0

        # Count by event_type
        type_query = self.db.query(
            AuditEvent.event_type,
            func.count(AuditEvent.id).label("count"),
        ).group_by(AuditEvent.event_type)
        if conditions:
            type_query = type_query.filter(and_(*conditions))
        by_event_type = {row[0]: row[1] for row in type_query.all()}

        # Count by tool (only for events that have a tool)
        tool_query = self.db.query(
            AuditEvent.tool,
            func.count(AuditEvent.id).label("count"),
        ).filter(AuditEvent.tool.isnot(None)).group_by(AuditEvent.tool)
        if conditions:
            tool_query = tool_query.filter(and_(*conditions))
        by_tool = {row[0]: row[1] for row in tool_query.all()}

        # Count by agent (only for events that have an agent)
        agent_query = self.db.query(
            AuditEvent.agent_id,
            func.count(AuditEvent.id).label("count"),
        ).filter(AuditEvent.agent_id.isnot(None)).group_by(AuditEvent.agent_id)
        if conditions:
            agent_query = agent_query.filter(and_(*conditions))
        by_agent = {row[0]: row[1] for row in agent_query.all()}

        # Time range
        time_range = {}
        if start_time:
            time_range["start"] = start_time.isoformat()
        if end_time:
            time_range["end"] = end_time.isoformat()

        return {
            "total_events": total_events,
            "by_event_type": by_event_type,
            "by_tool": by_tool,
            "by_agent": by_agent,
            "time_range": time_range,
        }

    def _redact_sensitive_data(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Redact sensitive fields from audit data.

        Fields like passwords, tokens, and secrets are replaced with "[REDACTED]".

        Args:
            data: The data to redact

        Returns:
            Redacted copy of the data
        """
        sensitive_keys = {
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "access_token",
            "refresh_token",
            "authorization",
            "credential",
            "private_key",
            "secret_key",
        }

        def redact_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: "[REDACTED]"
                    if k.lower() in sensitive_keys
                    else redact_recursive(v)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [redact_recursive(item) for item in obj]
            return obj

        return redact_recursive(data)


# Dependency injection helper
def get_audit_logger_service(db: Session) -> AuditLoggerService:
    """Get an instance of AuditLoggerService with the given session."""
    return AuditLoggerService(db)
