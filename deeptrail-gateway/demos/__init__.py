"""
Virtual MCP Server Demo Scripts.

This package contains demonstration scripts that showcase the
value propositions of the Virtual MCP Server pattern:

- Demo 1: Unified MCP Connection - One gateway, multiple backends
- Demo 2: Filtered Visibility - Agents see only delegated tools
- Demo 3: Delegation Execution - Agent acts on behalf of user
- Demo 4: Permission Enforcement - Unauthorized tools rejected
- Demo 5: Unified Audit - All actions logged under agent identity
- Demo 6: Fail-Closed Security - Secure handling of failures

Usage:
    # Run demos with mock mode (no services required)
    python -m demos.demo_01_unified_connection --mock
    
    # Run with live services
    docker compose up -d
    python -m demos.demo_01_unified_connection
"""

__version__ = "0.1.0"
