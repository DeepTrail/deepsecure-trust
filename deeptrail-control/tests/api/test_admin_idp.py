"""Tests for admin IdP group → role mapping CRUD."""

import pytest
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.api.deps import get_db
from app.middleware.admin_auth import require_admin
from app.models.idp_group_role_mapping import IdpGroupRoleMapping
from app.services.idp_mapping_service import IdpMappingService
from app.services.role_resolver import RoleResolver

import app.models.idp_group_role_mapping  # noqa: ensure table created


ISSUER = "https://keycloak.example.com/realms/deepsecure"


@pytest.fixture()
def client(db):
    def _override_db():
        yield db

    def _override_admin():
        return {"sub": "admin@test.com", "roles": ["admin"]}

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[require_admin] = _override_admin
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()


def test_list_mappings_empty(client):
    resp = client.get("/api/v1/admin/idp/mappings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["mappings"] == []
    assert "idp_metadata" in data


def test_create_and_list_mapping(client, db):
    resp = client.post(
        "/api/v1/admin/idp/mappings",
        json={
            "group_name": "engineering",
            "role": "engineer",
            "idp_issuer": ISSUER,
        },
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["group_name"] == "engineering"
    assert created["role"] == "engineer"
    assert created["enabled"] is True

    list_resp = client.get(f"/api/v1/admin/idp/mappings?idp_issuer={ISSUER}")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1


def test_create_duplicate_returns_409(client):
    payload = {
        "group_name": "sales-reps",
        "role": "sales",
        "idp_issuer": ISSUER,
    }
    assert client.post("/api/v1/admin/idp/mappings", json=payload).status_code == 201
    dup = client.post("/api/v1/admin/idp/mappings", json=payload)
    assert dup.status_code == 409


def test_create_invalid_role_returns_400(client):
    resp = client.post(
        "/api/v1/admin/idp/mappings",
        json={"group_name": "bad", "role": "superuser", "idp_issuer": ISSUER},
    )
    assert resp.status_code == 400


def test_patch_disable_mapping(client):
    created = client.post(
        "/api/v1/admin/idp/mappings",
        json={"group_name": "security-team", "role": "security", "idp_issuer": ISSUER},
    ).json()

    resp = client.patch(
        f"/api/v1/admin/idp/mappings/{created['id']}",
        json={"enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_delete_mapping(client):
    created = client.post(
        "/api/v1/admin/idp/mappings",
        json={"group_name": "temp-group", "role": "employee", "idp_issuer": ISSUER},
    ).json()

    del_resp = client.delete(f"/api/v1/admin/idp/mappings/{created['id']}")
    assert del_resp.status_code == 204

    listing = client.get(f"/api/v1/admin/idp/mappings?idp_issuer={ISSUER}")
    ids = [m["id"] for m in listing.json()["mappings"]]
    assert created["id"] not in ids


def test_import_yaml(client, db):
    resp = client.post("/api/v1/admin/idp/mappings/import-yaml")
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] >= 1
    assert data["skipped"] >= 0

    second = client.post("/api/v1/admin/idp/mappings/import-yaml")
    assert second.json()["imported"] == 0


def test_db_mapping_overrides_yaml_role(db):
    """DB mapping for a group should override YAML role for same group."""
    db.add(
        IdpGroupRoleMapping(
            idp_issuer=ISSUER,
            group_name="engineering@deeptrail.com",
            role="sales",
            enabled=True,
            created_by="admin@test.com",
        )
    )
    db.commit()

    svc = IdpMappingService(db)
    roles = svc.resolve_group_roles(
        ISSUER,
        ["engineering@deeptrail.com"],
        yaml_mapper=None,
    )
    assert roles == ["sales"]

    resolver = RoleResolver()
    resolved = resolver.resolve(
        jwt_roles=None,
        user_session_role=None,
        groups=["engineering@deeptrail.com"],
        db=db,
        idp_issuer=ISSUER,
    )
    assert resolved == ["sales"]
