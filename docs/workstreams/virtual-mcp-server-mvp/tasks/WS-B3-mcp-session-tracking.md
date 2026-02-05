# Task: WS-B3 Implement MCP Session Tracking

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-B: Gateway MCP Core |
| **Dependencies** | B2 (Initialize handler) |
| **Blocked By** | None (B2 is complete ✅) |
| **Assigned** | - |
| **Created** | January 30, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 3 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 1: Unified Connection |
| **Validates User Journey Step** | Step 6: Agent Connects to Virtual MCP Server |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] B2 (Initialize handler) is complete
- [ ] `deeptrail-gateway/` service structure exists
- [ ] Initialize handler can be imported from `deeptrail-gateway.gateway.mcp.handlers`

---

## Task Description

Implement the MCP Session Manager that tracks backend MCP connections for each agent session. When an agent connects to the Virtual MCP Server (gateway), the gateway creates individual MCP sessions to each backend server (Notion, Slack, etc.) on behalf of that agent.

### Context

From the MVP design (Section 2.7 - Step 6):

```
Gateway (Virtual MCP Server) handles initialize:
1. Validates Agent Session JWT
2. Extracts delegated_permissions
3. Looks up Sarah's connected services (Notion, Slack)
4. Creates MCP Sessions for each backend:

   MCP SESSION 1 (Notion):
   {
     "mcp_session_id": "mcpsess-notion-jkl012",
     "parent_agent_session": "asess-sdr-001-ghi789",
     "server_id": "notion",
     "connection_state": "initialized",
     "allowed_tools": ["notion.search_pages", "notion.read_page"],
     "injected_credentials": {
       "type": "oauth",
       "ref": "vault://sarah-notion-oauth-xyz"
     }
   }

   MCP SESSION 2 (Slack):
   {
     "mcp_session_id": "mcpsess-slack-mno345",
     ...
   }
```

### Technical Notes

- **One agent session → Multiple MCP sessions** (one per backend)
- **Session state**: Track connection state (initialized, connected, disconnected, error)
- **Allowed tools**: Pre-computed from delegation permissions + backend capabilities
- **Credential reference**: Stored for injection during tools/call (C7)
- **In-memory for MVP**: Use dict-based storage; Redis for production

---

## Acceptance Criteria

### Protocol
- [ ] Follows MCP session lifecycle (initialize → connected → disconnected)
- [ ] Each backend gets its own MCP session

### Security
- [ ] Sessions are isolated per agent (no cross-agent access)
- [ ] Credential references stored, not actual credentials
- [ ] Sessions expire when parent agent session expires

### Integration
- [ ] SessionManager can be imported from `deeptrail-gateway.gateway.mcp`
- [ ] Works with initialize handler (B2)
- [ ] Provides sessions for tools/list (B6) and tools/call (B7)

### Functional
- [ ] `create_agent_session(agent_session_id, delegated_permissions, connected_services)` → AgentMCPSession
- [ ] `get_agent_session(agent_session_id)` → AgentMCPSession or None
- [ ] `get_backend_session(agent_session_id, backend_id)` → BackendMCPSession or None
- [ ] `get_all_backend_sessions(agent_session_id)` → List[BackendMCPSession]
- [ ] `update_session_state(session_id, state)` → updates connection state
- [ ] `close_agent_session(agent_session_id)` → closes all backend sessions
- [ ] `get_allowed_tools(agent_session_id)` → aggregated list of allowed tools

### General
- [ ] Unit tests for session lifecycle
- [ ] Tests for multi-backend session management
- [ ] No new linting errors introduced

---

## Files to Create

| File | Purpose |
|------|---------|
| `deeptrail-gateway/gateway/mcp/session_manager.py` | MCP session tracking |
| `deeptrail-gateway/tests/gateway/mcp/test_session_manager.py` | Unit tests |

---

## Files to Modify

| File | Changes |
|------|---------|
| `deeptrail-gateway/gateway/mcp/__init__.py` | Export SessionManager |

