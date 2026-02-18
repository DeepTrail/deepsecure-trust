"""
HubSpot Client

Provides two client implementations for HubSpot:

1. HubSpotMCPClient - Uses BackendConnectionManager for MCP protocol (original)
2. HubSpotDirectClient - Makes direct REST API calls to HubSpot CRM API (WS-G4)

The HubSpotDirectClient is the primary implementation for production use,
translating MCP tool calls into direct HubSpot CRM REST API requests.

MVP Tools:
- get_contact: Get contact by ID or email -> GET /crm/v3/objects/contacts/{id}
- create_contact: Create a new contact -> POST /crm/v3/objects/contacts
- update_contact: Update contact properties -> PATCH /crm/v3/objects/contacts/{id}
- list_contacts: List contacts -> GET /crm/v3/objects/contacts
- search_contacts: Search contacts -> POST /crm/v3/objects/contacts/search
- get_deal: Get deal by ID -> GET /crm/v3/objects/deals/{id}
- create_deal: Create a new deal -> POST /crm/v3/objects/deals
- update_deal: Update deal properties -> PATCH /crm/v3/objects/deals/{id}
- list_deals: List deals -> GET /crm/v3/objects/deals

Usage:
    from app.backends.hubspot_client import HubSpotDirectClient

    client = HubSpotDirectClient()

    # List contacts (auth_token from credential injection)
    result = await client.list_contacts(
        limit=10,
        auth_token="pat-xxx"
    )
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

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
# Direct HubSpot API Client (WS-G4)
# =============================================================================


@dataclass
class HubSpotAPIConfig:
    """Configuration for HubSpot API client."""
    base_url: str = "https://api.hubapi.com"
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_backoff_factor: float = 0.5


class HubSpotDirectClient:
    """
    Direct HubSpot CRM REST API client.

    Makes direct HTTP calls to HubSpot's CRM API v3, translating tool calls
    into appropriate API requests. Uses configuration from HubSpotConfig (WS-G1).

    Attributes:
        base_url: HubSpot API base URL
        timeout: Request timeout in seconds

    Usage:
        client = HubSpotDirectClient()
        result = await client.list_contacts(limit=10, auth_token="pat-xxx")
    """

    def __init__(self, config: HubSpotAPIConfig | None = None) -> None:
        """
        Initialize HubSpot direct client.

        Args:
            config: Optional configuration. If not provided, loads from
                    GatewaySettings (WS-G1).
        """
        if config is not None:
            self._config = config
        else:
            # Load from gateway settings (WS-G1)
            try:
                from app.core.config import get_settings
                settings = get_settings()
                self._config = HubSpotAPIConfig(
                    base_url=settings.hubspot.base_url,
                    timeout_seconds=settings.hubspot.timeout_seconds,
                    retry_attempts=settings.hubspot.retry_attempts,
                    retry_backoff_factor=settings.hubspot.retry_backoff_factor,
                )
            except ImportError:
                # Fallback to defaults if config module not available
                self._config = HubSpotAPIConfig()

        self.base_url = self._config.base_url
        self.timeout = self._config.timeout_seconds

        logger.info(
            "HubSpotDirectClient initialized: base_url=%s",
            self.base_url,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HTTP Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _get_headers(self, auth_token: str) -> dict[str, str]:
        """
        Get headers for HubSpot API requests.

        Args:
            auth_token: HubSpot access token (Bearer token)

        Returns:
            Headers dict including Authorization and Content-Type
        """
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

    def _transform_response(
        self,
        tool_name: str,
        response: httpx.Response,
        start_time: datetime,
    ) -> ToolResult:
        """
        Transform httpx response into ToolResult.

        Args:
            tool_name: Name of the tool that was called
            response: httpx Response object
            start_time: Request start time for duration calculation

        Returns:
            ToolResult with success or error status
        """
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Handle error responses
        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("message", str(error_data))
                category = error_data.get("category", "unknown")
            except Exception:
                message = response.text[:500] if response.text else "Unknown error"
                category = "unknown"

            # Map HTTP status codes to error types
            error_message = f"{category}: {message}"

            if response.status_code == 401:
                error_message = f"Unauthorized: {message}"
            elif response.status_code == 403:
                error_message = f"Forbidden: {message}"
            elif response.status_code == 404:
                error_message = f"Not found: {message}"
            elif response.status_code == 429:
                error_message = f"Rate limit exceeded: {message}"
            elif response.status_code == 400:
                error_message = f"Validation error: {message}"

            logger.warning(
                "HubSpot API error for %s: %s (HTTP %d)",
                tool_name,
                error_message,
                response.status_code,
            )

            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=error_message,
                content=[{"type": "text", "text": error_message}],
                raw={"status_code": response.status_code, "error": message},
                duration_ms=duration_ms,
            )

        # Success response
        try:
            data = response.json()
        except Exception:
            data = {"raw_text": response.text}

        logger.debug(
            "HubSpot API success for %s in %.1fms",
            tool_name,
            duration_ms,
        )

        return ToolResult(
            status=ToolCallStatus.SUCCESS,
            is_error=False,
            content=[{"type": "text", "text": str(data)}],
            raw=data,
            duration_ms=duration_ms,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Contact Methods
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

        If contact_id is provided, calls GET /crm/v3/objects/contacts/{contactId}.
        If email is provided (without contact_id), uses search endpoint.

        Args:
            contact_id: HubSpot contact ID (numeric string)
            email: Contact email address (uses search if no contact_id)
            properties: Properties to return
            auth_token: HubSpot access token

        Returns:
            ToolResult with contact data or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        if contact_id:
            # Direct lookup by ID
            url = f"{self.base_url}/crm/v3/objects/contacts/{contact_id}"
            params: dict[str, Any] = {}
            if properties:
                params["properties"] = ",".join(properties)

            start_time = datetime.now(timezone.utc)

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        url,
                        params=params if params else None,
                        headers=self._get_headers(auth_token),
                    )
                return self._transform_response("get_contact", response, start_time)

            except httpx.TimeoutException:
                return ToolResult.from_error(
                    ToolCallStatus.TIMEOUT, "Request timed out"
                )
            except httpx.RequestError as e:
                return ToolResult.from_error(
                    ToolCallStatus.ERROR, f"Request failed: {e}"
                )

        elif email:
            # Use search endpoint for email lookup
            return await self.search_contacts(
                filters=[{"propertyName": "email", "operator": "EQ", "value": email}],
                limit=1,
                properties=properties,
                auth_token=auth_token,
            )

        else:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "Either contact_id or email is required"
            )

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

        Calls POST /crm/v3/objects/contacts

        Args:
            email: Contact email (required)
            firstname: First name
            lastname: Last name
            properties: Additional properties
            auth_token: HubSpot access token

        Returns:
            ToolResult with created contact data or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/crm/v3/objects/contacts"
        props: dict[str, Any] = {"email": email}
        if firstname:
            props["firstname"] = firstname
        if lastname:
            props["lastname"] = lastname
        if properties:
            props.update(properties)

        payload = {"properties": props}

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("create_contact", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def update_contact(
        self,
        contact_id: str,
        properties: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Update a contact's properties.

        Calls PATCH /crm/v3/objects/contacts/{contactId}

        Args:
            contact_id: HubSpot contact ID
            properties: Properties to update
            auth_token: HubSpot access token

        Returns:
            ToolResult with updated contact data or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/crm/v3/objects/contacts/{contact_id}"
        payload = {"properties": properties}

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.patch(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("update_contact", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def list_contacts(
        self,
        limit: int = 10,
        after: str | None = None,
        properties: list[str] | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List contacts in HubSpot.

        Calls GET /crm/v3/objects/contacts

        Args:
            limit: Maximum contacts to return (1-100)
            after: Cursor for pagination
            properties: Properties to return
            auth_token: HubSpot access token

        Returns:
            ToolResult with contact list or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/crm/v3/objects/contacts"
        params: dict[str, Any] = {"limit": min(max(limit, 1), 100)}
        if after:
            params["after"] = after
        if properties:
            params["properties"] = ",".join(properties)

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("list_contacts", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def search_contacts(
        self,
        filters: list[dict[str, Any]],
        sorts: list[dict[str, Any]] | None = None,
        properties: list[str] | None = None,
        limit: int = 10,
        after: str | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Search contacts using HubSpot's search API.

        Calls POST /crm/v3/objects/contacts/search

        Args:
            filters: Filter conditions (list of filter objects)
            sorts: Sort configuration
            properties: Properties to return
            limit: Maximum contacts to return (1-100)
            after: Cursor for pagination
            auth_token: HubSpot access token

        Returns:
            ToolResult with search results or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/crm/v3/objects/contacts/search"
        payload: dict[str, Any] = {
            "filterGroups": [{"filters": filters}],
            "limit": min(max(limit, 1), 100),
        }
        if sorts:
            payload["sorts"] = sorts
        if properties:
            payload["properties"] = properties
        if after:
            payload["after"] = after

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("search_contacts", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Deal Methods
    # ─────────────────────────────────────────────────────────────────────────

    async def get_deal(
        self,
        deal_id: str,
        properties: list[str] | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Get a deal by ID.

        Calls GET /crm/v3/objects/deals/{dealId}

        Args:
            deal_id: HubSpot deal ID
            properties: Properties to return
            auth_token: HubSpot access token

        Returns:
            ToolResult with deal data or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/crm/v3/objects/deals/{deal_id}"
        params: dict[str, Any] = {}
        if properties:
            params["properties"] = ",".join(properties)

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params if params else None,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("get_deal", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def create_deal(
        self,
        dealname: str,
        pipeline: str = "default",
        dealstage: str | None = None,
        amount: float | None = None,
        properties: dict[str, Any] | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Create a new deal in HubSpot.

        Calls POST /crm/v3/objects/deals

        Note: HubSpot requires amount to be a string, not a number.

        Args:
            dealname: Deal name (required)
            pipeline: Pipeline ID (default: "default")
            dealstage: Deal stage
            amount: Deal amount (will be converted to string)
            properties: Additional properties
            auth_token: HubSpot access token

        Returns:
            ToolResult with created deal data or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/crm/v3/objects/deals"
        props: dict[str, Any] = {"dealname": dealname, "pipeline": pipeline}
        if dealstage:
            props["dealstage"] = dealstage
        if amount is not None:
            # HubSpot requires amount as string
            props["amount"] = str(amount)
        if properties:
            props.update(properties)

        payload = {"properties": props}

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("create_deal", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def update_deal(
        self,
        deal_id: str,
        properties: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Update a deal's properties.

        Calls PATCH /crm/v3/objects/deals/{dealId}

        Args:
            deal_id: HubSpot deal ID
            properties: Properties to update
            auth_token: HubSpot access token

        Returns:
            ToolResult with updated deal data or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/crm/v3/objects/deals/{deal_id}"
        payload = {"properties": properties}

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.patch(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("update_deal", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def list_deals(
        self,
        limit: int = 10,
        after: str | None = None,
        properties: list[str] | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List deals in HubSpot.

        Calls GET /crm/v3/objects/deals

        Args:
            limit: Maximum deals to return (1-100)
            after: Cursor for pagination
            properties: Properties to return
            auth_token: HubSpot access token

        Returns:
            ToolResult with deal list or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/crm/v3/objects/deals"
        params: dict[str, Any] = {"limit": min(max(limit, 1), 100)}
        if after:
            params["after"] = after
        if properties:
            params["properties"] = ",".join(properties)

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("list_deals", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Tool Dispatcher
    # ─────────────────────────────────────────────────────────────────────────

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Dispatch a tool call to the appropriate method.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            auth_token: HubSpot access token

        Returns:
            ToolResult from the tool execution
        """
        # Map tool names to methods
        tool_map = {
            "get_contact": self._call_get_contact,
            "create_contact": self._call_create_contact,
            "update_contact": self._call_update_contact,
            "list_contacts": self._call_list_contacts,
            "search_contacts": self._call_search_contacts,
            "get_deal": self._call_get_deal,
            "create_deal": self._call_create_deal,
            "update_deal": self._call_update_deal,
            "list_deals": self._call_list_deals,
        }

        handler = tool_map.get(tool_name)
        if handler is None:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Unknown tool: {tool_name}"
            )

        return await handler(arguments, auth_token)

    async def _call_get_contact(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        return await self.get_contact(
            contact_id=args.get("contact_id"),
            email=args.get("email"),
            properties=args.get("properties"),
            auth_token=auth_token,
        )

    async def _call_create_contact(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        email = args.get("email")
        if not email:
            # Check if email is in properties
            props = args.get("properties", {})
            email = props.get("email")
            if not email:
                return ToolResult.from_error(
                    ToolCallStatus.ERROR, "email is required"
                )
        return await self.create_contact(
            email=email,
            firstname=args.get("firstname"),
            lastname=args.get("lastname"),
            properties=args.get("properties"),
            auth_token=auth_token,
        )

    async def _call_update_contact(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        contact_id = args.get("contact_id")
        if not contact_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "contact_id is required"
            )
        properties = args.get("properties")
        if not properties:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "properties is required"
            )
        return await self.update_contact(
            contact_id=contact_id,
            properties=properties,
            auth_token=auth_token,
        )

    async def _call_list_contacts(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        return await self.list_contacts(
            limit=args.get("limit", 10),
            after=args.get("after"),
            properties=args.get("properties"),
            auth_token=auth_token,
        )

    async def _call_search_contacts(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        filters = args.get("filters")
        if not filters:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "filters is required"
            )
        return await self.search_contacts(
            filters=filters,
            sorts=args.get("sorts"),
            properties=args.get("properties"),
            limit=args.get("limit", 10),
            after=args.get("after"),
            auth_token=auth_token,
        )

    async def _call_get_deal(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        deal_id = args.get("deal_id")
        if not deal_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "deal_id is required"
            )
        return await self.get_deal(
            deal_id=deal_id,
            properties=args.get("properties"),
            auth_token=auth_token,
        )

    async def _call_create_deal(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        dealname = args.get("dealname")
        if not dealname:
            # Check properties
            props = args.get("properties", {})
            dealname = props.get("dealname")
            if not dealname:
                return ToolResult.from_error(
                    ToolCallStatus.ERROR, "dealname is required"
                )
        return await self.create_deal(
            dealname=dealname,
            pipeline=args.get("pipeline", "default"),
            dealstage=args.get("dealstage"),
            amount=args.get("amount"),
            properties=args.get("properties"),
            auth_token=auth_token,
        )

    async def _call_update_deal(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        deal_id = args.get("deal_id")
        if not deal_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "deal_id is required"
            )
        properties = args.get("properties")
        if not properties:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "properties is required"
            )
        return await self.update_deal(
            deal_id=deal_id,
            properties=properties,
            auth_token=auth_token,
        )

    async def _call_list_deals(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        return await self.list_deals(
            limit=args.get("limit", 10),
            after=args.get("after"),
            properties=args.get("properties"),
            auth_token=auth_token,
        )


# =============================================================================
# HubSpot MCP Client (Original - for backwards compatibility)
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


def create_hubspot_direct_client(
    config: HubSpotAPIConfig | None = None,
) -> HubSpotDirectClient:
    """
    Create a HubSpot direct API client.

    Args:
        config: Optional configuration (loads from GatewaySettings if not provided)

    Returns:
        Configured HubSpotDirectClient
    """
    return HubSpotDirectClient(config)
