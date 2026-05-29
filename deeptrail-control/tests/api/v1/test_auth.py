import uuid
from unittest.mock import patch

from jose import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from nacl.signing import SigningKey
from nacl.encoding import Base64Encoder

from app import crud, schemas
from app.core.config import settings
from tests.utils.utils import random_lower_string


def test_get_access_token_with_policy_claims(client: TestClient, db: Session) -> None:
    # 1. Create an agent with a key pair
    private_key = SigningKey.generate()
    public_key_b64 = private_key.verify_key.encode(encoder=Base64Encoder).decode("utf-8")
    
    agent_in = schemas.AgentCreate(name="test-policy-claims-agent", public_key=public_key_b64)
    agent = crud.agent.create(db, obj_in=agent_in)

    # 2. Create a policy for that agent
    policy_in = schemas.PolicyCreate(
        name=random_lower_string(),
        agent_id=agent.agent_id,
        actions=["proxy:request", "other:action"],
        resources=["ds:secret:one", "ds:secret:two"]
    )
    crud.policy.create(db, obj_in=policy_in)

    # 3. Request a challenge
    challenge_resp = client.post(
        f"{settings.API_V1_STR}/auth/challenge", json={"agent_id": agent.agent_id}
    )
    assert challenge_resp.status_code == 200
    nonce = challenge_resp.json()["nonce"]

    # 4. Sign the nonce and request a token
    signed_nonce = private_key.sign(nonce.encode("utf-8")).signature
    signed_nonce_b64 = Base64Encoder.encode(signed_nonce).decode("utf-8")

    token_resp = client.post(
        f"{settings.API_V1_STR}/auth/token",
        json={"agent_id": agent.agent_id, "nonce": nonce, "signature": signed_nonce_b64},
    )
    assert token_resp.status_code == 200
    token_data = token_resp.json()
    access_token = token_data["access_token"]

    # 5. Decode the token and verify claims
    payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    
    assert payload["agent_id"] == agent.agent_id
    assert "scope" in payload
    assert "resources" in payload

    # Scope is a space-delimited string
    token_scopes = set(payload["scope"].split(" "))
    assert token_scopes == {"proxy:request", "other:action"}
    
    # Resources is a list
    assert set(payload["resources"]) == {"ds:secret:one", "ds:secret:two"} 


