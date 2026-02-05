"""Tests for HubSpot MCP client (WS-D5)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.backends.hubspot_client import (
    HubSpotMCPClient,
    HubSpotClientError,
    HubSpotRateLimitError,
    HubSpotObjectNotFoundError,
    HubSpotValidationError,
    HubSpotObjectType,
    HubSpotDealStage,
    create_hubspot_client,
)
from app.backends.base_mcp_client import ToolResult, ToolCallStatus


# =============================================================================
# Fixtures
# =============================================================================


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


# =============================================================================
# Basic Properties Tests
# =============================================================================


class TestHubSpotMCPClient:
    """Tests for HubSpotMCPClient basic properties."""
    
    def test_backend_id(self, hubspot_client):
        """Test backend_id is 'hubspot'."""
        assert hubspot_client.backend_id == "hubspot"
    
    def test_repr(self, hubspot_client):
        """Test string representation."""
        repr_str = repr(hubspot_client)
        assert "HubSpotMCPClient" in repr_str
        assert "hubspot" in repr_str
    
    def test_is_not_initialized_by_default(self, hubspot_client):
        """Test client is not initialized by default."""
        assert not hubspot_client.is_initialized
    
    def test_server_info_is_none_before_initialize(self, hubspot_client):
        """Test server_info is None before initialize."""
        assert hubspot_client.server_info is None
    
    def test_contact_properties_defined(self, hubspot_client):
        """Test CONTACT_PROPERTIES is defined."""
        assert len(hubspot_client.CONTACT_PROPERTIES) > 0
        assert "email" in hubspot_client.CONTACT_PROPERTIES
        assert "firstname" in hubspot_client.CONTACT_PROPERTIES
    
    def test_deal_properties_defined(self, hubspot_client):
        """Test DEAL_PROPERTIES is defined."""
        assert len(hubspot_client.DEAL_PROPERTIES) > 0
        assert "dealname" in hubspot_client.DEAL_PROPERTIES
        assert "amount" in hubspot_client.DEAL_PROPERTIES


# =============================================================================
# Argument Validation Tests
# =============================================================================


class TestArgumentValidation:
    """Tests for argument validation."""
    
    # ─────────────────────────────────────────────────────────────────────────
    # get_contact
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_get_contact_requires_one_of(self, hubspot_client):
        """Test get_contact requires contact_id or email."""
        with pytest.raises(ValueError) as exc:
            hubspot_client.validate_tool_arguments("get_contact", {})
        assert "contact_id" in str(exc.value) or "email" in str(exc.value)
    
    def test_get_contact_with_none_values(self, hubspot_client):
        """Test get_contact rejects None values for one_of."""
        with pytest.raises(ValueError):
            hubspot_client.validate_tool_arguments(
                "get_contact", {"contact_id": None, "email": None}
            )
    
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
    
    def test_get_contact_with_both(self, hubspot_client):
        """Test get_contact with both contact_id and email."""
        args = {"contact_id": "12345", "email": "test@example.com"}
        result = hubspot_client.validate_tool_arguments("get_contact", args)
        assert result["contact_id"] == "12345"
        assert result["email"] == "test@example.com"
    
    def test_get_contact_with_properties(self, hubspot_client):
        """Test get_contact with properties."""
        args = {"contact_id": "12345", "properties": ["email", "firstname"]}
        result = hubspot_client.validate_tool_arguments("get_contact", args)
        assert result["properties"] == ["email", "firstname"]
    
    # ─────────────────────────────────────────────────────────────────────────
    # create_contact
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_create_contact_requires_properties(self, hubspot_client):
        """Test create_contact requires properties."""
        with pytest.raises(ValueError) as exc:
            hubspot_client.validate_tool_arguments("create_contact", {})
        assert "properties" in str(exc.value)
    
    def test_create_contact_with_properties(self, hubspot_client):
        """Test create_contact with properties."""
        args = {"properties": {"email": "new@example.com", "firstname": "John"}}
        result = hubspot_client.validate_tool_arguments("create_contact", args)
        assert result["properties"]["email"] == "new@example.com"
    
    def test_create_contact_properties_must_be_dict(self, hubspot_client):
        """Test properties must be a dictionary."""
        with pytest.raises(ValueError) as exc:
            hubspot_client.validate_tool_arguments(
                "create_contact", {"properties": ["email"]}
            )
        assert "dictionary" in str(exc.value)
    
    def test_create_contact_properties_none_invalid(self, hubspot_client):
        """Test properties None is invalid."""
        with pytest.raises(ValueError):
            hubspot_client.validate_tool_arguments(
                "create_contact", {"properties": None}
            )
    
    # ─────────────────────────────────────────────────────────────────────────
    # update_contact
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_update_contact_requires_id_and_properties(self, hubspot_client):
        """Test update_contact requires contact_id and properties."""
        with pytest.raises(ValueError):
            hubspot_client.validate_tool_arguments("update_contact", {"contact_id": "123"})
    
    def test_update_contact_requires_properties(self, hubspot_client):
        """Test update_contact requires properties."""
        with pytest.raises(ValueError) as exc:
            hubspot_client.validate_tool_arguments(
                "update_contact", {"contact_id": "12345"}
            )
        assert "properties" in str(exc.value)
    
    def test_update_contact_with_all_required(self, hubspot_client):
        """Test update_contact with all required args."""
        args = {"contact_id": "12345", "properties": {"firstname": "Jane"}}
        result = hubspot_client.validate_tool_arguments("update_contact", args)
        assert result["contact_id"] == "12345"
        assert result["properties"]["firstname"] == "Jane"
    
    # ─────────────────────────────────────────────────────────────────────────
    # list_contacts
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_list_contacts_no_required(self, hubspot_client):
        """Test list_contacts has no required args."""
        result = hubspot_client.validate_tool_arguments("list_contacts", {})
        assert result == {}
    
    def test_list_contacts_with_limit(self, hubspot_client):
        """Test list_contacts with limit."""
        args = {"limit": 50}
        result = hubspot_client.validate_tool_arguments("list_contacts", args)
        assert result["limit"] == 50
    
    def test_list_contacts_with_all_options(self, hubspot_client):
        """Test list_contacts with all optional args."""
        args = {
            "limit": 25,
            "after": "cursor123",
            "properties": ["email", "firstname"],
            "filter_groups": [{"filters": []}],
            "sorts": [{"propertyName": "createdate"}],
        }
        result = hubspot_client.validate_tool_arguments("list_contacts", args)
        assert result["after"] == "cursor123"
        assert result["sorts"] == args["sorts"]
    
    # ─────────────────────────────────────────────────────────────────────────
    # list_deals
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_list_deals_no_required(self, hubspot_client):
        """Test list_deals has no required args."""
        result = hubspot_client.validate_tool_arguments("list_deals", {})
        assert result == {}
    
    def test_list_deals_with_limit(self, hubspot_client):
        """Test list_deals with limit."""
        args = {"limit": 30}
        result = hubspot_client.validate_tool_arguments("list_deals", args)
        assert result["limit"] == 30
    
    # ─────────────────────────────────────────────────────────────────────────
    # create_deal
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_create_deal_requires_properties(self, hubspot_client):
        """Test create_deal requires properties."""
        with pytest.raises(ValueError) as exc:
            hubspot_client.validate_tool_arguments("create_deal", {})
        assert "properties" in str(exc.value)
    
    def test_create_deal_with_properties(self, hubspot_client):
        """Test create_deal with properties."""
        args = {"properties": {"dealname": "New Deal", "amount": "1000"}}
        result = hubspot_client.validate_tool_arguments("create_deal", args)
        assert result["properties"]["dealname"] == "New Deal"
    
    def test_create_deal_with_associations(self, hubspot_client):
        """Test create_deal with associations."""
        args = {
            "properties": {"dealname": "Deal with Contact"},
            "associations": [{"to": {"id": "123"}, "types": [{"associationTypeId": 1}]}],
        }
        result = hubspot_client.validate_tool_arguments("create_deal", args)
        assert result["associations"] == args["associations"]
    
    # ─────────────────────────────────────────────────────────────────────────
    # update_deal
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_update_deal_requires_id_and_properties(self, hubspot_client):
        """Test update_deal requires deal_id and properties."""
        with pytest.raises(ValueError):
            hubspot_client.validate_tool_arguments("update_deal", {"deal_id": "123"})
    
    def test_update_deal_with_all_required(self, hubspot_client):
        """Test update_deal with all required args."""
        args = {"deal_id": "67890", "properties": {"dealstage": "closedwon"}}
        result = hubspot_client.validate_tool_arguments("update_deal", args)
        assert result["deal_id"] == "67890"
        assert result["properties"]["dealstage"] == "closedwon"
    
    # ─────────────────────────────────────────────────────────────────────────
    # limit validation
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_limit_validation_above_100(self, hubspot_client):
        """Test limit must be <= 100."""
        with pytest.raises(ValueError) as exc:
            hubspot_client.validate_tool_arguments("list_contacts", {"limit": 101})
        assert "limit" in str(exc.value)
    
    def test_limit_zero_invalid(self, hubspot_client):
        """Test limit 0 is invalid."""
        with pytest.raises(ValueError):
            hubspot_client.validate_tool_arguments("list_contacts", {"limit": 0})
    
    def test_limit_negative_invalid(self, hubspot_client):
        """Test negative limit is invalid."""
        with pytest.raises(ValueError):
            hubspot_client.validate_tool_arguments("list_contacts", {"limit": -1})
    
    def test_limit_not_integer_invalid(self, hubspot_client):
        """Test non-integer limit is invalid."""
        with pytest.raises(ValueError):
            hubspot_client.validate_tool_arguments("list_contacts", {"limit": "50"})
    
    def test_limit_boundary_1(self, hubspot_client):
        """Test limit = 1 is valid."""
        result = hubspot_client.validate_tool_arguments("list_contacts", {"limit": 1})
        assert result["limit"] == 1
    
    def test_limit_boundary_100(self, hubspot_client):
        """Test limit = 100 is valid."""
        result = hubspot_client.validate_tool_arguments("list_contacts", {"limit": 100})
        assert result["limit"] == 100
    
    # ─────────────────────────────────────────────────────────────────────────
    # Unknown tool handling
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_unknown_tool_passthrough(self, hubspot_client):
        """Test unknown tools pass through."""
        args = {"foo": "bar", "baz": 123}
        result = hubspot_client.validate_tool_arguments("unknown_tool", args)
        assert result == args


# =============================================================================
# HubSpot ID Validation Tests
# =============================================================================


class TestHubSpotIDValidation:
    """Tests for HubSpot ID validation."""
    
    def test_valid_numeric_id(self, hubspot_client):
        """Test valid numeric ID."""
        result = hubspot_client._validate_hubspot_id("12345", "contact_id")
        assert result == "12345"
    
    def test_valid_large_id(self, hubspot_client):
        """Test valid large numeric ID."""
        result = hubspot_client._validate_hubspot_id("123456789012", "contact_id")
        assert result == "123456789012"
    
    def test_valid_int_id(self, hubspot_client):
        """Test integer ID converted to string."""
        result = hubspot_client._validate_hubspot_id(12345, "contact_id")
        assert result == "12345"
    
    def test_valid_int_zero(self, hubspot_client):
        """Test integer 0 is valid (edge case)."""
        result = hubspot_client._validate_hubspot_id(0, "contact_id")
        assert result == "0"
    
    def test_invalid_non_numeric_id(self, hubspot_client):
        """Test non-numeric ID rejected."""
        with pytest.raises(ValueError) as exc:
            hubspot_client._validate_hubspot_id("abc123", "contact_id")
        assert "numeric" in str(exc.value).lower()
    
    def test_invalid_uuid_id(self, hubspot_client):
        """Test UUID-style ID rejected."""
        with pytest.raises(ValueError):
            hubspot_client._validate_hubspot_id("12345678-1234-1234-1234-123456789abc", "contact_id")
    
    def test_invalid_with_spaces(self, hubspot_client):
        """Test ID with spaces rejected."""
        with pytest.raises(ValueError):
            hubspot_client._validate_hubspot_id("123 456", "contact_id")
    
    def test_empty_id(self, hubspot_client):
        """Test empty ID rejected."""
        with pytest.raises(ValueError) as exc:
            hubspot_client._validate_hubspot_id("", "contact_id")
        assert "cannot be empty" in str(exc.value)


# =============================================================================
# Email Validation Tests
# =============================================================================


class TestEmailValidation:
    """Tests for email validation."""
    
    def test_valid_email(self, hubspot_client):
        """Test valid email."""
        result = hubspot_client._validate_email("test@example.com")
        assert result == "test@example.com"
    
    def test_valid_email_with_plus(self, hubspot_client):
        """Test valid email with plus sign."""
        result = hubspot_client._validate_email("test+label@example.com")
        assert result == "test+label@example.com"
    
    def test_valid_email_with_dots(self, hubspot_client):
        """Test valid email with dots in local part."""
        result = hubspot_client._validate_email("first.last@example.com")
        assert result == "first.last@example.com"
    
    def test_valid_email_subdomain(self, hubspot_client):
        """Test valid email with subdomain."""
        result = hubspot_client._validate_email("user@mail.example.com")
        assert result == "user@mail.example.com"
    
    def test_email_lowercased(self, hubspot_client):
        """Test email is lowercased."""
        result = hubspot_client._validate_email("Test@Example.COM")
        assert result == "test@example.com"
    
    def test_email_trimmed(self, hubspot_client):
        """Test email is trimmed."""
        result = hubspot_client._validate_email("  test@example.com  ")
        assert result == "test@example.com"
    
    def test_invalid_email_no_at(self, hubspot_client):
        """Test email without @ rejected."""
        with pytest.raises(ValueError) as exc:
            hubspot_client._validate_email("not-an-email")
        assert "Invalid email" in str(exc.value)
    
    def test_invalid_email_no_domain(self, hubspot_client):
        """Test email without domain rejected."""
        with pytest.raises(ValueError):
            hubspot_client._validate_email("user@")
    
    def test_invalid_email_no_tld(self, hubspot_client):
        """Test email without TLD rejected."""
        with pytest.raises(ValueError):
            hubspot_client._validate_email("user@domain")
    
    def test_empty_email(self, hubspot_client):
        """Test empty email rejected."""
        with pytest.raises(ValueError) as exc:
            hubspot_client._validate_email("")
        assert "cannot be empty" in str(exc.value)


# =============================================================================
# Result Transformation Tests
# =============================================================================


class TestResultTransformation:
    """Tests for result transformation."""
    
    def test_transform_rate_limit_error_429(self, hubspot_client):
        """Test rate limit error with 429."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="rate limit exceeded (429)",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("list_contacts", error_result)
        
        assert result.is_error
        assert "rate limit" in result.error_message.lower()
    
    def test_transform_rate_limit_error_too_many(self, hubspot_client):
        """Test rate limit with 'too many requests'."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="too many requests",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("list_contacts", error_result)
        
        assert result.is_error
        assert "rate limit" in result.error_message.lower()
    
    def test_transform_not_found_error_404(self, hubspot_client):
        """Test not found error with 404."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="Contact not found (404)",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("get_contact", error_result)
        
        assert result.is_error
        assert "not found" in result.error_message.lower()
    
    def test_transform_not_found_does_not_exist(self, hubspot_client):
        """Test 'does not exist' error."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="Object does not exist",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("get_contact", error_result)
        
        assert result.is_error
        assert "not found" in result.error_message.lower()
    
    def test_transform_validation_error_400(self, hubspot_client):
        """Test validation error with 400."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="Invalid request (400)",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("create_contact", error_result)
        
        assert result.is_error
        assert "validation" in result.error_message.lower()
    
    def test_transform_validation_error_keyword(self, hubspot_client):
        """Test validation error with 'validation' keyword."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="Validation failed: email already exists",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("create_contact", error_result)
        
        assert result.is_error
        assert "validation" in result.error_message.lower()
    
    def test_transform_property_error_doesnt_exist(self, hubspot_client):
        """Test property error with 'doesn't exist'."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="Property 'custom_field' doesn't exist",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("update_contact", error_result)
        
        assert result.is_error
        assert "property" in result.error_message.lower()
    
    def test_transform_property_error_not_valid(self, hubspot_client):
        """Test property error with 'not valid'."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="Property value is not valid",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("update_contact", error_result)
        
        assert result.is_error
        assert "property" in result.error_message.lower()
    
    def test_transform_auth_error_401(self, hubspot_client):
        """Test auth error with 401."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="Unauthorized (401)",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("list_deals", error_result)
        
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED
    
    def test_transform_auth_error_forbidden(self, hubspot_client):
        """Test auth error with 'forbidden'."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="Forbidden: insufficient scope",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("create_deal", error_result)
        
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED
    
    def test_transform_generic_error_unchanged(self, hubspot_client):
        """Test generic errors pass through unchanged."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="Some other error",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("get_contact", error_result)
        
        assert result.is_error
        assert result.error_message == "Some other error"
    
    def test_transform_none_error_message(self, hubspot_client):
        """Test handling of None error message."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message=None,
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = hubspot_client.transform_tool_result("get_contact", error_result)
        
        assert result.is_error
    
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
    
    def test_preserves_raw_and_duration(self, hubspot_client):
        """Test transformation preserves raw and duration_ms."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="rate limit exceeded",
            content=[{"type": "text", "text": "Error"}],
            raw={"original": "data"},
            duration_ms=150.5,
        )
        
        result = hubspot_client.transform_tool_result("list_contacts", error_result)
        
        assert result.raw == {"original": "data"}
        assert result.duration_ms == 150.5


