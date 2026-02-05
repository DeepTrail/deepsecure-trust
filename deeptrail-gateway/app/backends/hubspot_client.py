"""
HubSpot MCP Client

Extends BaseMCPClient to provide HubSpot CRM-specific tool operations.
Proxies MCP requests to a HubSpot MCP server backend.

MVP Tools:
- get_contact: Get contact by ID or email
- create_contact: Create a new contact
- update_contact: Update contact properties
- list_contacts: List contacts with filters
- list_deals: List deals in pipeline
- create_deal: Create a new deal
- update_deal: Update deal properties

Usage:
    from app.backends.hubspot_client import HubSpotMCPClient
    
    client = HubSpotMCPClient(connection_manager)
    await client.initialize(auth_token="Bearer xyz")
    
    # Get a contact
    result = await client.get_contact(
        contact_id="12345",
        auth_token="Bearer xyz"
    )
"""

import logging
import re
from typing import Any

from .base_mcp_client import (
    BaseMCPClient,
    BackendConnectionManager,
    ToolResult,
    ToolCallStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# HubSpot-Specific Types
# =============================================================================


class HubSpotObjectType:
    """HubSpot CRM object types."""
    CONTACT = "contact"
    COMPANY = "company"
    DEAL = "deal"
    TICKET = "ticket"


class HubSpotDealStage:
    """Common HubSpot deal stages."""
    APPOINTMENT_SCHEDULED = "appointmentscheduled"
    QUALIFIED_TO_BUY = "qualifiedtobuy"
    PRESENTATION_SCHEDULED = "presentationscheduled"
    DECISION_MAKER_BOUGHT_IN = "decisionmakerboughtin"
    CONTRACT_SENT = "contractsent"
    CLOSED_WON = "closedwon"
    CLOSED_LOST = "closedlost"


# =============================================================================
# Exceptions
# =============================================================================


class HubSpotClientError(Exception):
    """HubSpot-specific client error."""
    pass


class HubSpotRateLimitError(HubSpotClientError):
    """HubSpot API rate limit exceeded."""
    pass


class HubSpotObjectNotFoundError(HubSpotClientError):
    """HubSpot object (contact, deal, etc.) not found."""
    pass


class HubSpotValidationError(HubSpotClientError):
    """HubSpot property validation failed."""
    pass


# =============================================================================
# HubSpot MCP Client
# =============================================================================


class HubSpotMCPClient(BaseMCPClient):
    """
    MCP client for HubSpot CRM backend.
    
    Provides HubSpot-specific:
    - Argument validation for HubSpot tools
    - Result transformation for HubSpot responses
    - Error handling for HubSpot API errors
    
    Attributes:
        backend_id: Always "hubspot"
    """
    
    # HubSpot ID pattern: numeric string
    HUBSPOT_ID_PATTERN = re.compile(r"^\d+$")
    
    # Email pattern for contact lookup
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    
    # Tool-specific argument schemas for validation
    TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
        "get_contact": {
            "required": [],  # Either contact_id or email required
            "optional": ["contact_id", "email", "properties"],
            "one_of": ["contact_id", "email"],
        },
        "create_contact": {
            "required": ["properties"],
            "optional": [],
        },
        "update_contact": {
            "required": ["contact_id", "properties"],
            "optional": [],
        },
        "list_contacts": {
            "required": [],
            "optional": ["limit", "after", "properties", "filter_groups", "sorts"],
        },
        "list_deals": {
            "required": [],
            "optional": ["limit", "after", "properties", "filter_groups", "sorts"],
        },
        "create_deal": {
            "required": ["properties"],
            "optional": ["associations"],
        },
        "update_deal": {
            "required": ["deal_id", "properties"],
            "optional": [],
        },
    }
    
    # Common HubSpot contact properties
    CONTACT_PROPERTIES = [
        "email", "firstname", "lastname", "phone", "company",
        "website", "lifecyclestage", "hs_lead_status",
    ]
    
    # Common HubSpot deal properties
    DEAL_PROPERTIES = [
        "dealname", "amount", "dealstage", "pipeline",
        "closedate", "hs_priority", "hubspot_owner_id",
    ]
    
    @property
    def backend_id(self) -> str:
        """Return the HubSpot backend identifier."""
        return "hubspot"
    
    # ─────────────────────────────────────────────────────────────────────────
    # Argument Validation
    # ─────────────────────────────────────────────────────────────────────────
    
    def validate_tool_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate and transform HubSpot tool arguments.
        
        Args:
            tool_name: HubSpot tool name
            arguments: Raw arguments
            
        Returns:
            Validated arguments
            
        Raises:
            ValueError: If required arguments missing or invalid
        """
        schema = self.TOOL_SCHEMAS.get(tool_name)
        
        if schema is None:
            # Unknown tool - pass through to backend
            logger.warning(f"No schema for HubSpot tool: {tool_name}")
            return arguments
        
        # Check required arguments
        missing = [
            arg for arg in schema["required"]
            if arg not in arguments or arguments[arg] is None
        ]
        
        if missing:
            raise ValueError(
                f"Missing required arguments for {tool_name}: {', '.join(missing)}"
            )
        
        # Check one_of requirement (at least one must be present)
        if "one_of" in schema:
            one_of = schema["one_of"]
            has_one = any(
                arg in arguments and arguments[arg] is not None
                for arg in one_of
            )
            if not has_one:
                raise ValueError(
                    f"At least one of {', '.join(one_of)} is required for {tool_name}"
                )
        
        # Validate specific arguments
        validated = dict(arguments)
        
        # Validate HubSpot IDs
        if "contact_id" in validated and validated["contact_id"]:
            validated["contact_id"] = self._validate_hubspot_id(
                validated["contact_id"], "contact_id"
            )
        
        if "deal_id" in validated and validated["deal_id"]:
            validated["deal_id"] = self._validate_hubspot_id(
                validated["deal_id"], "deal_id"
            )
        
        # Validate email format
        if "email" in validated and validated["email"]:
            validated["email"] = self._validate_email(validated["email"])
        
        # Validate limit range
        if "limit" in validated:
            limit = validated["limit"]
            if not isinstance(limit, int) or limit < 1 or limit > 100:
                raise ValueError("limit must be integer between 1 and 100")
        
        # Validate properties based on tool type
        # For write operations, properties should be a dict
        # For read operations, properties should be a list of property names
        if "properties" in validated:
            props = validated["properties"]
            write_tools = ["create_contact", "update_contact", "create_deal", "update_deal"]
            if tool_name in write_tools:
                if not isinstance(props, dict):
                    raise ValueError("properties must be a dictionary")
            else:
                # Read operations can use list of property names
                if not isinstance(props, (list, dict)):
                    raise ValueError("properties must be a list or dictionary")
        
        return validated
    
    def _validate_hubspot_id(self, hubspot_id: str | int, field_name: str) -> str:
        """
        Validate HubSpot object ID format.
        
        HubSpot IDs are numeric strings.
        
        Args:
            hubspot_id: HubSpot object ID
            field_name: Field name for error messages
            
        Returns:
            Validated ID as string
            
        Raises:
            ValueError: If format is invalid
        """
        # Convert to string if int
        id_str = str(hubspot_id)
        
        if not id_str:
            raise ValueError(f"{field_name} cannot be empty")
        
        if not self.HUBSPOT_ID_PATTERN.match(id_str):
            raise ValueError(
                f"Invalid {field_name}: {hubspot_id}. Must be a numeric ID."
            )
        
        return id_str
    
    def _validate_email(self, email: str) -> str:
        """
        Validate email format.
        
        Args:
            email: Email address
            
        Returns:
            Validated email (lowercase)
            
        Raises:
            ValueError: If format is invalid
        """
        if not email:
            raise ValueError("Email cannot be empty")
        
        email_lower = email.lower().strip()
        
        if not self.EMAIL_PATTERN.match(email_lower):
            raise ValueError(f"Invalid email format: {email}")
        
        return email_lower
    
    # ─────────────────────────────────────────────────────────────────────────
    # Result Transformation
    # ─────────────────────────────────────────────────────────────────────────
    
    def transform_tool_result(
        self,
        tool_name: str,
        result: ToolResult,
    ) -> ToolResult:
        """
        Transform HubSpot tool results.
        
        Handles:
        - Rate limit errors (429)
        - Object not found errors (404)
        - Validation errors (400)
        - Property validation errors
        
        Args:
            tool_name: Tool that was called
            result: Raw result from backend
            
        Returns:
            Transformed result
        """
        # Check for HubSpot-specific errors in the result
        if result.is_error:
            result = self._transform_error(tool_name, result)
        
        return result
    
    def _transform_error(self, tool_name: str, result: ToolResult) -> ToolResult:
        """Transform HubSpot error responses."""
        error_msg = result.error_message or ""
        error_lower = error_msg.lower()
        
        # Detect rate limiting (HubSpot returns 429)
        if "rate limit" in error_lower or "429" in error_msg or "too many requests" in error_lower:
            logger.warning(f"HubSpot rate limit hit for {tool_name}")
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message="HubSpot rate limit exceeded. Please wait before retrying.",
                content=[{"type": "text", "text": "Rate limit exceeded. Retry after a moment."}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect object not found (404)
        if "not found" in error_lower or "404" in error_msg or "does not exist" in error_lower:
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=f"HubSpot object not found: {error_msg}",
                content=[{"type": "text", "text": "Object not found in HubSpot"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect validation errors (400)
        if "validation" in error_lower or "invalid" in error_lower or "400" in error_msg:
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=f"HubSpot validation error: {error_msg}",
                content=[{"type": "text", "text": f"Validation error: {error_msg}"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect property errors
        if "property" in error_lower and ("doesn't exist" in error_lower or "not valid" in error_lower):
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=f"Invalid HubSpot property: {error_msg}",
                content=[{"type": "text", "text": f"Property error: {error_msg}"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect auth errors
        if "unauthorized" in error_lower or "401" in error_msg or "forbidden" in error_lower:
            return ToolResult(
                status=ToolCallStatus.UNAUTHORIZED,
                is_error=True,
                error_message="HubSpot authentication failed or insufficient permissions",
                content=[{"type": "text", "text": "Authentication or permission error"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        return result
    
    # ─────────────────────────────────────────────────────────────────────────
    # Convenience Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    async def get_contact(
        self,
        contact_id: str | None = None,
        email: str | None = None,
        properties: list[str] | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Get a contact by ID or email.
        
        Args:
            contact_id: HubSpot contact ID
            email: Contact email address
            properties: Properties to return (defaults to common props)
            auth_token: Authorization token
            
        Returns:
            ToolResult with contact data
        """
        if not contact_id and not email:
            raise ValueError("Either contact_id or email is required")
        
        arguments: dict[str, Any] = {}
        if contact_id:
            arguments["contact_id"] = contact_id
        if email:
            arguments["email"] = email
        if properties:
            arguments["properties"] = properties
        else:
            arguments["properties"] = self.CONTACT_PROPERTIES
        
        return await self.call_tool("get_contact", arguments, auth_token=auth_token)
    
    async def create_contact(
        self,
        email: str,
        firstname: str | None = None,
        lastname: str | None = None,
        properties: dict[str, Any] | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Create a new contact in HubSpot.
        
        Args:
            email: Contact email (required)
            firstname: First name
            lastname: Last name
            properties: Additional properties
            auth_token: Authorization token
            
        Returns:
            ToolResult with created contact data
        """
        props = dict(properties) if properties else {}
        props["email"] = email
        if firstname:
            props["firstname"] = firstname
        if lastname:
            props["lastname"] = lastname
        
        return await self.call_tool(
            "create_contact",
            {"properties": props},
            auth_token=auth_token,
        )
    
    async def update_contact(
        self,
        contact_id: str,
        properties: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Update a contact's properties.
        
        Args:
            contact_id: HubSpot contact ID
            properties: Properties to update
            auth_token: Authorization token
            
        Returns:
            ToolResult with updated contact data
        """
        return await self.call_tool(
            "update_contact",
            {"contact_id": contact_id, "properties": properties},
            auth_token=auth_token,
        )
    
    async def list_contacts(
        self,
        limit: int = 10,
        properties: list[str] | None = None,
        after: str | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List contacts in HubSpot.
        
        Args:
            limit: Maximum contacts to return (1-100)
            properties: Properties to return
            after: Cursor for pagination
            auth_token: Authorization token
            
        Returns:
            ToolResult with contact list
        """
        arguments: dict[str, Any] = {"limit": limit}
        if properties:
            arguments["properties"] = properties
        else:
            arguments["properties"] = self.CONTACT_PROPERTIES
        if after:
            arguments["after"] = after
        
        return await self.call_tool("list_contacts", arguments, auth_token=auth_token)
    
    async def list_deals(
        self,
        limit: int = 10,
        properties: list[str] | None = None,
        after: str | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List deals in HubSpot.
        
        Args:
            limit: Maximum deals to return (1-100)
            properties: Properties to return
            after: Cursor for pagination
            auth_token: Authorization token
            
        Returns:
            ToolResult with deal list
        """
        arguments: dict[str, Any] = {"limit": limit}
        if properties:
            arguments["properties"] = properties
        else:
            arguments["properties"] = self.DEAL_PROPERTIES
        if after:
            arguments["after"] = after
        
        return await self.call_tool("list_deals", arguments, auth_token=auth_token)
    
    async def create_deal(
        self,
        dealname: str,
        amount: float | None = None,
        dealstage: str | None = None,
        properties: dict[str, Any] | None = None,
        associations: list[dict[str, Any]] | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Create a new deal in HubSpot.
        
        Args:
            dealname: Deal name (required)
            amount: Deal amount
            dealstage: Deal stage
            properties: Additional properties
            associations: Associations to other objects
            auth_token: Authorization token
            
        Returns:
            ToolResult with created deal data
        """
        props = dict(properties) if properties else {}
        props["dealname"] = dealname
        if amount is not None:
            props["amount"] = str(amount)
        if dealstage:
            props["dealstage"] = dealstage
        
        arguments: dict[str, Any] = {"properties": props}
        if associations:
            arguments["associations"] = associations
        
        return await self.call_tool(
            "create_deal",
            arguments,
            auth_token=auth_token,
        )
    
    async def update_deal(
        self,
        deal_id: str,
        properties: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Update a deal's properties.
        
        Args:
            deal_id: HubSpot deal ID
            properties: Properties to update
            auth_token: Authorization token
            
        Returns:
            ToolResult with updated deal data
        """
        return await self.call_tool(
            "update_deal",
            {"deal_id": deal_id, "properties": properties},
            auth_token=auth_token,
        )


# =============================================================================
# Factory Function
# =============================================================================


def create_hubspot_client(
    connection_manager: BackendConnectionManager,
    **kwargs: Any,
) -> HubSpotMCPClient:
    """
    Create a HubSpot MCP client.
    
    Args:
        connection_manager: Backend connection manager
        **kwargs: Additional client options
        
    Returns:
        Configured HubSpotMCPClient
    """
    return HubSpotMCPClient(connection_manager, **kwargs)
