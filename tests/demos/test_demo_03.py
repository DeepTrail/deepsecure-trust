"""
Tests for Demo 3: Delegation-Based Execution.

Tests verify that the demo correctly demonstrates zero-knowledge
credential injection where agents never see credentials.
"""

import pytest

from demos.demo_03_delegation_execution import (
    CONFIG,
    DemoConfig,
    DemoResult,
    GatewayStep,
    get_gateway_steps,
    run_demo,
)


# =============================================================================
# DemoConfig Tests
# =============================================================================


class TestDemoConfig:
    """Tests for DemoConfig dataclass."""
    
    def test_config_has_gateway_url(self):
        """Config has gateway URL."""
        assert CONFIG.GATEWAY_URL == "http://localhost:8002/mcp"
    
    def test_config_has_agent_id(self):
        """Config has agent ID."""
        assert CONFIG.AGENT_ID == "agent-sdr-001"
    
    def test_config_has_agent_name(self):
        """Config has agent name."""
        assert CONFIG.AGENT_NAME == "SDR-Assistant"
    
    def test_config_has_user_email(self):
        """Config has user email."""
        assert CONFIG.USER_EMAIL == "sarah@acme.com"
    
    def test_config_has_user_id(self):
        """Config has user ID."""
        assert CONFIG.USER_ID == "user-sarah-123"
    
    def test_config_has_delegation_id(self):
        """Config has delegation ID."""
        assert CONFIG.DELEGATION_ID == "del-sarah-sdr-001"
    
    def test_config_has_credential_ref(self):
        """Config has credential reference."""
        assert CONFIG.CREDENTIAL_REF == "vault://sarah-notion-oauth-xyz"
        assert CONFIG.CREDENTIAL_REF.startswith("vault://")
    
    def test_config_has_tool_name(self):
        """Config has tool name."""
        assert CONFIG.TOOL_NAME == "notion.search_pages"
    
    def test_config_has_backend(self):
        """Config has backend."""
        assert CONFIG.BACKEND == "notion"
    
    def test_default_config_can_be_created(self):
        """Default config can be instantiated."""
        config = DemoConfig()
        assert config.AGENT_ID == "agent-sdr-001"


# =============================================================================
# DemoResult Tests
# =============================================================================


class TestDemoResult:
    """Tests for DemoResult dataclass."""
    
    def test_success_result(self):
        """Test creating a success result."""
        result = DemoResult(success=True)
        
        assert result.success is True
        assert result.error is None
    
    def test_error_result(self):
        """Test creating an error result."""
        result = DemoResult(success=False, error="Test error")
        
        assert result.success is False
        assert result.error == "Test error"


# =============================================================================
# GatewayStep Tests
# =============================================================================


class TestGatewayStep:
    """Tests for GatewayStep dataclass."""
    
    def test_step_creation(self):
        """Test creating a gateway step."""
        step = GatewayStep(
            number=1,
            title="Test step",
            details=["Detail 1", "Detail 2"],
        )
        
        assert step.number == 1
        assert step.title == "Test step"
        assert len(step.details) == 2


class TestGetGatewaySteps:
    """Tests for get_gateway_steps function."""
    
    def test_returns_list_of_steps(self):
        """Returns a list of gateway steps."""
        steps = get_gateway_steps()
        
        assert isinstance(steps, list)
        assert len(steps) > 0
        assert all(isinstance(s, GatewayStep) for s in steps)
    
    def test_has_eight_steps(self):
        """Gateway processing has 8 steps."""
        steps = get_gateway_steps()
        assert len(steps) == 8
    
    def test_steps_are_numbered_sequentially(self):
        """Steps are numbered 1-8."""
        steps = get_gateway_steps()
        
        for i, step in enumerate(steps, start=1):
            assert step.number == i
    
    def test_first_step_is_receive(self):
        """First step is receiving the request."""
        steps = get_gateway_steps()
        assert "RECEIVE" in steps[0].title
    
    def test_step_four_is_credential_lookup(self):
        """Step 4 is credential lookup."""
        steps = get_gateway_steps()
        assert "LOOKUP" in steps[3].title
        assert "credentials" in steps[3].title.lower()
    
    def test_step_five_is_inject(self):
        """Step 5 is credential injection."""
        steps = get_gateway_steps()
        assert "INJECT" in steps[4].title
    
    def test_last_step_is_audit(self):
        """Last step is audit logging."""
        steps = get_gateway_steps()
        assert "LOG" in steps[7].title or "audit" in steps[7].title.lower()
    
    def test_all_steps_have_details(self):
        """All steps have at least one detail."""
        steps = get_gateway_steps()
        
        for step in steps:
            assert len(step.details) > 0


