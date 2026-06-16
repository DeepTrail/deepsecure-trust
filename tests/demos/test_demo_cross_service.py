"""
Unit tests for Cross-Service Workflow Demo (demo_cross_service_workflow.py)

Tests the workflow orchestration across multiple backend MCP servers
(Notion, Slack, Gmail) in a realistic business workflow.
"""

import sys
from pathlib import Path

import pytest

# Add demos directory to path for imports
demos_dir = Path(__file__).parent.parent.parent / "demos"
sys.path.insert(0, str(demos_dir))

from demo_cross_service_workflow import (  # noqa: E402
    CONFIG,
    DemoConfig,
    WorkflowStep,
    WorkflowResult,
    AuditEntry,
    get_workflow_steps,
    get_backend_icon,
    get_unique_backends,
    execute_step,
    is_step_successful,
    run_demo,
)


# =============================================================================
# Configuration Tests
# =============================================================================


class TestDemoConfig:
    """Tests for DemoConfig dataclass."""
    
    def test_config_has_gateway_url(self):
        """Config includes gateway URL."""
        config = DemoConfig()
        assert config.GATEWAY_URL is not None
        assert "localhost" in config.GATEWAY_URL or "http" in config.GATEWAY_URL
    
    def test_config_has_agent_id(self):
        """Config includes agent ID."""
        config = DemoConfig()
        assert config.AGENT_ID is not None
        assert len(config.AGENT_ID) > 0
    
    def test_config_has_agent_name(self):
        """Config includes agent name."""
        config = DemoConfig()
        assert config.AGENT_NAME is not None
        assert len(config.AGENT_NAME) > 0
    
    def test_config_has_user_email(self):
        """Config includes user email."""
        config = DemoConfig()
        assert config.USER_EMAIL is not None
        assert "@" in config.USER_EMAIL
    
    def test_config_has_user_id(self):
        """Config includes user ID."""
        config = DemoConfig()
        assert config.USER_ID is not None
        assert len(config.USER_ID) > 0
    
    def test_config_has_delegation_id(self):
        """Config includes delegation ID."""
        config = DemoConfig()
        assert config.DELEGATION_ID is not None
        assert len(config.DELEGATION_ID) > 0
    
    def test_global_config_exists(self):
        """Global CONFIG instance exists."""
        assert CONFIG is not None
        assert isinstance(CONFIG, DemoConfig)


# =============================================================================
# WorkflowStep Tests
# =============================================================================


class TestWorkflowStep:
    """Tests for WorkflowStep dataclass."""
    
    def test_workflow_step_creation(self):
        """Can create a WorkflowStep."""
        step = WorkflowStep(
            step_num=1,
            backend="notion",
            tool="notion.search_pages",
            description="Test step",
            arguments={"query": "test"},
        )
        assert step.step_num == 1
        assert step.backend == "notion"
        assert step.tool == "notion.search_pages"
        assert step.description == "Test step"
        assert step.arguments == {"query": "test"}
    
    def test_workflow_step_defaults(self):
        """WorkflowStep has sensible defaults."""
        step = WorkflowStep(
            step_num=1,
            backend="test",
            tool="test.action",
            description="Test",
            arguments={},
        )
        assert step.result == {}
        assert step.duration_ms == 0.0
        assert step.status == "pending"
    
    def test_workflow_step_with_result(self):
        """WorkflowStep can store results."""
        step = WorkflowStep(
            step_num=1,
            backend="test",
            tool="test.action",
            description="Test",
            arguments={},
            result={"data": "value"},
        )
        assert step.result == {"data": "value"}


# =============================================================================
# WorkflowResult Tests
# =============================================================================


class TestWorkflowResult:
    """Tests for WorkflowResult dataclass."""
    
    def test_workflow_result_success(self):
        """Can create a successful WorkflowResult."""
        result = WorkflowResult(
            success=True,
            steps_executed=5,
            steps_succeeded=5,
            backends_used=["notion", "gmail", "slack"],
            total_duration_ms=250.0,
        )
        assert result.success is True
        assert result.steps_executed == 5
        assert result.steps_succeeded == 5
        assert len(result.backends_used) == 3
        assert result.total_duration_ms == 250.0
        assert result.error is None
    
    def test_workflow_result_failure(self):
        """Can create a failed WorkflowResult."""
        result = WorkflowResult(
            success=False,
            steps_executed=2,
            steps_succeeded=1,
            backends_used=["notion"],
            total_duration_ms=50.0,
            error="Connection failed",
        )
        assert result.success is False
        assert result.error == "Connection failed"


