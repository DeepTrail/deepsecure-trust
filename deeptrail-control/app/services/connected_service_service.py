"""Service for managing user's connected backend services.

This service orchestrates between the ConnectedService model and VaultClient,
handling the business logic for connecting and disconnecting services.

Example flow:
    1. User clicks "Connect Notion" in UI
    2. OAuth flow completes, returns tokens
    3. ConnectedServiceService.connect_service() is called
    4. Service stores tokens in vault, creates ConnectedService record
    5. Later, agent needs Notion token for tools/call
    6. Gateway calls get_token_for_service() to retrieve token
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.connected_service import ConnectedService

from .vault_client import VaultClient

logger = logging.getLogger(__name__)


class ConnectedServiceError(Exception):
    """Base exception for connected service operations."""

    pass


class ServiceNotFoundError(ConnectedServiceError):
    """Raised when a service connection is not found."""

    pass


class ServiceAlreadyConnectedError(ConnectedServiceError):
    """Raised when trying to connect an already-connected service."""

    pass


class ConnectedServiceService:
    """Service for managing user's connected backend services.

    Orchestrates between ConnectedService model and VaultClient to:
    - Store OAuth tokens securely in vault
    - Create/update ConnectedService records in database
    - Retrieve tokens for credential injection

    Example:
        service = ConnectedServiceService(vault_client, db_session)

        # Connect Notion
        conn = service.connect_service(
            user_id="sarah@acme.com",
            service_id="notion",
            oauth_response={"access_token": "abc", "refresh_token": "xyz"},
            scopes_granted=["read_content", "search"]
        )

        # Get token for credential injection
        token = service.get_token_for_service("sarah@acme.com", "notion")
    """

    def __init__(self, vault_client: VaultClient, db_session: Session):
        """Initialize the service.

        Args:
            vault_client: VaultClient instance for token storage.
            db_session: SQLAlchemy database session.
        """
        self._vault = vault_client
        self._db = db_session

    def connect_service(
        self,
        user_id: str,
        service_id: str,
        oauth_response: Dict[str, Any],
        scopes_granted: List[str],
        service_name: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> ConnectedService:
        """Connect a user to a backend service.

        Stores OAuth tokens in vault and creates/updates ConnectedService record.
        If user was previously connected (and disconnected), re-connects.

        Args:
            user_id: User identifier (e.g., "sarah@acme.com")
            service_id: Service identifier (e.g., "notion", "slack")
            oauth_response: OAuth token response from provider containing
                           access_token, refresh_token, expires_in, etc.
            scopes_granted: List of scopes user consented to during OAuth.
            service_name: Optional human-readable service name.
            organization_id: Optional organization for multi-tenant deployments.

        Returns:
            ConnectedService record (new or updated).

        Note:
            If user already has an active connection, the old token is deleted
            and replaced with the new one (re-authorization flow).
        """
        # Store token securely in vault
        token_ref = self._vault.store_token(user_id, service_id, oauth_response)

        # Check for existing connection (active or disconnected)
        existing = (
            self._db.query(ConnectedService)
            .filter(
                ConnectedService.user_id == user_id,
                ConnectedService.service_id == service_id,
            )
            .first()
        )

        if existing:
            # Re-connect: delete old token (if any), update record
            if existing.oauth_token_ref:
                self._vault.delete_token(existing.oauth_token_ref)
                logger.debug(
                    "Deleted old token during reconnect: user=%s service=%s",
                    user_id,
                    service_id,
                )

            existing.oauth_token_ref = token_ref
            existing.scopes_granted = scopes_granted
            existing.connected_at = datetime.now(timezone.utc)
            existing.disconnected_at = None
            existing.last_used_at = None

            if service_name:
                existing.service_name = service_name
            if organization_id:
                existing.organization_id = organization_id

            logger.info(
                "Re-connected service: user=%s service=%s",
                user_id,
                service_id,
            )
            return existing

        # Create new connection
        connection = ConnectedService(
            user_id=user_id,
            service_id=service_id,
            oauth_token_ref=token_ref,
            scopes_granted=scopes_granted,
            service_name=service_name,
            organization_id=organization_id,
            connected_at=datetime.now(timezone.utc),
        )
        self._db.add(connection)

        logger.info(
            "Connected new service: user=%s service=%s id=%s",
            user_id,
            service_id,
            connection.id,
        )
        return connection

    def disconnect_service(self, user_id: str, service_id: str) -> bool:
        """Disconnect a user from a backend service.

        Deletes OAuth token from vault and marks ConnectedService as disconnected.
        Does NOT delete the ConnectedService record (soft delete for audit trail).

        Args:
            user_id: User identifier.
            service_id: Service identifier.

        Returns:
            True if disconnected, False if connection not found.
        """
        connection = (
            self._db.query(ConnectedService)
            .filter(
                ConnectedService.user_id == user_id,
                ConnectedService.service_id == service_id,
            )
            .first()
        )

        if not connection:
            logger.debug(
                "Connection not found for disconnect: user=%s service=%s",
                user_id,
                service_id,
            )
            return False

        # Already disconnected?
        if connection.disconnected_at is not None:
            logger.debug(
                "Service already disconnected: user=%s service=%s",
                user_id,
                service_id,
            )
            return True

        # Delete token from vault
        if connection.oauth_token_ref:
            self._vault.delete_token(connection.oauth_token_ref)

        # Mark as disconnected (soft delete)
        connection.disconnected_at = datetime.now(timezone.utc)
        # Clear token ref since we deleted it
        connection.oauth_token_ref = ""

        logger.info(
            "Disconnected service: user=%s service=%s",
            user_id,
            service_id,
        )
        return True

    def get_token_for_service(
        self,
        user_id: str,
        service_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get OAuth token for a user's connected service.

        Used by gateway for credential injection during tools/call.

        Args:
            user_id: User identifier.
            service_id: Service identifier.

        Returns:
            Decrypted OAuth token data, or None if not connected.
        """
        connection = (
            self._db.query(ConnectedService)
            .filter(
                ConnectedService.user_id == user_id,
                ConnectedService.service_id == service_id,
                ConnectedService.disconnected_at.is_(None),
            )
            .first()
        )

        if not connection:
            logger.debug(
                "No active connection for token retrieval: user=%s service=%s",
                user_id,
                service_id,
            )
            return None

        if not connection.oauth_token_ref:
            logger.warning(
                "Active connection has no token ref: user=%s service=%s",
                user_id,
                service_id,
            )
            return None

        # Record usage for audit
        connection.record_usage()

        return self._vault.retrieve_token(connection.oauth_token_ref)

    def get_connection(
        self,
        user_id: str,
        service_id: str,
        include_disconnected: bool = False,
    ) -> Optional[ConnectedService]:
        """Get a specific service connection.

        Args:
            user_id: User identifier.
            service_id: Service identifier.
            include_disconnected: If True, return even if disconnected.

        Returns:
            ConnectedService record, or None if not found.
        """
        query = self._db.query(ConnectedService).filter(
            ConnectedService.user_id == user_id,
            ConnectedService.service_id == service_id,
        )

        if not include_disconnected:
            query = query.filter(ConnectedService.disconnected_at.is_(None))

        return query.first()

    def get_user_connections(
        self,
        user_id: str,
        include_disconnected: bool = False,
    ) -> List[ConnectedService]:
        """Get all service connections for a user.

        Args:
            user_id: User identifier.
            include_disconnected: If True, include disconnected services.

        Returns:
            List of ConnectedService records.
        """
        query = self._db.query(ConnectedService).filter(
            ConnectedService.user_id == user_id,
        )

        if not include_disconnected:
            query = query.filter(ConnectedService.disconnected_at.is_(None))

        return query.all()

    def get_organization_connections(
        self,
        organization_id: str,
        include_disconnected: bool = False,
    ) -> List[ConnectedService]:
        """Get all service connections for an organization.

        Args:
            organization_id: Organization identifier.
            include_disconnected: If True, include disconnected services.

        Returns:
            List of ConnectedService records.
        """
        query = self._db.query(ConnectedService).filter(
            ConnectedService.organization_id == organization_id,
        )

        if not include_disconnected:
            query = query.filter(ConnectedService.disconnected_at.is_(None))

        return query.all()

    def is_connected(self, user_id: str, service_id: str) -> bool:
        """Check if a user has an active connection to a service.

        Args:
            user_id: User identifier.
            service_id: Service identifier.

        Returns:
            True if actively connected, False otherwise.
        """
        connection = self.get_connection(user_id, service_id)
        return connection is not None and connection.is_active

    def has_scope(self, user_id: str, service_id: str, scope: str) -> bool:
        """Check if a user's connection includes a specific scope.

        Args:
            user_id: User identifier.
            service_id: Service identifier.
            scope: Scope to check for.

        Returns:
            True if scope was granted, False otherwise.
        """
        connection = self.get_connection(user_id, service_id)
        if not connection:
            return False
        return connection.has_scope(scope)

    def refresh_token(
        self,
        user_id: str,
        service_id: str,
        new_token_data: Dict[str, Any],
    ) -> bool:
        """Update the OAuth token for an existing connection.

        Used after token refresh operations to update the stored token.

        Args:
            user_id: User identifier.
            service_id: Service identifier.
            new_token_data: New OAuth token data from refresh.

        Returns:
            True if token was updated, False if connection not found.
        """
        connection = self.get_connection(user_id, service_id)
        if not connection or not connection.oauth_token_ref:
            return False

        success = self._vault.update_token(
            connection.oauth_token_ref,
            new_token_data,
        )

        if success:
            logger.debug(
                "Refreshed token: user=%s service=%s",
                user_id,
                service_id,
            )

        return success

    def disconnect_all_user_services(self, user_id: str) -> int:
        """Disconnect all services for a user.

        Useful when a user account is deactivated or deleted.

        Args:
            user_id: User identifier.

        Returns:
            Number of services disconnected.
        """
        connections = self.get_user_connections(user_id)
        count = 0

        for conn in connections:
            if self.disconnect_service(user_id, conn.service_id):
                count += 1

        logger.info(
            "Disconnected all services for user: user=%s count=%d",
            user_id,
            count,
        )
        return count
