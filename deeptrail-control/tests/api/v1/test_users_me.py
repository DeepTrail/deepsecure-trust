"""Tests for PATCH /api/v1/users/me and GET /api/v1/users/me endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User


def test_get_user_profile_default(client: TestClient, db: Session):
    """Test GET /users/me returns defaults when user has no record."""
    response = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers={"Authorization": "Bearer mock_user_token_testuser@example.com"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "testuser@example.com"
    assert data["onboarding_completed"] is False


def test_patch_user_onboarding_completed(client: TestClient, db: Session):
    """Test PATCH /users/me sets onboarding_completed."""
    response = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers={"Authorization": "Bearer mock_user_token_onboard@example.com"},
        json={"onboarding_completed": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "onboard@example.com"
    assert data["onboarding_completed"] is True

    # Verify persisted in DB
    user = db.query(User).filter(User.user_id == "onboard@example.com").first()
    assert user is not None
    assert user.onboarding_completed is True


def test_patch_user_creates_record_if_not_exists(client: TestClient, db: Session):
    """Test PATCH /users/me creates user record if one doesn't exist."""
    user_id = "newuser@example.com"

    # Verify user doesn't exist yet
    assert db.query(User).filter(User.user_id == user_id).first() is None

    response = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers={"Authorization": f"Bearer mock_user_token_{user_id}"},
        json={"onboarding_completed": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user_id
    assert data["onboarding_completed"] is True

    # Verify created in DB
    user = db.query(User).filter(User.user_id == user_id).first()
    assert user is not None


def test_patch_user_idempotent(client: TestClient, db: Session):
    """Test PATCH /users/me is idempotent."""
    user_id = "idempotent@example.com"
    headers = {"Authorization": f"Bearer mock_user_token_{user_id}"}

    # First patch
    response1 = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
        json={"onboarding_completed": True},
    )
    assert response1.status_code == 200

    # Second patch with same data
    response2 = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
        json={"onboarding_completed": True},
    )
    assert response2.status_code == 200
    assert response2.json()["onboarding_completed"] is True


def test_patch_user_can_reset_onboarding(client: TestClient, db: Session):
    """Test PATCH /users/me can set onboarding_completed back to False."""
    user_id = "reset@example.com"
    headers = {"Authorization": f"Bearer mock_user_token_{user_id}"}

    # Set to True
    client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
        json={"onboarding_completed": True},
    )

    # Set back to False
    response = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
        json={"onboarding_completed": False},
    )
    assert response.status_code == 200
    assert response.json()["onboarding_completed"] is False


def test_get_user_profile_after_update(client: TestClient, db: Session):
    """Test GET /users/me reflects updates from PATCH."""
    user_id = "getafter@example.com"
    headers = {"Authorization": f"Bearer mock_user_token_{user_id}"}

    # Update first
    client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
        json={"onboarding_completed": True},
    )

    # Verify GET returns updated data
    response = client.get(f"{settings.API_V1_STR}/users/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user_id
    assert data["onboarding_completed"] is True


def test_patch_user_empty_body(client: TestClient, db: Session):
    """Test PATCH /users/me with empty body makes no changes."""
    user_id = "empty@example.com"
    headers = {"Authorization": f"Bearer mock_user_token_{user_id}"}

    # Create user with default
    client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
        json={"onboarding_completed": False},
    )

    # Patch with empty body
    response = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
        json={},
    )
    assert response.status_code == 200
    assert response.json()["onboarding_completed"] is False
