# DeepSecure Python SDK Reference

> **SDK Version:** 0.1.12  
> **HTTP API Reference:** [API_REFERENCE.md](API_REFERENCE.md) | **Quickstart:** [QUICKSTART.md](QUICKSTART.md)

---

## Table of Contents

1. [Installation](#1-installation)
2. [Client Initialization](#2-client-initialization)
3. [Authentication](#3-authentication)
4. [Agent Management](#4-agent-management)
5. [Credential Lifecycle](#5-credential-lifecycle)
6. [Vault and Secrets](#6-vault-and-secrets)
7. [Gateway Integration](#7-gateway-integration)
8. [Delegation](#8-delegation)
9. [Policy Management](#9-policy-management)
10. [Framework Integrations](#10-framework-integrations)
11. [CLI Reference](#11-cli-reference)
12. [Code Examples](#12-code-examples)
13. [Exceptions](#13-exceptions)

---

## 1. Installation

```bash
pip install deepsecure
```

For Ed25519 cryptographic operations:

```bash
pip install pynacl
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPSECURE_DEEPTRAIL_CONTROL_URL` | Yes | None | Control Plane URL (e.g., `http://localhost:8000`) |
| `DEEPSECURE_GATEWAY_URL` | No | None | Gateway URL (e.g., `http://localhost:8002`) |
| `DEEPSECURE_DEEPTRAIL_CONTROL_API_TOKEN` | No | None | Backend API token for admin operations |
| `DEEPSECURE_DEBUG` | No | `false` | Enable verbose logging |

---

## 2. Client Initialization

```python
from deepsecure import Client

# Using environment variables
client = Client()

# Explicit URLs
client = Client(
    deeptrail_control_url="http://localhost:8000",
    deeptrail_gateway_url="http://localhost:8002",
    silent_mode=False  # suppress non-error output
)
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `client.control_url` | `str` | The Control Plane URL |
| `client.gateway_url` | `str` | The Gateway URL |
| `client.version` | `str` | SDK version (e.g., `"0.1.12"`) |
| `client.identity_manager` | `IdentityManager` | Ed25519 key management |
| `client.credentials` | `CredentialsNamespace` | Credential operations |
| `client.agents` | `AgentClient` | Agent CRUD operations |
| `client.vault` | `VaultClient` | Secret and credential management |
| `client.gateway` | `GatewayClient` | HTTP proxy through Gateway |
| `client.policy` | `PolicyClient` | Policy CRUD operations |
| `client.openai` | `OpenAIIntegration` | OpenAI via Gateway |
| `client.anthropic` | `AnthropicIntegration` | Anthropic via Gateway |

---

## 3. Authentication

### Authenticate an Agent

Performs Ed25519 challenge-response against the Control Plane and stores the session JWT.

```python
# The agent must exist and have its keys in the OS keyring
client.authenticate("sdr-assistant-001")

# Alias
client.login("sdr-assistant-001")
```

The full flow:
1. Loads the agent's Ed25519 private key from the OS keyring
2. Requests a challenge nonce from `POST /api/v1/auth/agent/challenge`
3. Signs the challenge with the private key
4. Verifies the signature via `POST /api/v1/auth/agent/verify`
5. Stores the returned Agent Session JWT for subsequent requests

### Get Access Token

Lower-level method that returns the JWT directly:

```python
token = client.get_access_token("sdr-assistant-001")
```

---

## 4. Agent Management

### Create an Agent

```python
agent = client.agents.create(
    agent_id="sdr-assistant-001",
    name="SDR Sales Assistant"
)
# Returns an Agent resource object
```

The `create` method automatically generates an Ed25519 keypair, stores the private key in the OS keyring, and registers the public key with the Control Plane.

### Get or Create an Agent by Name

```python
# Returns existing agent or creates one
agent = client.agent("my-assistant", auto_create=True)

# Alias
agent = client.get_agent("my-assistant", auto_create=True)
```

### List Agents

```python
agents = client.agents.list_agents()
# Returns: [{"agent_id": "...", "name": "...", "status": "active", ...}]

# Also available at top level
agents = client.list_agents()
```

### Get Agent Details

```python
agent = client.agents.get("sdr-assistant-001")
# Returns: {"agent_id": "...", "name": "...", "publicKey": "...", ...}

# By name
agent = client.agents.get_by_name("SDR Sales Assistant")
```

### Describe Agent

```python
info = client.agents.describe_agent("sdr-assistant-001")
```

### Update Agent

```python
client.agents.update_agent("sdr-assistant-001", name="New Name")
```

### Delete Agent

```python
client.agents.delete_agent("sdr-assistant-001")
```

### Platform Bootstrap

Create agents using platform-native identity rather than pre-shared keys:

```python
# Kubernetes ServiceAccount
agent = client.agents.bootstrap_kubernetes(sat="eyJhbGci...")

# AWS IAM
agent = client.agents.bootstrap_aws(token="aws-sts-token...")

# Azure Managed Identity
agent = client.agents.bootstrap_azure(token="azure-mi-token...")

# Docker
agent = client.agents.bootstrap_docker(
    container_id="abc123",
    runtime_token="docker-token..."
)
```

---

## 5. Credential Lifecycle

Ephemeral credentials for short-lived access.

### Issue a Credential

```python
cred = client.credentials.issue(
    agent_id="sdr-assistant-001",
    scope="notion:read",
    ttl="5m"  # 5 minutes, also "1h", "7d"
)
# Returns: {"credential_id": "cred-abc123", "status": "active", ...}
```

### Verify a Credential

```python
result = client.credentials.verify("cred-abc123")
# Returns: {"is_valid": true, "status": "active", "scope": "notion:read", ...}
```

### Revoke a Credential

```python
client.credentials.revoke("cred-abc123")
# Returns: {"credential_id": "cred-abc123", "status": "revoked"}
```

### Using the Agent Resource

```python
agent = client.agent("my-agent")
cred = agent.issue_credential(scope="notion:read", ttl="5m")
```

---

## 6. Vault and Secrets

### Store a Secret (Admin)

Uses Shamir secret sharing across Control Plane and Gateway:

```python
client.store_secret_direct(
    name="openai-api-key",
    value="sk-...",
    target_base_url="https://api.openai.com",
    metadata={"service": "openai"}
)
```

### Retrieve a Secret (Admin)

```python
# With value (Shamir reassembly)
secret = client.get_secret_direct("openai-api-key", include_value=True)
# Returns: {"name": "openai-api-key", "value": "sk-...", "metadata": {...}}

# Metadata only
meta = client.get_secret_direct("openai-api-key", include_value=False)
```

### Delete a Secret (Admin)

```python
client.delete_secret_direct("openai-api-key")
```

### List Secrets (Admin)

```python
result = client.list_secrets_direct()
# Returns: {"secrets": [...], "count": 5}
```

### Agent-Scoped Secret Access

Secrets accessed through the Gateway never expose the raw value to the agent:

```python
# Access via Gateway proxy (agent never sees the secret)
result = client.get_secret(
    agent_id="sdr-assistant-001",
    secret_name="openai-api-key",
    path="/v1/models"
)
```

---

## 7. Gateway Integration

The Gateway proxies HTTP requests to external APIs with automatic credential injection.

### GatewayClient

```python
# Generic HTTP methods through the Gateway proxy
response = client.gateway.get(
    "https://api.openai.com",
    "/v1/models",
    secret_name="openai-api-key",
    agent_id="sdr-assistant-001"
)

response = client.gateway.post(
    "https://api.openai.com",
    "/v1/chat/completions",
    json={"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]},
    secret_name="openai-api-key",
    agent_id="sdr-assistant-001"
)

# Also: .put(), .delete(), .patch()
```

The Gateway adds the `X-Target-Base-URL` and `X-Deeptrail-Secret-Name` headers automatically, then injects the secret into the outbound request.

### OpenAI Integration

```python
# List models
models = client.openai.list_models(agent_id="sdr-assistant-001")

# Chat completion
response = client.openai.chat_completion(
    agent_id="sdr-assistant-001",
    model="gpt-4",
    messages=[{"role": "user", "content": "Summarize this document"}]
)

# Embeddings
embeddings = client.openai.create_embedding(
    agent_id="sdr-assistant-001",
    input="text to embed",
    model="text-embedding-3-small"
)
```

### Anthropic Integration

```python
# Create message
response = client.anthropic.create_message(
    agent_id="sdr-assistant-001",
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}]
)

# Count tokens
count = client.anthropic.count_tokens(
    agent_id="sdr-assistant-001",
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Agent Resource Shortcuts

```python
agent = client.agent("my-agent")

# Gateway request
response = agent.gateway_request(
    method="GET",
    target_base_url="https://api.openai.com",
    path="/v1/models",
    secret_name="openai-api-key"
)

# OpenAI models
models = agent.openai_list_models()
```

---

## 8. Delegation

Macaroon-based delegation for user-to-agent and agent-to-agent permission grants.

### Create a Delegation

```python
delegation = client.delegate_access(
    agent_id="sdr-assistant-001",
    permissions=["notion:pages:search", "notion:pages:read"],
    constraints={"rate_limit": 100}
)
# Returns: {"delegation_token": "...", "delegation_id": "...", ...}
```

### Create a Delegation Chain

For multi-agent workflows where one agent delegates to another:

```python
chain = client.create_delegation_chain(
    delegations=[
        {
            "target_agent_id": "sub-agent-002",
            "resource": "notion",
            "permissions": ["notion:pages:search"],
            "ttl_seconds": 3600
        }
    ]
)
```

### Verify a Delegation

```python
result = client.verify_delegation(delegation_token="MDAyNmxvY2F0...")
```

---

## 9. Policy Management

Policies define what agents are allowed to do at the organizational level.

### Create a Policy

```python
policy = client.policy.create(
    name="notion-read-policy",
    agent_id="sdr-assistant-001",
    actions=["read", "search"],
    resources=["notion:pages"],
    effect="allow",
    description="Allow reading Notion pages"
)
```

### List Policies

```python
policies = client.policy.list()
```

### Get / Delete a Policy

```python
policy = client.policy.get(policy_id)
policy = client.policy.get_by_name("notion-read-policy")
client.policy.delete(policy_id)
```

### Attestation Policies

For platform-native identity verification:

```python
# Create a Kubernetes attestation policy
policy = client.policy.create_attestation_policy(
    name="k8s-production",
    platform="kubernetes",
    rules={"namespace": "production", "service_account": "agent-sa"}
)

# List, get, update, delete
policies = client.policy.list_attestation_policies()
policy = client.policy.get_attestation_policy(policy_id)
client.policy.update_attestation_policy(policy_id, rules={...})
client.policy.delete_attestation_policy(policy_id)
```

---

## 10. Framework Integrations

### LangChain

Use DeepSecure tools within LangChain agents (see `examples/05_langchain_secure_tools.py`):

```python
from deepsecure import Client
from langchain.tools import Tool

client = Client()
client.authenticate("my-agent")

# Create a tool that uses the Gateway for API calls
def search_notion(query: str) -> str:
    response = client.gateway.post(
        "https://api.notion.com",
        "/v1/search",
        json={"query": query},
        secret_name="notion-api-key",
        agent_id="my-agent"
    )
    return response.text

notion_tool = Tool(
    name="search_notion",
    description="Search Notion workspace",
    func=search_notion
)
```

### CrewAI

See `examples/03_crewai_secure_tools.py` and `examples/10_crewai_delegation_workflow.py`.

### Multi-Agent Delegation

See `examples/07_multi_agent_communication.py` and `examples/11_advanced_delegation_patterns.py`.

---

## 11. CLI Reference

The `deepsecure` CLI provides administrative access to the platform.

### Configuration

```bash
# Set Control Plane URL
deepsecure configure set-url http://localhost:8000

# Set Gateway URL
deepsecure configure set-gateway-url http://localhost:8002

# Set API token (prompts for input)
deepsecure configure set-token

# View current configuration
deepsecure configure show

# Get individual values
deepsecure configure get-url
deepsecure configure get-gateway-url
deepsecure configure get-token
```

### Agent Commands

```bash
# Create an agent
deepsecure agent create --name "My Agent"

# List all agents
deepsecure agent list

# Describe an agent
deepsecure agent describe <agent-id>

# Delete an agent
deepsecure agent delete <agent-id>

# Cleanup unused agents
deepsecure agent cleanup
```

### Vault Commands

```bash
# Store a secret
deepsecure vault store --name "openai-api-key" --value "sk-..."

# Get a secret value
deepsecure vault get-secret <secret-name>

# List secrets (metadata only)
deepsecure vault list

# Delete a secret
deepsecure vault delete <secret-name>
```

### Policy Commands

```bash
# Create a policy
deepsecure policy create --name "read-policy" --agent-id "my-agent" \
  --actions read,search --resources "notion:pages"

# List policies
deepsecure policy list

# Get a policy
deepsecure policy get <policy-id>

# Delete a policy
deepsecure policy delete <policy-id>

# Attestation policies
deepsecure policy attestation create-k8s --name "prod-k8s" --namespace production
deepsecure policy attestation create-aws --name "prod-aws"
deepsecure policy attestation create-azure --name "prod-azure"
deepsecure policy attestation create-docker --name "prod-docker"
deepsecure policy attestation list
deepsecure policy attestation get <policy-id>
deepsecure policy attestation validate <policy-id>
```

### Gateway Commands

```bash
# Check Gateway health
deepsecure gateway health

# Test proxy connectivity
deepsecure gateway test-proxy

# Gateway status
deepsecure gateway status

# Connectivity check
deepsecure gateway connectivity
```

---

## 12. Code Examples

The `examples/` directory contains runnable scripts demonstrating common patterns:

| Script | Description |
|--------|-------------|
| `01_create_agent_and_issue_credential.py` | Create an agent and issue a short-lived credential |
| `02_sdk_secret_fetch.py` | Store and retrieve secrets through the vault |
| `03_crewai_secure_tools.py` | CrewAI agent with DeepSecure-backed tools |
| `05_langchain_secure_tools.py` | LangChain agent with Gateway-proxied API calls |
| `07_multi_agent_communication.py` | Multi-agent delegation patterns |
| `08_gateway_secret_injection_demo.py` | Gateway secret injection flow |
| `09_langchain_delegation_workflow.py` | LangChain with delegation chains |
| `10_crewai_delegation_workflow.py` | CrewAI with delegation workflows |
| `11_advanced_delegation_patterns.py` | Complex delegation topologies |
| `13_quickstart_openai_list_models.py` | Simplest OpenAI integration |
| `14_quickstart_openai_policy_enforcement.py` | OpenAI with policy enforcement |
| `15_langchain_composio_notion_integration.py` | LangChain + Composio + Notion |

### Minimal Working Example

```python
from deepsecure import Client

# Initialize
client = Client(
    deeptrail_control_url="http://localhost:8000",
    deeptrail_gateway_url="http://localhost:8002"
)

# Create an agent
agent = client.agents.create(agent_id="quickstart-agent", name="Quickstart")

# Authenticate
client.authenticate("quickstart-agent")

# Store a secret
client.store_secret_direct(
    name="openai-key",
    value="sk-your-key",
    target_base_url="https://api.openai.com"
)

# Call OpenAI through the Gateway (secret injected automatically)
models = client.openai.list_models(agent_id="quickstart-agent")
print(models)
```

---

## 13. Exceptions

All exceptions inherit from `DeepSecureError`:

| Exception | When Raised |
|-----------|-------------|
| `DeepSecureError` | Base exception for all SDK errors |
| `DeepSecureClientError` | Client configuration or general errors |
| `ApiError` | HTTP API errors (includes status code and response) |
| `VaultError` | Vault operations (secret store/retrieve/delete failures) |
| `AuthenticationError` | Authentication failures (missing keys, bad challenge) |
| `IdentityManagerError` | Key management errors (keyring access, key generation) |

### Error Handling

```python
from deepsecure import Client, ApiError, DeepSecureClientError

client = Client()

try:
    client.authenticate("unknown-agent")
except AuthenticationError as e:
    print(f"Auth failed: {e}")

try:
    client.store_secret_direct("key", "value", "https://api.example.com")
except ApiError as e:
    print(f"API error {e.status_code}: {e}")
except DeepSecureClientError as e:
    print(f"Client error: {e}")
```

---

*SDK Reference Version: 2.0 | April 2026 | Package: deepsecure v0.1.12*
