"""Unified bootstrap client for DeepSecure agent identity.

Orchestrates the platform-specific bootstrap flow:
  1. Detect platform (GCP / AWS / local)
  2. Obtain a platform identity token
  3. Exchange it at the control plane for a DeepSecure agent JWT
  4. Optionally fetch delegations and per-delegation JWTs

Reference implementation: agents/gemini/entrypoint.sh
"""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

from ..exceptions import DeepSecureError
from .config import get_effective_deeptrail_control_url, get_effective_deeptrail_gateway_url

logger = logging.getLogger(__name__)

_METADATA_TIMEOUT = 3.0
_API_TIMEOUT = 15.0


class Platform(str, Enum):
    GCP = "gcp"
    AWS = "aws"
    LOCAL = "local"
    AUTO = "auto"


@dataclass
class Delegation:
    delegation_id: str
    service: str
    permissions: List[str]
    jwt: Optional[str] = None


@dataclass
class BootstrapResult:
    """Returned by :func:`bootstrap` — everything an agent needs to call the gateway."""

    agent_id: str
    jwt: str
    platform: Platform
    control_url: str
    gateway_url: str
    delegations: List[Delegation] = field(default_factory=list)
    expires_in: Optional[int] = None

    def to_mcp_json(self) -> Dict[str, Any]:
        """Produce the JSON config block that Gemini / Claude Code / Codex expect."""
        if self.delegations:
            jwt_to_use = self.delegations[0].jwt or self.jwt
        else:
            jwt_to_use = self.jwt

        return {
            "mcpServers": {
                "deepsecure": {
                    "url": f"{self.gateway_url}/mcp",
                    "transport": "http",
                    "headers": {
                        "Authorization": f"Bearer {jwt_to_use}",
                    },
                }
            }
        }

    def to_env(self) -> str:
        """Produce shell ``export`` statements."""
        lines = [
            f'export DEEPSECURE_AGENT_JWT="{self.jwt}"',
            f'export DEEPSECURE_GATEWAY_URL="{self.gateway_url}"',
            f'export DEEPSECURE_CONTROL_URL="{self.control_url}"',
            f'export DEEPSECURE_AGENT_ID="{self.agent_id}"',
            f'export DEEPSECURE_PLATFORM="{self.platform.value}"',
        ]
        if self.delegations:
            first_del = self.delegations[0]
            if first_del.jwt:
                lines.append(f'export DEEPSECURE_DELEGATION_JWT="{first_del.jwt}"')
            lines.append(f'export DEEPSECURE_DELEGATION_ID="{first_del.delegation_id}"')
        return "\n".join(lines)


