# Task: WS-A2 Implement UserSessionService

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
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 2 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | N/A (foundation service) |
| **Validates User Journey Step** | Step 2: Sarah Authenticates (session creation) |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] A1 (User Session data model) is complete
- [ ] `deeptrail-control/` service structure exists
- [ ] Database/ORM setup is available (SQLAlchemy)
- [ ] UserSession model can be imported from `deeptrail-control.models`

---

## Task Description

Implement the UserSessionService that manages user session lifecycle in the DeepTrail Control Plane. This service handles creating, reading, validating, and expiring user sessions after a user authenticates via their enterprise IdP.

### Context

From the MVP design (Section 2.3 - Step 2):

```
DeepTrail Console creates User Session:
{
  "session_id": "usess-sarah-abc123",
  "user_id": "sarah@acme.com",
  "idp_issuer": "https://acme.okta.com",
  "permission_grants": {},      // Empty, will be populated
  "connected_services": {},     // Empty, will be populated
  "created_at": "2026-01-21T10:00:00Z",
  "expires_at": "2026-01-21T18:00:00Z"  // 8 hour work day
}

RESULT: Sarah has an active User Session in DeepTrail
```

### Technical Notes

- Service should follow existing patterns in `deeptrail-control/services/`
- Use dependency injection for database session (SQLAlchemy)
- Session lookup should be O(1) by session_id
- Consider caching for frequently accessed sessions
- Default session duration: 8 hours (configurable)

---

## Acceptance Criteria

### Protocol
- [ ] N/A (internal service)

### Security
- [ ] Sessions cannot be modified after creation (only expired/revoked)
- [ ] Expired sessions return None/raise exception on lookup
- [ ] Session IDs are not predictable (UUID-based from A1)

### Integration
- [ ] Service can be imported from `deeptrail-control.services`
- [ ] Works with SQLAlchemy async session
- [ ] Follows repository/service pattern if established in codebase

### Functional
- [ ] `create_session(user_id, idp_issuer, expires_in_hours=8)` → UserSession
- [ ] `get_session(session_id)` → UserSession | None
- [ ] `get_sessions_by_user(user_id)` → List[UserSession]
- [ ] `expire_session(session_id)` → bool
- [ ] `is_valid(session_id)` → bool (not expired, not revoked)
- [ ] `refresh_session(session_id, additional_hours)` → UserSession (extend expiry)

### General
- [ ] Unit tests for all methods
- [ ] Tests for edge cases (expired session, non-existent session)
- [ ] No new linting errors introduced

---

## Files to Create

| File | Purpose |
|------|---------|
| `deeptrail-control/services/user_session_service.py` | UserSessionService implementation |
| `deeptrail-control/tests/services/test_user_session_service.py` | Unit tests |

---

## Files to Modify

| File | Changes |
|------|---------|
| `deeptrail-control/services/__init__.py` | Export UserSessionService |

---

## Implementation Hints

```python
# deeptrail-control/services/user_session_service.py

from datetime import datetime, timedelta, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from deeptrail_control.models import UserSession


class UserSessionService:
    """Service for managing user session lifecycle."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_session(
        self,
        user_id: str,
        idp_issuer: str,
        organization_id: Optional[str] = None,
        expires_in_hours: int = 8
    ) -> UserSession:
        """Create a new user session after IdP authentication."""
        session = UserSession(
            user_id=user_id,
            idp_issuer=idp_issuer,
            organization_id=organization_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session
    
    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a session by ID. Returns None if not found or expired."""
        result = await self.db.execute(
            select(UserSession).where(UserSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if session and session.is_expired:
            return None  # Treat expired sessions as non-existent
        
        return session
    
    async def get_sessions_by_user(self, user_id: str) -> List[UserSession]:
        """Get all active (non-expired) sessions for a user."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(UserSession)
            .where(UserSession.user_id == user_id)
            .where(UserSession.expires_at > now)
        )
        return list(result.scalars().all())
    
    async def expire_session(self, session_id: str) -> bool:
        """Immediately expire a session. Returns True if found and expired."""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        session.expires_at = datetime.now(timezone.utc)
        await self.db.commit()
        return True
    
    async def is_valid(self, session_id: str) -> bool:
        """Check if a session exists and is not expired."""
        session = await self.get_session(session_id)
        return session is not None
    
    async def refresh_session(
        self, 
        session_id: str, 
        additional_hours: int = 8
    ) -> Optional[UserSession]:
        """Extend a session's expiry. Returns None if session not found."""
        result = await self.db.execute(
            select(UserSession).where(UserSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return None
        
        session.expires_at = datetime.now(timezone.utc) + timedelta(hours=additional_hours)
        await self.db.commit()
        await self.db.refresh(session)
        return session
```

---

## Post-Conditions

After completing this task:

- [ ] All acceptance criteria met
- [ ] Tests pass locally: `pytest deeptrail-control/tests/services/test_user_session_service.py`
- [ ] Linting passes: `ruff check deeptrail-control/services/`
- [ ] Type checking passes: `mypy deeptrail-control/services/`
- [ ] Service can be used by future API endpoints (Step 2 authentication)

---

## References

- Design Doc Section 2.3: Step 2 - Sarah Authenticates
- A1 Task: UserSession model definition
- Existing services in `deeptrail-control/services/` for patterns

---

## Notes

- This is a foundational service - keep interface simple and extensible
- Future tasks (A3, A4, A5) will add connected_services and delegations
- Consider adding `revoked_at` field support for explicit revocation vs expiry

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
