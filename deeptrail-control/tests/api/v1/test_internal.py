import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import uuid
import json

from app.core.config import settings
from app.models.credential import Secret


def _create_test_secret(db: Session, name: str, share_1: str = '[1, "aabbccdd"]', metadata: dict = None):
    """Directly insert a Secret row for testing, bypassing the split logic."""
    secret = Secret(
        name=name,
        share_1=share_1,
        secret_metadata=metadata,
    )
    db.add(secret)
    db.commit()
    db.refresh(secret)
    return secret


def test_get_secret_share_success(client: TestClient, db: Session):
    secret_name = f"component-test-secret-{uuid.uuid4()}"
    target_url = "http://my-target-service.com"
    metadata = {"target_base_url": target_url}

    _create_test_secret(db, name=secret_name, metadata=metadata)

    headers = {"X-Internal-API-Token": settings.GATEWAY_INTERNAL_API_TOKEN}
    response = client.get(f"/api/v1/internal/secrets/{secret_name}/share", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["share_1"] is not None
    assert data["target_base_url"] == target_url


def test_get_secret_share_no_metadata(client: TestClient, db: Session):
    secret_name = f"component-test-secret-no-meta-{uuid.uuid4()}"

    _create_test_secret(db, name=secret_name)

    headers = {"X-Internal-API-Token": settings.GATEWAY_INTERNAL_API_TOKEN}
    response = client.get(f"/api/v1/internal/secrets/{secret_name}/share", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["share_1"] is not None
    assert data["target_base_url"] is None


def test_get_secret_share_not_found(client: TestClient, db: Session):
    secret_name = "does-not-exist"
    headers = {"X-Internal-API-Token": settings.GATEWAY_INTERNAL_API_TOKEN}
    response = client.get(f"/api/v1/internal/secrets/{secret_name}/share", headers=headers)
    assert response.status_code == 404


def test_get_secret_share_wrong_auth(client: TestClient, db: Session):
    response_no_auth = client.get("/api/v1/internal/secrets/some-secret/share")
    assert response_no_auth.status_code == 403

    headers = {"X-Internal-API-Token": "wrong-token"}
    response_wrong_auth = client.get("/api/v1/internal/secrets/some-secret/share", headers=headers)
    assert response_wrong_auth.status_code == 401