---

## Implementation Hints

```python
# deeptrail-gateway/gateway/mcp/session_manager.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid


class SessionState(Enum):
    """MCP session connection states."""
    PENDING = "pending"
    INITIALIZED = "initialized"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class CredentialRef:
    """Reference to credentials in vault."""
    type: str  # "oauth", "api_key", etc.
    ref: str   # "vault://sarah-notion-oauth-xyz"


@dataclass
class BackendMCPSession:
    """
    MCP session to a single backend server.
    
    Represents the gateway's connection to one backend (e.g., Notion)
    on behalf of an agent.
    """
    mcp_session_id: str
    parent_agent_session: str
    server_id: str  # "notion", "slack", etc.
    connection_state: SessionState
    allowed_tools: List[str]  # ["notion.search_pages", "notion.read_page"]
    credential_ref: Optional[CredentialRef]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mcp_session_id": self.mcp_session_id,
            "parent_agent_session": self.parent_agent_session,
            "server_id": self.server_id,
            "connection_state": self.connection_state.value,
            "allowed_tools": self.allowed_tools,
            "injected_credentials": {
                "type": self.credential_ref.type,
                "ref": self.credential_ref.ref
            } if self.credential_ref else None
        }


@dataclass
class AgentMCPSession:
    """
    Aggregate session for an agent connected to the Virtual MCP Server.
    
    Contains multiple BackendMCPSession instances (one per backend).
    """
    agent_session_id: str
    delegator: str  # User who delegated (e.g., "sarah@acme.com")
    delegated_permissions: List[str]
    backend_sessions: Dict[str, BackendMCPSession] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def get_all_allowed_tools(self) -> List[str]:
        """Get aggregated list of all allowed tools across backends."""
        tools = []
        for session in self.backend_sessions.values():
            tools.extend(session.allowed_tools)
        return tools


class MCPSessionManager:
    """
    Manages MCP sessions between gateway and backend servers.
    
    For each agent that connects, we maintain:
    - One AgentMCPSession (the agent's view of the gateway)
    - Multiple BackendMCPSessions (gateway's connections to backends)
    """
    
    def __init__(self):
        # agent_session_id -> AgentMCPSession
        self._sessions: Dict[str, AgentMCPSession] = {}
    
    def _generate_session_id(self, prefix: str) -> str:
        """Generate unique session ID."""
        return f"{prefix}-{uuid.uuid4().hex[:12]}"
    
    def _filter_tools_by_permissions(
        self,
        backend_tools: List[str],
        delegated_permissions: List[str],
        backend_id: str
    ) -> List[str]:
        """
        Filter backend tools by delegated permissions.
        
        Args:
            backend_tools: Tools offered by backend (e.g., ["search_pages", "create_page"])
            delegated_permissions: Permissions from delegation (e.g., ["notion:pages:search"])
            backend_id: Backend identifier (e.g., "notion")
        
        Returns:
            Filtered list of namespaced tools agent can access
        """
        allowed = []
        for tool in backend_tools:
            namespaced_tool = f"{backend_id}.{tool}"
            # Convert tool to permission format for checking
            # e.g., "notion.search_pages" → check against "notion:pages:search"
            # For MVP, use simple prefix matching
            for perm in delegated_permissions:
                if perm.startswith(f"{backend_id}:"):
                    # Permission is for this backend
                    allowed.append(namespaced_tool)
                    break
        return allowed
    
    def create_agent_session(
        self,
        agent_session_id: str,
        delegator: str,
        delegated_permissions: List[str],
        connected_services: List[Dict[str, Any]]
    ) -> AgentMCPSession:
        """
        Create a new agent session with backend connections.
        
        Args:
            agent_session_id: Agent's session ID from auth
            delegator: User who delegated permissions
            delegated_permissions: List of delegated permission strings
            connected_services: List of {service_id, oauth_token_ref, available_tools}
        
        Returns:
            Created AgentMCPSession with backend sessions
        """
        # Create agent session
        agent_session = AgentMCPSession(
            agent_session_id=agent_session_id,
            delegator=delegator,
            delegated_permissions=delegated_permissions
        )
        
        # Create backend session for each connected service
        for service in connected_services:
            service_id = service["service_id"]
            
            # Filter tools by permissions
            available_tools = service.get("available_tools", [])
            allowed_tools = self._filter_tools_by_permissions(
                available_tools,
                delegated_permissions,
                service_id
            )
            
            # Skip if no allowed tools for this backend
            if not allowed_tools:
                continue
            
            # Create backend session
            backend_session = BackendMCPSession(
                mcp_session_id=self._generate_session_id(f"mcpsess-{service_id}"),
                parent_agent_session=agent_session_id,
                server_id=service_id,
                connection_state=SessionState.INITIALIZED,
                allowed_tools=allowed_tools,
                credential_ref=CredentialRef(
                    type="oauth",
                    ref=service.get("oauth_token_ref", "")
                ) if service.get("oauth_token_ref") else None
            )
            
            agent_session.backend_sessions[service_id] = backend_session
        
        # Store session
        self._sessions[agent_session_id] = agent_session
        return agent_session
    
    def get_agent_session(self, agent_session_id: str) -> Optional[AgentMCPSession]:
        """Get agent session by ID."""
        return self._sessions.get(agent_session_id)
    
    def get_backend_session(
        self,
        agent_session_id: str,
        backend_id: str
    ) -> Optional[BackendMCPSession]:
        """Get specific backend session for an agent."""
        agent_session = self.get_agent_session(agent_session_id)
        if not agent_session:
            return None
        return agent_session.backend_sessions.get(backend_id)
    
    def get_all_backend_sessions(
        self,
        agent_session_id: str
    ) -> List[BackendMCPSession]:
        """Get all backend sessions for an agent."""
        agent_session = self.get_agent_session(agent_session_id)
        if not agent_session:
            return []
        return list(agent_session.backend_sessions.values())
    
    def update_session_state(
        self,
        agent_session_id: str,
        backend_id: str,
        state: SessionState
    ) -> bool:
        """Update connection state for a backend session."""
        session = self.get_backend_session(agent_session_id, backend_id)
        if not session:
            return False
        session.connection_state = state
        session.last_activity = datetime.now(timezone.utc)
        return True
    
    def close_agent_session(self, agent_session_id: str) -> bool:
        """
        Close agent session and all backend sessions.
        
        Returns:
            True if session existed and was closed
        """
        if agent_session_id not in self._sessions:
            return False
        
        agent_session = self._sessions[agent_session_id]
        
        # Mark all backend sessions as disconnected
        for backend_session in agent_session.backend_sessions.values():
            backend_session.connection_state = SessionState.DISCONNECTED
        
        # Remove from active sessions
        del self._sessions[agent_session_id]
        return True
    
    def get_allowed_tools(self, agent_session_id: str) -> List[str]:
        """Get aggregated list of allowed tools for agent."""
        agent_session = self.get_agent_session(agent_session_id)
        if not agent_session:
            return []
        return agent_session.get_all_allowed_tools()
    
    def get_credential_ref_for_tool(
        self,
        agent_session_id: str,
        namespaced_tool: str
    ) -> Optional[CredentialRef]:
        """
        Get credential reference for executing a tool.
        
        Used by credential injection (C7).
        
        Args:
            agent_session_id: Agent's session
            namespaced_tool: Tool name (e.g., "notion.search_pages")
        
        Returns:
            CredentialRef for the backend, or None
        """
        # Extract backend from tool name
        if "." not in namespaced_tool:
            return None
        
        backend_id = namespaced_tool.split(".")[0]
        backend_session = self.get_backend_session(agent_session_id, backend_id)
        
        if not backend_session:
            return None
        
        return backend_session.credential_ref
```

