import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from tests.utils.utils import random_lower_string, random_uuid


def test_create_k8s_attestation_policy(
    client: TestClient, superuser_token_headers: dict, db: Session
) -> None:
    agent_name = random_lower_string()
    selector = f"system:serviceaccount:default:test-sa-{random_lower_string(6)}"

    data = {
        "agent_name_to_bootstrap": agent_name,
        "platform": "kubernetes",
        "selector": selector,
    }
    response = client.post(
        f"{settings.API_V1_STR}/policies/attestation/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["agent_name_to_bootstrap"] == agent_name
    assert content["platform"] == "kubernetes"
    assert content["selector"] == selector
    assert "id" in content


def test_create_aws_attestation_policy(
    client: TestClient, superuser_token_headers: dict, db: Session
) -> None:
    agent_name = random_lower_string()
    role_arn = f"arn:aws:iam::{random_uuid()}:role/test-role"

    data = {
        "agent_name_to_bootstrap": agent_name,
        "platform": "aws_iam",
        "selector": role_arn,
    }
    response = client.post(
        f"{settings.API_V1_STR}/policies/attestation/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["agent_name_to_bootstrap"] == agent_name
    assert content["platform"] == "aws_iam"
    assert content["selector"] == role_arn
    assert "id" in content


def test_read_attestation_policy(
    client: TestClient, superuser_token_headers: dict, db: Session
) -> None:
    agent_name = random_lower_string()
    selector = f"system:serviceaccount:default:read-sa-{random_lower_string(6)}"
    data = {
        "agent_name_to_bootstrap": agent_name,
        "platform": "kubernetes",
        "selector": selector,
    }
    response = client.post(
        f"{settings.API_V1_STR}/policies/attestation/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    policy_id = response.json()["id"]

    response = client.get(
        f"{settings.API_V1_STR}/policies/attestation/{policy_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == policy_id
    assert content["agent_name_to_bootstrap"] == agent_name


def test_list_attestation_policies(
    client: TestClient, superuser_token_headers: dict, db: Session
) -> None:
    client.post(
        f"{settings.API_V1_STR}/policies/attestation/",
        headers=superuser_token_headers,
        json={
            "agent_name_to_bootstrap": "list-agent-1",
            "platform": "kubernetes",
            "selector": f"system:serviceaccount:ns1:sa1-{random_lower_string(6)}",
        },
    )
    client.post(
        f"{settings.API_V1_STR}/policies/attestation/",
        headers=superuser_token_headers,
        json={
            "agent_name_to_bootstrap": "list-agent-2",
            "platform": "aws_iam",
            "selector": f"arn:aws:iam:::role/test-role-{random_lower_string(6)}",
        },
    )

    response = client.get(
        f"{settings.API_V1_STR}/policies/attestation",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert isinstance(content, list)
    assert len(content) >= 2


def test_delete_attestation_policy(
    client: TestClient, superuser_token_headers: dict, db: Session
) -> None:
    data = {
        "agent_name_to_bootstrap": "delete-me",
        "platform": "kubernetes",
        "selector": f"system:serviceaccount:to-delete:delete-sa-{random_lower_string(6)}",
    }
    response = client.post(
        f"{settings.API_V1_STR}/policies/attestation/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    policy_id = response.json()["id"]

    response = client.delete(
        f"{settings.API_V1_STR}/policies/attestation/{policy_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == policy_id

    response = client.get(
        f"{settings.API_V1_STR}/policies/attestation/{policy_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