class BootstrapClient:
    """Thin HTTP client that performs the DeepSecure bootstrap flow.

    Unlike the heavier ``BaseClient`` / ``AgentClient`` stack this class is
    intentionally self-contained so that ``pip install deepsecure`` (core only)
    is sufficient to bootstrap.
    """

    def __init__(
        self,
        control_url: Optional[str] = None,
        gateway_url: Optional[str] = None,
        timeout: float = _API_TIMEOUT,
    ):
        self.control_url = (
            control_url
            or get_effective_deeptrail_control_url()
            or "http://localhost:8000"
        )
        self.gateway_url = (
            gateway_url
            or get_effective_deeptrail_gateway_url()
            or "http://localhost:8002"
        )
        self._http = httpx.Client(timeout=timeout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def bootstrap(
        self,
        agent_id: str,
        platform: Platform = Platform.AUTO,
        *,
        fetch_delegations: bool = True,
    ) -> BootstrapResult:
        """Run the full bootstrap flow and return a :class:`BootstrapResult`.

        1. Resolve *platform* (auto-detect if ``AUTO``).
        2. Obtain a DeepSecure agent JWT via the platform-specific endpoint.
        3. (Optional) Fetch delegations and per-delegation JWTs.
        """
        if platform is Platform.AUTO:
            platform = self._detect_platform()
            logger.info("Auto-detected platform: %s", platform.value)

        jwt_token, resolved_agent_id, expires_in = self._bootstrap_for_platform(
            agent_id, platform
        )

        delegations: List[Delegation] = []
        if fetch_delegations:
            try:
                delegations = self._fetch_delegations(jwt_token, resolved_agent_id)
            except Exception as exc:
                logger.warning("Could not fetch delegations: %s", exc)

        return BootstrapResult(
            agent_id=resolved_agent_id,
            jwt=jwt_token,
            platform=platform,
            control_url=self.control_url,
            gateway_url=self.gateway_url,
            delegations=delegations,
            expires_in=expires_in,
        )

    # ------------------------------------------------------------------
    # Platform detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_platform() -> Platform:
        if _is_gcp():
            return Platform.GCP
        if _is_aws():
            return Platform.AWS
        return Platform.LOCAL

    # ------------------------------------------------------------------
    # Platform dispatchers
    # ------------------------------------------------------------------

    def _bootstrap_for_platform(
        self, agent_id: str, platform: Platform
    ) -> tuple[str, str, Optional[int]]:
        """Return ``(jwt, agent_id, expires_in)``."""
        if platform is Platform.GCP:
            return self._bootstrap_gcp(agent_id)
        if platform is Platform.AWS:
            return self._bootstrap_aws(agent_id)
        if platform is Platform.LOCAL:
            return self._bootstrap_local(agent_id)
        raise DeepSecureError(f"Unsupported platform: {platform}")

    # ------------------------------------------------------------------
    # GCP bootstrap
    # ------------------------------------------------------------------

    def _bootstrap_gcp(self, agent_id: str) -> tuple[str, str, Optional[int]]:
        oidc_token = _gcp_fetch_identity_token(audience=self.control_url)
        resp = self._post(
            "/api/v1/auth/bootstrap/gcp",
            json={"identity_token": oidc_token},
        )
        data = resp.json()
        return (
            data["access_token"],
            data.get("agent_id", agent_id),
            data.get("expires_in"),
        )

    # ------------------------------------------------------------------
    # AWS bootstrap
    # ------------------------------------------------------------------

    def _bootstrap_aws(self, agent_id: str) -> tuple[str, str, Optional[int]]:
        token = _aws_fetch_identity_token()
        resp = self._post(
            "/api/v1/auth/bootstrap/aws",
            json={"token": token},
        )
        data = resp.json()
        return (
            data["access_token"],
            data.get("agent_id", agent_id),
            data.get("expires_in"),
        )

    # ------------------------------------------------------------------
    # Local (keyring) bootstrap — challenge / response
    # ------------------------------------------------------------------

    def _bootstrap_local(self, agent_id: str) -> tuple[str, str, Optional[int]]:
        private_key_b64 = _local_get_private_key(agent_id)

        challenge_resp = self._post(
            "/api/v1/auth/agent/challenge",
            json={"agent_id": agent_id},
        )
        challenge = challenge_resp.json()["challenge"]

        signature = _sign_challenge(private_key_b64, challenge)

        verify_resp = self._post(
            "/api/v1/auth/agent/verify",
            json={
                "agent_id": agent_id,
                "challenge": challenge,
                "signature": signature,
            },
        )
        data = verify_resp.json()
        return (
            data["access_token"],
            data.get("agent_id", agent_id),
            data.get("expires_in"),
        )

    # ------------------------------------------------------------------
    # Delegation helpers (mirrors entrypoint.sh logic)
    # ------------------------------------------------------------------

    def _fetch_delegations(
        self, jwt_token: str, agent_id: str
    ) -> List[Delegation]:
        resp = self._get(
            "/api/v1/auth/agent/delegations",
            headers={"Authorization": f"Bearer {jwt_token}"},
        )
        raw = resp.json()
        items: list = raw if isinstance(raw, list) else raw.get("delegations", [])

        delegations: List[Delegation] = []
        for item in items:
            del_id = item.get("delegation_id") or item.get("id", "")
            service = item.get("service", "unknown")
            permissions = item.get("permissions", [])

            del_jwt: Optional[str] = None
            try:
                tok_resp = self._post(
                    "/api/v1/auth/agent/delegation-token",
                    json={"delegation_id": del_id},
                    headers={"Authorization": f"Bearer {jwt_token}"},
                )
                del_jwt = tok_resp.json().get("access_token")
            except Exception as exc:
                logger.warning(
                    "Failed to get delegation token for %s: %s", del_id, exc
                )

            delegations.append(
                Delegation(
                    delegation_id=del_id,
                    service=service,
                    permissions=permissions,
                    jwt=del_jwt,
                )
            )
        return delegations

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _post(self, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.control_url}{path}"
        headers = kwargs.pop("headers", {})
        try:
            resp = self._http.post(url, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            _raise_api_error(exc, path)
        except httpx.RequestError as exc:
            raise DeepSecureError(f"Network error calling {path}: {exc}") from exc

    def _get(self, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.control_url}{path}"
        headers = kwargs.pop("headers", {})
        try:
            resp = self._http.get(url, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            _raise_api_error(exc, path)
        except httpx.RequestError as exc:
            raise DeepSecureError(f"Network error calling {path}: {exc}") from exc

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "BootstrapClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ======================================================================
# Module-level helpers (keep BootstrapClient dependency-light)
# ======================================================================

def _is_gcp() -> bool:
    return bool(
        os.environ.get("K_SERVICE")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCE_METADATA_HOST")
    )


def _is_aws() -> bool:
    return bool(
        os.environ.get("AWS_EXECUTION_ENV")
        or os.environ.get("ECS_CONTAINER_METADATA_URI")
        or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    )


def _gcp_fetch_identity_token(audience: str) -> str:
    """Fetch a GCP OIDC identity token from the metadata server."""
    import urllib.request

    url = (
        "http://metadata.google.internal/computeMetadata/v1/"
        f"instance/service-accounts/default/identity?audience={audience}&format=full"
    )
    req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
    try:
        with urllib.request.urlopen(req, timeout=_METADATA_TIMEOUT) as resp:
            return resp.read().decode().strip()
    except Exception as exc:
        raise DeepSecureError(
            f"Failed to fetch GCP identity token from metadata server: {exc}"
        ) from exc


def _aws_fetch_identity_token() -> str:
    """Fetch AWS identity via IMDS v2 + STS ``GetCallerIdentity``."""
    try:
        import boto3  # type: ignore[import-untyped]

        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        return identity["Arn"]
    except ImportError:
        raise DeepSecureError(
            "boto3 is required for AWS bootstrap. Install with: pip install boto3"
        )
    except Exception as exc:
        raise DeepSecureError(f"Failed to fetch AWS identity: {exc}") from exc


def _local_get_private_key(agent_id: str) -> str:
    """Retrieve the Ed25519 private key from the OS keyring."""
    try:
        import keyring  # type: ignore[import-untyped]
        from .identity_provider import _get_keyring_service_name_for_agent

        service = _get_keyring_service_name_for_agent(agent_id)
        key = keyring.get_password(service, agent_id)
        if not key:
            raise DeepSecureError(
                f"No private key found for agent '{agent_id}' in system keyring. "
                "Register the agent first with: deepsecure agent create"
            )
        return key
    except ImportError:
        raise DeepSecureError(
            "keyring is required for local bootstrap. "
            "Install with: pip install deepsecure[cli]"
        )


def _sign_challenge(private_key_b64: str, challenge: str) -> str:
    """Sign a challenge string with an Ed25519 private key."""
    from cryptography.hazmat.primitives.asymmetric import ed25519

    raw_bytes = base64.b64decode(private_key_b64)
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes)
    signature = private_key.sign(challenge.encode("utf-8"))
    return base64.b64encode(signature).decode("utf-8")


def _raise_api_error(exc: httpx.HTTPStatusError, path: str) -> None:
    """Convert an httpx status error into a DeepSecureError with context."""
    try:
        detail = exc.response.json().get("detail", exc.response.text)
    except Exception:
        detail = exc.response.text
    raise DeepSecureError(
        f"API error {exc.response.status_code} on {path}: {detail}"
    ) from exc


# ------------------------------------------------------------------
# Convenience function (top-level SDK export)
# ------------------------------------------------------------------

def bootstrap(
    agent_id: str,
    *,
    platform: str = "auto",
    control_url: Optional[str] = None,
    gateway_url: Optional[str] = None,
    fetch_delegations: bool = True,
) -> BootstrapResult:
    """One-call convenience wrapper used by ``from deepsecure import bootstrap``.

    >>> result = bootstrap("agent-abc123", platform="gcp")
    >>> print(result.jwt)
    """
    plat = Platform(platform)
    with BootstrapClient(control_url=control_url, gateway_url=gateway_url) as client:
        return client.bootstrap(agent_id, plat, fetch_delegations=fetch_delegations)