---

## Post-Conditions

After completing this task:

- [ ] All acceptance criteria met
- [ ] Tests pass locally: `pytest deeptrail-gateway/tests/gateway/mcp/test_session_manager.py`
- [ ] Linting passes: `ruff check deeptrail-gateway/gateway/mcp/`
- [ ] Type checking passes: `mypy deeptrail-gateway/gateway/mcp/`
- [ ] Task B6 (tools/list handler) can use session manager
- [ ] Task B7 (tools/call handler) can use session manager
- [ ] Task C7 (credential injection) can get credential refs

---

## References

- Design Doc Section 2.7: Step 6 - Agent Connects to Virtual MCP Server
- Design Doc Section 4.1: Component Implementation Status (MCP Session Service)
- B2 Task: Initialize handler (creates sessions on initialize)
- C7 Task: Credential injection (uses credential refs from sessions)

---

## Notes

- **In-memory storage for MVP**: Production needs Redis or distributed cache
- **Session isolation**: Critical that agents cannot access each other's sessions
- **Tool filtering**: Pre-compute allowed tools on session creation for fast tools/list
- **Credential refs**: Store only references; actual tokens fetched on demand from vault
- **Consider**: Adding session TTL and automatic cleanup

---

## Test Cases to Cover

```python
# test_session_manager.py

def test_create_agent_session_with_backends():
    manager = MCPSessionManager()
    
    session = manager.create_agent_session(
        agent_session_id="agent-session-123",
        delegator="sarah@acme.com",
        delegated_permissions=["notion:pages:search", "slack:messages:search"],
        connected_services=[
            {"service_id": "notion", "oauth_token_ref": "vault://ref1", "available_tools": ["search_pages", "read_page"]},
            {"service_id": "slack", "oauth_token_ref": "vault://ref2", "available_tools": ["search_messages"]}
        ]
    )
    
    assert session.agent_session_id == "agent-session-123"
    assert len(session.backend_sessions) == 2
    assert "notion" in session.backend_sessions
    assert "slack" in session.backend_sessions

def test_get_backend_session():
    manager = MCPSessionManager()
    manager.create_agent_session("agent-1", "user", ["notion:pages:read"], [
        {"service_id": "notion", "oauth_token_ref": "ref", "available_tools": ["read_page"]}
    ])
    
    notion = manager.get_backend_session("agent-1", "notion")
    assert notion is not None
    assert notion.server_id == "notion"
    
    slack = manager.get_backend_session("agent-1", "slack")
    assert slack is None  # Not connected

def test_get_allowed_tools_aggregated():
    manager = MCPSessionManager()
    manager.create_agent_session("agent-1", "user", 
        ["notion:pages:search", "slack:messages:search"], [
            {"service_id": "notion", "available_tools": ["search_pages"]},
            {"service_id": "slack", "available_tools": ["search_messages"]}
        ]
    )
    
    tools = manager.get_allowed_tools("agent-1")
    assert "notion.search_pages" in tools
    assert "slack.search_messages" in tools

def test_close_session_removes_agent():
    manager = MCPSessionManager()
    manager.create_agent_session("agent-1", "user", [], [])
    
    assert manager.get_agent_session("agent-1") is not None
    manager.close_agent_session("agent-1")
    assert manager.get_agent_session("agent-1") is None

def test_session_isolation():
    manager = MCPSessionManager()
    manager.create_agent_session("agent-1", "user-1", ["notion:pages:read"], [
        {"service_id": "notion", "oauth_token_ref": "vault://user1-token", "available_tools": ["read_page"]}
    ])
    manager.create_agent_session("agent-2", "user-2", ["slack:messages:read"], [
        {"service_id": "slack", "oauth_token_ref": "vault://user2-token", "available_tools": ["search_messages"]}
    ])
    
    # Agent 1 cannot see Agent 2's sessions
    assert manager.get_backend_session("agent-1", "slack") is None
    assert manager.get_backend_session("agent-2", "notion") is None
```

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