# =============================================================================
# Convenience Methods Tests
# =============================================================================


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
        
        await hubspot_client.get_contact(
            contact_id="12345",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "get_contact"
        assert call_args.kwargs["arguments"]["contact_id"] == "12345"
        assert "properties" in call_args.kwargs["arguments"]
    
    @pytest.mark.asyncio
    async def test_get_contact_by_email(self, hubspot_client, mock_connection_manager):
        """Test get_contact by email."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "contact"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await hubspot_client.get_contact(
            email="test@example.com",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["arguments"]["email"] == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_get_contact_requires_id_or_email(self, hubspot_client):
        """Test get_contact requires at least id or email."""
        with pytest.raises(ValueError):
            await hubspot_client.get_contact()
    
    @pytest.mark.asyncio
    async def test_get_contact_with_custom_properties(self, hubspot_client, mock_connection_manager):
        """Test get_contact with custom properties."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "contact"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await hubspot_client.get_contact(
            contact_id="12345",
            properties=["email", "custom_field"]
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["arguments"]["properties"] == ["email", "custom_field"]
    
    @pytest.mark.asyncio
    async def test_create_contact(self, hubspot_client, mock_connection_manager):
        """Test create_contact."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "created"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await hubspot_client.create_contact(
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
        assert props["lastname"] == "Doe"
    
    @pytest.mark.asyncio
    async def test_create_contact_with_additional_props(self, hubspot_client, mock_connection_manager):
        """Test create_contact with additional properties."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "created"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await hubspot_client.create_contact(
            email="new@example.com",
            properties={"company": "Acme Inc", "phone": "555-1234"}
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        props = call_args.kwargs["arguments"]["properties"]
        assert props["email"] == "new@example.com"
        assert props["company"] == "Acme Inc"
        assert props["phone"] == "555-1234"
    
    @pytest.mark.asyncio
    async def test_update_contact(self, hubspot_client, mock_connection_manager):
        """Test update_contact."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "updated"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await hubspot_client.update_contact(
            contact_id="12345",
            properties={"phone": "555-9999"},
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "update_contact"
        assert call_args.kwargs["arguments"]["contact_id"] == "12345"
        assert call_args.kwargs["arguments"]["properties"]["phone"] == "555-9999"
    
    @pytest.mark.asyncio
    async def test_list_contacts(self, hubspot_client, mock_connection_manager):
        """Test list_contacts."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "contacts"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await hubspot_client.list_contacts(
            limit=50,
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "list_contacts"
        assert call_args.kwargs["arguments"]["limit"] == 50
    
    @pytest.mark.asyncio
    async def test_list_contacts_with_pagination(self, hubspot_client, mock_connection_manager):
        """Test list_contacts with pagination cursor."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "contacts"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await hubspot_client.list_contacts(
            limit=25,
            after="cursor123"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["arguments"]["after"] == "cursor123"
    
    @pytest.mark.asyncio
    async def test_list_deals(self, hubspot_client, mock_connection_manager):
        """Test list_deals."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "deals"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await hubspot_client.list_deals(
            limit=20,
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "list_deals"
        assert call_args.kwargs["arguments"]["limit"] == 20
    
    @pytest.mark.asyncio
    async def test_create_deal(self, hubspot_client, mock_connection_manager):
        """Test create_deal."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "created"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await hubspot_client.create_deal(
            dealname="Big Sale",
            amount=10000.50,
            dealstage="appointmentscheduled",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "create_deal"
        props = call_args.kwargs["arguments"]["properties"]
        assert props["dealname"] == "Big Sale"
        assert props["amount"] == "10000.5"
        assert props["dealstage"] == "appointmentscheduled"
    
    @pytest.mark.asyncio
    async def test_create_deal_with_associations(self, hubspot_client, mock_connection_manager):
        """Test create_deal with associations."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "created"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        associations = [{"to": {"id": "123"}, "types": [{"associationTypeId": 1}]}]
        
        await hubspot_client.create_deal(
            dealname="Deal with Contact",
            associations=associations
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["arguments"]["associations"] == associations
    
    @pytest.mark.asyncio
    async def test_update_deal(self, hubspot_client, mock_connection_manager):
        """Test update_deal."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "updated"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await hubspot_client.update_deal(
            deal_id="67890",
            properties={"dealstage": "closedwon"},
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "update_deal"
        assert call_args.kwargs["arguments"]["deal_id"] == "67890"
        assert call_args.kwargs["arguments"]["properties"]["dealstage"] == "closedwon"


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_hubspot_client(self, mock_connection_manager):
        """Test create_hubspot_client factory."""
        client = create_hubspot_client(mock_connection_manager)
        
        assert isinstance(client, HubSpotMCPClient)
        assert client.backend_id == "hubspot"
    
    def test_create_hubspot_client_with_options(self, mock_connection_manager):
        """Test create_hubspot_client with additional options."""
        client = create_hubspot_client(
            mock_connection_manager,
            auto_initialize=True
        )
        
        assert isinstance(client, HubSpotMCPClient)


# =============================================================================
# Type Constants Tests
# =============================================================================


class TestTypeConstants:
    """Tests for type constant classes."""
    
    def test_hubspot_object_types(self):
        """Test HubSpotObjectType constants."""
        assert HubSpotObjectType.CONTACT == "contact"
        assert HubSpotObjectType.COMPANY == "company"
        assert HubSpotObjectType.DEAL == "deal"
        assert HubSpotObjectType.TICKET == "ticket"
    
    def test_hubspot_deal_stages(self):
        """Test HubSpotDealStage constants."""
        assert HubSpotDealStage.APPOINTMENT_SCHEDULED == "appointmentscheduled"
        assert HubSpotDealStage.QUALIFIED_TO_BUY == "qualifiedtobuy"
        assert HubSpotDealStage.CLOSED_WON == "closedwon"
        assert HubSpotDealStage.CLOSED_LOST == "closedlost"


# =============================================================================
# Exception Classes Tests
# =============================================================================


class TestExceptionClasses:
    """Tests for exception classes."""
    
    def test_hubspot_client_error(self):
        """Test HubSpotClientError base exception."""
        error = HubSpotClientError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_hubspot_rate_limit_error(self):
        """Test HubSpotRateLimitError inheritance."""
        error = HubSpotRateLimitError("Rate limit exceeded")
        assert isinstance(error, HubSpotClientError)
        assert str(error) == "Rate limit exceeded"
    
    def test_hubspot_object_not_found_error(self):
        """Test HubSpotObjectNotFoundError inheritance."""
        error = HubSpotObjectNotFoundError("Contact not found")
        assert isinstance(error, HubSpotClientError)
        assert str(error) == "Contact not found"
    
    def test_hubspot_validation_error(self):
        """Test HubSpotValidationError inheritance."""
        error = HubSpotValidationError("Invalid property")
        assert isinstance(error, HubSpotClientError)
        assert str(error) == "Invalid property"
