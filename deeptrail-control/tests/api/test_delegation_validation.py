"""Unit tests for delegation permission validation.

Tests the enhanced delegation endpoint that validates requested permissions
against the user's connected service scopes (monotonic attenuation principle).
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
    """Test client with dependency overrides."""
    return TestClient(app)


@pytest.fixture
def user_token():
    """Mock user token for authorization."""
    return "mock_user_token_sarah@acme.com"


def create_mock_connection(service_id: str, scopes: list[str]) -> MagicMock:
    """Create a mock ConnectedService."""
    conn = MagicMock(spec=ConnectedService)
    conn.user_id = "sarah@acme.com"
    conn.service_id = service_id
    conn.scopes_granted = scopes
    conn.disconnected_at = None
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


class TestDelegationPermissionValidation:
    """Test permission validation in delegation endpoint."""
    
    def test_valid_permissions_succeed(self, user_token):
        """Should succeed when permissions match scopes."""
        connections = [create_mock_connection("notion", ["read_pages", "search_content"])]
        
        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)
        
        try:
            response = client.post(
                "/api/v1/auth/delegate",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "agent_id": "test-agent",
                    "permissions": ["notion:pages:search", "notion:pages:read"],
                },
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "delegation_token" in data
            assert data["permissions"] == ["notion:pages:search", "notion:pages:read"]
        finally:
            app.dependency_overrides.clear()
    
    def test_invalid_permissions_rejected(self, user_token):
        """Should reject permissions not in connected scopes."""
        connections = [create_mock_connection("notion", ["read_pages", "search_content"])]
        
        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)
        
        try:
            response = client.post(
                "/api/v1/auth/delegate",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "agent_id": "test-agent",
                    "permissions": ["notion:pages:create"],  # Requires write scope!
                },
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert data["detail"]["error"] == "permission_validation_failed"
            assert "notion:pages:create" in data["detail"]["invalid_permissions"]
            assert "notion:pages:read" in data["detail"]["allowed_permissions"]
            assert "notion:pages:search" in data["detail"]["allowed_permissions"]
        finally:
            app.dependency_overrides.clear()
    
    def test_mixed_permissions_shows_invalid_only(self, user_token):
        """Should list only invalid permissions in error."""
        connections = [create_mock_connection("notion", ["read_pages", "search_content"])]
        
        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)
        
        try:
            response = client.post(
                "/api/v1/auth/delegate",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "agent_id": "test-agent",
                    "permissions": [
                        "notion:pages:search",  # Valid
                        "notion:pages:create",  # Invalid
                        "notion:pages:update",  # Invalid
                    ],
                },
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            invalid = data["detail"]["invalid_permissions"]
            assert "notion:pages:search" not in invalid
            assert "notion:pages:create" in invalid
            assert "notion:pages:update" in invalid
        finally:
            app.dependency_overrides.clear()
    
    def test_no_connected_services_error(self, user_token):
        """Should error if user has no connected services."""
        app.dependency_overrides[deps.get_db] = override_db_with_connections([])
        client = TestClient(app)
        
        try:
            response = client.post(
                "/api/v1/auth/delegate",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "agent_id": "test-agent",
                    "permissions": ["notion:pages:search"],
                },
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert response.json()["detail"]["error"] == "no_connected_services"
        finally:
            app.dependency_overrides.clear()
    
    def test_unknown_service_rejected(self, user_token):
        """Should reject permissions for services user hasn't connected."""
        connections = [create_mock_connection("notion", ["read_pages", "search_content"])]
        
        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)
        
        try:
            response = client.post(
                "/api/v1/auth/delegate",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "agent_id": "test-agent",
                    "permissions": ["slack:messages:send"],  # Slack not connected
                },
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert data["detail"]["error"] == "permission_validation_failed"
            assert "slack:messages:send" in data["detail"]["invalid_permissions"]
        finally:
            app.dependency_overrides.clear()
    
    def test_valid_with_write_scopes(self, user_token):
        """Should succeed when user has write scopes."""
        connections = [create_mock_connection("notion", ["read_pages", "search_content", "write_pages"])]
        
        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)
        
        try:
            response = client.post(
                "/api/v1/auth/delegate",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "agent_id": "test-agent",
                    "permissions": [
                        "notion:pages:search",
                        "notion:pages:create",
                        "notion:pages:update",
                    ],
                },
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "delegation_token" in data
        finally:
            app.dependency_overrides.clear()
    
    def test_cross_service_permissions(self, user_token):
        """Should validate permissions across multiple services."""
        connections = [
            create_mock_connection("notion", ["read_pages", "search_content"]),
            create_mock_connection("slack", ["channels:read", "chat:write"]),
        ]
        
        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)
        
        try:
            response = client.post(
                "/api/v1/auth/delegate",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "agent_id": "test-agent",
                    "permissions": [
                        "notion:pages:search",    # Valid - from Notion
                        "slack:channels:list",    # Valid - from Slack
                        "slack:messages:send",    # Valid - from Slack chat:write
                    ],
                },
            )
            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()
    
    def test_error_response_contains_hint(self, user_token):
        """Error response should include actionable hint."""
        connections = [create_mock_connection("notion", ["read_pages", "search_content"])]
        
        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)
        
        try:
            response = client.post(
                "/api/v1/auth/delegate",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "agent_id": "test-agent",
                    "permissions": ["notion:pages:create"],
                },
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert "hint" in data["detail"]
            assert "scopes" in data["detail"]["hint"].lower()
        finally:
            app.dependency_overrides.clear()
    
    def test_allowed_permissions_sorted(self, user_token):
        """Allowed permissions in error should be sorted alphabetically."""
        connections = [create_mock_connection("notion", ["read_pages", "search_content"])]
        
        app.dependency_overrides[deps.get_db] = override_db_with_connections(connections)
        client = TestClient(app)
        
        try:
            response = client.post(
                "/api/v1/auth/delegate",
                headers={"Authorization": f"Bearer {user_token}"},
                json={
                    "agent_id": "test-agent",
                    "permissions": ["notion:pages:create"],
                },
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            allowed = data["detail"]["allowed_permissions"]
            assert allowed == sorted(allowed)
        finally:
            app.dependency_overrides.clear()


class TestDelegationServiceValidation:
    """Test DelegationService._validate_permissions_subset."""
    
    def test_validate_permissions_uses_scope_mapper(self):
        """DelegationService should use ScopeMapper for validation."""
        from app.services.delegation_service import DelegationService
        
        mock_db = MagicMock()
        
        # Create mock connection
        conn = MagicMock()
        conn.service_id = "notion"
        conn.scopes_granted = ["read_pages"]
        
        mock_db.query.return_value.filter.return_value.all.return_value = [conn]
        
        service = DelegationService(mock_db)
        
        # Valid permission
        is_valid, reason, invalid, allowed = service._validate_permissions_subset(
            "sarah@acme.com",
            ["notion:pages:read"],
        )
        assert is_valid is True
        assert invalid == []
        
        # Invalid permission
        is_valid, reason, invalid, allowed = service._validate_permissions_subset(
            "sarah@acme.com",
            ["notion:pages:create"],
        )
        assert is_valid is False
        assert "notion:pages:create" in invalid
        assert "notion:pages:read" in allowed


class TestPermissionValidationError:
    """Test PermissionValidationError exception."""
    
    def test_exception_has_required_fields(self):
        """Exception should have invalid_permissions and allowed_permissions."""
        from app.services.delegation_service import PermissionValidationError
        
        error = PermissionValidationError(
            message="Test error",
            invalid_permissions=["notion:pages:create"],
            allowed_permissions=["notion:pages:read"],
        )
        
        assert error.message == "Test error"
        assert error.invalid_permissions == ["notion:pages:create"]
        assert error.allowed_permissions == ["notion:pages:read"]
    
    def test_exception_defaults_to_empty_lists(self):
        """Exception should default to empty lists."""
        from app.services.delegation_service import PermissionValidationError
        
        error = PermissionValidationError(message="Test error")
        
        assert error.invalid_permissions == []
        assert error.allowed_permissions == []
