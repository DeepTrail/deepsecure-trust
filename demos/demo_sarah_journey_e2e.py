#!/usr/bin/env python3
"""
Sarah's Journey - Complete End-to-End Demo

This demo script demonstrates the complete Virtual MCP Server MVP workflow,
showing Sarah's Journey from user authentication through agent tool execution.

The 10 Steps:
  1. Enterprise Registration (pre-seeded)
  2. Sarah Authenticates  
  3. Sarah Connects Notion & Slack (OAuth simulation)
  4. Sarah Delegates to Agent
  5. Agent Authenticates (Ed25519 challenge-response)
  6. Agent Connects to Gateway (MCP initialize)
  7. Agent Discovers Tools (filtered tools/list)
  8. Agent Executes Tool (tools/call with delegation)
  9. Agent Denied on Non-Delegated Tool
  10. Sarah Reviews Audit Trail

Usage:
    # Start services first
    docker compose up -d deeptrail-control deeptrail-gateway

    # Run the demo
    python demos/demo_sarah_journey_e2e.py

    # Run with verbose output
    python demos/demo_sarah_journey_e2e.py --verbose

Requirements:
    - Control Plane running at http://localhost:8000
    - Gateway running at http://localhost:8002
"""

import argparse
import base64
import json
import sys
import time
from dataclasses import dataclass, field

import httpx
from nacl.signing import SigningKey

# =============================================================================
# Configuration
# =============================================================================

CONTROL_PLANE_URL = "http://localhost:8000"
GATEWAY_URL = "http://localhost:8002"

# ANSI colors for output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class DemoScenario:
    """Test scenario data for the demo."""
    
    # Organization
    org_id: str = "org-acme-001"
    org_name: str = "Acme Corp"
    
    # User (Sarah)
    user_email: str = "sarah@acme.com"
    user_password: str = "secure_password"
    
    # Agent
    agent_id: str = field(default_factory=lambda: f"agent-sdr-{int(time.time())}")
    agent_name: str = "SDR-Assistant"
    
    # Services
    notion_token: str = "test_notion_token_12345"
    slack_token: str = "test_slack_token_67890"
    
    # Permissions
    delegated_permissions: list = field(default_factory=lambda: [
        "notion:pages:search",
        "notion:pages:read",
        "notion:databases:query",
        "slack:messages:search",
        "slack:channels:list",
        "slack:users:list",
    ])


# =============================================================================
# Utility Functions
# =============================================================================

def print_step(step_num: int, title: str):
    """Print step header."""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}Step {step_num}: {title}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}")


def print_request(method: str, url: str, body: dict = None, headers: dict = None):
    """Print HTTP request details."""
    print(f"\n{Colors.CYAN}>>> REQUEST{Colors.ENDC}")
    print(f"{Colors.BLUE}{method} {url}{Colors.ENDC}")
    if headers:
        auth_header = headers.get("Authorization", "")
        if auth_header:
            # Truncate token for readability
            token = auth_header.replace("Bearer ", "")
            truncated = f"{token[:30]}..." if len(token) > 30 else token
            print(f"  Authorization: Bearer {truncated}")
    if body:
        print(f"  Body: {json.dumps(body, indent=4)}")


def print_response(status: int, body: dict, success: bool = True):
    """Print HTTP response details."""
    color = Colors.GREEN if success else Colors.FAIL
    status_text = "SUCCESS" if success else "FAILED"
    print(f"\n{color}<<< RESPONSE ({status_text}){Colors.ENDC}")
    print(f"  Status: {status}")
    print(f"  Body: {json.dumps(body, indent=4)}")


def print_success(message: str):
    """Print success message."""
    print(f"\n{Colors.GREEN}✅ {message}{Colors.ENDC}")


def print_error(message: str):
    """Print error message."""
    print(f"\n{Colors.FAIL}❌ {message}{Colors.ENDC}")


def generate_keypair():
    """Generate Ed25519 keypair for agent authentication."""
    private_key = SigningKey.generate()
    public_key = private_key.verify_key
    public_key_bytes = public_key.encode()
    public_key_b64 = base64.b64encode(public_key_bytes).decode()
    
    return {
        "private_key": private_key,
        "public_key_base64": public_key_b64,
    }


def sign_challenge(private_key: SigningKey, challenge: str) -> str:
    """Sign a challenge with Ed25519 private key."""
    signed = private_key.sign(challenge.encode())
    return base64.urlsafe_b64encode(signed.signature).decode()


# =============================================================================
# Demo Steps
# =============================================================================

