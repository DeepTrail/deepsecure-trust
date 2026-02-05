# Task: WS-A3 Define Connected Services Model

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-A: Control Plane Foundation |
| **Dependencies** | A1 (User Session data model) |
| **Blocked By** | None (A1 is complete ✅) |
| **Assigned** | - |
| **Created** | January 30, 2026 |
| **Estimated Complexity** | `S` (< 2 hours) |
| **Batch** | 2 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 1: Unified Connection (foundation) |
| **Validates User Journey Step** | Step 3: Sarah Connects Notion & Slack |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] A1 (User Session data model) is complete
- [ ] `deeptrail-control/` service structure exists
- [ ] Database/ORM setup is available (SQLAlchemy)
- [ ] UserSession model can be imported from `deeptrail-control.models`

---

## Task Description

Define the Connected Services data model that represents a user's OAuth connections to backend services (Notion, Slack, HubSpot, etc.). This model stores references to OAuth tokens (stored in vault) and the scopes the user granted to each service.

### Context

From the MVP design (Section 2.4 - Step 3):

```
DeepTrail stores connection:
INSERT INTO connected_services:
{
  "user_id": "sarah@acme.com",
  "service_id": "notion",
  "oauth_token_ref": "vault://sarah-notion-oauth-xyz",  // Encrypted
  "scopes_granted": ["read_content", "search", "create_pages"],
  "connected_at": "2026-01-21T10:05:00Z"
}
```

This enables:
- Sarah connects Notion → DeepTrail holds her OAuth token securely
- Agent can later use Sarah's credentials (via delegation) to access Notion
- Sarah consents in HER browser; agent never does OAuth

### Technical Notes

- Use SQLAlchemy ORM for database model
- OAuth tokens stored in vault, NOT in this table (only references)
- `oauth_token_ref` format: `vault://{user}-{service}-{unique-id}`
- Scopes stored as JSON array for flexibility
- Consider composite unique key on (user_id, service_id)
- Foreign key to UserSession for user association

---

## Acceptance Criteria

### Protocol
- [ ] N/A (data model only)

### Security
- [ ] OAuth tokens are NOT stored directly (only vault references)
- [ ] Token reference format is opaque (no secrets in reference string)
- [ ] Model supports revocation timestamp for disconnection

### Integration
- [ ] Model can be imported from `deeptrail-control.models`
- [ ] Model follows existing ORM patterns in the codebase
- [ ] Foreign key relationship to UserSession (optional, by user_id)

### Functional
- [ ] All fields from Step 3 are present: user_id, service_id, oauth_token_ref, scopes_granted, connected_at
- [ ] Unique constraint on (user_id, service_id) - one connection per service per user
- [ ] `is_active` property to check if connection is not revoked
- [ ] Supports disconnection via `disconnected_at` timestamp

### General
- [ ] Unit tests for model instantiation and validation
- [ ] No new linting errors introduced

---

## Files to Create

| File | Purpose |
|------|---------|
| `deeptrail-control/models/connected_service.py` | Connected Service SQLAlchemy model |
| `deeptrail-control/tests/models/test_connected_service.py` | Unit tests for the model |

---

## Files to Modify

| File | Changes |
|------|---------|
| `deeptrail-control/models/__init__.py` | Export ConnectedService model |

---

## Implementation Hints

```python
# deeptrail-control/models/connected_service.py

from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

class ConnectedService(Base):
    __tablename__ = "connected_services"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # User association
    user_id = Column(String, nullable=False, index=True)  # e.g., "sarah@acme.com"
    
    # Service identification
    service_id = Column(String, nullable=False, index=True)  # e.g., "notion", "slack"
    service_name = Column(String, nullable=True)  # Display name: "Notion", "Slack"
    
    # OAuth token reference (stored in vault, not here)
    oauth_token_ref = Column(String, nullable=False)  # e.g., "vault://sarah-notion-oauth-xyz"
    
    # Scopes granted by user during OAuth consent
    scopes_granted = Column(JSON, nullable=False, default=list)
    # e.g., ["read_content", "search", "create_pages"]
    
    # Timestamps
    connected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    disconnected_at = Column(DateTime(timezone=True), nullable=True)  # None = still connected
    
    # Unique constraint: one connection per service per user
    __table_args__ = (
        UniqueConstraint('user_id', 'service_id', name='uq_user_service'),
    )
    
    @property
    def is_active(self) -> bool:
        """Check if the connection is still active (not disconnected)."""
        return self.disconnected_at is None
    
    def has_scope(self, scope: str) -> bool:
        """Check if a specific scope was granted."""
        return scope in (self.scopes_granted or [])
```

---

## Post-Conditions

After completing this task:

- [ ] All acceptance criteria met
- [ ] Tests pass locally: `pytest deeptrail-control/tests/models/test_connected_service.py`
- [ ] Linting passes: `ruff check deeptrail-control/models/`
- [ ] Type checking passes: `mypy deeptrail-control/models/`
- [ ] Task A4 can now start (OAuth token vault storage depends on A3)

---

## References

- Design Doc Section 2.4: Step 3 - Sarah Connects Notion & Slack
- Design Doc Section 4.2: Token Flow (OAuth token storage)
- A1 Task: UserSession model for user_id pattern

---

## Notes

- This is a foundational model - keep schema flexible
- A4 will implement the actual vault storage for OAuth tokens
- Consider adding `refresh_token_ref` for OAuth token refresh (post-MVP)
- Scopes format should match MCP permission patterns

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
