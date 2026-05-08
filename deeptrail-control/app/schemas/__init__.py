"""Expose Pydantic schemas for easier importing."""

from .token import Token
from .agent import Agent, AgentCreate, AgentUpdate, AgentList, AgentCreateResponse, AgentToolInfo, AgentToolsResponse  # noqa
from .user import UserUpdate, UserResponse  # noqa
from .credential import Credential, CredentialIssueRequest, CredentialIssueResponse, CredentialRevokeResponse, CredentialVerifyResponse # noqa
from .policy import Policy, PolicyCreate, PolicyUpdate # noqa
from .auth import ChallengeRequest, ChallengeResponse, TokenRequest, KubernetesBootstrapRequest, AWSBootstrapRequest, AzureBootstrapRequest, DockerBootstrapRequest, BootstrapResponse # noqa
from .delegation import DelegationRequest, DelegationResponse # noqa
from .attestation_policy import ( # noqa
    AttestationPolicy,
    AttestationPolicyCreate,
    AttestationPolicyUpdate,
)
from .bootstrap import BootstrapRequest, BootstrapResponse # noqa
from .agent_auth import ( # noqa
    AgentChallengeRequest,
    AgentChallengeResponse,
    AgentVerifyRequest,
    AgentVerifyResponse,
    AgentAuthError,
)

__all__ = [
    "AgentBase",
    "AgentCreate",
    "AgentUpdate",
    "Agent",
    "AgentList",
    "AgentRotateKeyRequest",
    "CredentialBase",
    "Credential",
    "CredentialIssueRequest",
    "CredentialIssueResponse",
    "CredentialRevokeResponse",
    "CredentialVerifyResponse",
    "CredentialRevokeRequest",
    "DelegationRequest",
    "DelegationResponse",
    "PolicyBase",
    "PolicyCreate",
    "PolicyUpdate",
    "Policy",
    "Token",
    "AgentLogin",
    "ChallengeRequest",
    "ChallengeResponse",
    "TokenRequest",
    "KubernetesBootstrapRequest",
    "AWSBootstrapRequest",
    "AzureBootstrapRequest",
    "DockerBootstrapRequest",
    "AttestationPolicy",
    "AttestationPolicyCreate",
    "AttestationPolicyUpdate",
    "BootstrapResponse",
    # Agent auth (Virtual MCP Server MVP)
    "AgentChallengeRequest",
    "AgentChallengeResponse",
    "AgentVerifyRequest",
    "AgentVerifyResponse",
    "AgentAuthError",
    # Agent tools
    "AgentCreateResponse",
    "AgentToolInfo",
    "AgentToolsResponse",
    # User
    "UserUpdate",
    "UserResponse",
]

# Add any other schemas needed globally here 