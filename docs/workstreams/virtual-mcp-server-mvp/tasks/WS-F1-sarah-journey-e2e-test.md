# Task: WS-F1 Create Sarah's Journey E2E Test

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `pending` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-F: Integration & Demos |
| **Dependencies** | All core tasks (A-E workstreams) |
| **Blocked By** | E3 (Audit middleware) - final component |
| **Assigned** | - |
| **Created** | February 5, 2026 |
| **Estimated Complexity** | `L` (4+ hours) |
| **Batch** | 7 |
| **Target Worktree** | Both (`vmcp-control` and `vmcp-gateway`) |

---

## Validation Mapping

| Validates | Reference |
|-----------|-----------|
| **Design Doc Section 2** | Sarah's Journey: Phase 1 (Notion + Slack) |
| **All 10 Steps** | Steps 1-10 from design doc fully automated |
| **Demo 1-5** | All demos validated as part of journey |
| **MP4 Requirement** | E2E test required before final merge |

---

## Pre-Conditions

Before starting this task, ensure all core components are complete:

**Control Plane (vmcp-control):**
- [x] A4 (OAuth token vault storage)
- [x] A5 (User session with connected services)
- [x] A6 (Delegation service)
- [x] A7 (Agent session service)
- [x] A8 (Challenge-response authentication)
- [x] E1 (Audit event model)
- [ ] E2 (Audit logger service) ← Pending

**Gateway (vmcp-gateway):**
- [x] B3 (MCP transport)
- [x] B6 (tools/list handler)
- [x] B7 (tools/call handler)
- [x] B8 (Session state manager)
- [x] C1 (Agent authentication endpoint)
- [x] C3 (JWT validation middleware)
- [x] C5 (Permission filter)
- [x] C6 (Delegation validator)
- [x] C7 (Credential injection)
- [x] D1 (Backend manager)
- [x] D3-D5 (Backend clients)
- [x] D6 (Backend router)
- [ ] E3 (Audit middleware) ← Pending

---

## Task Description

Create a comprehensive **End-to-End test** that automates all 10 steps of Sarah's Journey as defined in the design document. This test validates the complete system integration from user authentication through agent task execution to audit trail review.

### Context

Sarah's Journey represents the complete user experience:
1. Enterprise setup (simplified for MVP)
2. **Sarah authenticates** to DeepTrail console
3. **Sarah connects** Notion and Slack via OAuth
4. **Sarah delegates** permissions to her AI assistant
5. **Agent authenticates** using challenge-response
6. **Agent connects** to the Virtual MCP Server
7. **Agent discovers tools** via filtered `tools/list`
8. **Agent executes tool** with credential injection
9. **Agent is denied** on non-delegated tool
10. **Sarah reviews** the audit trail

This test is the **ultimate validation** of the MVP - if this passes, the system works.

### The 10 Steps in Detail

#### Step 1: Enterprise Registration (Simplified for MVP)
```
Organization "Acme Corp" is pre-configured in the system.
Agent "SDR-Assistant" (agent-sdr-001) is registered.
Sarah (sarah@acme.com) is a user in the organization.
```

#### Step 2: Sarah Authenticates
```python
# Sarah logs into DeepTrail console
response = await control_plane.post("/api/v1/auth/login", json={
    "email": "sarah@acme.com",
    "password": "secure_password"
})
user_token = response.json()["token"]
```

#### Step 3: Sarah Connects Notion & Slack
```python
# Sarah connects Notion via OAuth (simulated)
await control_plane.post("/api/v1/users/sarah/services/connect", 
    headers={"Authorization": f"Bearer {user_token}"},
    json={"service_id": "notion", "oauth_token": {...}}
)

# Sarah connects Slack via OAuth (simulated)
await control_plane.post("/api/v1/users/sarah/services/connect",
    headers={"Authorization": f"Bearer {user_token}"},
    json={"service_id": "slack", "oauth_token": {...}}
)
```

