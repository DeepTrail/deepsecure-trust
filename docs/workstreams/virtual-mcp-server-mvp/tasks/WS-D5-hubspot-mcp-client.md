# Task: WS-D5 Implement HubSpot MCP Client

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-D: Backend Connectors |
| **Dependencies** | D2 (Base MCP Client) ✅ |
| **Blocked By** | None (D2 complete) |
| **Assigned** | - |
| **Created** | February 5, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 5 |
| **Target Worktree** | `vmcp-gateway` |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 1: Unified Connection, Demo 3: Delegation Execution |
| **Validates User Journey Step** | Step 8: Agent Executes Task |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] D2 (Base MCP Client) is complete
- [x] D1 (Backend Connection Manager) is complete
- [x] `BaseMCPClient` class available in `app/backends/base_mcp_client.py`
- [x] `BackendConnectionManager` available for HTTP transport
- [ ] HubSpot API documentation reviewed for tool schemas

---

## Task Description

Implement the HubSpot MCP client that extends `BaseMCPClient` to provide HubSpot-specific tool operations. This enables the gateway to proxy MCP requests to a HubSpot MCP server backend, allowing agents to manage CRM data.

### Context

From the MVP design (Section 2.6 - Step 8: Agent Executes Task):

```
Sarah's agent needs to access HubSpot CRM tools:
- get_contact: Retrieve contact information
- update_contact: Update contact properties
- list_deals: List deals in the pipeline

The HubSpot MCP client:
1. Extends BaseMCPClient with backend_id = "hubspot"
2. Provides HubSpot-specific argument validation
3. Transforms HubSpot API responses to standard MCP format
4. Handles HubSpot-specific error cases (rate limits, validation)
```

### MVP HubSpot Tools

| Tool Name | Permission | Description |
|-----------|------------|-------------|
| `get_contact` | `hubspot:contacts:read` | Get contact by ID or email |
| `create_contact` | `hubspot:contacts:create` | Create a new contact |
| `update_contact` | `hubspot:contacts:update` | Update contact properties |
| `list_contacts` | `hubspot:contacts:list` | List contacts with filters |
| `list_deals` | `hubspot:deals:list` | List deals in pipeline |
| `create_deal` | `hubspot:deals:create` | Create a new deal |
| `update_deal` | `hubspot:deals:update` | Update deal properties |

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/backends/hubspot_client.py` | **CREATE** | HubSpot MCP client implementation |
| `deeptrail-gateway/app/backends/__init__.py` | **MODIFY** | Export HubSpotMCPClient |
| `deeptrail-gateway/tests/backends/test_hubspot_client.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. HubSpot MCP Client

Create `deeptrail-gateway/app/backends/hubspot_client.py`:

```python
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
    result = await client.call_tool(
        "get_contact",
        {"contact_id": "12345"},
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
    TOOL_SCHEMAS = {
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
        
        # Validate properties is a dict
        if "properties" in validated:
            props = validated["properties"]
            if not isinstance(props, dict):
                raise ValueError("properties must be a dictionary")
        
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
        props = properties or {}
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
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List contacts in HubSpot.
        
        Args:
            limit: Maximum contacts to return (1-100)
            properties: Properties to return
            auth_token: Authorization token
            
        Returns:
            ToolResult with contact list
        """
        arguments: dict[str, Any] = {"limit": limit}
        if properties:
            arguments["properties"] = properties
        else:
            arguments["properties"] = self.CONTACT_PROPERTIES
        
        return await self.call_tool("list_contacts", arguments, auth_token=auth_token)
    
    async def list_deals(
        self,
        limit: int = 10,
        properties: list[str] | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List deals in HubSpot.
        
        Args:
            limit: Maximum deals to return (1-100)
            properties: Properties to return
            auth_token: Authorization token
            
        Returns:
            ToolResult with deal list
        """
        arguments: dict[str, Any] = {"limit": limit}
        if properties:
            arguments["properties"] = properties
        else:
            arguments["properties"] = self.DEAL_PROPERTIES
        
        return await self.call_tool("list_deals", arguments, auth_token=auth_token)
    
    async def create_deal(
        self,
        dealname: str,
        amount: float | None = None,
        dealstage: str | None = None,
        properties: dict[str, Any] | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Create a new deal in HubSpot.
        
        Args:
            dealname: Deal name (required)
            amount: Deal amount
            dealstage: Deal stage
            properties: Additional properties
            auth_token: Authorization token
            
        Returns:
            ToolResult with created deal data
        """
        props = properties or {}
        props["dealname"] = dealname
        if amount is not None:
            props["amount"] = str(amount)
        if dealstage:
            props["dealstage"] = dealstage
        
        return await self.call_tool(
            "create_deal",
            {"properties": props},
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
```

