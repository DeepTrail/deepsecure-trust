# Task: WS-B1 Implement MCP JSON-RPC 2.0 Parser

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-B: Gateway MCP Core |
| **Dependencies** | None |
| **Blocked By** | None |
| **Assigned** | - |
| **Created** | January 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 1 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 1: Unified Connection (foundation) |
| **Validates User Journey Step** | Step 6: Agent Connects to Virtual MCP (foundation) |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] No dependency tasks (this is a Batch 1 task)
- [ ] `deeptrail-gateway/` service structure exists
- [ ] FastAPI or similar HTTP framework is set up

---

## Task Description

Implement a JSON-RPC 2.0 parser that handles the MCP (Model Context Protocol) message format. This parser is the entry point for all MCP communication with the Virtual MCP Server.

### Context

The MCP protocol uses JSON-RPC 2.0 for all messages. The gateway must parse three main methods:
- `initialize` - Handshake to establish MCP session
- `tools/list` - List available tools
- `tools/call` - Execute a tool

From the MVP design (Section 2.7 - Step 6):
```python
# Agent sees ONE MCP server - the gateway
client = MCPClient("https://gateway.deeptrail.io/mcp")
client.set_auth_header(f"Bearer {agent_session_jwt}")

# MCP initialize handshake
await client.initialize()
```

### Technical Notes

- JSON-RPC 2.0 format: `{"jsonrpc": "2.0", "id": 1, "method": "...", "params": {...}}`
- Must handle batch requests (array of requests)
- Must return proper JSON-RPC error codes for invalid requests
- Consider using Pydantic for request/response validation

---

## Acceptance Criteria

### Protocol
- [ ] Parses valid JSON-RPC 2.0 requests with `jsonrpc`, `id`, `method`, `params` fields
- [ ] Handles `initialize`, `tools/list`, `tools/call` method routing
- [ ] Returns proper JSON-RPC 2.0 responses with `jsonrpc`, `id`, `result` or `error`
- [ ] Returns `-32600` (Invalid Request) for malformed requests
- [ ] Returns `-32601` (Method not found) for unknown methods
- [ ] Returns `-32700` (Parse error) for invalid JSON

### Security
- [ ] Does not expose internal errors in responses (generic error messages)
- [ ] Validates request size limits (prevent DoS)

### Integration
- [ ] Integrates with FastAPI endpoint at `/mcp` or similar
- [ ] Passes parsed method and params to handler functions
- [ ] Handlers are pluggable (will be implemented in B2, B6, B7)

### General
- [ ] Unit tests for parsing valid and invalid requests
- [ ] Unit tests for all error codes
- [ ] No new linting errors introduced

---

## Files to Create

| File | Purpose |
|------|---------|
| `deeptrail-gateway/gateway/mcp/protocol.py` | JSON-RPC 2.0 parser and MCP protocol handler |
| `deeptrail-gateway/tests/mcp/test_protocol.py` | Unit tests for protocol parsing |

---

## Files to Modify

| File | Changes |
|------|---------|
| `deeptrail-gateway/gateway/__init__.py` | Export MCP protocol handler |
| `deeptrail-gateway/gateway/routes.py` | Add `/mcp` endpoint (if exists) |

---

## Implementation Hints

```python
# deeptrail-gateway/gateway/mcp/protocol.py

from pydantic import BaseModel, Field
from typing import Any, Optional, Union, Dict
from enum import IntEnum

class JsonRpcErrorCode(IntEnum):
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # Custom MCP errors
    PERMISSION_DENIED = -32001
    POLICY_UNAVAILABLE = -32000

class JsonRpcRequest(BaseModel):
    jsonrpc: str = Field(default="2.0")
    id: Union[str, int, None] = None
    method: str
    params: Optional[Dict[str, Any]] = None

class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Union[str, int, None]
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

class MCPProtocolHandler:
    """Handles MCP JSON-RPC 2.0 protocol parsing and routing."""
    
    def __init__(self):
        self._handlers: Dict[str, callable] = {}
    
    def register_handler(self, method: str, handler: callable):
        """Register a handler for an MCP method."""
        self._handlers[method] = handler
    
    async def handle_request(self, raw_body: bytes) -> JsonRpcResponse:
        """Parse and route an MCP request."""
        try:
            # Parse JSON
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            return self._error_response(None, JsonRpcErrorCode.PARSE_ERROR, "Parse error")
        
        try:
            request = JsonRpcRequest(**data)
        except ValidationError:
            return self._error_response(None, JsonRpcErrorCode.INVALID_REQUEST, "Invalid Request")
        
        # Route to handler
        handler = self._handlers.get(request.method)
        if not handler:
            return self._error_response(request.id, JsonRpcErrorCode.METHOD_NOT_FOUND, "Method not found")
        
        try:
            result = await handler(request.params or {})
            return JsonRpcResponse(id=request.id, result=result)
        except Exception as e:
            return self._error_response(request.id, JsonRpcErrorCode.INTERNAL_ERROR, "Internal error")
    
    def _error_response(self, id: Any, code: int, message: str) -> JsonRpcResponse:
        return JsonRpcResponse(id=id, error={"code": code, "message": message})
```

---

## Post-Conditions

After completing this task:

- [ ] All acceptance criteria met
- [ ] Tests pass locally: `pytest deeptrail-gateway/tests/mcp/test_protocol.py`
- [ ] Linting passes: `ruff check deeptrail-gateway/gateway/mcp/`
- [ ] Type checking passes: `mypy deeptrail-gateway/gateway/mcp/`
- [ ] Tasks B2, B4 can now start (they depend on B1)

---

## References

- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [MCP Protocol Specification](https://modelcontextprotocol.io/specification)
- Design Doc Section 2.7: Step 6 - Agent Connects to Virtual MCP

---

## Notes

- This is the protocol foundation - handlers are stubs initially
- B2, B6, B7 will implement the actual `initialize`, `tools/list`, `tools/call` handlers
- Consider streaming support for future (out of MVP scope)

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