#### Step 4: Sarah Delegates to Agent
```python
# Sarah grants limited permissions to SDR-Assistant
delegation = await control_plane.post("/api/v1/delegations",
    headers={"Authorization": f"Bearer {user_token}"},
    json={
        "agent_id": "agent-sdr-001",
        "permissions": [
            "notion:pages:search",
            "notion:pages:read",
            "slack:messages:search",
            "slack:channels:list"
        ],
        "constraints": {"rate_limit": 100}
    }
)
delegation_token = delegation.json()["delegation_token"]
```

#### Step 5: Agent Authenticates
```python
# Agent requests challenge
challenge = await control_plane.post("/api/v1/agents/challenge",
    json={"agent_id": "agent-sdr-001"}
)

# Agent signs challenge with private key
signature = agent_private_key.sign(challenge.json()["challenge"])

# Agent verifies and receives JWT
auth_result = await control_plane.post("/api/v1/agents/verify",
    json={
        "agent_id": "agent-sdr-001",
        "challenge": challenge.json()["challenge"],
        "signature": signature.hex(),
        "delegation_token": delegation_token
    }
)
agent_jwt = auth_result.json()["jwt"]
```

#### Step 6: Agent Connects to Gateway
```python
# Agent sends MCP initialize to Gateway
init_response = await gateway.post("/mcp",
    headers={"Authorization": f"Bearer {agent_jwt}"},
    json={
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1,
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "SDR-Assistant", "version": "1.0"}
        }
    }
)
assert init_response.json()["result"]["protocolVersion"] == "2024-11-05"
```

#### Step 7: Agent Discovers Tools
```python
# Agent lists available tools
tools_response = await gateway.post("/mcp",
    headers={"Authorization": f"Bearer {agent_jwt}"},
    json={"jsonrpc": "2.0", "method": "tools/list", "id": 2, "params": {}}
)

tools = tools_response.json()["result"]["tools"]
tool_names = [t["name"] for t in tools]

# Verify filtering worked
assert "notion.search_pages" in tool_names  # ✓ Delegated
assert "notion.read_page" in tool_names     # ✓ Delegated
assert "slack.search_messages" in tool_names # ✓ Delegated
assert "notion.create_page" not in tool_names  # ✗ Not delegated
```

#### Step 8: Agent Executes Tool
```python
# Agent calls a delegated tool
call_response = await gateway.post("/mcp",
    headers={"Authorization": f"Bearer {agent_jwt}"},
    json={
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": 3,
        "params": {
            "name": "notion.search_pages",
            "arguments": {"query": "project updates"}
        }
    }
)

result = call_response.json()["result"]
assert "isError" not in result or result["isError"] == False
assert "content" in result
```

#### Step 9: Agent Denied
```python
# Agent tries to call a non-delegated tool
denied_response = await gateway.post("/mcp",
    headers={"Authorization": f"Bearer {agent_jwt}"},
    json={
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": 4,
        "params": {
            "name": "notion.create_page",  # Not delegated!
            "arguments": {"title": "New Page"}
        }
    }
)

error = denied_response.json()["error"]
assert error["code"] == -32001  # Permission denied
assert "not delegated" in error["message"].lower()
```