### 2. Update `__init__.py`

Add to `deeptrail-gateway/app/backends/__init__.py`:

```python
from .hubspot_client import (
    HubSpotMCPClient,
    HubSpotClientError,
    HubSpotRateLimitError,
    HubSpotObjectNotFoundError,
    HubSpotValidationError,
    create_hubspot_client,
)

__all__ = [
    # ... existing exports ...
    # HubSpot client
    "HubSpotMCPClient",
    "HubSpotClientError",
    "HubSpotRateLimitError",
    "HubSpotObjectNotFoundError",
    "HubSpotValidationError",
    "create_hubspot_client",
]
```

---

## Acceptance Criteria

### Implementation Criteria

- [ ] `HubSpotMCPClient` extends `BaseMCPClient`
- [ ] `backend_id` property returns `"hubspot"`
- [ ] Implements `validate_tool_arguments()` for HubSpot tools
- [ ] Implements `transform_tool_result()` for HubSpot responses

### Tool Support Criteria

- [ ] `get_contact` tool supported with contact_id or email
- [ ] `create_contact` tool supported with properties
- [ ] `update_contact` tool supported with contact_id and properties
- [ ] `list_contacts` tool supported with pagination
- [ ] `list_deals` tool supported with pagination
- [ ] `create_deal` tool supported with properties
- [ ] `update_deal` tool supported with deal_id and properties

### Validation Criteria

- [ ] Missing required arguments raise `ValueError`
- [ ] `get_contact` requires either contact_id OR email
- [ ] HubSpot ID validated (numeric string)
- [ ] Email format validated
- [ ] limit validated (1-100)
- [ ] properties validated as dict

### Error Handling Criteria

- [ ] Rate limit errors (429) transformed
- [ ] Not found errors (404) transformed
- [ ] Validation errors (400) transformed
- [ ] Property errors transformed
- [ ] Auth errors (401/403) transformed
- [ ] Errors logged at appropriate levels

### Test Criteria

- [ ] Test `backend_id` property
- [ ] Test argument validation for each tool
- [ ] Test HubSpot ID validation
- [ ] Test email validation
- [ ] Test one_of requirement (contact_id OR email)
- [ ] Test error transformation
- [ ] Test convenience methods
- [ ] All tests pass with `pytest tests/backends/test_hubspot_client.py`

---

## Test Cases

Create `deeptrail-gateway/tests/backends/test_hubspot_client.py`:

