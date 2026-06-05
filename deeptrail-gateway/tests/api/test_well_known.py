"""
Tests for Protected Resource Metadata (RFC 9728) endpoints.

Validates that:
- PRM is accessible without authentication
- Response contains required RFC 9728 fields
- Path-based variant returns identical content
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.api.well_known import router, _build_prm_document


class TestPRMDocument:
    """Unit tests for the PRM document builder."""

    def test_prm_has_resource(self):
        doc = _build_prm_document()
        assert "resource" in doc
        assert isinstance(doc["resource"], str)

    def test_prm_has_authorization_servers(self):
        doc = _build_prm_document()
        assert "authorization_servers" in doc
        assert isinstance(doc["authorization_servers"], list)
        assert len(doc["authorization_servers"]) >= 1

    def test_prm_has_scopes_supported(self):
        doc = _build_prm_document()
        assert "scopes_supported" in doc
        assert "mcp:tools" in doc["scopes_supported"]

    def test_prm_has_bearer_methods(self):
        doc = _build_prm_document()
        assert "bearer_methods_supported" in doc
        assert "header" in doc["bearer_methods_supported"]


class TestPRMEndpoints:
    """Integration tests for the PRM HTTP endpoints."""

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_well_known_oauth_protected_resource(self, client):
        response = client.get("/.well-known/oauth-protected-resource")
        assert response.status_code == 200
        data = response.json()
        assert "resource" in data
        assert "authorization_servers" in data
        assert "scopes_supported" in data

    def test_well_known_oauth_protected_resource_mcp(self, client):
        response = client.get("/.well-known/oauth-protected-resource/mcp")
        assert response.status_code == 200
        data = response.json()
        assert "resource" in data
        assert "authorization_servers" in data

    def test_both_endpoints_return_same_content(self, client):
        r1 = client.get("/.well-known/oauth-protected-resource").json()
        r2 = client.get("/.well-known/oauth-protected-resource/mcp").json()
        assert r1 == r2

    def test_no_auth_required(self, client):
        """PRM must be accessible without any Authorization header."""
        response = client.get("/.well-known/oauth-protected-resource")
        assert response.status_code == 200

    def test_content_type_is_json(self, client):
        response = client.get("/.well-known/oauth-protected-resource")
        assert "application/json" in response.headers["content-type"]

    def test_authorization_server_url_format(self, client):
        data = client.get("/.well-known/oauth-protected-resource").json()
        for url in data["authorization_servers"]:
            assert url.startswith("http")
