"""
Container integration: revoked agent JWT must be rejected at gateway.

Marked integration — runs against live docker-compose services when available.
"""

import base64
import json
import subprocess
import time

import pytest
from nacl.signing import SigningKey


def _curl(method, url, data=None, headers=None, fail_on_http_error=True):
    flags = ["curl", "-s", "-w", "\n__HTTP__%{http_code}", "-X", method, url]
    if fail_on_http_error:
        flags.insert(1, "-f")
    cmd = flags
    for key, value in (headers or {}).items():
        cmd += ["-H", f"{key}: {value}"]
    if data is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(data)]
    try:
        out = subprocess.check_output(cmd, text=True, timeout=15)
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"service unavailable: {exc}")
    body, http = out.rsplit("__HTTP__", 1)
    return body.strip(), http.strip()


def _services_healthy():
    try:
        _, c = _curl("GET", "http://localhost:8000/health")
        _, g = _curl("GET", "http://localhost:8002/health")
        return c == "200" and g == "200"
    except Exception:
        return False


@pytest.mark.integration
def test_revoked_agent_jwt_rejected_at_gateway():
    if not _services_healthy():
        pytest.skip("control/gateway containers not healthy on localhost")

    login_body, _ = _curl(
        "POST",
        "http://localhost:8000/api/v1/auth/login",
        {"email": "sarah@acme.com", "password": "sarah123"},
    )
    user_token = json.loads(login_body)["token"]

    agent_id = f"revoke-int-{int(time.time())}"
    sk = SigningKey.generate()
    pub = base64.b64encode(sk.verify_key.encode()).decode()
    _curl(
        "POST",
        "http://localhost:8000/api/v1/agents",
        {"agent_id": agent_id, "name": "revoke-int", "public_key": pub},
        {"Authorization": f"Bearer {user_token}"},
    )
    _curl(
        "POST",
        "http://localhost:8000/api/v1/auth/delegate",
        {"agent_id": agent_id, "permissions": ["notion:pages:search"]},
        {"Authorization": f"Bearer {user_token}"},
    )
    challenge = json.loads(
        _curl(
            "POST",
            "http://localhost:8000/api/v1/auth/agent/challenge",
            {"agent_id": agent_id},
        )[0]
    )["challenge"]
    sig = base64.urlsafe_b64encode(sk.sign(challenge.encode()).signature).decode()
    verify = json.loads(
        _curl(
            "POST",
            "http://localhost:8000/api/v1/auth/agent/verify",
            {"agent_id": agent_id, "challenge": challenge, "signature": sig},
        )[0]
    )
    access = verify["access_token"]
    session_id = verify["session_id"]

    refresh_body, refresh_http = _curl(
        "POST",
        "http://localhost:8000/api/v1/auth/agent/refresh",
        None,
        {"Authorization": f"Bearer {access}"},
    )
    assert refresh_http == "200", refresh_body
    new_access = json.loads(refresh_body)["access_token"]

    revoke_body, revoke_http = _curl(
        "POST",
        "http://localhost:8000/api/v1/auth/agent/revoke",
        {"session_id": session_id},
        {"Authorization": f"Bearer {new_access}"},
    )
    assert revoke_http == "200", revoke_body
    assert json.loads(revoke_body)["revoked"] is True

    _, gateway_http = _curl(
        "POST",
        "http://localhost:8002/mcp",
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        {
            "Authorization": f"Bearer {new_access}",
            "Mcp-Method": "tools/list",
        },
        fail_on_http_error=False,
    )
    assert gateway_http == "401", (
        f"expected revoked JWT to be rejected at gateway, got HTTP {gateway_http}"
    )