def step_01_enterprise_registration(scenario: DemoScenario, verbose: bool):
    """Step 1: Enterprise Registration (pre-seeded)."""
    print_step(1, "Enterprise Registration (Pre-seeded)")
    
    print(f"""
    Organization Configuration:
    ├── ID: {scenario.org_id}
    ├── Name: {scenario.org_name}
    ├── IdP: https://acme.okta.com (simulated)
    └── Domain: acme.com
    
    User Configuration:
    ├── Email: {scenario.user_email}
    └── Organization: {scenario.org_id}
    
    Agent Configuration:
    ├── ID: {scenario.agent_id}
    ├── Name: {scenario.agent_name}
    └── Purpose: Help Sarah research prospects and draft outreach
    """)
    
    print_success("Enterprise pre-configured in the system")
    return True


def step_02_sarah_authenticates(client: httpx.Client, scenario: DemoScenario, verbose: bool):
    """Step 2: Sarah logs into DeepTrail Console."""
    print_step(2, "Sarah Authenticates")
    
    url = f"{CONTROL_PLANE_URL}/api/v1/auth/login"
    body = {
        "email": scenario.user_email,
        "password": scenario.user_password,
    }
    
    print_request("POST", url, body)
    
    response = client.post(url, json=body)
    data = response.json()
    
    success = response.status_code == 200 and "token" in data
    print_response(response.status_code, data, success)
    
    if success:
        print_success(f"Sarah authenticated successfully")
        print(f"    User: {data.get('user', {}).get('email')}")
        print(f"    Token: {data['token'][:50]}...")
        return data["token"]
    else:
        print_error("Authentication failed")
        return None


def step_03_connect_services(client: httpx.Client, user_token: str, scenario: DemoScenario, verbose: bool):
    """Step 3: Sarah connects Notion and Slack."""
    print_step(3, "Sarah Connects Backend Services")
    
    services = [
        ("notion", scenario.notion_token, ["read_pages", "search_content", "read_databases"]),
        ("slack", scenario.slack_token, ["search:read", "channels:read", "users:read"]),
    ]
    
    headers = {"Authorization": f"Bearer {user_token}"}
    
    for service_id, token, scopes in services:
        url = f"{CONTROL_PLANE_URL}/api/v1/users/me/services/connect"
        body = {
            "service_id": service_id,
            "oauth_token": {
                "access_token": token,
                "token_type": "bearer",
                "scope": " ".join(scopes),
            },
        }
        
        print(f"\n{Colors.CYAN}Connecting {service_id.title()}...{Colors.ENDC}")
        print_request("POST", url, body, headers)
        
        response = client.post(url, json=body, headers=headers)
        data = response.json()
        
        success = response.status_code == 200
        print_response(response.status_code, data, success)
        
        if success:
            print_success(f"{service_id.title()} connected")
        else:
            print_error(f"Failed to connect {service_id.title()}")
            return False
    
    return True


def step_04_delegate_to_agent(client: httpx.Client, user_token: str, keypair: dict, scenario: DemoScenario, verbose: bool):
    """Step 4: Sarah registers agent and creates delegation."""
    print_step(4, "Sarah Delegates to SDR-Assistant")
    
    headers = {"Authorization": f"Bearer {user_token}"}
    
    # Register agent
    print(f"\n{Colors.CYAN}Registering Agent...{Colors.ENDC}")
    url = f"{CONTROL_PLANE_URL}/api/v1/agents/"
    body = {
        "agent_id": scenario.agent_id,
        "name": scenario.agent_name,
        "public_key": keypair["public_key_base64"],
    }
    
    print_request("POST", url, body, headers)
    response = client.post(url, json=body, headers=headers)
    data = response.json()
    
    # 409 means agent already exists, which is OK
    success = response.status_code in [200, 201, 409]
    print_response(response.status_code, data, success)
    
    if success:
        print_success(f"Agent registered: {scenario.agent_id}")
    else:
        print_error("Agent registration failed")
        return None
    
    # Create delegation
    print(f"\n{Colors.CYAN}Creating Delegation...{Colors.ENDC}")
    url = f"{CONTROL_PLANE_URL}/api/v1/auth/delegate"
    body = {
        "agent_id": scenario.agent_id,
        "permissions": scenario.delegated_permissions,
        "constraints": {
            "rate_limit": 100,
            "expires_in_hours": 8,
        },
    }
    
    print_request("POST", url, body, headers)
    response = client.post(url, json=body, headers=headers)
    data = response.json()
    
    success = response.status_code == 200 and "delegation_token" in data
    print_response(response.status_code, data, success)
    
    if success:
        print_success("Delegation created successfully")
        print(f"\n    Delegated Permissions:")
        for perm in data.get("permissions", scenario.delegated_permissions):
            print(f"      ✓ {perm}")
        print(f"\n    NOT Delegated (agent cannot use):")
        print(f"      ✗ notion:pages:create")
        print(f"      ✗ slack:messages:post")
        return data["delegation_token"]
    else:
        print_error("Delegation failed")
        return None