```python
"""Tests for HubSpot MCP client (D5)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.backends.hubspot_client import (
    HubSpotMCPClient,
    HubSpotClientError,
    create_hubspot_client,
)
from app.backends.base_mcp_client import ToolResult, ToolCallStatus


@pytest.fixture
def mock_connection_manager():
    """Create mock connection manager."""
    manager = MagicMock()
    manager.send_initialize = AsyncMock()
    manager.send_tools_list = AsyncMock()
    manager.send_tools_call = AsyncMock()
    manager.check_backend_health = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def hubspot_client(mock_connection_manager):
    """Create HubSpot client with mock connection manager."""
    return HubSpotMCPClient(mock_connection_manager)


class TestHubSpotMCPClient:
    """Tests for HubSpotMCPClient."""
    
    def test_backend_id(self, hubspot_client):
        """Test backend_id is 'hubspot'."""
        assert hubspot_client.backend_id == "hubspot"
    
    def test_repr(self, hubspot_client):
        """Test string representation."""
        assert "HubSpotMCPClient" in repr(hubspot_client)
        assert "hubspot" in repr(hubspot_client)


class TestArgumentValidation:
    """Tests for argument validation."""
    
    def test_get_contact_requires_one_of(self, hubspot_client):
        """Test get_contact requires contact_id or email."""
        with pytest.raises(ValueError) as exc:
            hubspot_client.validate_tool_arguments("get_contact", {})
        assert "contact_id" in str(exc.value) or "email" in str(exc.value)
    
    def test_get_contact_with_id(self, hubspot_client):
        """Test get_contact with contact_id."""
        args = {"contact_id": "12345"}
        result = hubspot_client.validate_tool_arguments("get_contact", args)
        assert result["contact_id"] == "12345"
    
    def test_get_contact_with_email(self, hubspot_client):
        """Test get_contact with email."""
        args = {"email": "test@example.com"}
        result = hubspot_client.validate_tool_arguments("get_contact", args)
        assert result["email"] == "test@example.com"
    
    def test_create_contact_requires_properties(self, hubspot_client):
        """Test create_contact requires properties."""
        with pytest.raises(ValueError) as exc:
            hubspot_client.validate_tool_arguments("create_contact", {})
        assert "properties" in str(exc.value)
    
    def test_update_contact_requires_id_and_properties(self, hubspot_client):
        """Test update_contact requires contact_id and properties."""
        with pytest.raises(ValueError):
            hubspot_client.validate_tool_arguments("update_contact", {"contact_id": "123"})
    
    def test_list_contacts_no_required(self, hubspot_client):
        """Test list_contacts has no required args."""
        result = hubspot_client.validate_tool_arguments("list_contacts", {})
        assert result == {}
    
    def test_limit_validation(self, hubspot_client):
        """Test limit must be 1-100."""
        with pytest.raises(ValueError) as exc:
            hubspot_client.validate_tool_arguments("list_contacts", {"limit": 101})
        assert "limit" in str(exc.value)
    
    def test_properties_must_be_dict(self, hubspot_client):
        """Test properties must be a dictionary."""
        with pytest.raises(ValueError):
            hubspot_client.validate_tool_arguments(
                "create_contact", {"properties": ["email"]}
            )


class TestHubSpotIDValidation:
    """Tests for HubSpot ID validation."""
    
    def test_valid_numeric_id(self, hubspot_client):
        """Test valid numeric ID."""
        result = hubspot_client._validate_hubspot_id("12345", "contact_id")
        assert result == "12345"
    
    def test_valid_int_id(self, hubspot_client):
        """Test integer ID converted to string."""
        result = hubspot_client._validate_hubspot_id(12345, "contact_id")
        assert result == "12345"
    
    def test_invalid_non_numeric_id(self, hubspot_client):
        """Test non-numeric ID rejected."""
        with pytest.raises(ValueError) as exc:
            hubspot_client._validate_hubspot_id("abc123", "contact_id")
        assert "numeric" in str(exc.value).lower()
    
    def test_empty_id(self, hubspot_client):
        """Test empty ID rejected."""
        with pytest.raises(ValueError):
            hubspot_client._validate_hubspot_id("", "contact_id")


class TestEmailValidation:
    """Tests for email validation."""
    
    def test_valid_email(self, hubspot_client):
        """Test valid email."""
        result = hubspot_client._validate_email("test@example.com")
        assert result == "test@example.com"
    
    def test_email_lowercased(self, hubspot_client):
        """Test email is lowercased."""
        result = hubspot_client._validate_email("Test@Example.COM")
        assert result == "test@example.com"
    
    def test_email_trimmed(self, hubspot_client):
        """Test email is trimmed."""
        result = hubspot_client._validate_email("  test@example.com  ")
        assert result == "test@example.com"
    
    def test_invalid_email(self, hubspot_client):
        """Test invalid email rejected."""
        with pytest.raises(ValueError):
            hubspot_client._validate_email("not-an-email")
    
    def test_empty_email(self, hubspot_client):
        """Test empty email rejected."""
        with pytest.raises(ValueError):
            hubspot_client._validate_email("")


class TestResultTransformation:
    """Tests for result transformation."""
    
    def test_transform_rate_limit_error(self, hubspot_client):
        """Test rate limit error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="rate limit exceeded (429)",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("list_contacts", error_result)
        
        assert result.is_error
        assert "rate limit" in result.error_message.lower()
    
    def test_transform_not_found_error(self, hubspot_client):
        """Test not found error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="Contact not found (404)",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("get_contact", error_result)
        
        assert result.is_error
        assert "not found" in result.error_message.lower()
    
    def test_transform_validation_error(self, hubspot_client):
        """Test validation error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="Validation failed: invalid property",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("create_contact", error_result)
        
        assert result.is_error
        assert "validation" in result.error_message.lower()
    
    def test_transform_auth_error(self, hubspot_client):
        """Test auth error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="unauthorized (401)",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("list_deals", error_result)
        
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED
    
    def test_successful_result_unchanged(self, hubspot_client):
        """Test successful results pass through."""
        success_result = ToolResult(
            status=ToolCallStatus.SUCCESS,
            is_error=False,
            content=[{"type": "text", "text": "Contact data"}],
        )
        
        result = hubspot_client.transform_tool_result("get_contact", success_result)
        
        assert not result.is_error
        assert result.content == success_result.content


class TestConvenienceMethods:
    """Tests for convenience methods."""
    
    @pytest.mark.asyncio
    async def test_get_contact_by_id(self, hubspot_client, mock_connection_manager):
        """Test get_contact by ID."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "contact"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        result = await hubspot_client.get_contact(
            contact_id="12345",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "get_contact"
        assert call_args.kwargs["arguments"]["contact_id"] == "12345"
    
    @pytest.mark.asyncio
    async def test_get_contact_by_email(self, hubspot_client, mock_connection_manager):
        """Test get_contact by email."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "contact"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        result = await hubspot_client.get_contact(
            email="test@example.com",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["arguments"]["email"] == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_create_contact(self, hubspot_client, mock_connection_manager):
        """Test create_contact."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "created"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        result = await hubspot_client.create_contact(
            email="new@example.com",
            firstname="John",
            lastname="Doe",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "create_contact"
        props = call_args.kwargs["arguments"]["properties"]
        assert props["email"] == "new@example.com"
        assert props["firstname"] == "John"
    
    @pytest.mark.asyncio
    async def test_list_deals(self, hubspot_client, mock_connection_manager):
        """Test list_deals."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "deals"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        result = await hubspot_client.list_deals(
            limit=20,
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "list_deals"
        assert call_args.kwargs["arguments"]["limit"] == 20


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_hubspot_client(self, mock_connection_manager):
        """Test create_hubspot_client factory."""
        client = create_hubspot_client(mock_connection_manager)
        
        assert isinstance(client, HubSpotMCPClient)
        assert client.backend_id == "hubspot"
```