# =============================================================================
# Demo Run Tests
# =============================================================================


class TestRunDemo:
    """Tests for the run_demo function."""
    
    @pytest.mark.asyncio
    async def test_run_demo_succeeds(self):
        """Demo runs successfully."""
        result = await run_demo(mock_mode=True)
        
        assert result.success is True
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_run_demo_returns_demo_result(self):
        """Demo returns a DemoResult."""
        result = await run_demo(mock_mode=True)
        
        assert isinstance(result, DemoResult)


# =============================================================================
# Value Proposition Tests
# =============================================================================


class TestValueProposition:
    """Tests that verify the demo's security value proposition."""
    
    def test_credential_ref_is_vault_reference(self):
        """
        Credentials are referenced by vault URL, not actual values.
        """
        assert CONFIG.CREDENTIAL_REF.startswith("vault://")
        
        # Should not contain actual token values
        assert "eyJ" not in CONFIG.CREDENTIAL_REF
        assert "Bearer" not in CONFIG.CREDENTIAL_REF
    
    def test_agent_identity_is_separate_from_user(self):
        """
        Agent identity is separate from user identity.
        """
        assert CONFIG.AGENT_ID != CONFIG.USER_ID
        assert CONFIG.AGENT_ID != CONFIG.USER_EMAIL
    
    def test_delegation_links_agent_to_user(self):
        """
        Delegation ID links agent actions to user.
        """
        assert CONFIG.DELEGATION_ID.startswith("del-")
        assert "sarah" in CONFIG.DELEGATION_ID
        assert "sdr" in CONFIG.DELEGATION_ID
    
    def test_credential_injection_step_exists(self):
        """
        Gateway processing includes credential injection step.
        """
        steps = get_gateway_steps()
        
        inject_steps = [s for s in steps if "INJECT" in s.title]
        assert len(inject_steps) == 1
        
        inject_step = inject_steps[0]
        assert any("Authorization" in d for d in inject_step.details)
    
    def test_audit_step_includes_attribution(self):
        """
        Audit step includes agent and user attribution.
        """
        steps = get_gateway_steps()
        
        audit_step = steps[-1]  # Last step
        details_str = " ".join(audit_step.details)
        
        assert CONFIG.AGENT_ID in details_str
        assert CONFIG.USER_EMAIL in details_str
    
    def test_response_sanitization_step_exists(self):
        """
        Gateway processing includes response sanitization step.
        """
        steps = get_gateway_steps()
        
        # Step 7 should be stripping credentials
        strip_step = steps[6]
        assert "STRIP" in strip_step.title or "credential" in strip_step.title.lower()


# =============================================================================
# Security Model Tests
# =============================================================================


class TestSecurityModel:
    """Tests verifying the security model is correctly represented."""
    
    def test_eight_step_security_process(self):
        """
        The complete security process has 8 steps.
        """
        steps = get_gateway_steps()
        assert len(steps) == 8
    
    def test_permission_check_before_credential_lookup(self):
        """
        Permission is checked BEFORE looking up credentials.
        """
        steps = get_gateway_steps()
        
        permission_step = None
        lookup_step = None
        
        for step in steps:
            if "CHECK" in step.title and "permission" in step.title.lower():
                permission_step = step
            if "LOOKUP" in step.title and "credential" in step.title.lower():
                lookup_step = step
        
        assert permission_step is not None
        assert lookup_step is not None
        assert permission_step.number < lookup_step.number
    
    def test_session_validation_early_in_process(self):
        """
        Session validation happens early (step 2).
        """
        steps = get_gateway_steps()
        
        validate_step = steps[1]  # Second step
        assert "VALIDATE" in validate_step.title
        assert validate_step.number == 2
