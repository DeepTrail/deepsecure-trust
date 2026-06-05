"""MCP 2026-07-28 header validation (WS-B4)."""


def mcp_method_header_mismatch(
    mcp_method_header: str | None,
    jsonrpc_method: str | None,
) -> bool:
    """Return True when ``Mcp-Method`` is present and disagrees with the body method."""
    if not mcp_method_header or not jsonrpc_method:
        return False
    return mcp_method_header.strip() != jsonrpc_method.strip()
