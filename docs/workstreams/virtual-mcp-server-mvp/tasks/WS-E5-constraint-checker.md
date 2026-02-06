# Task: WS-E5 Implement Constraint Checker

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-E: Audit & Security |
| **Code Dependencies** | C6 (Delegation validator) ✅ |
| **Runtime Dependencies** | Control Plane (deeptrail-control) for delegation state |
| **Blocked By** | None |
| **Assigned** | - |
| **Created** | February 6, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 8 |
| **Target Worktree** | `vmcp-gateway` |

---

## Dependencies

### Code Dependencies (must complete before starting)

| Task | What We Need | Status |
|------|--------------|--------|
| C6 | Delegation validator patterns, delegation data model | ✅ |

### Runtime Dependencies (must be deployed for integration testing)

| Service | Endpoint | Required For |
|---------|----------|--------------|
| Control Plane | `http://localhost:8000` | Persisting and checking action counts |

### Development Mode

When runtime dependencies are unavailable:

- [x] **Fallback behavior**: In-memory constraint tracking for testing
- [x] **Local testing**: Unit tests with mocked constraint state
- [x] **Integration testing**: Container deployment needed for persistent counters

---

## Pre-Conditions

Before starting this task, ensure:

- [x] C6 (Delegation validator) is complete ✅
- [x] Delegation model includes constraints field
- [x] Understand constraint schema from design doc

---

## Task Description

Implement **constraint checking** in the Gateway to enforce delegation constraints such as `max_actions_per_day`, time-based limits, and other usage boundaries.

### Context

From the design doc (Section 2.5 - Step 4):
```json
{
  "delegation_token": "...",
  "permissions": ["notion:pages:search", "slack:messages:search", ...],
  "constraints": {
    "max_actions_per_day": 100
  },
  "exp": 1738512000
}
```

From Step 7 (tools/call processing):
```
3. VALIDATE constraints:
   • max_actions_per_day: 100
   • Current count: 0 → Increment to 1 ✓ ALLOWED
```

The constraint checker validates that the agent's actions stay within the bounds set by the user in the delegation.

### Technical Notes

Constraints to support in MVP:
1. **`max_actions_per_day`**: Limit total tool calls per 24-hour period
2. **`max_actions_per_session`**: Limit tool calls per agent session (optional)
3. **Expiration**: Already handled by delegation validator, but verify here too

Counter storage options:
- MVP: In-memory with Redis fallback
- Production: Redis with TTL-based cleanup

---

## Acceptance Criteria

- [ ] `max_actions_per_day` constraint enforced
- [ ] Action counter increments on successful tool calls
- [ ] Counter resets at midnight UTC (or 24h rolling window)
- [ ] Constraint violation returns specific error response
- [ ] Constraint state is persistent (survives gateway restart)
- [ ] Unit tests cover constraint validation logic
- [ ] Integration tests verify counter persistence
- [ ] No new linting errors introduced

---

## Files to Modify/Create

### Files to Create

- `deeptrail-gateway/app/security/constraint_checker.py` - Constraint validation logic
- `deeptrail-gateway/app/security/constraint_store.py` - Counter storage abstraction

### Files to Modify

- `deeptrail-gateway/app/middleware/delegation.py` - Integrate constraint checking
- `deeptrail-gateway/app/mcp/handlers/tools_call.py` - Check constraints before execution
- `deeptrail-gateway/app/core/config.py` - Add constraint store configuration

### Tests to Add

- `deeptrail-gateway/tests/security/test_constraint_checker.py` - Constraint validation tests

---

## Implementation Details

### ConstraintChecker Class

