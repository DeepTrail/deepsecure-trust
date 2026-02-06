"""
Tests for Constraint Checker (WS-E5).

Tests the ConstraintChecker and ConstraintStore implementations
including daily limits, session limits, and counter behavior.
"""

import pytest

from app.security.constraint_checker import (
    ConstraintChecker,
    ConstraintStatus,
    ConstraintType,
    ConstraintViolation,
    configure_constraint_checker,
    get_constraint_checker,
    reset_constraint_checker,
)
from app.security.constraint_store import (
    InMemoryConstraintStore,
    configure_constraint_store,
    get_constraint_store,
    reset_constraint_store,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def store():
    """Create a fresh in-memory constraint store."""
    return InMemoryConstraintStore()


@pytest.fixture
def checker(store):
    """Create a constraint checker with the test store."""
    return ConstraintChecker(store)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances before each test."""
    reset_constraint_checker()
    reset_constraint_store()
    yield
    reset_constraint_checker()
    reset_constraint_store()


# =============================================================================
# InMemoryConstraintStore Tests
# =============================================================================


class TestInMemoryConstraintStore:
    """Tests for InMemoryConstraintStore."""
    
    @pytest.mark.asyncio
    async def test_get_returns_zero_for_new_counter(self, store):
        """New counters return 0."""
        count = await store.get_daily_action_count("agent-1", "del-1")
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_increment_creates_counter(self, store):
        """Increment creates a counter if it doesn't exist."""
        count = await store.increment_daily_action_count("agent-1", "del-1")
        assert count == 1
    
    @pytest.mark.asyncio
    async def test_increment_increases_counter(self, store):
        """Increment increases existing counter."""
        await store.increment_daily_action_count("agent-1", "del-1")
        await store.increment_daily_action_count("agent-1", "del-1")
        count = await store.increment_daily_action_count("agent-1", "del-1")
        assert count == 3
    
    @pytest.mark.asyncio
    async def test_separate_agents_have_separate_counters(self, store):
        """Different agents have independent counters."""
        await store.increment_daily_action_count("agent-1", "del-1")
        await store.increment_daily_action_count("agent-1", "del-1")
        await store.increment_daily_action_count("agent-2", "del-1")
        
        count1 = await store.get_daily_action_count("agent-1", "del-1")
        count2 = await store.get_daily_action_count("agent-2", "del-1")
        
        assert count1 == 2
        assert count2 == 1
    
    @pytest.mark.asyncio
    async def test_separate_delegations_have_separate_counters(self, store):
        """Different delegations have independent counters."""
        await store.increment_daily_action_count("agent-1", "del-1")
        await store.increment_daily_action_count("agent-1", "del-1")
        await store.increment_daily_action_count("agent-1", "del-2")
        
        count1 = await store.get_daily_action_count("agent-1", "del-1")
        count2 = await store.get_daily_action_count("agent-1", "del-2")
        
        assert count1 == 2
        assert count2 == 1
    
    @pytest.mark.asyncio
    async def test_session_counters_separate_from_daily(self, store):
        """Session counters are independent from daily counters."""
        await store.increment_daily_action_count("agent-1", "del-1")
        await store.increment_session_action_count("agent-1", "session-1")
        
        daily_count = await store.get_daily_action_count("agent-1", "del-1")
        session_count = await store.get_session_action_count("agent-1", "session-1")
        
        assert daily_count == 1
        assert session_count == 1
    
    @pytest.mark.asyncio
    async def test_session_counter_increment(self, store):
        """Session counter increments correctly."""
        await store.increment_session_action_count("agent-1", "session-1")
        await store.increment_session_action_count("agent-1", "session-1")
        count = await store.get_session_action_count("agent-1", "session-1")
        assert count == 2
    
    @pytest.mark.asyncio
    async def test_reset_session_count(self, store):
        """Session counters can be reset."""
        await store.increment_session_action_count("agent-1", "session-1")
        await store.increment_session_action_count("agent-1", "session-1")
        
        await store.reset_session_count("agent-1", "session-1")
        
        count = await store.get_session_action_count("agent-1", "session-1")
        assert count == 0
    
    def test_clear_all(self, store):
        """clear_all removes all counters."""
        # This is sync - just testing the clear function
        store._daily_counts[("a", "d", "2026-01-30")] = 5
        store._session_counts[("a", "s")] = 3
        
        store.clear_all()
        
        assert len(store._daily_counts) == 0
        assert len(store._session_counts) == 0
    
    def test_get_all_counts(self, store):
        """get_all_counts returns debugging info."""
        store._daily_counts[("a", "d", "2026-01-30")] = 5
        store._session_counts[("a", "s")] = 3
        
        counts = store.get_all_counts()
        
        assert "daily" in counts
        assert "session" in counts
        assert len(counts["daily"]) == 1
        assert len(counts["session"]) == 1


# =============================================================================
# ConstraintViolation Tests
# =============================================================================


class TestConstraintViolation:
    """Tests for ConstraintViolation dataclass."""
    
    def test_violation_creation(self):
        """Test creating a constraint violation."""
        violation = ConstraintViolation(
            constraint_name="max_actions_per_day",
            constraint_type=ConstraintType.MAX_ACTIONS_PER_DAY,
            current_value=100,
            limit_value=100,
            message="Daily limit exceeded",
        )
        
        assert violation.constraint_name == "max_actions_per_day"
        assert violation.constraint_type == ConstraintType.MAX_ACTIONS_PER_DAY
        assert violation.current_value == 100
        assert violation.limit_value == 100
        assert "exceeded" in violation.message


class TestConstraintStatus:
    """Tests for ConstraintStatus dataclass."""
    
    def test_status_creation(self):
        """Test creating a constraint status."""
        status = ConstraintStatus(
            current=25,
            limit=100,
            remaining=75,
            percentage_used=25.0,
        )
        
        assert status.current == 25
        assert status.limit == 100
        assert status.remaining == 75
        assert status.percentage_used == 25.0


# =============================================================================
# ConstraintChecker Tests
# =============================================================================


class TestConstraintChecker:
    """Tests for ConstraintChecker."""
    
    @pytest.mark.asyncio
    async def test_allows_action_under_daily_limit(self, checker):
        """Actions under the daily limit are allowed."""
        constraints = {"max_actions_per_day": 100}
        
        violation = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-1",
            session_id="session-1",
            constraints=constraints,
        )
        
        assert violation is None
    
    @pytest.mark.asyncio
    async def test_blocks_action_at_daily_limit(self, checker, store):
        """Actions at the daily limit are blocked."""
        constraints = {"max_actions_per_day": 5}
        
        # Use up the limit
        for _ in range(5):
            violation = await checker.check_and_increment(
                agent_id="agent-1",
                delegation_id="del-1",
                session_id="session-1",
                constraints=constraints,
            )
            assert violation is None
        
        # 6th action should be blocked
        violation = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-1",
            session_id="session-1",
            constraints=constraints,
        )
        
        assert violation is not None
        assert violation.constraint_name == "max_actions_per_day"
        assert violation.current_value == 5
        assert violation.limit_value == 5
    
    @pytest.mark.asyncio
    async def test_allows_action_under_session_limit(self, checker):
        """Actions under the session limit are allowed."""
        constraints = {"max_actions_per_session": 50}
        
        violation = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-1",
            session_id="session-1",
            constraints=constraints,
        )
        
        assert violation is None
    
    @pytest.mark.asyncio
    async def test_blocks_action_at_session_limit(self, checker, store):
        """Actions at the session limit are blocked."""
        constraints = {"max_actions_per_session": 3}
        
        # Use up the limit
        for _ in range(3):
            violation = await checker.check_and_increment(
                agent_id="agent-1",
                delegation_id="del-1",
                session_id="session-1",
                constraints=constraints,
            )
            assert violation is None
        
        # 4th action should be blocked
        violation = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-1",
            session_id="session-1",
            constraints=constraints,
        )
        
        assert violation is not None
        assert violation.constraint_name == "max_actions_per_session"
        assert violation.current_value == 3
        assert violation.limit_value == 3
    
    @pytest.mark.asyncio
    async def test_both_constraints_enforced(self, checker, store):
        """Both daily and session constraints are enforced."""
        constraints = {
            "max_actions_per_day": 100,
            "max_actions_per_session": 3,
        }
        
        # Use up session limit
        for _ in range(3):
            await checker.check_and_increment(
                agent_id="agent-1",
                delegation_id="del-1",
                session_id="session-1",
                constraints=constraints,
            )
        
        # Should be blocked by session limit
        violation = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-1",
            session_id="session-1",
            constraints=constraints,
        )
        
        assert violation is not None
        assert violation.constraint_name == "max_actions_per_session"
    
    @pytest.mark.asyncio
    async def test_daily_limit_checked_first(self, checker, store):
        """Daily limit is checked before session limit."""
        constraints = {
            "max_actions_per_day": 2,
            "max_actions_per_session": 10,
        }
        
        # Use up daily limit
        await checker.check_and_increment("agent-1", "del-1", "session-1", constraints)
        await checker.check_and_increment("agent-1", "del-1", "session-1", constraints)
        
        # Should be blocked by daily limit
        violation = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-1",
            session_id="session-1",
            constraints=constraints,
        )
        
        assert violation is not None
        assert violation.constraint_name == "max_actions_per_day"
    
    @pytest.mark.asyncio
    async def test_separate_counters_per_delegation(self, checker):
        """Different delegations have separate counters."""
        constraints = {"max_actions_per_day": 2}
        
        # Use limit on delegation 1
        await checker.check_and_increment("agent-1", "del-1", "s-1", constraints)
        await checker.check_and_increment("agent-1", "del-1", "s-1", constraints)
        
        # Delegation 2 should still have capacity
        violation = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-2",
            session_id="s-1",
            constraints=constraints,
        )
        
        assert violation is None
    
    @pytest.mark.asyncio
    async def test_no_constraint_means_unlimited(self, checker):
        """No constraints means unlimited actions."""
        constraints = {}  # No constraints
        
        for _ in range(100):
            violation = await checker.check_and_increment(
                agent_id="agent-1",
                delegation_id="del-1",
                session_id="session-1",
                constraints=constraints,
            )
            assert violation is None
    
    @pytest.mark.asyncio
    async def test_session_constraint_ignored_without_session_id(self, checker):
        """Session constraint is skipped if no session_id provided."""
        constraints = {"max_actions_per_session": 1}
        
        # Two calls without session_id should not be blocked
        violation1 = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-1",
            session_id=None,  # No session
            constraints=constraints,
        )
        violation2 = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-1",
            session_id=None,
            constraints=constraints,
        )
        
        assert violation1 is None
        assert violation2 is None
    
    @pytest.mark.asyncio
    async def test_check_constraints_does_not_increment(self, checker, store):
        """check_constraints only checks, doesn't increment."""
        constraints = {"max_actions_per_day": 5}
        
        # Check multiple times
        for _ in range(10):
            violation = await checker.check_constraints(
                agent_id="agent-1",
                delegation_id="del-1",
                session_id="s-1",
                constraints=constraints,
            )
            assert violation is None
        
        # Count should still be 0
        count = await store.get_daily_action_count("agent-1", "del-1")
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_get_constraint_status_daily(self, checker, store):
        """Can retrieve daily constraint status."""
        constraints = {"max_actions_per_day": 100}
        
        # Perform 10 actions
        for _ in range(10):
            await checker.check_and_increment("agent-1", "del-1", "s-1", constraints)
        
        status = await checker.get_constraint_status(
            "agent-1", "del-1", "s-1", constraints
        )
        
        assert "max_actions_per_day" in status
        assert status["max_actions_per_day"].current == 10
        assert status["max_actions_per_day"].limit == 100
        assert status["max_actions_per_day"].remaining == 90
        assert status["max_actions_per_day"].percentage_used == 10.0
    
    @pytest.mark.asyncio
    async def test_get_constraint_status_session(self, checker, store):
        """Can retrieve session constraint status."""
        constraints = {"max_actions_per_session": 50}
        
        # Perform 5 actions
        for _ in range(5):
            await checker.check_and_increment("agent-1", "del-1", "s-1", constraints)
        
        status = await checker.get_constraint_status(
            "agent-1", "del-1", "s-1", constraints
        )
        
        assert "max_actions_per_session" in status
        assert status["max_actions_per_session"].current == 5
        assert status["max_actions_per_session"].limit == 50
        assert status["max_actions_per_session"].remaining == 45
        assert status["max_actions_per_session"].percentage_used == 10.0
    
    @pytest.mark.asyncio
    async def test_get_constraint_status_empty_for_no_constraints(self, checker):
        """Empty status when no constraints configured."""
        constraints = {}
        
        status = await checker.get_constraint_status(
            "agent-1", "del-1", "s-1", constraints
        )
        
        assert status == {}


