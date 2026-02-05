# Task: WS-A1 Define User Session Data Model

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-A: Control Plane Foundation |
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
| **Validates Demo** | N/A (foundation task) |
| **Validates User Journey Step** | Step 1: Enterprise Registration, Step 2: Sarah Authenticates |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] No dependency tasks (this is a Batch 1 task)
- [ ] `deeptrail-control/` service structure exists
- [ ] Database/ORM setup is available (SQLAlchemy)

---

## Task Description

Define the User Session data model that represents an authenticated user's session in the DeepTrail Control Plane. This model is the foundation for all user-related operations including connected services, delegations, and agent sessions.

### Context

From the MVP design (Section 2.3 - Step 2):

```
CREATE USER SESSION:
{
  "session_id": "usess-sarah-abc123",
  "user_id": "sarah@acme.com",
  "idp_issuer": "https://acme.okta.com",
  "permission_grants": {},      // Empty, will be populated
  "connected_services": {},     // Empty, will be populated
  "created_at": "2026-01-21T10:00:00Z",
  "expires_at": "2026-01-21T18:00:00Z"  // 8 hour work day
}
```

### Technical Notes

- Use SQLAlchemy ORM for database model
- Follow existing model patterns in `deeptrail-control/`
- Session ID should be a unique, URL-safe string (e.g., `usess-{uuid}`)
- Timestamps should be timezone-aware (UTC)
- Consider adding an `organization_id` field for multi-tenant support

---

## Acceptance Criteria

### Protocol
- [ ] N/A (data model only)

### Security
- [ ] Session ID is cryptographically random (UUID4 or similar)
- [ ] Expiry is enforced at model level (default 8 hours)

### Integration
- [ ] Model can be imported from `deeptrail-control.models`
- [ ] Model follows existing ORM patterns in the codebase
- [ ] Database migrations are generated (if using Alembic)

### General
- [ ] All fields from Step 2 are present: session_id, user_id, idp_issuer, expires_at, created_at
- [ ] Model includes relationship placeholders for connected_services and delegations
- [ ] Unit tests for model instantiation and validation
- [ ] No new linting errors introduced

---

## Files to Create

| File | Purpose |
|------|---------|
| `deeptrail-control/models/user_session.py` | User Session SQLAlchemy model |
| `deeptrail-control/tests/models/test_user_session.py` | Unit tests for the model |

---

## Files to Modify

| File | Changes |
|------|---------|
| `deeptrail-control/models/__init__.py` | Export UserSession model |

---

## Implementation Hints

```python
# deeptrail-control/models/user_session.py

from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import uuid

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    session_id = Column(String, primary_key=True, default=lambda: f"usess-{uuid.uuid4()}")
    user_id = Column(String, nullable=False, index=True)  # email
    idp_issuer = Column(String, nullable=False)  # e.g., "https://acme.okta.com"
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc) + timedelta(hours=8))
    
    # Relationships (to be populated by later tasks)
    # connected_services = relationship("ConnectedService", back_populates="user_session")
    # delegations = relationship("Delegation", back_populates="user_session")
    
    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at
```

---

## Post-Conditions

After completing this task:

- [ ] All acceptance criteria met
- [ ] Tests pass locally: `pytest deeptrail-control/tests/models/test_user_session.py`
- [ ] Linting passes: `ruff check deeptrail-control/models/`
- [ ] Type checking passes: `mypy deeptrail-control/models/`
- [ ] Tasks A2, A3, A5 can now start (they depend on A1)

---

## References

- Design Doc Section 2.3: Step 2 - Sarah Authenticates
- Design Doc Section 4.2: Token Flow in MVP
- Existing models in `deeptrail-control/models/` for patterns

---

## Notes

- This is the foundational model - keep it simple for MVP
- permission_grants and connected_services will be separate models (A3, A5)
- Consider adding `revoked_at` field for explicit session revocation

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