```python
# deeptrail-gateway/app/security/constraint_checker.py

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ConstraintViolation:
    constraint_name: str
    current_value: int
    limit_value: int
    message: str


class ConstraintChecker:
    """Validates delegation constraints."""
    
    def __init__(self, store: "ConstraintStore"):
        self.store = store
    
    async def check_and_increment(
        self,
        agent_id: str,
        delegation_id: str,
        constraints: Dict[str, Any]
    ) -> Optional[ConstraintViolation]:
        """
        Check constraints and increment counter if allowed.
        
        Args:
            agent_id: The agent making the request
            delegation_id: The delegation being used
            constraints: Constraint configuration from delegation
            
        Returns:
            ConstraintViolation if violated, None if allowed
        """
        # Check max_actions_per_day
        if "max_actions_per_day" in constraints:
            max_actions = constraints["max_actions_per_day"]
            current_count = await self.store.get_daily_action_count(
                agent_id, delegation_id
            )
            
            if current_count >= max_actions:
                return ConstraintViolation(
                    constraint_name="max_actions_per_day",
                    current_value=current_count,
                    limit_value=max_actions,
                    message=f"Daily action limit exceeded ({current_count}/{max_actions})"
                )
            
            # Increment counter
            await self.store.increment_daily_action_count(
                agent_id, delegation_id
            )
        
        # Add more constraint types here as needed
        
        return None
    
    async def get_constraint_status(
        self,
        agent_id: str,
        delegation_id: str,
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get current constraint usage status."""
        status = {}
        
        if "max_actions_per_day" in constraints:
            current = await self.store.get_daily_action_count(
                agent_id, delegation_id
            )
            status["max_actions_per_day"] = {
                "current": current,
                "limit": constraints["max_actions_per_day"],
                "remaining": max(0, constraints["max_actions_per_day"] - current)
            }
        
        return status
```

### ConstraintStore Interface

```python
# deeptrail-gateway/app/security/constraint_store.py

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict


class ConstraintStore(ABC):
    """Abstract base for constraint counter storage."""
    
    @abstractmethod
    async def get_daily_action_count(
        self, agent_id: str, delegation_id: str
    ) -> int:
        """Get today's action count."""
        pass
    
    @abstractmethod
    async def increment_daily_action_count(
        self, agent_id: str, delegation_id: str
    ) -> int:
        """Increment and return new count."""
        pass


class InMemoryConstraintStore(ConstraintStore):
    """In-memory store for testing and development."""
    
    def __init__(self):
        # Key: (agent_id, delegation_id, date_str) -> count
        self._counts: Dict[tuple, int] = {}
    
    def _get_key(self, agent_id: str, delegation_id: str) -> tuple:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return (agent_id, delegation_id, today)
    
    async def get_daily_action_count(
        self, agent_id: str, delegation_id: str
    ) -> int:
        key = self._get_key(agent_id, delegation_id)
        return self._counts.get(key, 0)
    
    async def increment_daily_action_count(
        self, agent_id: str, delegation_id: str
    ) -> int:
        key = self._get_key(agent_id, delegation_id)
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]


class RedisConstraintStore(ConstraintStore):
    """Redis-backed store for production."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def _get_key(self, agent_id: str, delegation_id: str) -> str:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"constraints:{agent_id}:{delegation_id}:{today}"
    
    async def get_daily_action_count(
        self, agent_id: str, delegation_id: str
    ) -> int:
        key = self._get_key(agent_id, delegation_id)
        value = await self.redis.get(key)
        return int(value) if value else 0
    
    async def increment_daily_action_count(
        self, agent_id: str, delegation_id: str
    ) -> int:
        key = self._get_key(agent_id, delegation_id)
        # INCR with TTL of 48 hours (covers timezone edge cases)
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 48 * 60 * 60)  # 48 hours
        result = await pipe.execute()
        return result[0]
```

### Integration with tools/call

```python
# In tools_call.py handler:

async def handle_tools_call(request: MCPRequest, ...):
    # ... existing validation ...
    
    # Check constraints before execution
    violation = await constraint_checker.check_and_increment(
        agent_id=agent_session.agent_id,
        delegation_id=delegation.delegation_id,
        constraints=delegation.constraints
    )
    
    if violation:
        return MCPErrorResponse(
            code=-32002,  # Custom error code for constraint violation
            message=f"Constraint violated: {violation.constraint_name}",
            data={
                "constraint": violation.constraint_name,
                "current": violation.current_value,
                "limit": violation.limit_value
            }
        )
    
    # Continue with tool execution...
```

---

## Test Cases

### Unit Tests