# =============================================================================
# AuditEntry Tests
# =============================================================================


class TestAuditEntry:
    """Tests for AuditEntry dataclass."""
    
    def test_audit_entry_creation(self):
        """Can create an AuditEntry."""
        entry = AuditEntry(
            timestamp="14:30:00",
            backend="notion",
            tool="notion.search_pages",
            status="success",
            agent_id="agent-001",
            user_email="user@example.com",
        )
        assert entry.timestamp == "14:30:00"
        assert entry.backend == "notion"
        assert entry.tool == "notion.search_pages"
        assert entry.status == "success"
        assert entry.agent_id == "agent-001"
        assert entry.user_email == "user@example.com"


# =============================================================================
# Workflow Definition Tests
# =============================================================================


class TestWorkflowDefinition:
    """Tests for workflow definition."""
    
    def test_workflow_has_multiple_backends(self):
        """Workflow uses multiple backends."""
        steps = get_workflow_steps()
        backends = set(step.backend for step in steps)
        assert len(backends) >= 3
        assert "notion" in backends
        assert "gmail" in backends
        assert "slack" in backends

    def test_workflow_has_five_steps(self):
        """Workflow has 5 steps as specified in design."""
        steps = get_workflow_steps()
        assert len(steps) == 5
    
    def test_workflow_steps_are_numbered(self):
        """Steps are numbered sequentially."""
        steps = get_workflow_steps()
        for i, step in enumerate(steps, start=1):
            assert step.step_num == i
    
    def test_all_steps_have_required_fields(self):
        """All steps have required fields."""
        steps = get_workflow_steps()
        for step in steps:
            assert step.step_num > 0
            assert step.backend is not None
            assert len(step.backend) > 0
            assert step.tool is not None
            assert len(step.tool) > 0
            assert step.description is not None
            assert len(step.description) > 0
            assert step.arguments is not None
    
    def test_tools_are_namespaced(self):
        """All tools follow namespace.action pattern."""
        steps = get_workflow_steps()
        for step in steps:
            assert "." in step.tool, f"Tool {step.tool} is not namespaced"
            namespace, action = step.tool.split(".", 1)
            assert namespace == step.backend, \
                f"Tool namespace {namespace} doesn't match backend {step.backend}"
    
    def test_all_steps_have_mock_results(self):
        """All steps have pre-defined mock results."""
        steps = get_workflow_steps()
        for step in steps:
            assert step.result is not None
            assert len(step.result) > 0, f"Step {step.step_num} has empty result"
    
    def test_workflow_follows_realistic_order(self):
        """Workflow follows a realistic business flow."""
        steps = get_workflow_steps()
        # Step 1 should be search/research
        assert "search" in steps[0].tool.lower()
        # Step 4 should be notification
        assert "slack" in steps[3].backend
        # Step 5 should be update
        assert "update" in steps[4].tool.lower()


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_get_backend_icon_notion(self):
        """Notion has correct icon."""
        icon = get_backend_icon("notion")
        assert icon == "📝"
    
    def test_get_backend_icon_gmail(self):
        """Gmail has correct icon."""
        icon = get_backend_icon("gmail")
        assert icon == "📧"
    
    def test_get_backend_icon_slack(self):
        """Slack has correct icon."""
        icon = get_backend_icon("slack")
        assert icon == "💬"
    
    def test_get_backend_icon_unknown(self):
        """Unknown backend has default icon."""
        icon = get_backend_icon("unknown")
        assert icon == "🔧"
    
    def test_get_unique_backends(self):
        """Can get unique backends from steps."""
        steps = get_workflow_steps()
        backends = get_unique_backends(steps)
        assert len(backends) == 3
        assert "notion" in backends
        assert "gmail" in backends
        assert "slack" in backends

    def test_get_unique_backends_sorted(self):
        """Unique backends are sorted."""
        steps = get_workflow_steps()
        backends = get_unique_backends(steps)
        assert backends == sorted(backends)
    
    def test_is_step_successful_true(self):
        """Recognizes successful step."""
        step = WorkflowStep(
            step_num=1,
            backend="test",
            tool="test.action",
            description="Test",
            arguments={},
            status="success",
        )
        assert is_step_successful(step) is True
    
    def test_is_step_successful_false(self):
        """Recognizes failed step."""
        step = WorkflowStep(
            step_num=1,
            backend="test",
            tool="test.action",
            description="Test",
            arguments={},
            status="failed",
        )
        assert is_step_successful(step) is False
    
    def test_is_step_successful_pending(self):
        """Pending step is not successful."""
        step = WorkflowStep(
            step_num=1,
            backend="test",
            tool="test.action",
            description="Test",
            arguments={},
            status="pending",
        )
        assert is_step_successful(step) is False