#### Step 10: Sarah Reviews Audit
```python
# Sarah queries audit trail
audit_response = await control_plane.get("/api/v1/audit/events",
    headers={"Authorization": f"Bearer {user_token}"},
    params={"agent_id": "agent-sdr-001", "limit": 10}
)

events = audit_response.json()["events"]

# Verify all actions were logged
assert len(events) >= 2  # At least: success + denial

# Find the successful call
success_event = next(e for e in events if e["tool"] == "notion.search_pages")
assert success_event["on_behalf_of"] == "sarah@acme.com"

# Find the denied call
denied_event = next(e for e in events if e["tool"] == "notion.create_page")
assert denied_event["event_type"] == "permission_denied"
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `tests/e2e/test_sarah_journey.py` | **CREATE** | Main E2E test |
| `tests/e2e/__init__.py` | **CREATE** | Package init |
| `tests/e2e/conftest.py` | **CREATE** | Fixtures for E2E tests |
| `tests/e2e/test_fixtures.py` | **CREATE** | Test data (Sarah, Agent, etc.) |
| `pytest.ini` | **MODIFY** | Add e2e marker |

---

## Implementation Details

### 1. Test File Structure

```
tests/
├── e2e/
│   ├── __init__.py
│   ├── conftest.py           # Shared fixtures
│   ├── test_fixtures.py      # Test data definitions
│   └── test_sarah_journey.py # Main journey test
```

### 2. Main Test File

```python
"""
Sarah's Journey E2E Test - WS-F1

Validates the complete user journey from the design document:
- Section 2: Sarah's Journey: Phase 1 (Notion + Slack)
- Steps 1-10 fully automated

This is the ultimate MVP validation test. If this passes, the system works.

Usage:
    pytest tests/e2e/test_sarah_journey.py -v --tb=short
    
    # With container services running:
    docker compose up -d
    pytest tests/e2e/test_sarah_journey.py -v
"""

import pytest
import httpx
from nacl.signing import SigningKey
from nacl.encoding import HexEncoder