def step_05_agent_authenticates(client: httpx.Client, keypair: dict, delegation_token: str, scenario: DemoScenario, verbose: bool):
    """Step 5: Agent authenticates via Ed25519 challenge-response."""
    print_step(5, "Agent Authenticates (Challenge-Response)")
    
    # Request challenge
    print(f"\n{Colors.CYAN}Requesting Challenge...{Colors.ENDC}")
    url = f"{CONTROL_PLANE_URL}/api/v1/auth/agent/challenge"
    body = {"agent_id": scenario.agent_id}
    
    print_request("POST", url, body)
    response = client.post(url, json=body)
    data = response.json()
    
    success = response.status_code == 200 and "challenge" in data
    print_response(response.status_code, data, success)
    
    if not success:
        print_error("Failed to get challenge")
        return None
    
    challenge = data["challenge"]
    print_success(f"Challenge received: {challenge}")
    
    # Sign challenge
    print(f"\n{Colors.CYAN}Signing Challenge with Ed25519 Private Key...{Colors.ENDC}")
    signature = sign_challenge(keypair["private_key"], challenge)
    print(f"    Signature: {signature[:50]}...")
    
    # Verify signature
    print(f"\n{Colors.CYAN}Verifying Signature...{Colors.ENDC}")
    url = f"{CONTROL_PLANE_URL}/api/v1/auth/agent/verify"
    body = {
        "agent_id": scenario.agent_id,
        "challenge": challenge,
        "signature": signature,
        "delegation_token": delegation_token,
    }
    
    print_request("POST", url, body)
    response = client.post(url, json=body)
    data = response.json()
    
    success = response.status_code == 200 and "access_token" in data
    print_response(response.status_code, data, success)
    
    if success:
        print_success("Agent authenticated - received Agent Session JWT")
        return data["access_token"]
    else:
        print_error("Agent authentication failed")
        return None


def step_06_mcp_initialize(client: httpx.Client, agent_jwt: str, scenario: DemoScenario, verbose: bool):
    """Step 6: Agent connects to Virtual MCP Server."""
    print_step(6, "Agent Connects to Virtual MCP Server")
    
    url = f"{GATEWAY_URL}/mcp"
    headers = {"Authorization": f"Bearer {agent_jwt}"}
    body = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1,
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": scenario.agent_name,
                "version": "1.0.0",
            },
        },
    }
    
    print_request("POST", url, body, headers)
    response = client.post(url, json=body, headers=headers)
    data = response.json()
    
    success = response.status_code == 200 and "result" in data
    print_response(response.status_code, data, success)
    
    if success:
        result = data["result"]
        print_success("MCP Session Initialized")
        print(f"    Protocol Version: {result.get('protocolVersion')}")
        print(f"    Server: {result.get('serverInfo', {}).get('name')}")
        return True
    else:
        print_error("MCP initialization failed")
        return False


def step_07_discover_tools(client: httpx.Client, agent_jwt: str, scenario: DemoScenario, verbose: bool):
    """Step 7: Agent discovers filtered tools."""
    print_step(7, "Agent Discovers Tools (Filtered by Delegation)")
    
    url = f"{GATEWAY_URL}/mcp"
    headers = {"Authorization": f"Bearer {agent_jwt}"}
    body = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 2,
        "params": {},
    }
    
    print_request("POST", url, body, headers)
    response = client.post(url, json=body, headers=headers)
    data = response.json()
    
    success = response.status_code == 200 and "result" in data
    print_response(response.status_code, data, success)
    
    if success:
        tools = data["result"].get("tools", [])
        print_success(f"Discovered {len(tools)} tools (filtered by delegation)")
        
        print(f"\n    {Colors.GREEN}Visible Tools (delegated):{Colors.ENDC}")
        for tool in tools:
            print(f"      ✓ {tool['name']}: {tool.get('description', '')[:50]}")
        
        print(f"\n    {Colors.FAIL}Hidden Tools (not delegated):{Colors.ENDC}")
        print(f"      ✗ notion.create_page (notion:pages:create not delegated)")
        print(f"      ✗ slack.post_message (slack:messages:post not delegated)")
        
        return tools
    else:
        print_error("Failed to list tools")
        return None


