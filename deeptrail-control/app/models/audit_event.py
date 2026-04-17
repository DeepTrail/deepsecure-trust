"""SQLAlchemy model for Audit Event entities.

Audit events capture all MCP tool calls, permission denials, and session
lifecycle events for the unified audit trail. This enables users to review
what their agents did on their behalf.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, JSON, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

from app.db.base import Base


class AuditEventType(str, enum.Enum):
    """Types of audit events that can be logged."""

    # Tool execution events
    MCP_TOOL_CALL = "mcp_tool_call"
    PERMISSION_DENIED = "permission_denied"

    # Session lifecycle events
    SESSION_CREATED = "session_created"
    SESSION_EXPIRED = "session_expired"

    # Delegation events
    DELEGATION_CREATED = "delegation_created"
    DELEGATION_REVOKED = "delegation_revoked"

    # Agent session events
    AGENT_SESSION_CREATED = "agent_session_created"
    AGENT_SESSION_EXPIRED = "agent_session_expired"


def generate_event_id() -> str:
    """Generate a unique event ID."""
    return f"evt-{uuid.uuid4()}"


class AuditEvent(Base):
    """Represents an audit event in the database.

    Audit events are immutable records of actions taken by agents or users.
    They support the unified audit trail that allows users like Sarah to
    review what their agents did on their behalf.

    Key query patterns supported:
    - "What did agent X do?" (by agent_id + timestamp)
    - "What happened on behalf of user Y?" (by on_behalf_of + timestamp)
    - "What happened in organization Z?" (by organization_id + timestamp)
    - "What events of type T occurred?" (by event_type + timestamp)
    """

    __tablename__ = "audit_events"

    # Primary key - unique event identifier
    id = Column(
        String(64),
        primary_key=True,
        default=generate_event_id,
        comment="Unique event identifier (e.g., evt-<uuid>)",
    )

    # Timestamp - when the event occurred
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="When the event occurred (UTC)",
    )

    # Event type - what kind of event this is
    event_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of audit event (e.g., mcp_tool_call, permission_denied)",
    )

    # Attribution - who is responsible for this event
    agent_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="Agent that performed the action (null for user-direct actions)",
    )

    on_behalf_of = Column(
        String(255),
        nullable=False,
        index=True,
        comment="User on whose behalf the action was taken (e.g., sarah@acme.com)",
    )

    organization_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="Organization context for multi-tenant deployments",
    )

    # Whether the action succeeded
    success = Column(
        Boolean,
        nullable=True,
        comment="Whether the action succeeded (true for mcp_tool_call, false for denials/errors)",
    )

    # Tool call details (for mcp_tool_call events)
    tool = Column(
        String(255),
        nullable=True,
        comment="Tool that was called (e.g., notion.search_pages)",
    )

    arguments = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Arguments passed to the tool (JSON)",
    )

    result_summary = Column(
        String(500),
        nullable=True,
        comment="Brief summary of the result (e.g., '3 pages found')",
    )

    # Permission denied details (for permission_denied events)
    attempted_tool = Column(
        String(255),
        nullable=True,
        comment="Tool that was attempted but denied (e.g., notion.create_page)",
    )

    required_permission = Column(
        String(255),
        nullable=True,
        comment="Permission that was required (e.g., notion:pages:create)",
    )

    reason = Column(
        Text,
        nullable=True,
        comment="Reason for the event (e.g., denial reason, error message)",
    )

    # Session context
    session_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="User session ID (usess-*)",
    )

    agent_session_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="Agent session ID (asess-*)",
    )

    mcp_session_id = Column(
        String(64),
        nullable=True,
        comment="MCP session ID for backend connection (mcpsess-*)",
    )

    delegation_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="Delegation that authorized this action (del-*)",
    )

    # Additional metadata for extensibility
    extra_data = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="Additional event data/metadata (JSON)",
    )

    # Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_audit_agent_time", "agent_id", "timestamp"),
        Index("ix_audit_user_time", "on_behalf_of", "timestamp"),
        Index("ix_audit_org_time", "organization_id", "timestamp"),
        Index("ix_audit_type_time", "event_type", "timestamp"),
        Index("ix_audit_delegation_time", "delegation_id", "timestamp"),
    )

    def __repr__(self) -> str:
        """Return a string representation of the AuditEvent."""
        return (
            f"<AuditEvent(id='{self.id}', "
            f"event_type='{self.event_type}', "
            f"on_behalf_of='{self.on_behalf_of}', "
            f"timestamp='{self.timestamp}')>"
        )

    @classmethod
    def create_tool_call_event(
        cls,
        agent_id: str,
        on_behalf_of: str,
        tool: str,
        arguments: dict | None = None,
        result_summary: str | None = None,
        session_id: str | None = None,
        agent_session_id: str | None = None,
        mcp_session_id: str | None = None,
        delegation_id: str | None = None,
        organization_id: str | None = None,
    ) -> "AuditEvent":
        """Factory method to create an MCP tool call audit event."""
        return cls(
            event_type=AuditEventType.MCP_TOOL_CALL.value,
            agent_id=agent_id,
            on_behalf_of=on_behalf_of,
            tool=tool,
            arguments=arguments,
            result_summary=result_summary,
            session_id=session_id,
            agent_session_id=agent_session_id,
            mcp_session_id=mcp_session_id,
            delegation_id=delegation_id,
            organization_id=organization_id,
        )

    @classmethod
    def create_permission_denied_event(
        cls,
        agent_id: str,
        on_behalf_of: str,
        attempted_tool: str,
        required_permission: str,
        reason: str,
        session_id: str | None = None,
        agent_session_id: str | None = None,
        delegation_id: str | None = None,
        organization_id: str | None = None,
    ) -> "AuditEvent":
        """Factory method to create a permission denied audit event."""
        return cls(
            event_type=AuditEventType.PERMISSION_DENIED.value,
            agent_id=agent_id,
            on_behalf_of=on_behalf_of,
            attempted_tool=attempted_tool,
            required_permission=required_permission,
            reason=reason,
            session_id=session_id,
            agent_session_id=agent_session_id,
            delegation_id=delegation_id,
            organization_id=organization_id,
        )