---

## Post-Conditions

After completing this task:

- [ ] `HubSpotMCPClient` is available in `app/backends/`
- [ ] Gateway can proxy MCP requests to HubSpot backend
- [ ] HubSpot tool arguments are validated before sending
- [ ] HubSpot errors are transformed to user-friendly messages
- [ ] D6 (Backend Router) can route to HubSpot client
- [ ] Demo 1 (Unified Connection) can include HubSpot tools
- [ ] F8 (Cross-service workflow) can use HubSpot
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.6 Step 8: Agent Executes Task
- **Upstream Tasks**:
  - [WS-D2: Base MCP Client](./WS-D2-base-mcp-client.md) - Provides base class
  - [WS-D1: Connection Manager](./WS-D1-backend-connection-manager.md) - HTTP transport
- **Parallel Tasks**:
  - [WS-D3: Notion MCP Client](./WS-D3-notion-mcp-client.md) - Similar implementation
  - [WS-D4: Slack MCP Client](./WS-D4-slack-mcp-client.md) - Similar implementation
- **Downstream Tasks**:
  - [WS-D6: Backend Router](./WS-D6-backend-router.md) - Routes to this client
  - [WS-F8: Cross-Service Workflow](./WS-F8-cross-service-demo.md) - Uses HubSpot
- **External References**:
  - [HubSpot CRM API Reference](https://developers.hubspot.com/docs/api/crm)

---

## Notes

- HubSpot IDs are numeric strings (not UUIDs like Notion)
- `get_contact` supports lookup by either ID or email (one_of requirement)
- Email validation is important for contact creation/lookup
- HubSpot has strict rate limits - handle 429 errors gracefully
- Property names must match HubSpot schema (case-sensitive)
- The MCP server backend handles actual HubSpot API authentication
- HubSpot is used in Demo F8 for cross-service workflow (Notion → HubSpot)
