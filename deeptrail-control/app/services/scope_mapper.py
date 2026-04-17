"""Scope to Permission Mapper for DeepSecure.

Maps OAuth scopes (what user grants during service connection) to
DeepSecure permission strings (what gets delegated to agents).

This enables:
1. Validation that delegated permissions are subset of connected scopes
2. UI display of what permissions user can delegate
3. Automatic permission suggestions based on connected services

Usage:
    from app.services.scope_mapper import ScopeMapper
    
    # Get permissions for a scope
    perms = ScopeMapper.get_permissions_for_scope("notion", "read_pages")
    # Returns: ["notion:pages:read", "notion:pages:search"]
    
    # Validate permissions
    is_valid, invalid = ScopeMapper.validate_permissions(
        ["notion:pages:search", "notion:pages:create"],
        [("notion", ["read_pages"])],
    )
    # Returns: (False, ["notion:pages:create"])

Note:
    Permission strings MUST match those used by the Gateway's PermissionMapper.
    See: deeptrail-gateway/app/mcp/permission_mapper.py
"""

import logging
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


class ScopeMapper:
    """Maps OAuth scopes to DeepSecure permission strings.
    
    Used by:
    - DelegationService: Validate delegated permissions against connected scopes
    - Available Permissions endpoint: Show what user can delegate
    
    Design Principle:
    - Scopes are what the user grants during OAuth/service connection
    - Permissions are fine-grained actions on resources
    - Multiple scopes can grant the same permission
    - One scope can grant multiple permissions
    
    Permission String Format:
    - {service}:{resource}:{action}
    - Examples: notion:pages:search, slack:messages:send
    """
    
    # Static mapping: service_id → {scope → [permissions]}
    # NOTE: Permission strings must match Gateway's PermissionMapper
    SCOPE_TO_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
        "notion": {
            # Notion API capabilities (from integration settings)
            "read_content": [
                "notion:pages:read",
                "notion:pages:search",
                "notion:blocks:read",
                "notion:databases:list",
                "notion:databases:query",
            ],
            "update_content": ["notion:pages:update"],
            "insert_content": ["notion:pages:create"],
            # User-friendly aliases (commonly used in demos/tests)
            "read_pages": ["notion:pages:read", "notion:pages:search", "notion:blocks:read"],
            "search_content": ["notion:pages:search"],
            "write_pages": ["notion:pages:create", "notion:pages:update"],
            "read_databases": ["notion:databases:list", "notion:databases:query"],
            # Full access
            "full_access": [
                "notion:pages:read",
                "notion:pages:search",
                "notion:blocks:read",
                "notion:pages:create",
                "notion:pages:update",
                "notion:pages:delete",
                "notion:databases:list",
                "notion:databases:query",
            ],
        },
        "slack": {
            # Official Slack OAuth scopes
            "channels:read": ["slack:channels:list"],
            "channels:history": ["slack:messages:search", "slack:channels:history"],
            "chat:write": ["slack:messages:send"],
            "users:read": ["slack:users:list"],
            "reactions:write": ["slack:reactions:write"],
            "search:read": ["slack:messages:search"],
            # User-friendly aliases
            "read_messages": ["slack:messages:search"],
            "send_messages": ["slack:messages:send"],
            "list_channels": ["slack:channels:list"],
            "list_users": ["slack:users:list"],
            # Full access
            "full_access": [
                "slack:channels:list",
                "slack:channels:history",
                "slack:messages:search",
                "slack:messages:send",
                "slack:users:list",
                "slack:reactions:write",
                "slack:channels:join",
            ],
        },
        "hubspot": {
            # Official HubSpot OAuth scopes
            "crm.objects.contacts.read": ["hubspot:contacts:read", "hubspot:contacts:list"],
            "crm.objects.contacts.write": ["hubspot:contacts:create", "hubspot:contacts:update"],
            "crm.objects.deals.read": ["hubspot:deals:list"],
            "crm.objects.deals.write": ["hubspot:deals:create", "hubspot:deals:update"],
            # User-friendly aliases
            "read_contacts": ["hubspot:contacts:read", "hubspot:contacts:list"],
            "write_contacts": ["hubspot:contacts:create", "hubspot:contacts:update"],
            "read_deals": ["hubspot:deals:list"],
            "write_deals": ["hubspot:deals:create", "hubspot:deals:update"],
            # Full access
            "full_access": [
                "hubspot:contacts:read",
                "hubspot:contacts:list",
                "hubspot:contacts:create",
                "hubspot:contacts:update",
                "hubspot:deals:list",
                "hubspot:deals:create",
                "hubspot:deals:update",
            ],
        },
    }
    
    @classmethod
    def get_permissions_for_scope(
        cls,
        service_id: str,
        scope: str,
    ) -> List[str]:
        """Get permissions granted by a single scope.
        
        Args:
            service_id: Service identifier (e.g., "notion")
            scope: Scope string (e.g., "read_pages")
            
        Returns:
            List of permission strings, empty if scope unknown
            
        Example:
            >>> ScopeMapper.get_permissions_for_scope("notion", "read_pages")
            ["notion:pages:read", "notion:pages:search"]
        """
        service_map = cls.SCOPE_TO_PERMISSIONS.get(service_id.lower(), {})
        return service_map.get(scope, [])
    
    @classmethod
    def get_permissions_for_scopes(
        cls,
        service_id: str,
        scopes: List[str],
    ) -> Set[str]:
        """Get all permissions granted by multiple scopes.
        
        Args:
            service_id: Service identifier
            scopes: List of scope strings
            
        Returns:
            Set of unique permission strings
            
        Example:
            >>> ScopeMapper.get_permissions_for_scopes("notion", ["read_pages", "write_pages"])
            {"notion:pages:read", "notion:pages:search", "notion:pages:create", "notion:pages:update"}
        """
        permissions: Set[str] = set()
        for scope in scopes:
            permissions.update(cls.get_permissions_for_scope(service_id, scope))
        return permissions
    
    @classmethod
    def get_all_allowed_permissions(
        cls,
        connected_services: List[Tuple[str, List[str]]],
    ) -> Set[str]:
        """Get all permissions allowed across multiple connected services.
        
        Args:
            connected_services: List of (service_id, scopes) tuples
            
        Returns:
            Set of all allowed permission strings
            
        Example:
            >>> connected = [
            ...     ("notion", ["read_pages", "search_content"]),
            ...     ("slack", ["channels:read"]),
            ... ]
            >>> ScopeMapper.get_all_allowed_permissions(connected)
            {"notion:pages:read", "notion:pages:search", "slack:channels:list"}
        """
        allowed: Set[str] = set()
        for service_id, scopes in connected_services:
            allowed.update(cls.get_permissions_for_scopes(service_id, scopes))
        return allowed
    
    @classmethod
    def validate_permissions(
        cls,
        requested_permissions: List[str],
        connected_services: List[Tuple[str, List[str]]],
    ) -> Tuple[bool, List[str]]:
        """Validate that requested permissions are allowed by connected scopes.
        
        Args:
            requested_permissions: List of permissions to validate
            connected_services: List of (service_id, scopes) tuples
            
        Returns:
            Tuple of (is_valid, list of invalid permissions)
            
        Example:
            >>> perms = ["notion:pages:search", "notion:pages:create"]
            >>> connected = [("notion", ["read_pages"])]  # No write scope!
            >>> ScopeMapper.validate_permissions(perms, connected)
            (False, ["notion:pages:create"])
        """
        allowed = cls.get_all_allowed_permissions(connected_services)
        invalid = [p for p in requested_permissions if p not in allowed]
        return (len(invalid) == 0, invalid)
    
    @classmethod
    def get_available_permissions_by_service(
        cls,
        connected_services: List[Tuple[str, List[str]]],
    ) -> Dict[str, List[str]]:
        """Get available permissions grouped by service.
        
        Useful for UI display.
        
        Args:
            connected_services: List of (service_id, scopes) tuples
            
        Returns:
            Dict mapping service_id to list of available permissions
            
        Example:
            >>> connected = [("notion", ["read_pages"])]
            >>> ScopeMapper.get_available_permissions_by_service(connected)
            {"notion": ["notion:pages:read", "notion:pages:search"]}
        """
        result: Dict[str, List[str]] = {}
        for service_id, scopes in connected_services:
            perms = cls.get_permissions_for_scopes(service_id, scopes)
            if perms:
                result[service_id] = sorted(list(perms))
        return result
    
    @classmethod
    def get_supported_services(cls) -> List[str]:
        """Get list of services with scope mappings.
        
        Returns:
            List of supported service identifiers
        """
        return list(cls.SCOPE_TO_PERMISSIONS.keys())
    
    @classmethod
    def get_supported_scopes(cls, service_id: str) -> List[str]:
        """Get list of known scopes for a service.
        
        Args:
            service_id: Service identifier
            
        Returns:
            List of known scope strings for the service
        """
        return list(cls.SCOPE_TO_PERMISSIONS.get(service_id.lower(), {}).keys())
    
    @classmethod
    def get_all_permissions_for_service(cls, service_id: str) -> Set[str]:
        """Get all unique permissions for a service (across all scopes).
        
        Args:
            service_id: Service identifier
            
        Returns:
            Set of all permission strings for the service
        """
        all_perms: Set[str] = set()
        service_map = cls.SCOPE_TO_PERMISSIONS.get(service_id.lower(), {})
        for perms in service_map.values():
            all_perms.update(perms)
        return all_perms
