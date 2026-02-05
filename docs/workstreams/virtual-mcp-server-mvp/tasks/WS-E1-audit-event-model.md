# Task: WS-E1 Define Audit Event Model

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-E: Audit & Security |
| **Dependencies** | None |
| **Blocked By** | None |
| **Assigned** | - |
| **Created** | January 2026 |
| **Estimated Complexity** | `S` (< 2 hours) |
| **Batch** | 1 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 5: Unified Audit (foundation) |
| **Validates User Journey Step** | Step 10: Sarah Reviews Audit |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] No dependency tasks (this is a Batch 1 task)
- [ ] `deeptrail-control/` service structure exists
- [ ] Database/ORM setup is available (SQLAlchemy)

---

## Task Description

Define the Audit Event data model that captures all MCP tool calls made by agents. This model enables the unified audit trail that allows users like Sarah to review what their agents did on their behalf.

### Context

From the MVP design (Section 2.9 - Step 8):

```json
{
  "timestamp": "2026-01-21T10:15:32Z",
  "event_type": "mcp_tool_call",
  "agent_id": "agent-sdr-001",
  "on_behalf_of": "sarah@acme.com",      // KEY: Attribution
  "tool": "notion.search_pages",
  "arguments": {"query": "competitor analysis", "limit": 5},
  "result_summary": "3 pages found",
  "session_id": "asess-sdr-001-ghi789",
  "mcp_session_id": "mcpsess-notion-jkl012"
}
```

Also from Step 9 (Permission Denied):
```json
{
  "timestamp": "2026-01-21T10:16:45Z",
  "event_type": "permission_denied",
  "agent_id": "agent-sdr-001",
  "on_behalf_of": "sarah@acme.com",
  "attempted_tool": "notion.create_page",
  "required_permission": "notion:pages:create",
  "reason": "Permission not in delegation"
}
```

### Technical Notes

- Use SQLAlchemy ORM for database model
- Event types: `mcp_tool_call`, `permission_denied`, `session_created`, `session_expired`
- Timestamps must be timezone-aware (UTC)
- Consider partitioning strategy for high-volume audit logs (post-MVP)
- Arguments should be stored as JSON for flexibility

---

## Acceptance Criteria

### Protocol
- [ ] N/A (data model only)

### Security
- [ ] Sensitive data in arguments can be redacted (placeholder for future)
- [ ] Audit events are immutable (no UPDATE/DELETE)

### Integration
- [ ] Model can be imported from `deeptrail-control.models`
- [ ] Model follows existing ORM patterns in the codebase
- [ ] Supports efficient queries by: agent_id, on_behalf_of, timestamp range

### General
- [ ] All fields from Step 8 audit log are present
- [ ] Supports both `mcp_tool_call` and `permission_denied` event types
- [ ] Unit tests for model instantiation and validation
- [ ] Database indexes for common query patterns
- [ ] No new linting errors introduced

---

## Files to Create

| File | Purpose |
|------|---------|
| `deeptrail-control/models/audit_event.py` | Audit Event SQLAlchemy model |
| `deeptrail-control/tests/models/test_audit_event.py` | Unit tests for the model |

---

## Files to Modify

| File | Changes |
|------|---------|
| `deeptrail-control/models/__init__.py` | Export AuditEvent model |

---

## Implementation Hints

```python
# deeptrail-control/models/audit_event.py

from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum

class AuditEventType(str, enum.Enum):
    MCP_TOOL_CALL = "mcp_tool_call"
    PERMISSION_DENIED = "permission_denied"
    SESSION_CREATED = "session_created"
    SESSION_EXPIRED = "session_expired"
    DELEGATION_CREATED = "delegation_created"
    DELEGATION_REVOKED = "delegation_revoked"

class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    event_type = Column(SQLEnum(AuditEventType), nullable=False, index=True)
    
    # Attribution
    agent_id = Column(String, nullable=True, index=True)  # Null for user-direct actions
    on_behalf_of = Column(String, nullable=False, index=True)  # Always present
    organization_id = Column(String, nullable=True, index=True)
    
    # Tool call details (for mcp_tool_call events)
    tool = Column(String, nullable=True)  # e.g., "notion.search_pages"
    arguments = Column(JSON, nullable=True)  # Tool arguments
    result_summary = Column(String, nullable=True)  # Brief result description
    
    # Permission denied details (for permission_denied events)
    attempted_tool = Column(String, nullable=True)
    required_permission = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    
    # Session context
    session_id = Column(String, nullable=True)  # Agent session ID
    mcp_session_id = Column(String, nullable=True)  # MCP session ID
    delegation_id = Column(String, nullable=True)  # Delegation being used
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_audit_agent_time', 'agent_id', 'timestamp'),
        Index('ix_audit_user_time', 'on_behalf_of', 'timestamp'),
        Index('ix_audit_org_time', 'organization_id', 'timestamp'),
    )
```

---

## Post-Conditions

After completing this task:

- [ ] All acceptance criteria met
- [ ] Tests pass locally: `pytest deeptrail-control/tests/models/test_audit_event.py`
- [ ] Linting passes: `ruff check deeptrail-control/models/`
- [ ] Type checking passes: `mypy deeptrail-control/models/`
- [ ] Task E2 can now start (it depends on E1)

---

## References

- Design Doc Section 2.9: Step 8 - Agent Executes Task (audit log format)
- Design Doc Section 2.10: Step 9 - Agent Denied (permission denied audit)
- Design Doc Section 2.11: Step 10 - Sarah Reviews Audit Trail
- Design Doc Section 5.5: Demo 5 - Unified Audit Trail

---

## Notes

- This is the audit foundation - keep schema flexible with JSON fields
- Demo 5 requires query "what did agent X do?" to complete in <1 second
- Consider event sourcing patterns for future (post-MVP)
- Arguments may contain sensitive data - add redaction support later

---

## Execution Log

### Progress Updates

| Date | Update |
|------|--------|
| - | Task created, ready to start |

### Blockers Encountered

| Date | Blocker | Resolution |
|------|---------|------------|
| - | - | - |