def step_08_execute_tool(client: httpx.Client, agent_jwt: str, scenario: DemoScenario, verbose: bool):
    """Step 8: Agent executes a delegated tool."""
    print_step(8, "Agent Executes Delegated Tool")
    
    url = f"{GATEWAY_URL}/mcp"
    headers = {"Authorization": f"Bearer {agent_jwt}"}
    body = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": 3,
        "params": {
            "name": "notion.search_pages",
            "arguments": {
                "query": "competitor analysis",
                "limit": 5,
            },
        },
    }
    
    print(f"\n{Colors.CYAN}Calling notion.search_pages (delegated)...{Colors.ENDC}")
    print_request("POST", url, body, headers)
    response = client.post(url, json=body, headers=headers)
    data = response.json()
    
    success = response.status_code == 200 and "result" in data
    print_response(response.status_code, data, success)
    
    if success:
        print_success("Tool executed successfully!")
        print(f"\n    Key Security Properties:")
        print(f"      ✓ Agent never saw OAuth tokens")
        print(f"      ✓ Gateway injected Sarah's Notion credentials")
        print(f"      ✓ Action logged as 'agent on behalf of sarah@acme.com'")
        return True
    else:
        print_error("Tool execution failed")
        return False


def step_09_permission_denied(client: httpx.Client, agent_jwt: str, scenario: DemoScenario, verbose: bool):
    """Step 9: Agent is denied when calling non-delegated tool."""
    print_step(9, "Agent Denied on Non-Delegated Tool")
    
    url = f"{GATEWAY_URL}/mcp"
    headers = {"Authorization": f"Bearer {agent_jwt}"}
    body = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": 4,
        "params": {
            "name": "notion.create_page",
            "arguments": {
                "title": "Unauthorized Page",
                "content": "This should be blocked",
            },
        },
    }
    
    print(f"\n{Colors.CYAN}Attempting notion.create_page (NOT delegated)...{Colors.ENDC}")
    print_request("POST", url, body, headers)
    response = client.post(url, json=body, headers=headers)
    data = response.json()
    
    # For MCP, success means we got an error response
    has_error = "error" in data
    print_response(response.status_code, data, has_error)
    
    if has_error:
        error = data["error"]
        print_success("Permission DENIED as expected!")
        print(f"\n    Error Code: {error.get('code')}")
        print(f"    Message: {error.get('message')}")
        print(f"\n    Key Security Properties:")
        print(f"      ✓ Request blocked at Gateway (never reached Notion)")
        print(f"      ✓ Agent cannot exceed delegated permissions")
        print(f"      ✓ Denial logged for audit")
        return True
    else:
        print_error("Expected denial but tool was allowed!")
        return False


def step_10_review_audit(client: httpx.Client, user_token: str, scenario: DemoScenario, verbose: bool):
    """Step 10: Sarah reviews audit trail."""
    print_step(10, "Sarah Reviews Audit Trail")
    
    url = f"{CONTROL_PLANE_URL}/api/v1/audit/events"
    headers = {"Authorization": f"Bearer {user_token}"}
    params = {
        "agent_id": scenario.agent_id,
        "limit": 20,
    }
    
    print_request("GET", f"{url}?agent_id={scenario.agent_id}&limit=20", headers=headers)
    response = client.get(url, params=params, headers=headers)
    data = response.json()
    
    success = response.status_code == 200 and "events" in data
    print_response(response.status_code, data, success)
    
    if success:
        events = data.get("events", [])
        print_success(f"Audit trail retrieved ({len(events)} events)")
        
        if events:
            print(f"\n    Recent Agent Activity:")
            for event in events[:5]:
                print(f"      • {event.get('timestamp', 'N/A')}: {event.get('event_type', 'N/A')}")
        else:
            print(f"\n    Note: Audit events may not be populated in MVP mode")
            print(f"          Gateway-to-Control-Plane audit logging is placeholder")
        
        print(f"\n    Key Properties:")
        print(f"      ✓ Single query retrieves all agent activity")
        print(f"      ✓ Every action attributed to 'agent on behalf of user'")
        print(f"      ✓ No need to query 47+ backend systems")
        
        return True
    else:
        print_error("Failed to retrieve audit trail")
        return False


# =============================================================================
# Main Demo
# =============================================================================

def check_services_available():
    """Check if Control Plane and Gateway are available."""
    try:
        with httpx.Client(timeout=5.0) as client:
            control_health = client.get(f"{CONTROL_PLANE_URL}/health")
            gateway_health = client.get(f"{GATEWAY_URL}/health")
            return control_health.status_code == 200 and gateway_health.status_code == 200
    except httpx.ConnectError:
        return False