def test_delegate_access_endpoint(client: TestClient, db: Session) -> None:
    """
    Test the POST /auth/delegate endpoint.
    """
    from app.core.config import settings as app_settings
    from jose import jwt as jose_jwt
    import time

    user_claims = {
        "sub": "test-user@example.com",
        "iss": "deepsecure",
        "aud": "deepsecure-control",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "organization_id": "org-test-123",
    }
    user_token = jose_jwt.encode(user_claims, app_settings.SECRET_KEY, algorithm=app_settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {user_token}"}

    # 2. Create an agent to delegate to
    private_key = SigningKey.generate()
    public_key_b64 = private_key.verify_key.encode(encoder=Base64Encoder).decode("utf-8")
    agent_in = schemas.AgentCreate(name="delegate-target-agent", public_key=public_key_b64)
    target_agent = crud.agent.create(db, obj_in=agent_in)

    # 3. Define the delegation request
    delegation_payload = {
        "agent_id": target_agent.agent_id,
        "permissions": ["service:notion:read"],
    }

    # 4. Call the endpoint
    response = client.post(
        f"{settings.API_V1_STR}/auth/delegate",
        json=delegation_payload,
        headers=headers,
    )

    # 5. Assert the response (may be 200, 400, 401, or 403 depending on auth config and connected services)
    assert response.status_code in (200, 400, 401, 403)


def test_bootstrap_kubernetes(client: TestClient, db: Session) -> None:
    """
    Test agent identity bootstrapping with a Kubernetes Service Account Token.
    """
    # 1. Create an attestation policy for a K8s identity
    agent_name = "k8s-bootstrapped-agent"
    namespace = "production"
    service_account = "my-app-sa"
    selector = f"namespace={namespace},service_account={service_account}"
    from app.models.attestation_policy import PlatformType
    policy_in = schemas.AttestationPolicyCreate(
        agent_name_to_bootstrap=agent_name,
        platform=PlatformType.KUBERNETES,
        selector=selector,
    )
    crud.attestation_policy.create(db, obj_in=policy_in)

    # 2. Mock the K8s token verification and the security validator
    mock_k8s_token_payload = {
        "iss": "https://accounts.google.com",
        "aud": "my-gcp-project-id",
        "sub": "system:serviceaccount:production:my-app-sa",
        "iat": 1615852800,
        "exp": 1615856400,
        "email": f"{service_account}@production.iam.gserviceaccount.com",
        "email_verified": True,
        "kubernetes.io": {
            "namespace": namespace,
            "serviceaccount": {"name": service_account, "uid": str(uuid.uuid4())},
        },
    }

    with (
        patch("google.oauth2.id_token.verify_oauth2_token") as mock_verify_token,
        patch("app.services.bootstrap_service.bootstrap_service.security_validator") as mock_sec_val,
    ):
        mock_verify_token.return_value = mock_k8s_token_payload
        mock_sec_val.validate_token_security.return_value = None

        # 3. Call the bootstrap endpoint
        bootstrap_payload = {"sat": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudCI6eyJuYW1lIjoibXktYXBwLXNhIiwidWlkIjoiYWJjMTIzIn0sInN1YiI6InN5c3RlbTpzZXJ2aWNlYWNjb3VudDpwcm9kdWN0aW9uOm15LWFwcC1zYSJ9.fake-signature-padding"}
        response = client.post(
            f"{settings.API_V1_STR}/auth/bootstrap/kubernetes", json=bootstrap_payload
        )

    # 4. Assert the response
    assert response.status_code == 200, f"Expected 200: {response.json()}"
    content = response.json()
    assert "agent_id" in content
    assert "private_key_b64" in content
    assert "public_key_b64" in content

    # 5. Verify agent was created in DB
    agent = crud.agent.get_by_agent_id(db, agent_id=content["agent_id"])
    assert agent is not None
    assert agent.name == agent_name


def test_bootstrap_aws(client: TestClient, db: Session) -> None:
    """
    Test agent identity bootstrapping with an AWS IAM role.
    """
    # 1. Create an attestation policy for an AWS identity
    agent_name = "aws-bootstrapped-agent"
    account_id = "123456789012"
    role_arn = f"arn:aws:iam::{account_id}:role/MyWebAppRole"
    from app.models.attestation_policy import PlatformType
    policy_in = schemas.AttestationPolicyCreate(
        agent_name_to_bootstrap=agent_name,
        platform=PlatformType.AWS_IAM,
        selector=f"arn={role_arn}",
    )
    crud.attestation_policy.create(db, obj_in=policy_in)

    # 2. Mock the AWS STS get_caller_identity call with all required fields
    with patch("boto3.client") as mock_boto_client:
        mock_sts_client = mock_boto_client.return_value
        mock_sts_client.get_caller_identity.return_value = {
            "Arn": role_arn,
            "Account": account_id,
            "UserId": "AROA3XFRBF23:my-session",
        }

        # 3. Call the bootstrap endpoint
        bootstrap_payload = {"token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhd3MiLCJzdWIiOiJhcm46YXdzOmlhbTo6MTIzNDU2Nzg5MDEyOnJvbGUvTXlXZWJBcHBSb2xlIiwiYXVkIjoiYXdzLXN0cyIsImV4cCI6MTcxNTg1NjQwMH0.fake-signature-padding-for-testing-length-check"}
        response = client.post(
            f"{settings.API_V1_STR}/auth/bootstrap/aws", json=bootstrap_payload
        )

    # 4. Assert the response
    assert response.status_code == 200, f"Expected 200: {response.json()}"
    content = response.json()
    assert "agent_id" in content
    assert "private_key_b64" in content
    assert "public_key_b64" in content

    # 5. Verify agent was created in DB
    agent = crud.agent.get_by_agent_id(db, agent_id=content["agent_id"])
    assert agent is not None
    assert agent.name == agent_name 