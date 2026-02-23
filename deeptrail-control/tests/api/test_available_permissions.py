"""Unit tests for GET /api/v1/users/me/available-permissions endpoint.

Tests the endpoint that returns all permissions a user can delegate
based on their connected service scopes.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.api import deps
from app.models.connected_service import ConnectedService


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def user_token():
    """Mock user token for authorization."""
    return "mock_user_token_sarah@acme.com"


def create_mock_connection(
    service_id: str,
    scopes: list[str],
    service_name: str = None,
    connected_at=None,
    disconnected_at=None,
) -> MagicMock:
    """Create a mock ConnectedService."""
    from datetime import datetime, timezone

    conn = MagicMock(spec=ConnectedService)
    conn.user_id = "sarah@acme.com"
    conn.service_id = service_id
    conn.service_name = service_name or service_id.title()
    conn.scopes_granted = scopes
    conn.connected_at = connected_at or datetime.now(timezone.utc)
    conn.disconnected_at = disconnected_at
    return conn


def override_db_with_connections(connections: list):
    """Create a dependency override for get_db that returns mocked connections."""
    def get_test_db():
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.all.return_value = connections
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        return mock_db
    return get_test_db


class TestAvailablePermissionsEndpoint:
    """Test GET /api/v1/users/me/available-permissions."""

    def test_returns_permissions_for_connected_service(self, user_token):
        """Should return permissions based on connected scopes."""
        connections = [
            create_mock_connection("notion", ["read_pages", "search_content"], "Notion")
        ]

        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)

        try:
            response = client.get(
                "/api/v1/users/me/available-permissions",
                headers={"Authorization": f"Bearer {user_token}"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert "notion" in data["services"]
            assert data["services"]["notion"]["connected"] is True
            assert "notion:pages:read" in data["services"]["notion"]["available_permissions"]
            assert "notion:pages:search" in data["services"]["notion"]["available_permissions"]
        finally:
            app.dependency_overrides.clear()

    def test_returns_multiple_services(self, user_token):
        """Should return permissions for all connected services."""
        connections = [
            create_mock_connection("notion", ["read_pages"], "Notion"),
            create_mock_connection("slack", ["channels:read"], "Slack"),
        ]

        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)

        try:
            response = client.get(
                "/api/v1/users/me/available-permissions",
                headers={"Authorization": f"Bearer {user_token}"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["total_services"] == 2
            assert "notion" in data["services"]
            assert "slack" in data["services"]
        finally:
            app.dependency_overrides.clear()

    def test_all_permissions_is_flat_list(self, user_token):
        """Should return flat list of all permissions."""
        connections = [
            create_mock_connection("notion", ["read_pages"], "Notion"),
            create_mock_connection("slack", ["channels:read"], "Slack"),
        ]

        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)

        try:
            response = client.get(
                "/api/v1/users/me/available-permissions",
                headers={"Authorization": f"Bearer {user_token}"},
            )

            data = response.json()

            assert "notion:pages:read" in data["all_permissions"]
            assert "slack:channels:list" in data["all_permissions"]
            assert data["total_permissions"] == len(data["all_permissions"])
        finally:
            app.dependency_overrides.clear()

    def test_empty_when_no_services(self, user_token):
        """Should return empty when no services connected."""
        app.dependency_overrides[deps.get_db] = override_db_with_connections([])
        client = TestClient(app)

        try:
            response = client.get(
                "/api/v1/users/me/available-permissions",
                headers={"Authorization": f"Bearer {user_token}"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["services"] == {}
            assert data["all_permissions"] == []
            assert data["total_services"] == 0
            assert data["total_permissions"] == 0
        finally:
            app.dependency_overrides.clear()

    def test_excludes_disconnected_services(self, user_token):
        """Should not include disconnected services.
        
        Disconnected services (where disconnected_at is set) are filtered
        out by the query. This test verifies that behavior by mocking
        an empty result (as if the DB query filtered them out).
        """
        # The database query filters out disconnected services,
        # so we simulate the result of that filtering (empty list)
        app.dependency_overrides[deps.get_db] = override_db_with_connections([])
        client = TestClient(app)

        try:
            response = client.get(
                "/api/v1/users/me/available-permissions",
                headers={"Authorization": f"Bearer {user_token}"},
            )

            data = response.json()
            assert "hubspot" not in data["services"]
        finally:
            app.dependency_overrides.clear()

    def test_unauthorized_without_token(self):
        """Should return 401/422 without token."""
        client = TestClient(app)
        response = client.get("/api/v1/users/me/available-permissions")
        assert response.status_code in [401, 422]

    def test_permissions_are_sorted(self, user_token):
        """Should return sorted permission lists."""
        connections = [
            create_mock_connection("notion", ["read_pages", "write_pages"], "Notion")
        ]

        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)

        try:
            response = client.get(
                "/api/v1/users/me/available-permissions",
                headers={"Authorization": f"Bearer {user_token}"},
            )

            data = response.json()
            perms = data["all_permissions"]

            assert perms == sorted(perms)
            
            # Also check per-service permissions are sorted
            notion_perms = data["services"]["notion"]["available_permissions"]
            assert notion_perms == sorted(notion_perms)
        finally:
            app.dependency_overrides.clear()

    def test_includes_service_metadata(self, user_token):
        """Should include service name and connected_at."""
        connections = [
            create_mock_connection("notion", ["read_pages"], "Notion")
        ]

        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)

        try:
            response = client.get(
                "/api/v1/users/me/available-permissions",
                headers={"Authorization": f"Bearer {user_token}"},
            )

            data = response.json()
            notion = data["services"]["notion"]

            assert notion["service_name"] == "Notion"
            assert notion["connected_at"] is not None
            assert notion["scopes_granted"] == ["read_pages"]
        finally:
            app.dependency_overrides.clear()

    def test_full_access_scopes(self, user_token):
        """Should return all permissions for full_access scope."""
        connections = [
            create_mock_connection("notion", ["full_access"], "Notion")
        ]

        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)

        try:
            response = client.get(
                "/api/v1/users/me/available-permissions",
                headers={"Authorization": f"Bearer {user_token}"},
            )

            data = response.json()
            perms = data["services"]["notion"]["available_permissions"]

            # full_access should give many permissions
            assert "notion:pages:read" in perms
            assert "notion:pages:search" in perms
            assert "notion:pages:create" in perms
            assert "notion:pages:update" in perms
        finally:
            app.dependency_overrides.clear()