@pytest.mark.e2e
@pytest.mark.asyncio
class TestSarahJourney:
    """
    Complete E2E test validating all 10 steps of Sarah's Journey.
    
    Requires:
    - Control Plane running at CONTROL_PLANE_URL
    - Gateway running at GATEWAY_URL
    - Database seeded with test organization
    """
    
    # =========================================================================
    # Step 1: Enterprise Registration (Setup Fixtures)
    # =========================================================================
    
    @pytest.fixture
    async def organization(self, control_plane_client):
        """Step 1: Enterprise is pre-registered."""
        # MVP: Use pre-seeded organization
        return {
            "id": "org-acme-001",
            "name": "Acme Corp",
            "idp": "https://acme.okta.com"
        }
    
    @pytest.fixture
    def agent_keypair(self):
        """Agent's Ed25519 keypair for authentication."""
        private_key = SigningKey.generate()
        public_key = private_key.verify_key
        return {
            "private_key": private_key,
            "public_key": public_key,
            "public_key_hex": public_key.encode(encoder=HexEncoder).decode()
        }
    
    # =========================================================================
    # Step 2: Sarah Authenticates
    # =========================================================================
    
    async def test_step_02_sarah_authenticates(
        self, control_plane_client, organization
    ):
        """Step 2: Sarah logs into DeepTrail console."""
        response = await control_plane_client.post(
            "/api/v1/auth/login",
            json={
                "email": "sarah@acme.com",
                "password": "secure_password",
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "sarah@acme.com"
        
        return data["token"]
    
    # =========================================================================
    # Step 3: Sarah Connects Services
    # =========================================================================
    
    async def test_step_03_sarah_connects_services(
        self, control_plane_client, user_token
    ):
        """Step 3: Sarah connects Notion and Slack via OAuth."""
        # Connect Notion
        notion_response = await control_plane_client.post(
            "/api/v1/users/me/services/connect",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "service_id": "notion",
                "oauth_token": {
                    "access_token": "test_notion_token",
                    "token_type": "bearer",
                    "scope": "read_pages search_content"
                }
            }
        )
        assert notion_response.status_code == 200
        
        # Connect Slack
        slack_response = await control_plane_client.post(
            "/api/v1/users/me/services/connect",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "service_id": "slack",
                "oauth_token": {
                    "access_token": "test_slack_token",
                    "token_type": "bearer",
                    "scope": "search:read channels:read"
                }
            }
        )
        assert slack_response.status_code == 200
        
        # Verify both connected
        services = await control_plane_client.get(
            "/api/v1/users/me/services",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        connected = [s["service_id"] for s in services.json()["services"]]
        assert "notion" in connected
        assert "slack" in connected
    
    # =========================================================================
    # Step 4: Sarah Delegates to Agent
    # =========================================================================
    
    async def test_step_04_sarah_delegates_to_agent(
        self, control_plane_client, user_token, agent_keypair
    ):
        """Step 4: Sarah grants limited permissions to SDR-Assistant."""
        # First, register agent with public key
        register_response = await control_plane_client.post(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "agent_id": "agent-sdr-001",
                "name": "SDR-Assistant",
                "public_key": agent_keypair["public_key_hex"]
            }
        )
        assert register_response.status_code in [200, 201]
        
        # Create delegation
        delegation_response = await control_plane_client.post(
            "/api/v1/delegations",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "agent_id": "agent-sdr-001",
                "permissions": [
                    "notion:pages:search",
                    "notion:pages:read",
                    "slack:messages:search",
                    "slack:channels:list"
                ],
                "constraints": {
                    "rate_limit": 100,
                    "expires_in_hours": 8
                }
            }
        )
        assert delegation_response.status_code == 200
        
        data = delegation_response.json()
        assert "delegation_token" in data
        
        # Verify monotonic attenuation
        delegated = data["permissions"]
        assert "notion:pages:search" in delegated
        assert "notion:pages:create" not in delegated  # Not granted
        
        return data["delegation_token"]
    
    # =========================================================================
    # Step 5: Agent Authenticates
    # =========================================================================
    
    async def test_step_05_agent_authenticates(
        self, control_plane_client, delegation_token, agent_keypair
    ):
        """Step 5: Agent authenticates via challenge-response."""
        # Request challenge
        challenge_response = await control_plane_client.post(
            "/api/v1/agents/challenge",
            json={"agent_id": "agent-sdr-001"}
        )
        assert challenge_response.status_code == 200
        challenge = challenge_response.json()["challenge"]
        
        # Sign challenge with private key
        signature = agent_keypair["private_key"].sign(
            challenge.encode(),
            encoder=HexEncoder
        ).signature
        
        # Verify and get JWT
        verify_response = await control_plane_client.post(
            "/api/v1/agents/verify",
            json={
                "agent_id": "agent-sdr-001",
                "challenge": challenge,
                "signature": signature.decode(),
                "delegation_token": delegation_token
            }
        )
        assert verify_response.status_code == 200
        
        data = verify_response.json()
        assert "jwt" in data
        
        # JWT should contain delegation info
        # (We can decode and verify claims in a more detailed test)
        
        return data["jwt"]
    
    # =========================================================================
    # Step 6: Agent Connects to Gateway
    # =========================================================================
    
    async def test_step_06_agent_connects_to_gateway(
        self, gateway_client, agent_jwt
    ):
        """Step 6: Agent initializes MCP session with Gateway."""
        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "SDR-Assistant",
                        "version": "1.0"
                    }
                }
            }
        )
        
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["protocolVersion"] == "2024-11-05"
        assert "serverInfo" in result
    
    # =========================================================================
    # Step 7: Agent Discovers Tools
    # =========================================================================
    
    async def test_step_07_agent_discovers_filtered_tools(
        self, gateway_client, agent_jwt
    ):
        """Step 7: Agent sees only delegated tools."""
        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 2,
                "params": {}
            }
        )
        
        assert response.status_code == 200
        tools = response.json()["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        
        # Delegated tools should be visible
        assert "notion.search_pages" in tool_names
        assert "notion.read_page" in tool_names
        assert "slack.search_messages" in tool_names
        assert "slack.list_channels" in tool_names
        
        # Non-delegated tools should be hidden
        assert "notion.create_page" not in tool_names
        assert "slack.post_message" not in tool_names
        
        # This is the core value prop: Agent sees 4 tools, not 20+
        assert len(tools) <= 10, "Too many tools visible - filtering not working"
    
    # =========================================================================
    # Step 8: Agent Executes Tool
    # =========================================================================
    
    async def test_step_08_agent_executes_tool(
        self, gateway_client, agent_jwt
    ):
        """Step 8: Agent successfully calls a delegated tool."""
        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 3,
                "params": {
                    "name": "notion.search_pages",
                    "arguments": {"query": "project updates"}
                }
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Should have result, not error
        assert "result" in result
        assert "error" not in result
        
        # Result should have MCP content format
        assert "content" in result["result"]
        
        # Agent should NOT see credentials in response
        response_text = str(result)
        assert "access_token" not in response_text.lower()
        assert "oauth" not in response_text.lower()
        assert "bearer" not in response_text.lower()
    
    # =========================================================================
    # Step 9: Agent Denied
    # =========================================================================
    
    async def test_step_09_agent_denied_non_delegated_tool(
        self, gateway_client, agent_jwt
    ):
        """Step 9: Agent is denied when calling non-delegated tool."""
        response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 4,
                "params": {
                    "name": "notion.create_page",  # Not delegated!
                    "arguments": {"title": "New Page"}
                }
            }
        )
        
        assert response.status_code == 200  # JSON-RPC returns 200 with error
        result = response.json()
        
        # Should have error response
        assert "error" in result
        error = result["error"]
        
        # Verify permission denied
        assert error["code"] == -32001  # Permission denied code
        assert "permission" in error["message"].lower() or "denied" in error["message"].lower()
    
    # =========================================================================
    # Step 10: Sarah Reviews Audit
    # =========================================================================
    
    async def test_step_10_sarah_reviews_audit(
        self, control_plane_client, user_token
    ):
        """Step 10: Sarah can see all agent actions in audit trail."""
        response = await control_plane_client.get(
            "/api/v1/audit/events",
            headers={"Authorization": f"Bearer {user_token}"},
            params={
                "agent_id": "agent-sdr-001",
                "limit": 20
            }
        )
        
        assert response.status_code == 200
        events = response.json()["events"]
        
        # Should have at least 2 events (success + denial)
        assert len(events) >= 2
        
        # Find the successful call
        success_events = [e for e in events if e["tool"] == "notion.search_pages"]
        assert len(success_events) >= 1
        success_event = success_events[0]
        assert success_event["on_behalf_of"] == "sarah@acme.com"
        assert success_event["agent_id"] == "agent-sdr-001"
        
        # Find the denied call
        denied_events = [e for e in events if e["event_type"] == "permission_denied"]
        assert len(denied_events) >= 1
        denied_event = denied_events[0]
        assert denied_event["tool"] == "notion.create_page"
        
        # Verify audit has timestamps
        for event in events:
            assert "timestamp" in event
    
    # =========================================================================
    # Complete Journey Test (All Steps in Sequence)
    # =========================================================================
    
    @pytest.mark.slow
    async def test_complete_journey(
        self,
        control_plane_client,
        gateway_client,
        agent_keypair,
    ):
        """
        Complete E2E test running all 10 steps in sequence.
        
        This is the ultimate MVP validation test.
        """
        # Step 2: Sarah authenticates
        auth_response = await control_plane_client.post(
            "/api/v1/auth/login",
            json={"email": "sarah@acme.com", "password": "secure_password"}
        )
        assert auth_response.status_code == 200
        user_token = auth_response.json()["token"]
        
        # Step 3: Sarah connects services
        for service in ["notion", "slack"]:
            connect_response = await control_plane_client.post(
                "/api/v1/users/me/services/connect",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "service_id": service,
                    "oauth_token": {"access_token": f"test_{service}_token"}
                }
            )
            assert connect_response.status_code == 200
        
        # Step 4: Sarah delegates
        register_response = await control_plane_client.post(
            "/api/v1/agents",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "agent_id": "agent-sdr-001",
                "name": "SDR-Assistant",
                "public_key": agent_keypair["public_key_hex"]
            }
        )
        
        delegation_response = await control_plane_client.post(
            "/api/v1/delegations",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "agent_id": "agent-sdr-001",
                "permissions": [
                    "notion:pages:search", "notion:pages:read",
                    "slack:messages:search", "slack:channels:list"
                ]
            }
        )
        assert delegation_response.status_code == 200
        delegation_token = delegation_response.json()["delegation_token"]
        
        # Step 5: Agent authenticates
        challenge_response = await control_plane_client.post(
            "/api/v1/agents/challenge",
            json={"agent_id": "agent-sdr-001"}
        )
        challenge = challenge_response.json()["challenge"]
        signature = agent_keypair["private_key"].sign(
            challenge.encode(), encoder=HexEncoder
        ).signature
        
        verify_response = await control_plane_client.post(
            "/api/v1/agents/verify",
            json={
                "agent_id": "agent-sdr-001",
                "challenge": challenge,
                "signature": signature.decode(),
                "delegation_token": delegation_token
            }
        )
        assert verify_response.status_code == 200
        agent_jwt = verify_response.json()["jwt"]
        
        # Step 6: Agent connects to Gateway
        init_response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json={
                "jsonrpc": "2.0", "method": "initialize", "id": 1,
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                          "clientInfo": {"name": "SDR-Assistant", "version": "1.0"}}
            }
        )
        assert init_response.status_code == 200
        
        # Step 7: Agent discovers filtered tools
        tools_response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 2, "params": {}}
        )
        tools = tools_response.json()["result"]["tools"]
        assert len(tools) <= 10  # Filtered!
        
        # Step 8: Agent executes tool
        call_response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json={
                "jsonrpc": "2.0", "method": "tools/call", "id": 3,
                "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
            }
        )
        assert "result" in call_response.json()
        
        # Step 9: Agent denied
        denied_response = await gateway_client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {agent_jwt}"},
            json={
                "jsonrpc": "2.0", "method": "tools/call", "id": 4,
                "params": {"name": "notion.create_page", "arguments": {"title": "X"}}
            }
        )
        assert "error" in denied_response.json()
        
        # Step 10: Sarah reviews audit
        audit_response = await control_plane_client.get(
            "/api/v1/audit/events",
            headers={"Authorization": f"Bearer {user_token}"},
            params={"agent_id": "agent-sdr-001"}
        )
        events = audit_response.json()["events"]
        assert len(events) >= 2  # Success + denial logged
        
        print("✅ Sarah's Journey Complete - All 10 Steps Passed!")