# =============================================================================
# Module Configuration Tests
# =============================================================================


class TestModuleConfiguration:
    """Tests for module-level configuration functions."""
    
    def test_get_constraint_store_returns_singleton(self):
        """get_constraint_store returns the same instance."""
        store1 = get_constraint_store()
        store2 = get_constraint_store()
        
        assert store1 is store2
    
    def test_configure_constraint_store(self):
        """configure_constraint_store sets up the singleton."""
        custom_store = InMemoryConstraintStore()
        
        configure_constraint_store(custom_store)
        
        assert get_constraint_store() is custom_store
    
    def test_reset_constraint_store(self):
        """reset_constraint_store clears the singleton."""
        configure_constraint_store(InMemoryConstraintStore())
        store1 = get_constraint_store()
        
        reset_constraint_store()
        
        store2 = get_constraint_store()
        assert store1 is not store2
    
    def test_get_constraint_checker_returns_singleton(self):
        """get_constraint_checker returns the same instance."""
        checker1 = get_constraint_checker()
        checker2 = get_constraint_checker()
        
        assert checker1 is checker2
    
    def test_configure_constraint_checker(self):
        """configure_constraint_checker sets up the singleton."""
        custom_store = InMemoryConstraintStore()
        
        checker = configure_constraint_checker(custom_store)
        
        assert get_constraint_checker() is checker
        assert checker._store is custom_store
    
    def test_reset_constraint_checker(self):
        """reset_constraint_checker clears the singleton."""
        configure_constraint_checker(InMemoryConstraintStore())
        checker1 = get_constraint_checker()
        
        reset_constraint_checker()
        
        checker2 = get_constraint_checker()
        assert checker1 is not checker2


