# Task: WS-B2 Implement Initialize Handler

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-B: Gateway MCP Core |
| **Dependencies** | B1 (MCP JSON-RPC 2.0 parser) |
| **Blocked By** | None (B1 is complete ✅) |
| **Assigned** | - |
| **Created** | January 30, 2026 |
| **Estimated Complexity** | `S` (< 2 hours) |
| **Batch** | 2 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 1: Unified Connection |
| **Validates User Journey Step** | Step 6: Agent Connects to Virtual MCP Server |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] B1 (MCP JSON-RPC 2.0 parser) is complete
- [ ] `deeptrail-gateway/` service structure exists
- [ ] MCP protocol module can be imported from `deeptrail-gateway.gateway.mcp`
- [ ] JSON-RPC request/response structures are available from B1

---

## Task Description

Implement the MCP `initialize` request handler that responds to the agent's initial MCP handshake. This handler receives the client's capabilities and returns the server's capabilities and metadata (serverInfo).

### Context

From the MVP design (Section 2.7 - Step 6):

```
Agent Code:
  # Agent sees ONE MCP server - the gateway
  client = MCPClient("https://gateway.deeptrail.io/mcp")
  client.set_auth_header(f"Bearer {agent_session_jwt}")
  
  # MCP initialize handshake
  await client.initialize()

Gateway (Virtual MCP Server) handles initialize:
  1. Validates Agent Session JWT
  2. Extracts delegated_permissions
  3. Looks up user's connected services
  4. Creates MCP Sessions for each backend
  5. Gateway responds to agent with initialize/initialized
```

The initialize handler is the first step in MCP protocol - it establishes the session and exchanges capabilities.

### MCP Protocol Reference

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "roots": { "listChanged": true },
      "sampling": {}
    },
    "clientInfo": {
      "name": "ExampleClient",
      "version": "1.0.0"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": { "listChanged": true }
    },
    "serverInfo": {
      "name": "DeepTrail Virtual MCP Server",
      "version": "0.1.0"
    }
  }
}
```

### Technical Notes

- This handler is called before any tools/list or tools/call
- Must validate the protocolVersion is supported
- Server capabilities should advertise `tools` capability
- The handler should be stateless - session state is managed separately (B3)
- JWT validation happens in middleware (C3), not in this handler

---

## Acceptance Criteria

### Protocol
- [ ] Handles MCP `initialize` method correctly
- [ ] Returns valid `initialize` response per MCP spec
- [ ] Supports protocol version `2024-11-05`
- [ ] Returns appropriate error for unsupported protocol versions

### Security
- [ ] Does not expose internal server details in serverInfo
- [ ] Validates required params (protocolVersion, clientInfo)

### Integration
- [ ] Handler registered in MCP router/dispatcher
- [ ] Uses protocol structures from B1 (MCPRequest, MCPResponse)
- [ ] Follows handler pattern established in `deeptrail-gateway`

### Functional
- [ ] Returns serverInfo with name and version
- [ ] Returns capabilities object advertising `tools` support
- [ ] Stores client capabilities for later reference (optional)
- [ ] Returns correct JSON-RPC 2.0 response format

### General
- [ ] Unit tests for handler with valid/invalid requests
- [ ] No new linting errors introduced

---

## Files to Create

| File | Purpose |
|------|---------|
| `deeptrail-gateway/gateway/mcp/handlers/initialize.py` | Initialize request handler |
| `deeptrail-gateway/tests/gateway/mcp/handlers/test_initialize.py` | Unit tests |

---

## Files to Modify

| File | Changes |
|------|---------|
| `deeptrail-gateway/gateway/mcp/handlers/__init__.py` | Export initialize handler |
| `deeptrail-gateway/gateway/mcp/router.py` | Register initialize handler (if router exists) |

---

## Implementation Hints

```python
# deeptrail-gateway/gateway/mcp/handlers/initialize.py

from typing import Any, Dict, Optional
from dataclasses import dataclass

from ..protocol import MCPRequest, MCPResponse, MCPError

# Supported protocol versions
SUPPORTED_PROTOCOL_VERSIONS = ["2024-11-05"]

# Server metadata
SERVER_INFO = {
    "name": "DeepTrail Virtual MCP Server",
    "version": "0.1.0"
}

# Server capabilities
SERVER_CAPABILITIES = {
    "tools": {
        "listChanged": True  # We support notifying when tool list changes
    }
}


@dataclass
class InitializeParams:
    """Parameters for initialize request."""
    protocol_version: str
    capabilities: Dict[str, Any]
    client_info: Dict[str, str]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InitializeParams":
        return cls(
            protocol_version=data.get("protocolVersion", ""),
            capabilities=data.get("capabilities", {}),
            client_info=data.get("clientInfo", {})
        )


@dataclass
class InitializeResult:
    """Result for initialize response."""
    protocol_version: str
    capabilities: Dict[str, Any]
    server_info: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocolVersion": self.protocol_version,
            "capabilities": self.capabilities,
            "serverInfo": self.server_info
        }


async def handle_initialize(request: MCPRequest) -> MCPResponse:
    """
    Handle MCP initialize request.
    
    This is the first message in the MCP protocol handshake.
    Client sends its capabilities and we respond with ours.
    """
    # Parse params
    params = InitializeParams.from_dict(request.params or {})
    
    # Validate protocol version
    if params.protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
        return MCPResponse(
            id=request.id,
            error=MCPError(
                code=-32602,  # Invalid params
                message=f"Unsupported protocol version: {params.protocol_version}. "
                        f"Supported: {SUPPORTED_PROTOCOL_VERSIONS}"
            )
        )
    
    # Validate client info
    if not params.client_info.get("name"):
        return MCPResponse(
            id=request.id,
            error=MCPError(
                code=-32602,
                message="Missing required field: clientInfo.name"
            )
        )
    
    # Build response
    result = InitializeResult(
        protocol_version=params.protocol_version,
        capabilities=SERVER_CAPABILITIES,
        server_info=SERVER_INFO
    )
    
    return MCPResponse(
        id=request.id,
        result=result.to_dict()
    )


# Handler registration
HANDLER_METHOD = "initialize"
```

---

## Post-Conditions

After completing this task:

- [ ] All acceptance criteria met
- [ ] Tests pass locally: `pytest deeptrail-gateway/tests/gateway/mcp/handlers/test_initialize.py`
- [ ] Linting passes: `ruff check deeptrail-gateway/gateway/mcp/`
- [ ] Type checking passes: `mypy deeptrail-gateway/gateway/mcp/`
- [ ] Task B3 can proceed (session tracking builds on initialize)

---

## References

- Design Doc Section 2.7: Step 6 - Agent Connects to Virtual MCP Server
- MCP Specification: [Initialize lifecycle](https://spec.modelcontextprotocol.io/specification/basic/lifecycle/)
- B1 Task: MCP JSON-RPC 2.0 parser for protocol structures

---

## Notes

- The `initialize` handler is intentionally simple - it's just capability exchange
- Session creation logic (MCP Sessions per backend) is in B3, not here
- JWT validation is middleware (C3), not in the handler
- Consider adding `notifications/initialized` support in future batch
- Client capabilities can be used to negotiate features (e.g., sampling)

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