```

### 3. Test Fixtures (conftest.py)

```python
"""
E2E Test Fixtures - Shared setup for end-to-end tests.
"""

import os
import pytest
import httpx


@pytest.fixture(scope="session")
def control_plane_url():
    """Control Plane URL from environment or default."""
    return os.getenv("DEEPSECURE_CONTROL_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def gateway_url():
    """Gateway URL from environment or default."""
    return os.getenv("DEEPSECURE_GATEWAY_URL", "http://localhost:8002")


@pytest.fixture
async def control_plane_client(control_plane_url):
    """Async HTTP client for Control Plane."""
    async with httpx.AsyncClient(base_url=control_plane_url) as client:
        yield client


@pytest.fixture
async def gateway_client(gateway_url):
    """Async HTTP client for Gateway."""
    async with httpx.AsyncClient(base_url=gateway_url) as client:
        yield client


@pytest.fixture
async def user_token(control_plane_client):
    """Get Sarah's user token (Step 2)."""
    response = await control_plane_client.post(
        "/api/v1/auth/login",
        json={"email": "sarah@acme.com", "password": "secure_password"}
    )
    return response.json()["token"]


@pytest.fixture
async def agent_jwt(control_plane_client, user_token, agent_keypair):
    """Get agent JWT (Steps 4-5 combined)."""
    from nacl.encoding import HexEncoder
    
    # Register and delegate (simplified)
    await control_plane_client.post(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "agent_id": "agent-sdr-001",
            "public_key": agent_keypair["public_key_hex"]
        }
    )
    
    delegation = await control_plane_client.post(
        "/api/v1/delegations",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "agent_id": "agent-sdr-001",
            "permissions": ["notion:pages:search", "notion:pages:read"]
        }
    )
    delegation_token = delegation.json()["delegation_token"]
    
    # Challenge-response auth
    challenge = await control_plane_client.post(
        "/api/v1/agents/challenge",
        json={"agent_id": "agent-sdr-001"}
    )
    signature = agent_keypair["private_key"].sign(
        challenge.json()["challenge"].encode(),
        encoder=HexEncoder
    ).signature
    
    verify = await control_plane_client.post(
        "/api/v1/agents/verify",
        json={
            "agent_id": "agent-sdr-001",
            "challenge": challenge.json()["challenge"],
            "signature": signature.decode(),
            "delegation_token": delegation_token
        }
    )
    return verify.json()["jwt"]