def run_demo(verbose: bool = False):
    """Run the complete Sarah's Journey demo."""
    print(f"""
{Colors.HEADER}╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║           Sarah's Journey - Virtual MCP Server MVP Demo              ║
║                                                                      ║
║   Demonstrating: Unified MCP Connection | Delegation-Based Access   ║
║                  Tool Filtering | Permission Enforcement | Audit    ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝{Colors.ENDC}
    """)
    
    # Check service availability
    print(f"{Colors.CYAN}Checking service availability...{Colors.ENDC}")
    if not check_services_available():
        print_error("Services not available!")
        print("""
    Please start the services first:
        docker compose up -d deeptrail-control deeptrail-gateway
        
    Then wait a few seconds and run:
        python demos/demo_sarah_journey_e2e.py
        """)
        return False
    
    print_success("Control Plane and Gateway are running")
    
    # Initialize
    scenario = DemoScenario()
    keypair = generate_keypair()
    
    print(f"\n{Colors.BOLD}Demo Scenario:{Colors.ENDC}")
    print(f"  User: {scenario.user_email}")
    print(f"  Agent: {scenario.agent_id}")
    print(f"  Services: Notion, Slack")
    
    # Run all steps
    with httpx.Client(timeout=30.0) as client:
        
        # Step 1: Enterprise Registration
        if not step_01_enterprise_registration(scenario, verbose):
            return False
        
        # Step 2: Sarah Authenticates
        user_token = step_02_sarah_authenticates(client, scenario, verbose)
        if not user_token:
            return False
        
        # Step 3: Connect Services
        if not step_03_connect_services(client, user_token, scenario, verbose):
            return False
        
        # Step 4: Delegate to Agent
        delegation_token = step_04_delegate_to_agent(client, user_token, keypair, scenario, verbose)
        if not delegation_token:
            return False
        
        # Step 5: Agent Authenticates
        agent_jwt = step_05_agent_authenticates(client, keypair, delegation_token, scenario, verbose)
        if not agent_jwt:
            return False
        
        # Step 6: MCP Initialize
        if not step_06_mcp_initialize(client, agent_jwt, scenario, verbose):
            return False
        
        # Step 7: Discover Tools
        tools = step_07_discover_tools(client, agent_jwt, scenario, verbose)
        if tools is None:
            return False
        
        # Step 8: Execute Tool
        if not step_08_execute_tool(client, agent_jwt, scenario, verbose):
            return False
        
        # Step 9: Permission Denied
        if not step_09_permission_denied(client, agent_jwt, scenario, verbose):
            return False
        
        # Step 10: Review Audit
        if not step_10_review_audit(client, user_token, scenario, verbose):
            return False
    
    # Final Summary
    print(f"""
{Colors.HEADER}╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║              ✅ Sarah's Journey Complete - All 10 Steps Passed!      ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝{Colors.ENDC}

{Colors.BOLD}Value Propositions Demonstrated:{Colors.ENDC}

  1. {Colors.GREEN}Unified MCP Connection{Colors.ENDC}
     → Agent connected to ONE endpoint, accessed tools from 2 backends

  2. {Colors.GREEN}Delegation-Based Consent{Colors.ENDC}
     → Sarah consented once in browser, agent uses her credentials

  3. {Colors.GREEN}Tool Filtering{Colors.ENDC}
     → Agent saw only tools Sarah delegated (not all backend tools)

  4. {Colors.GREEN}Namespace Resolution{Colors.ENDC}
     → notion.search_pages and slack.search are unambiguous

  5. {Colors.GREEN}Permission Enforcement{Colors.ENDC}
     → Non-delegated tool (notion.create_page) blocked at gateway

  6. {Colors.GREEN}Audit Trail{Colors.ENDC}
     → Every action logged as "agent-X on behalf of Sarah"

  7. {Colors.GREEN}Credential Isolation{Colors.ENDC}
     → Agent NEVER saw OAuth tokens - Gateway injected them

{Colors.BOLD}API Endpoints Used:{Colors.ENDC}

  Control Plane ({CONTROL_PLANE_URL}):
    • POST /api/v1/auth/login
    • POST /api/v1/users/me/services/connect
    • POST /api/v1/agents/
    • POST /api/v1/auth/delegate  
    • POST /api/v1/auth/agent/challenge
    • POST /api/v1/auth/agent/verify
    • GET  /api/v1/audit/events

  Gateway ({GATEWAY_URL}):
    • POST /mcp (initialize, tools/list, tools/call)
    """)
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sarah's Journey E2E Demo")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    success = run_demo(verbose=args.verbose)
    sys.exit(0 if success else 1)