# =============================================================================
# Integration-Style Tests
# =============================================================================


class TestIntegrationScenarios:
    """Integration-style tests for realistic scenarios."""
    
    @pytest.mark.asyncio
    async def test_daily_limit_scenario(self, store):
        """Simulates a realistic daily limit scenario."""
        checker = ConstraintChecker(store)
        constraints = {"max_actions_per_day": 100}
        
        # Agent uses 99 actions
        for i in range(99):
            violation = await checker.check_and_increment(
                agent_id="agent-1",
                delegation_id="del-1",
                session_id=f"session-{i % 5}",  # Multiple sessions
                constraints=constraints,
            )
            assert violation is None, f"Action {i+1} should be allowed"
        
        # 100th action should work
        violation = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-1",
            session_id="session-0",
            constraints=constraints,
        )
        assert violation is None
        
        # 101st action should be blocked
        violation = await checker.check_and_increment(
            agent_id="agent-1",
            delegation_id="del-1",
            session_id="session-0",
            constraints=constraints,
        )
        assert violation is not None
        assert "100/100" in violation.message
    
    @pytest.mark.asyncio
    async def test_multiple_agents_independent(self, store):
        """Multiple agents have independent constraints."""
        checker = ConstraintChecker(store)
        constraints = {"max_actions_per_day": 5}
        
        # Agent 1 uses all 5 actions
        for _ in range(5):
            await checker.check_and_increment("agent-1", "del-1", "s-1", constraints)
        
        # Agent 1 should be blocked
        violation1 = await checker.check_and_increment(
            "agent-1", "del-1", "s-1", constraints
        )
        assert violation1 is not None
        
        # Agent 2 should still have all 5 actions
        for _ in range(5):
            violation2 = await checker.check_and_increment(
                "agent-2", "del-1", "s-2", constraints
            )
            assert violation2 is None
    
    @pytest.mark.asyncio
    async def test_session_renewal_resets_session_count(self, store):
        """New session gets fresh session counter."""
        checker = ConstraintChecker(store)
        constraints = {
            "max_actions_per_day": 100,
            "max_actions_per_session": 3,
        }
        
        # Use up session 1
        for _ in range(3):
            await checker.check_and_increment("agent-1", "del-1", "session-1", constraints)
        
        # Session 1 blocked
        violation = await checker.check_and_increment(
            "agent-1", "del-1", "session-1", constraints
        )
        assert violation is not None
        assert violation.constraint_name == "max_actions_per_session"
        
        # New session should work
        for _ in range(3):
            violation = await checker.check_and_increment(
                "agent-1", "del-1", "session-2", constraints
            )
            assert violation is None
    
    @pytest.mark.asyncio
    async def test_constraint_status_for_billing(self, store):
        """Constraint status can be used for billing/monitoring."""
        checker = ConstraintChecker(store)
        constraints = {
            "max_actions_per_day": 1000,
            "max_actions_per_session": 100,
        }
        
        # Use 50 actions (under both limits)
        for _ in range(50):
            await checker.check_and_increment("agent-1", "del-1", "s-1", constraints)
        
        status = await checker.get_constraint_status(
            "agent-1", "del-1", "s-1", constraints
        )
        
        # Daily: 50/1000 = 5%
        assert status["max_actions_per_day"].current == 50
        assert status["max_actions_per_day"].percentage_used == 5.0
        
        # Session: 50/100 = 50%
        assert status["max_actions_per_session"].current == 50
        assert status["max_actions_per_session"].percentage_used == 50.0