```python
# tests/security/test_constraint_checker.py

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from app.security.constraint_checker import ConstraintChecker, ConstraintViolation
from app.security.constraint_store import InMemoryConstraintStore

class TestConstraintChecker:
    
    @pytest.fixture
    def store(self):
        return InMemoryConstraintStore()
    
    @pytest.fixture
    def checker(self, store):
        return ConstraintChecker(store)
    
    @pytest.mark.asyncio
    async def test_allows_action_under_limit(self, checker):
        """Actions under the limit are allowed."""
        constraints = {"max_actions_per_day": 100}
        
        violation = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-1",
            constraints=constraints
        )
        
        assert violation is None
    
    @pytest.mark.asyncio
    async def test_blocks_action_at_limit(self, checker, store):
        """Actions at the limit are blocked."""
        constraints = {"max_actions_per_day": 5}
        
        # Use up the limit
        for _ in range(5):
            await checker.check_and_increment(
                agent_id="agent-1",
                delegation_id="del-1",
                constraints=constraints
            )
        
        # 6th action should be blocked
        violation = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-1",
            constraints=constraints
        )
        
        assert violation is not None
        assert violation.constraint_name == "max_actions_per_day"
        assert violation.current_value == 5
        assert violation.limit_value == 5
    
    @pytest.mark.asyncio
    async def test_separate_counters_per_delegation(self, checker):
        """Different delegations have separate counters."""
        constraints = {"max_actions_per_day": 2}
        
        # Use limit on delegation 1
        await checker.check_and_increment("agent-1", "del-1", constraints)
        await checker.check_and_increment("agent-1", "del-1", constraints)
        
        # Delegation 2 should still have capacity
        violation = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-2",
            constraints=constraints
        )
        
        assert violation is None
    
    @pytest.mark.asyncio
    async def test_no_constraint_means_unlimited(self, checker):
        """No constraints means unlimited actions."""
        constraints = {}  # No constraints
        
        for _ in range(1000):
            violation = await checker.check_and_increment(
                agent_id="agent-1",
                delegation_id="del-1",
                constraints=constraints
            )
            assert violation is None
    
    @pytest.mark.asyncio
    async def test_get_constraint_status(self, checker, store):
        """Can retrieve current constraint status."""
        constraints = {"max_actions_per_day": 100}
        
        # Perform 10 actions
        for _ in range(10):
            await checker.check_and_increment("agent-1", "del-1", constraints)
        
        status = await checker.get_constraint_status(
            "agent-1", "del-1", constraints
        )
        
        assert status["max_actions_per_day"]["current"] == 10
        assert status["max_actions_per_day"]["limit"] == 100
        assert status["max_actions_per_day"]["remaining"] == 90


class TestInMemoryConstraintStore:
    
    @pytest.mark.asyncio
    async def test_increment_creates_counter(self):
        store = InMemoryConstraintStore()
        
        count = await store.increment_daily_action_count("agent-1", "del-1")
        assert count == 1
    
    @pytest.mark.asyncio
    async def test_increment_increases_counter(self):
        store = InMemoryConstraintStore()
        
        await store.increment_daily_action_count("agent-1", "del-1")
        await store.increment_daily_action_count("agent-1", "del-1")
        count = await store.increment_daily_action_count("agent-1", "del-1")
        
        assert count == 3
    
    @pytest.mark.asyncio
    async def test_separate_agents_have_separate_counters(self):
        store = InMemoryConstraintStore()
        
        await store.increment_daily_action_count("agent-1", "del-1")
        await store.increment_daily_action_count("agent-1", "del-1")
        await store.increment_daily_action_count("agent-2", "del-1")
        
        count1 = await store.get_daily_action_count("agent-1", "del-1")
        count2 = await store.get_daily_action_count("agent-2", "del-1")
        
        assert count1 == 2
        assert count2 == 1
```

---

## Post-Conditions

### Code Complete (enables dependent tasks to start)

- [ ] All acceptance criteria met
- [ ] Unit tests pass locally: `pytest deeptrail-gateway/tests/security/`
- [ ] Linting passes: `ruff check deeptrail-gateway/`
- [ ] Type checking passes: `mypy deeptrail-gateway/`
- [ ] Completion report created

### Integration Complete (validated at merge point)

- [ ] Integration tests pass with Redis container
- [ ] Counter persists across gateway restarts
- [ ] Counter resets correctly at day boundary

### Unblocks

| Task | Type | Notes |
|------|------|-------|
| - | - | No direct dependencies |

---

## References

- Design Doc: [Section 2.5 - Step 4: Constraints](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md)
- Design Doc: [Section 2.8 - Step 7: Constraint Validation](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md)
- Related Code: `deeptrail-gateway/app/middleware/delegation.py`

---

## Notes

- MVP uses simple daily counter; production may need more complex rate limiting
- Consider adding constraint info to audit events
- Future: Support more constraint types (time-of-day, resource-specific limits)

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