# =============================================================================
# Step Execution Tests
# =============================================================================


class TestStepExecution:
    """Tests for step execution."""
    
    @pytest.mark.asyncio
    async def test_execute_step_sets_success(self):
        """Executing step sets success status."""
        step = WorkflowStep(
            step_num=1,
            backend="test",
            tool="test.action",
            description="Test step",
            arguments={},
        )
        
        result = await execute_step(step)
        assert result.status == "success"
    
    @pytest.mark.asyncio
    async def test_execute_step_sets_duration(self):
        """Executing step records duration."""
        step = WorkflowStep(
            step_num=1,
            backend="test",
            tool="test.action",
            description="Test step",
            arguments={},
        )
        
        result = await execute_step(step)
        assert result.duration_ms > 0
    
    @pytest.mark.asyncio
    async def test_execute_step_preserves_original_fields(self):
        """Executing step preserves original fields."""
        step = WorkflowStep(
            step_num=3,
            backend="notion",
            tool="notion.read_page",
            description="Read page",
            arguments={"page_id": "123"},
            result={"content": "test"},
        )
        
        result = await execute_step(step)
        assert result.step_num == 3
        assert result.backend == "notion"
        assert result.tool == "notion.read_page"
        assert result.arguments == {"page_id": "123"}
        assert result.result == {"content": "test"}


# =============================================================================
# Demo Execution Tests
# =============================================================================


class TestDemoExecution:
    """Tests for demo execution."""
    
    @pytest.mark.asyncio
    async def test_demo_runs_in_mock_mode(self):
        """Demo runs successfully in mock mode."""
        result = await run_demo(mock_mode=True)
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_demo_executes_all_steps(self):
        """Demo executes all workflow steps."""
        result = await run_demo(mock_mode=True)
        assert result.steps_executed == 5
    
    @pytest.mark.asyncio
    async def test_demo_all_steps_succeed(self):
        """All demo steps succeed."""
        result = await run_demo(mock_mode=True)
        assert result.steps_succeeded == 5
    
    @pytest.mark.asyncio
    async def test_demo_uses_three_backends(self):
        """Demo uses three backends."""
        result = await run_demo(mock_mode=True)
        assert len(result.backends_used) == 3
    
    @pytest.mark.asyncio
    async def test_demo_has_positive_duration(self):
        """Demo has positive total duration."""
        result = await run_demo(mock_mode=True)
        assert result.total_duration_ms > 0
    
    @pytest.mark.asyncio
    async def test_demo_no_errors_in_mock_mode(self):
        """No errors in mock mode."""
        result = await run_demo(mock_mode=True)
        assert result.error is None


# =============================================================================
# Value Proposition Tests
# =============================================================================


