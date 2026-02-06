"""
Permission Filter for tools/list responses.

Filters MCP tools/list responses to only include tools the agent
has delegated permission to use.

This is Step 7 of Sarah's journey: Agent sees only delegated tools.

Key Features:
- Intercepts tools/list responses
- Uses delegated_permissions from JWT (via AgentContext)
- Uses PermissionMapper to filter tools
- Fail-closed: returns empty list if permissions unavailable
- Logs filtering statistics for audit/debugging

Security:
- **Fail-closed**: No agent context → empty tool list, not all tools
- Unknown tools are excluded (handled by C4's PermissionMapper)
- No information leakage about excluded tools
- Filtering logged for audit trail

Usage:
    from app.middleware.permission_filter import PermissionFilter
    from app.middleware.jwt_validation import AgentContext
    
    # In tools/list handler
    filtered_tools = PermissionFilter.filter_tools(
        tools=aggregated_tools,
        agent_context=request.state.agent_context
    )
    
    # Get permitted backends for optimization
    backends = PermissionFilter.get_permitted_backends(agent_context)
"""

import logging
from typing import Any

from .jwt_validation import AgentContext
from ..mcp.permission_mapper import PermissionMapper

logger = logging.getLogger(__name__)


class PermissionFilter:
    """
    Filters tools by delegated permissions.
    
    Can be used as:
    1. Direct function call in handlers
    2. Helper methods for permission analysis
    
    Key Security Behavior:
    - Fail-closed: Returns empty list if agent_context is None
    - Delegates to PermissionMapper for actual filtering
    - Logs filtering statistics for audit trail
    
    Demo 2 Metric:
    - Demonstrates 90%+ tool reduction when agent has limited delegation
    - Example: 20 total tools → 2 delegated = 90% reduction
    """
    
    @staticmethod
    def filter_tools(
        tools: list[dict[str, Any]],
        agent_context: AgentContext | None,
    ) -> list[dict[str, Any]]:
        """
        Filter tools by agent's delegated permissions.
        
        Args:
            tools: List of tool schemas from aggregator (with 'name' field)
            agent_context: Validated agent context with delegated_permissions
            
        Returns:
            Filtered list of tools agent can use
            
        Security:
            - Returns empty list if agent_context is None (fail-closed)
            - Returns empty list if no delegated permissions
            - Uses PermissionMapper.filter_tools() for actual filtering
            
        Example:
            >>> tools = [
            ...     {"name": "notion.search_pages", "description": "Search"},
            ...     {"name": "slack.send_message", "description": "Send"},
            ... ]
            >>> context = AgentContext(
            ...     agent_id="agent-123",
            ...     owner="sarah@example.com",
            ...     delegated_permissions=["notion:pages:search"],
            ...     delegation_id="del-456",
            ...     session_id="sess-789",
            ... )
            >>> filtered = PermissionFilter.filter_tools(tools, context)
            >>> [t["name"] for t in filtered]
            ["notion.search_pages"]
        """
        # Fail-closed: no context means no tools
        if agent_context is None:
            logger.warning(
                "Permission filter: No agent context - returning empty tool list (fail-closed)"
            )
            return []
        
        # No permissions means no tools
        if not agent_context.delegated_permissions:
            logger.info(
                "Permission filter: Agent %s has no delegated permissions - returning empty",
                agent_context.agent_id,
            )
            return []
        
        # Delegate to PermissionMapper for actual filtering
        filtered = PermissionMapper.filter_tools(
            tools,
            agent_context.delegated_permissions,
        )
        
        # Calculate reduction for Demo 2 metric
        original_count = len(tools)
        filtered_count = len(filtered)
        
        if original_count > 0:
            reduction_pct = (original_count - filtered_count) / original_count * 100
        else:
            reduction_pct = 0.0
        
        logger.info(
            "Permission filter: %d/%d tools (%.1f%% reduction) for agent %s",
            filtered_count,
            original_count,
            reduction_pct,
            agent_context.agent_id,
        )
        
        return filtered
    
    @staticmethod
    def filter_tools_by_permissions(
        tools: list[dict[str, Any]],
        delegated_permissions: list[str],
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Filter tools by permissions list (without AgentContext).
        
        Alternative to filter_tools() when only permissions list is available.
        
        Args:
            tools: List of tool schemas from aggregator
            delegated_permissions: List of permission strings
            agent_id: Optional agent ID for logging
            
        Returns:
            Filtered list of tools
            
        Note:
            Prefer filter_tools() with AgentContext for full audit trail.
        """
        if not delegated_permissions:
            logger.info(
                "Permission filter: Empty permissions list for agent %s - returning empty",
                agent_id or "unknown",
            )
            return []
        
        filtered = PermissionMapper.filter_tools(tools, delegated_permissions)
        
        original_count = len(tools)
        filtered_count = len(filtered)
        
        if original_count > 0:
            reduction_pct = (original_count - filtered_count) / original_count * 100
        else:
            reduction_pct = 0.0
        
        logger.info(
            "Permission filter: %d/%d tools (%.1f%% reduction) for agent %s",
            filtered_count,
            original_count,
            reduction_pct,
            agent_id or "unknown",
        )
        
        return filtered
    
    @staticmethod
    def get_permitted_backends(
        agent_context: AgentContext | None,
    ) -> set[str]:
        """
        Get set of backends the agent has any permission for.
        
        Useful for optimizing tool aggregation - only query 
        backends the agent can actually use.
        
        Args:
            agent_context: Validated agent context (or None)
            
        Returns:
            Set of backend IDs (e.g., {"notion", "slack"})
            Returns empty set if agent_context is None (fail-closed)
            
        Example:
            >>> context = AgentContext(
            ...     delegated_permissions=[
            ...         "notion:pages:search",
            ...         "slack:messages:send",
            ...     ],
            ...     ...
            ... )
            >>> backends = PermissionFilter.get_permitted_backends(context)
            >>> backends
            {"notion", "slack"}
        """
        if agent_context is None:
            logger.debug("get_permitted_backends: No agent context - returning empty set")
            return set()
        
        if not agent_context.delegated_permissions:
            return set()
        
        backends = set()
        for perm in agent_context.delegated_permissions:
            # Permission format: backend:resource:action
            parts = perm.split(":")
            if len(parts) >= 1 and parts[0]:
                backends.add(parts[0])
        
        logger.debug(
            "Agent %s has permissions for backends: %s",
            agent_context.agent_id,
            backends,
        )
        
        return backends
    
    @staticmethod
    def get_permitted_backends_from_permissions(
        delegated_permissions: list[str],
    ) -> set[str]:
        """
        Get set of backends from permissions list (without AgentContext).
        
        Args:
            delegated_permissions: List of permission strings
            
        Returns:
            Set of backend IDs
        """
        backends = set()
        for perm in delegated_permissions:
            parts = perm.split(":")
            if len(parts) >= 1 and parts[0]:
                backends.add(parts[0])
        return backends
    
    @staticmethod
    def calculate_reduction(
        original_count: int,
        filtered_count: int,
    ) -> float:
        """
        Calculate the reduction percentage.
        
        Args:
            original_count: Number of tools before filtering
            filtered_count: Number of tools after filtering
            
        Returns:
            Reduction percentage (0-100)
            
        Example:
            >>> PermissionFilter.calculate_reduction(20, 2)
            90.0
        """
        if original_count <= 0:
            return 0.0
        return (original_count - filtered_count) / original_count * 100
    
    @staticmethod
    def is_tool_permitted(
        tool_name: str,
        agent_context: AgentContext | None,
    ) -> bool:
        """
        Check if a single tool is permitted for the agent.
        
        Args:
            tool_name: Namespaced tool name (e.g., "notion.search_pages")
            agent_context: Agent context with permissions
            
        Returns:
            True if permitted, False otherwise
            
        Security:
            Returns False if agent_context is None (fail-closed)
        """
        if agent_context is None:
            return False
        
        if not agent_context.delegated_permissions:
            return False
        
        return PermissionMapper.is_tool_permitted(
            tool_name,
            agent_context.delegated_permissions,
        )


# =============================================================================
# Convenience Functions
# =============================================================================


def filter_tools_for_agent(
    tools: list[dict[str, Any]],
    agent_context: AgentContext | None,
) -> list[dict[str, Any]]:
    """
    Convenience function for filtering tools.
    
    Same as PermissionFilter.filter_tools() but as a standalone function.
    
    Args:
        tools: List of tool schemas
        agent_context: Agent context with permissions
        
    Returns:
        Filtered list of tools
    """
    return PermissionFilter.filter_tools(tools, agent_context)


def get_permitted_backends_for_agent(
    agent_context: AgentContext | None,
) -> set[str]:
    """
    Convenience function for getting permitted backends.
    
    Same as PermissionFilter.get_permitted_backends() but as a standalone function.
    
    Args:
        agent_context: Agent context with permissions
        
    Returns:
        Set of backend IDs
    """
    return PermissionFilter.get_permitted_backends(agent_context)