```

---

## Acceptance Criteria

### Journey Completeness
- [ ] All 10 steps automated and passing
- [ ] Each step has individual test method
- [ ] Complete journey runs end-to-end

### Step Validations
- [ ] **Step 2**: Sarah can authenticate
- [ ] **Step 3**: OAuth tokens stored correctly
- [ ] **Step 4**: Delegation created with correct permissions
- [ ] **Step 5**: Agent gets JWT via challenge-response
- [ ] **Step 6**: MCP session established
- [ ] **Step 7**: Only delegated tools visible
- [ ] **Step 8**: Tool call succeeds with credential injection
- [ ] **Step 9**: Non-delegated tool denied
- [ ] **Step 10**: Audit trail contains all events

### Security Validations
- [ ] Agent never sees OAuth tokens
- [ ] Permission filtering works correctly
- [ ] Audit has full attribution

### Demo Coverage
- [ ] Demo 1 (Unified Connection): Validated in Step 6
- [ ] Demo 2 (Filtered Visibility): Validated in Step 7
- [ ] Demo 3 (Delegation Execution): Validated in Step 8
- [ ] Demo 4 (Permission Enforcement): Validated in Step 9
- [ ] Demo 5 (Unified Audit): Validated in Step 10

---

## Test Cases

### Individual Step Tests
```bash
# Run all E2E tests
pytest tests/e2e/ -v