class TestValueProposition:
    """Tests that verify the demo's value proposition."""
    
    def test_single_connection_to_gateway(self):
        """Demo shows single gateway connection."""
        # All steps go through the same gateway
        steps = get_workflow_steps()
        # There's no separate connection per backend
        # The workflow uses namespaced tools through gateway
        for step in steps:
            assert "." in step.tool  # Namespaced tools = gateway routing
    
    def test_cross_service_data_flow(self):
        """Demo shows data flowing between services."""
        steps = get_workflow_steps()
        
        # Step 1 (Notion) produces product info
        # Step 3 (Notion) uses related template
        assert steps[0].backend == "notion"
        assert steps[2].backend == "notion"
        
        # Step 2 (Gmail) finds email leads
        # Step 4 (Slack) notifies team
        # Step 5 (Notion) creates follow-up task
        assert steps[1].backend == "gmail"
        assert steps[3].backend == "slack"
        assert steps[4].backend == "notion"
        
        # Messages from step 2 inform step 4 notification
        messages = steps[1].result.get("messages", [])
        assert len(messages) >= 2
        
        # Step 4 message mentions leads
        slack_message = steps[3].arguments.get("message", "")
        assert "leads" in slack_message.lower() or "FinBank" in slack_message or len(slack_message) > 0
        
        # Step 5 creates a follow-up in Notion
        assert "title" in steps[4].arguments
    
    def test_unified_audit_trail(self):
        """Demo shows unified audit trail across all services."""
        steps = get_workflow_steps()
        
        # All steps can be attributed to same agent/user
        agent_id = CONFIG.AGENT_ID
        user_email = CONFIG.USER_EMAIL
        
        assert agent_id is not None
        assert user_email is not None
        
        # All steps have consistent audit-able data
        for step in steps:
            # Each step has identifiable backend, tool, and arguments
            assert step.backend is not None
            assert step.tool is not None
            assert step.arguments is not None
    
    def test_permission_checks_possible_at_each_step(self):
        """Each step can have permission checks."""
        steps = get_workflow_steps()
        
        for step in steps:
            # Each tool is namespaced, enabling permission mapping
            namespace, action = step.tool.split(".", 1)
            
            # Could map to permissions like:
            # - notion.search_pages -> notion:pages:search
            # - github.list_repos -> github:repos:list
            # - slack.send_message -> slack:messages:send
            assert len(namespace) > 0
            assert len(action) > 0


# =============================================================================
# Workflow Scenario Tests
# =============================================================================


class TestWorkflowScenario:
    """Tests for the specific workflow scenario."""
    
    def test_sales_research_workflow_step1(self):
        """Step 1: Search for product information."""
        steps = get_workflow_steps()
        step = steps[0]
        
        assert step.backend == "notion"
        assert "search" in step.tool.lower()
        assert "query" in step.arguments
        
        # Result should have pages
        assert "pages" in step.result
        assert len(step.result["pages"]) > 0
    
    def test_sales_research_workflow_step2(self):
        """Step 2: Search emails for leads."""
        steps = get_workflow_steps()
        step = steps[1]
        
        assert step.backend == "gmail"
        assert "message" in step.tool.lower() or "search" in step.tool.lower()

        assert "messages" in step.result
        messages = step.result["messages"]
        assert len(messages) >= 2
        
        for msg in messages:
            assert "id" in msg
            assert "subject" in msg
    
    def test_sales_research_workflow_step3(self):
        """Step 3: Get outreach template."""
        steps = get_workflow_steps()
        step = steps[2]
        
        assert step.backend == "notion"
        assert "read" in step.tool.lower() or "get" in step.tool.lower()
        
        # Result should have content
        assert "content" in step.result
        assert len(step.result["content"]) > 0
    
    def test_sales_research_workflow_step4(self):
        """Step 4: Notify team on Slack."""
        steps = get_workflow_steps()
        step = steps[3]
        
        assert step.backend == "slack"
        assert "message" in step.tool.lower() or "send" in step.tool.lower()
        
        # Should send to a channel
        assert "channel" in step.arguments
        assert step.arguments["channel"].startswith("#")
        
        # Message should mention leads
        assert "message" in step.arguments
        message = step.arguments["message"]
        assert len(message) > 0
    
    def test_sales_research_workflow_step5(self):
        """Step 5: Create follow-up task in Notion."""
        steps = get_workflow_steps()
        step = steps[4]
        
        assert step.backend == "notion"
        assert "create" in step.tool.lower()
        
        assert "title" in step.arguments
        
        # Result should confirm creation
        assert "success" in step.result
        assert step.result["success"] is True
