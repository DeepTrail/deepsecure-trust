'''Base client class for API interaction.'''

import os
import re
from typing import Dict, Any, Optional, List
import requests
import logging
from datetime import datetime, timedelta
import jwt
import httpx

from .. import exceptions
from .. import __version__ # Import the version
from ..exceptions import DeepSecureError
from .identity_manager import IdentityManager
from .config import get_effective_deeptrail_control_url, get_effective_deeptrail_gateway_url
from .scope_mapper import merge_scopes, scopes_to_permissions

logger = logging.getLogger(__name__)


class BaseClient:
    def __init__(
        self,
        api_url: Optional[str] = None,
        token: Optional[str] = None,
        silent_mode: bool = False,
    ):
        # Phase 1: Use effective control URL for all operations
        self._api_url = api_url or get_effective_deeptrail_control_url() or "http://localhost:8000"
        
        # Phase 2: Gateway URL will be used for tool call routing
        self._gateway_url = get_effective_deeptrail_gateway_url() or "http://localhost:8002"
        
        self._token = token
        self._silent_mode = silent_mode
        self._identity_manager = IdentityManager(api_client=self, silent_mode=silent_mode)
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._step_up_retry_count: int = 0
        self._cumulative_oauth_scopes: List[str] = []
        self._max_step_up_retries: int = 2
        self.client = httpx.Client(
            headers={"User-Agent": f"DeepSecureCLI/{__version__}"}, timeout=30.0
        )



    def _request(
        self,
        method: str,
        path: str,
        expected_status: int = 200,
        *,
        raise_on_error: bool = True,
        **kwargs,
    ):
        headers = kwargs.pop("headers", {})
        # Remove internal parameters that shouldn't be passed to httpx
        kwargs.pop("is_backend_request", None)
        base_url_override = kwargs.pop("base_url_override", None)
        
        # Check if Authorization header is already set (e.g., by _authenticated_request)
        if "Authorization" not in headers:
            if not self._token:
                # For BaseClient, we can't authenticate without knowing which agent
                # This is typically handled by subclasses or by passing a token explicitly
                raise DeepSecureError(
                    "No authentication token available. BaseClient requires explicit token or subclass implementation."
                )
            headers["Authorization"] = f"Bearer {self._token}"
        
        # Check for explicit URL override first
        if base_url_override:
            url = f"{base_url_override}{path}"
        elif self._is_management_operation(path):
            # Phase 1: Direct routing to deeptrail-control
            # Management operations: agent management, policy management, authentication, credentials
            url = f"{self._api_url}{path}"
        else:
            # Phase 2: Gateway routing (future implementation)
            # Tool calls to external services route through deeptrail-gateway
            url = f"{self._gateway_url}{path}"

        try:
            response = self.client.request(
                method, url, headers=headers, **kwargs
            )
            if raise_on_error:
                response.raise_for_status()
            return response
        except httpx.TimeoutException as e:
            logger.error(f"Request timed out: {method} {path}")
            raise DeepSecureError(f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            logger.error(f"Network error during API request: {method} {path}: {e}")
            raise DeepSecureError(f"Network error during API request to {path}: {e}") from e

    def _is_management_operation(self, path: str) -> bool:
        """
        Determine if a path represents a management operation that should route to control.
        
        Management Operations (Phase 1) -> Direct to deeptrail-control:
        - Agent Management (create, list, delete)
        - Policy Management (create, update, delete)
        - Authentication (challenge, token)
        - Credential Operations (issue, revoke)
        
        Tool Operations (Phase 2) -> Through deeptrail-gateway:
        - External API Calls (OpenAI, Google, AWS)
        - Secret Injection
        - Policy Enforcement
        - Audit Logging
        """
        management_prefixes = [
            "/api/v1/agents",
            "/api/v1/auth",
            "/api/v1/vault",
            "/api/v1/policies",
            "/api/v1/credentials",
            "/api/v1/bootstrap",
            "/health",
            "/ready",
            "/metrics",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]
        
        # Make the comparison case-insensitive
        path_lower = path.lower()
        return any(path_lower.startswith(prefix.lower()) for prefix in management_prefixes)

    def _authenticate(self):
        """
        Base authentication method.
        Subclasses should override this to implement specific authentication logic.
        """
        raise NotImplementedError(
            "BaseClient._authenticate() must be implemented by subclasses or a token must be provided explicitly."
        )

    def get_access_token(self, agent_id: str) -> str:
        """
        Performs challenge-response authentication to get a new JWT access token.
        """
        try:
            # The challenge request must be unauthenticated.
            challenge_url = f"{self._api_url}/api/v1/auth/challenge"
            challenge_response = self.client.post(challenge_url, json={"agent_id": agent_id})
            challenge_response.raise_for_status()
            nonce = challenge_response.json()["nonce"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise DeepSecureError(f"Authentication failed: Agent '{agent_id}' not found on the server.")
            raise DeepSecureError(f"Failed to get challenge: {e.response.text}") from e
        except Exception as e:
            raise DeepSecureError(f"An unexpected error occurred during challenge request: {e}") from e

        private_key_b64 = self._identity_manager.get_private_key(agent_id)
        if not private_key_b64:
            raise DeepSecureError(f"Could not find private key for agent '{agent_id}'. Cannot authenticate.")
        
        try:
            signature = self._identity_manager.sign(private_key_b64, nonce)
        except Exception as e:
            raise DeepSecureError(f"Failed to sign challenge: {e}") from e

        try:
            # C7: Include resource parameter (RFC 8707) for audience-restricted tokens
            token_url = f"{self._api_url}/api/v1/auth/token"
            token_payload: Dict[str, Any] = {
                "agent_id": agent_id,
                "nonce": nonce,
                "signature": signature,
            }
            resource_url = os.environ.get("DEEPSECURE_GATEWAY_RESOURCE_URL") or self._gateway_url
            if resource_url:
                token_payload["resource"] = resource_url
            token_response = self.client.post(token_url, json=token_payload)
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = token_data["access_token"]
            
            try:
                decoded_token = jwt.decode(access_token, options={"verify_signature": False})
                self._token_expires_at = datetime.fromtimestamp(decoded_token.get("exp", 0))
            except jwt.PyJWTError:
                self._token_expires_at = datetime.now() + timedelta(minutes=5)

            self._access_token = access_token
            return self._access_token
        except httpx.HTTPStatusError as e:
            raise DeepSecureError(f"Failed to get token: {e.response.text}") from e
        except Exception as e:
            raise DeepSecureError(f"An unexpected error occurred during token request: {e}") from e

    @staticmethod
    def _parse_www_authenticate_scopes(www_authenticate: str) -> List[str]:
        """Extract scope values from a WWW-Authenticate Bearer header (E3)."""
        if not www_authenticate:
            return []
        match = re.search(r'scope="([^"]+)"', www_authenticate)
        if not match:
            return []
        return match.group(1).split()

    def _handle_insufficient_scope(
        self,
        www_authenticate: str,
        agent_id: str,
    ) -> bool:
        """Attempt step-up by expanding OAuth scopes. Returns True if retry allowed."""
        if self._step_up_retry_count >= self._max_step_up_retries:
            logger.warning(
                "Step-up retry budget exhausted (%d/%d)",
                self._step_up_retry_count,
                self._max_step_up_retries,
            )
            return False

        new_scopes = self._parse_www_authenticate_scopes(www_authenticate)
        if not new_scopes:
            return False

        self._cumulative_oauth_scopes = merge_scopes(
            self._cumulative_oauth_scopes, new_scopes
        )
        self._step_up_retry_count += 1
        logger.info(
            "Step-up auth attempt %d/%d for agent %s — scopes: %s",
            self._step_up_retry_count,
            self._max_step_up_retries,
            agent_id,
            self._cumulative_oauth_scopes,
        )

        # Re-authenticate agent JWT (user must have expanded delegation out-of-band)
        self._access_token = None
        self._token_expires_at = None
        self.get_access_token(agent_id)
        return True

    def gateway_request_with_step_up(
        self,
        method: str,
        path: str,
        agent_id: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Gateway request with automatic step-up on insufficient_scope 403 (E3)."""
        while True:
            response = self._authenticated_request(
                method, path, agent_id, raise_on_error=False, **kwargs
            )
            if response.status_code != 403:
                response.raise_for_status()
                return response

            www_auth = response.headers.get("WWW-Authenticate", "")
            if 'error="insufficient_scope"' not in www_auth:
                response.raise_for_status()
                return response

            if not self._handle_insufficient_scope(www_auth, agent_id):
                response.raise_for_status()
                return response

    def get_cumulative_oauth_scopes(self) -> List[str]:
        """Return scopes accumulated during step-up retries."""
        return list(self._cumulative_oauth_scopes)

    def get_step_up_permissions(self) -> List[str]:
        """Return DeepSecure permissions implied by cumulative OAuth scopes."""
        return scopes_to_permissions(self._cumulative_oauth_scopes)

    def _authenticated_request(
        self,
        method: str,
        path: str,
        agent_id: str,
        delegation_token: Optional[str] = None,
        **kwargs: Any
    ) -> httpx.Response:
        """
        Ensures the client is authenticated before making a request.
        If a delegation_token (macaroon) is provided, it is used instead of the
        standard agent JWT.
        """
        auth_headers = kwargs.pop("headers", {})

        if delegation_token:
            # If a macaroon is provided, use it for delegation.
            # The gateway will handle this special header.
            auth_headers["X-Delegation-Token"] = delegation_token
        else:
            # Otherwise, perform standard JWT authentication.
            if not self._access_token or not self._token_expires_at or (self._token_expires_at <= datetime.now() + timedelta(seconds=10)):
                self.get_access_token(agent_id)
            
            auth_headers["Authorization"] = f"Bearer {self._access_token}"
        
        raise_on_error = kwargs.pop("raise_on_error", True)
        return self._request(
            method, path, headers=auth_headers, raise_on_error=raise_on_error, **kwargs
        )

    def _unauthenticated_request(
        self,
        method: str,
        path: str,
        **kwargs: Any
    ) -> httpx.Response:
        """
        Makes an unauthenticated request using standardized routing.
        Used for initial agent creation and other pre-authentication operations.
        """
        headers = kwargs.pop("headers", {})
        
        # Phase 1: Direct routing to deeptrail-control
        url = f"{self._api_url}{path}"
        
        try:
            response = self.client.request(
                method, url, headers=headers, **kwargs
            )
            response.raise_for_status()
            return response
        except httpx.TimeoutException as e:
            logger.error(f"Request timed out: {method} {path}")
            raise DeepSecureError(f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            logger.error(f"Network error during API request: {method} {path}: {e}")
            raise DeepSecureError(f"Network error during API request to {path}: {e}") from e

    def bootstrap_kubernetes(self, k8s_token: str, agent_id: Optional[str] = None) -> httpx.Response:
        """
        Calls the backend to bootstrap an agent's identity using a K8s Service Account Token.
        Enhanced to work with the new backend implementation.
        """
        import uuid
        
        # Create correlation ID for audit logging
        correlation_id = str(uuid.uuid4())
        
        # Use the correct schema format expected by the backend
        payload = {"token": k8s_token}
        
        headers = {
            "X-Correlation-ID": correlation_id,
            "User-Agent": f"DeepSecureCLI/{__version__}"
        }
        
        try:
            url = f"{self._api_url}/api/v1/auth/bootstrap/kubernetes"
            response = self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response
            
        except httpx.HTTPStatusError as e:
            # Handle structured error responses from enhanced backend
            self._handle_bootstrap_error(e, "kubernetes", correlation_id)
        except httpx.RequestError as e:
            logger.error(f"Network error during Kubernetes bootstrap: {e}")
            raise DeepSecureError(f"Network error during Kubernetes bootstrap: {e}") from e

    def bootstrap_aws(self, iam_token: str, agent_id: Optional[str] = None) -> httpx.Response:
        """
        Calls the backend to bootstrap an agent's identity using an AWS STS token.
        Enhanced to work with the new backend implementation.
        """
        import uuid
        
        # Create correlation ID for audit logging
        correlation_id = str(uuid.uuid4())
        
        # Use the correct schema format expected by the backend
        payload = {"token": iam_token}
        
        headers = {
            "X-Correlation-ID": correlation_id,
            "User-Agent": f"DeepSecureCLI/{__version__}"
        }
        
        try:
            url = f"{self._api_url}/api/v1/auth/bootstrap/aws"
            response = self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response
            
        except httpx.HTTPStatusError as e:
            # Handle structured error responses from enhanced backend
            self._handle_bootstrap_error(e, "aws", correlation_id)
        except httpx.RequestError as e:
            logger.error(f"Network error during AWS bootstrap: {e}")
            raise DeepSecureError(f"Network error during AWS bootstrap: {e}") from e

    def bootstrap_azure(self, imds_token: str, agent_id: Optional[str] = None) -> httpx.Response:
        """
        Calls the backend to bootstrap an agent's identity using an Azure IMDS token.
        New method for Azure Managed Identity support.
        """
        import uuid
        
        # Create correlation ID for audit logging
        correlation_id = str(uuid.uuid4())
        
        # Use the correct schema format expected by the backend
        payload = {"token": imds_token}
        
        headers = {
            "X-Correlation-ID": correlation_id,
            "User-Agent": f"DeepSecureCLI/{__version__}"
        }
        
        try:
            url = f"{self._api_url}/api/v1/auth/bootstrap/azure"
            response = self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response
            
        except httpx.HTTPStatusError as e:
            # Handle structured error responses from enhanced backend
            self._handle_bootstrap_error(e, "azure", correlation_id)
        except httpx.RequestError as e:
            logger.error(f"Network error during Azure bootstrap: {e}")
            raise DeepSecureError(f"Network error during Azure bootstrap: {e}") from e

    def bootstrap_gcp(self, identity_token: str, agent_id: Optional[str] = None) -> httpx.Response:
        """
        Calls the backend to bootstrap an agent's identity using a GCP OIDC identity token.
        GCP bootstrap returns a JWT (access_token) instead of key material.
        """
        import uuid
        
        correlation_id = str(uuid.uuid4())
        
        payload = {"identity_token": identity_token}
        
        headers = {
            "X-Correlation-ID": correlation_id,
            "User-Agent": f"DeepSecureCLI/{__version__}"
        }
        
        try:
            url = f"{self._api_url}/api/v1/auth/bootstrap/gcp"
            response = self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response
            
        except httpx.HTTPStatusError as e:
            self._handle_bootstrap_error(e, "gcp", correlation_id)
        except httpx.RequestError as e:
            logger.error(f"Network error during GCP bootstrap: {e}")
            raise DeepSecureError(f"Network error during GCP bootstrap: {e}") from e

    def bootstrap_docker(self, runtime_token: str, agent_id: Optional[str] = None) -> httpx.Response:
        """
        Calls the backend to bootstrap an agent's identity using a Docker runtime token.
        New method for Docker container identity support.
        """
        import uuid
        
        # Create correlation ID for audit logging
        correlation_id = str(uuid.uuid4())
        
        # Use the correct schema format expected by the backend
        payload = {"token": runtime_token}
        
        headers = {
            "X-Correlation-ID": correlation_id,
            "User-Agent": f"DeepSecureCLI/{__version__}"
        }
        
        try:
            url = f"{self._api_url}/api/v1/auth/bootstrap/docker"
            response = self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response
            
        except httpx.RequestError as e:
            # Handle structured error responses from enhanced backend
            self._handle_bootstrap_error(e, "docker", correlation_id)
        except httpx.RequestError as e:
            logger.error(f"Network error during Docker bootstrap: {e}")
            raise DeepSecureError(f"Network error during Docker bootstrap: {e}") from e

    def _handle_bootstrap_error(self, error: httpx.HTTPStatusError, platform: str, correlation_id: str):
        """
        Handle structured error responses from the enhanced bootstrap backend.
        """
        try:
            error_detail = error.response.json().get("detail", {})
            
            if isinstance(error_detail, dict):
                error_code = error_detail.get("error_code", "UNKNOWN_ERROR")
                error_message = error_detail.get("message", str(error))
                platform_info = error_detail.get("platform", platform)
                correlation = error_detail.get("correlation_id", correlation_id)
                
                logger.error(
                    f"Bootstrap failed for {platform_info}: {error_message} "
                    f"(Code: {error_code}, Correlation: {correlation})"
                )
                
                # Raise appropriate exception based on error type
                if error.response.status_code == 401:
                    raise DeepSecureError(f"Token validation failed for {platform}: {error_message}")
                elif error.response.status_code == 403:
                    raise DeepSecureError(f"No matching policy found for {platform}: {error_message}")
                elif error.response.status_code == 502:
                    raise DeepSecureError(f"External service unavailable for {platform}: Please try again later")
                elif error.response.status_code == 504:
                    raise DeepSecureError(f"Bootstrap timeout for {platform}: Please try again")
                else:
                    raise DeepSecureError(f"Bootstrap failed for {platform}: {error_message}")
            else:
                # Fallback for non-structured error responses
                raise DeepSecureError(f"Bootstrap failed for {platform}: {error.response.text}")
                
        except (ValueError, KeyError) as e:
            # Error parsing response JSON
            logger.error(f"Failed to parse error response: {e}")
            raise DeepSecureError(f"Bootstrap failed for {platform}: {error.response.text}") from error 