# Run just the complete journey
pytest tests/e2e/test_sarah_journey.py::TestSarahJourney::test_complete_journey -v

# Run individual steps
pytest tests/e2e/test_sarah_journey.py -k "step_07" -v
```

### Container Integration
```bash
# Start services
docker compose up -d db redis deeptrail-control deeptrail-gateway

# Wait for health
sleep 15

# Run E2E tests
pytest tests/e2e/test_sarah_journey.py -v --tb=short

# Cleanup
docker compose down
```

---

## Post-Conditions

After completing this task:

1. All 10 steps of Sarah's Journey are automated
2. MVP is fully validated end-to-end
3. MP4 requirements satisfied
4. System ready for demo

---

## Unblocks

| Task | Name | Notes |
|------|------|-------|
| **F2** | Demo 1: Unified Connection | Can extract demo script from Step 6-7 |
| **F3** | Demo 2: Filtered Visibility | Can extract demo script from Step 7 |
| **F4** | Demo 3: Delegation Execution | Can extract demo script from Step 8 |
| **F5** | Demo 4: Permission Enforcement | Can extract demo script from Step 9 |
| **F6** | Demo 5: Unified Audit | Can extract demo script from Step 10 |
| **MP4** | Final Merge | E2E test is MP4 gate |

---

## References

- **Design Doc Section 2**: Sarah's Journey: Phase 1 (Notion + Slack)
- **MERGE_POINTS.md**: Container Test Scenario 1 (Sarah's Complete Journey)
- **All Workstream Completion Reports**: Context for what's implemented

---

## Notes

- This is a **Large (L)** task due to comprehensive scope
- Test requires both Control Plane and Gateway running
- Use mock backends (Notion, Slack) for deterministic results
- Consider adding retry logic for flaky container startup
- Future: Add Phase 2 journey with HubSpot
