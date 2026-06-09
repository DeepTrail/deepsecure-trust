# SDK Agent Bootstrap Flow

How a DeepSecure agent deployed with `Dockerfile.sdk` bootstraps its identity, fetches delegations, and executes tool calls — without any static secrets.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Cloud Run Job (or ECS Task)                                            │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Container: gemini-agent-sdk:latest                             │    │
│  │                                                                 │    │
│  │  ┌──────────────┐    ┌───────────────┐    ┌────────────────┐   │    │
│  │  │ Python 3.11  │    │  Gemini CLI   │    │ DeepSecure SDK │   │    │
│  │  │ (entrypoint) │───▶│  (Node 20)    │◀───│ (httpx, pyjwt) │   │    │
│  │  └──────────────┘    └───────┬───────┘    └───────┬────────┘   │    │
│  │                              │                    │             │    │
│  └──────────────────────────────┼────────────────────┼─────────────┘    │
│                                 │                    │                   │
│  Service Account (GCP) or       │                    │                   │
│  IAM Role (AWS) attached ───────┘                    │                   │
└─────────────────────────────────────────────────────┼───────────────────┘
                                                      │
                                    ┌─────────────────┼──────────────────┐
                                    │                 ▼                  │
                                    │   DeepSecure Control Plane        │
                                    │   (https://app.deepsecure.one)    │
                                    │                                   │
                                    │   /api/v1/auth/bootstrap/gcp      │
                                    │   /api/v1/auth/bootstrap/aws      │
                                    │   /api/v1/auth/agent/delegations  │
                                    │   /api/v1/auth/agent/delegation-  │
                                    │          token                    │
                                    └──────────────┬────────────────────┘
                                                   │
                                    ┌──────────────▼────────────────────┐
                                    │   DeepSecure MCP Gateway          │
                                    │   (https://app.deepsecure.one/mcp)│
                                    │                                   │
                                    │   tools/call → Notion, Slack,     │
                                    │                Exa, Gmail, etc.   │
                                    └───────────────────────────────────┘
```

## Image Layers

`Dockerfile.sdk` produces a dual-runtime image:

```
┌─────────────────────────────────────────┐
│  Layer 5: ENTRYPOINT [python3, ...]     │  ← Python-based entrypoint
├─────────────────────────────────────────┤
│  Layer 4: entrypoint_sdk.py,            │  ← Agent scripts
│           entrypoint.sh (fallback),     │
│           mcp-bridge.mjs                │
├─────────────────────────────────────────┤
│  Layer 3: deepsecure SDK (core only)    │  ← httpx, pyjwt, pydantic, toml
│           pip install /tmp/sdk          │     NO keyring, typer, rich
├─────────────────────────────────────────┤
│  Layer 2: Python 3.11 + venv            │  ← ~40 MB
│           curl, jq, ca-certificates     │
├─────────────────────────────────────────┤
│  Layer 1: @google/gemini-cli (Node 20)  │  ← Gemini CLI (npm global)
├─────────────────────────────────────────┤
│  Base: node:20-slim (Debian)            │
└─────────────────────────────────────────┘
```

Key design choice: the SDK is installed with **core dependencies only** (`pip install deepsecure`), not `deepsecure[cli]`. This means `keyring`, `typer`, and `rich` are not present. All imports of these packages in the SDK are guarded with `try/except ImportError` to support this minimal environment.

---

## GCP OIDC Bootstrap (Production Path)

Used when the agent runs on **Cloud Run**, **GKE**, or **Compute Engine** with a GCP Service Account attached.

### Prerequisites

| Component | Value | Set By |
|-----------|-------|--------|
| Cloud Run Job | `gemini-deepsecure-agent` | Platform engineer |
| Service Account | `debugging-agent-sa@project.iam.gserviceaccount.com` | Platform engineer |
| Agent registered in DeepSecure | `debugging-agent-sa` with `platform=gcp_workload_identity` | Admin via UI/API |
| Attestation policy | Maps SA email → agent identity | Admin via UI/API |
| Delegations | At least one active delegation with permissions | Admin via UI |

### Env vars (injected by Cloud Run Job config)

```yaml
DEEPSECURE_CONTROL_URL: https://app.deepsecure.one
DEEPSECURE_GATEWAY_URL: https://app.deepsecure.one/mcp
AGENT_ID:               debugging-agent-sa
AGENT_MAX_ROUNDS:       3
AGENT_INTERVAL_SECONDS: 60
GEMINI_API_KEY:         (from Secret Manager)
```

### Step-by-Step Flow

#### Step 1: Container starts, Python entrypoint runs

Cloud Run execs the Dockerfile's `ENTRYPOINT`:

```
/opt/deepsecure-venv/bin/python3 /app/entrypoint_sdk.py
```

The script reads env vars and detects no `AGENT_JWT` is set, so `platform = Platform.GCP`.

```python
client = BootstrapClient(
    control_url="https://app.deepsecure.one",
    gateway_url="https://app.deepsecure.one/mcp"
)
result = client.bootstrap("debugging-agent-sa", Platform.GCP)
```

#### Step 2: Fetch GCP OIDC identity token from metadata server

The SDK calls the **GCP metadata server** (available to all GCP workloads):

```
GET http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity
    ?audience=https://app.deepsecure.one&format=full
Header: Metadata-Flavor: Google
```

Returns a **Google-signed OIDC JWT** containing:

```json
{
  "iss": "https://accounts.google.com",
  "sub": "112345678901234567890",
  "email": "debugging-agent-sa@deepsecure-saas.iam.gserviceaccount.com",
  "aud": "https://app.deepsecure.one",
  "exp": 1749427200,
  "iat": 1749423600
}
```

This token proves the caller is the GCP Service Account. No secrets are involved — the metadata server is only accessible from within the GCP project.

#### Step 3: Exchange OIDC token for DeepSecure agent JWT

The SDK sends the OIDC token to the **DeepSecure Control Plane**:

```
POST https://app.deepsecure.one/api/v1/auth/bootstrap/gcp
Content-Type: application/json

{
  "identity_token": "<google-signed-oidc-jwt>"
}
```

The control plane:

1. **Fetches Google's JWKS** from `https://www.googleapis.com/oauth2/v3/certs`
2. **Verifies the OIDC token signature** using Google's public keys
3. **Extracts claims**: `email`, `aud`, `exp` from the verified JWT
4. **Validates audience** matches the expected control plane URL
5. **Looks up the agent** by matching `email` → attestation policy → agent record
6. **Issues a DeepSecure agent JWT** (1-hour TTL) signed with the control plane's key

Response:

```json
{
  "access_token": "<deepsecure-agent-jwt>",
  "agent_id": "debugging-agent-sa",
  "expires_in": 3600,
  "token_type": "bearer"
}
```

```
┌──────────────┐          ┌───────────────────┐         ┌──────────────────────┐
│  Agent        │          │  GCP Metadata     │         │  DeepSecure Control  │
│  Container    │          │  Server           │         │  Plane               │
└──────┬───────┘          └─────────┬─────────┘         └──────────┬───────────┘
       │                            │                               │
       │  GET /identity?aud=...     │                               │
       │───────────────────────────▶│                               │
       │  ◀── OIDC JWT (google-     │                               │
       │       signed, contains     │                               │
       │       SA email)            │                               │
       │                            │                               │
       │  POST /api/v1/auth/bootstrap/gcp                          │
       │  { "identity_token": "..." }                              │
       │──────────────────────────────────────────────────────────▶│
       │                                                           │
       │                                     1. Verify OIDC sig    │
       │                                        (Google JWKS)      │
       │                                     2. Extract SA email   │
       │                                     3. Match agent policy │
       │                                     4. Issue DS JWT       │
       │                                                           │
       │  ◀── { "access_token": "<ds-jwt>", "agent_id": "..." }   │
       │                                                           │
```

#### Step 4: Fetch delegations

With the DeepSecure JWT, the SDK fetches all active delegations:

```
GET https://app.deepsecure.one/api/v1/auth/agent/delegations
Authorization: Bearer <deepsecure-agent-jwt>
```

Response (array of delegation objects):

```json
[
  {
    "delegation_id": "del-f7c4525f-...",
    "delegator": "admin@company.com",
    "delegated_permissions": ["exa:web_search_exa:call", "exa:web_fetch_exa:call"],
    "expires_at": "2026-07-01T00:00:00Z"
  },
  {
    "delegation_id": "del-0b448193-...",
    "delegator": "admin@company.com",
    "delegated_permissions": ["notion:pages:search", "notion:pages:read", "slack:channels:list"],
    "expires_at": "2026-07-01T00:00:00Z"
  }
]
```

#### Step 5: Get delegation-scoped JWTs

For each delegation, the SDK requests a scoped JWT:

```
POST https://app.deepsecure.one/api/v1/auth/agent/delegation-token
Authorization: Bearer <deepsecure-agent-jwt>
Content-Type: application/json

{ "delegation_id": "del-f7c4525f-..." }
```

Response:

```json
{
  "access_token": "<delegation-scoped-jwt>",
  "delegation_id": "del-f7c4525f-..."
}
```

The delegation-scoped JWT encodes the specific permissions so the MCP Gateway can enforce them.

#### Step 6: Configure Gemini CLI with MCP server

For each delegation, the entrypoint registers the DeepSecure MCP Gateway as a tool server:

```bash
gemini mcp add deepsecure https://app.deepsecure.one/mcp \
  --type http --scope user --trust --timeout 30000 \
  -H "Authorization: Bearer <delegation-scoped-jwt>"
```

This writes to `~/.gemini/settings.json` so Gemini CLI knows where to send `tools/call` requests.

#### Step 7: Pre-warm gateway session

The entrypoint sends an MCP `initialize` to establish a session:

```
POST https://app.deepsecure.one/mcp
Authorization: Bearer <delegation-scoped-jwt>
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "initialize",
  "id": 0,
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": { "name": "warmup", "version": "1.0.0" }
  }
}
```

#### Step 8: Execute prompts via Gemini CLI

Prompts are selected based on which services the delegation's permissions grant access to. For example, if permissions include `exa:web_search_exa:call`, the Exa search prompt is selected.

```bash
gemini -y --sandbox=false --allowed-mcp-server-names deepsecure \
  -p "Call exa.web_search_exa with query 'DeepSecure' and numResults 3..."
```

Gemini CLI sends `tools/call` to the gateway, which validates the JWT, checks permissions, and proxies to the external service.

#### Step 9: Round-robin and refresh

After processing all delegations, the agent sleeps for `INTERVAL` seconds, then **re-bootstraps** to get a fresh JWT and updated delegations (new delegations may have been added, expired ones removed).

```
Round 1 → bootstrap → delegations → prompts → sleep 60s
Round 2 → bootstrap → delegations → prompts → sleep 60s
Round 3 → bootstrap → delegations → prompts → exit
```

---

## AWS OIDC Bootstrap

Used when the agent runs on **ECS**, **EKS**, **Lambda**, or **EC2** with an IAM Role attached.

### Prerequisites

| Component | Value | Set By |
|-----------|-------|--------|
| ECS Task / Lambda | Agent container | Platform engineer |
| IAM Role | `arn:aws:iam::123456789012:role/deepsecure-agent-role` | Platform engineer |
| Agent registered in DeepSecure | `my-agent` with `platform=aws` | Admin via UI/API |
| Attestation policy | Maps IAM ARN → agent identity | Admin via UI/API |
| Delegations | At least one active delegation | Admin via UI |

### Env vars

```yaml
DEEPSECURE_CONTROL_URL: https://app.deepsecure.one
DEEPSECURE_GATEWAY_URL: https://app.deepsecure.one/mcp
AGENT_ID:               my-aws-agent
# AWS_EXECUTION_ENV, ECS_CONTAINER_METADATA_URI, or AWS_LAMBDA_FUNCTION_NAME
# are automatically set by AWS — used for platform auto-detection
```

### Step-by-Step Flow

#### Step 1: Container starts, platform auto-detected as AWS

The SDK detects AWS by checking environment variables:

```python
def _is_aws() -> bool:
    return bool(
        os.environ.get("AWS_EXECUTION_ENV")           # ECS, Lambda
        or os.environ.get("ECS_CONTAINER_METADATA_URI")  # ECS Fargate
        or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")    # Lambda
    )
```

If `platform=AUTO`, it resolves to `Platform.AWS` when any of these are set.

#### Step 2: Fetch AWS identity via STS

The SDK uses `boto3` to call **AWS STS GetCallerIdentity**:

```python
import boto3
sts = boto3.client("sts")
identity = sts.get_caller_identity()
# Returns: { "Arn": "arn:aws:sts::123456789012:assumed-role/deepsecure-agent-role/...", ... }
token = identity["Arn"]
```

This requires no static credentials — the IAM Role attached to the ECS Task / Lambda function provides temporary credentials automatically via the instance metadata service (IMDS) or task role credential provider.

```
┌──────────────┐          ┌───────────────────┐         ┌──────────────────────┐
│  Agent        │          │  AWS STS          │         │  DeepSecure Control  │
│  Container    │          │  (via IAM Role)   │         │  Plane               │
└──────┬───────┘          └─────────┬─────────┘         └──────────┬───────────┘
       │                            │                               │
       │  GetCallerIdentity()       │                               │
       │  (boto3, no static creds)  │                               │
       │───────────────────────────▶│                               │
       │  ◀── { "Arn": "arn:aws:    │                               │
       │       sts::123456789012:   │                               │
       │       assumed-role/..." }  │                               │
       │                            │                               │
       │  POST /api/v1/auth/bootstrap/aws                          │
       │  { "token": "arn:aws:sts::123456789012:assumed-role/..." }│
       │──────────────────────────────────────────────────────────▶│
       │                                                           │
       │                                     1. Validate ARN       │
       │                                     2. Match agent policy │
       │                                     3. Issue DS JWT       │
       │                                                           │
       │  ◀── { "access_token": "<ds-jwt>", "agent_id": "..." }   │
       │                                                           │
```

#### Step 3: Exchange AWS identity for DeepSecure agent JWT

```
POST https://app.deepsecure.one/api/v1/auth/bootstrap/aws
Content-Type: application/json

{
  "token": "arn:aws:sts::123456789012:assumed-role/deepsecure-agent-role/task-id"
}
```

The control plane:

1. **Parses the ARN** to extract account ID, role name, and session info
2. **Matches against attestation policies** — looks for a policy that maps this ARN pattern to an agent
3. **Issues a DeepSecure agent JWT** (1-hour TTL)

Response:

```json
{
  "access_token": "<deepsecure-agent-jwt>",
  "agent_id": "my-aws-agent",
  "expires_in": 3600
}
```

#### Steps 4–9: Identical to GCP

From this point forward, the flow is **platform-agnostic**. The SDK uses the same code path for delegations, MCP configuration, and prompt execution regardless of whether the JWT was obtained via GCP or AWS bootstrap.

---

## Side-by-Side Comparison

| Step | GCP | AWS |
|------|-----|-----|
| **Platform detection** | `K_SERVICE`, `GOOGLE_CLOUD_PROJECT`, or `GCE_METADATA_HOST` env var | `AWS_EXECUTION_ENV`, `ECS_CONTAINER_METADATA_URI`, or `AWS_LAMBDA_FUNCTION_NAME` env var |
| **Identity source** | GCP metadata server (`metadata.google.internal`) | AWS STS via `boto3.client("sts").get_caller_identity()` |
| **Identity format** | Google-signed OIDC JWT (RS256, contains SA email) | IAM ARN string (e.g., `arn:aws:sts::123:assumed-role/...`) |
| **Bootstrap endpoint** | `POST /api/v1/auth/bootstrap/gcp` | `POST /api/v1/auth/bootstrap/aws` |
| **Request body** | `{ "identity_token": "<oidc-jwt>" }` | `{ "token": "<iam-arn>" }` |
| **Server-side validation** | Verify OIDC signature via Google JWKS | Validate ARN format + policy match |
| **Agent resolution** | SA email → attestation policy → agent | IAM ARN → attestation policy → agent |
| **Output** | DeepSecure JWT (1h TTL) | DeepSecure JWT (1h TTL) |
| **Extra dependency** | None (uses stdlib `urllib`) | `boto3` (must be in image or Lambda runtime) |
| **Delegations onward** | Identical | Identical |

---

## SDK Code Summary

The entire bootstrap is 3 lines from the caller's perspective:

```python
from deepsecure import BootstrapClient, Platform

client = BootstrapClient(control_url="https://app.deepsecure.one",
                         gateway_url="https://app.deepsecure.one/mcp")
result = client.bootstrap("my-agent", Platform.GCP)  # or Platform.AWS, Platform.AUTO

# result.jwt            → DeepSecure agent JWT (1h TTL)
# result.delegations    → List[Delegation] with per-delegation JWTs
# result.to_mcp_json()  → MCP server config for Gemini/Claude/Codex
# result.to_env()       → Shell export statements
```

Or as a one-liner:

```python
from deepsecure import bootstrap
result = bootstrap("my-agent", platform="gcp")
```

---

## Security Properties

| Property | How It's Achieved |
|----------|-------------------|
| **No static secrets** | Platform identity (OIDC / IAM Role) is the only credential. No API keys baked into the image. |
| **Short-lived tokens** | DeepSecure JWT expires in 1 hour. Agent re-bootstraps each round. |
| **Least privilege** | Each delegation grants only specific service:action permissions. The gateway enforces these. |
| **Delegation scoping** | Per-delegation JWTs encode which tools the agent can call. Different delegations get different JWTs. |
| **Audit trail** | Every bootstrap, delegation fetch, and tool call is logged in the control plane. |
| **Rollback** | `entrypoint.sh` + original `Dockerfile` are preserved. Switch ENTRYPOINT to roll back. |

---

## Dockerfile Comparison

### Original (bash, no SDK)

```dockerfile
FROM node:20-slim
RUN npm install -g @google/gemini-cli@latest
RUN apt-get update && apt-get install -y curl jq ca-certificates procps
COPY entrypoint.sh /app/entrypoint.sh
COPY mcp-bridge.mjs /app/mcp-bridge.mjs
RUN chmod +x /app/entrypoint.sh
WORKDIR /app
ENTRYPOINT ["/app/entrypoint.sh"]
```

- 265-line bash script
- Uses `curl` + `jq` for all API calls
- No Python, no SDK

### SDK (Python + Node)

```dockerfile
FROM node:20-slim
RUN npm install -g @google/gemini-cli@latest
RUN apt-get update && apt-get install -y curl jq ca-certificates procps \
    python3 python3-pip python3-venv
RUN python3 -m venv /opt/deepsecure-venv
ENV PATH="/opt/deepsecure-venv/bin:$PATH"
COPY pyproject.toml /tmp/sdk/pyproject.toml
COPY deepsecure/ /tmp/sdk/deepsecure/
COPY README.md /tmp/sdk/README.md
RUN pip install --no-cache-dir /tmp/sdk && rm -rf /tmp/sdk
COPY agents/gemini/entrypoint_sdk.py /app/entrypoint_sdk.py
WORKDIR /app
ENTRYPOINT ["/opt/deepsecure-venv/bin/python3", "/app/entrypoint_sdk.py"]
```

- 183-line Python script
- Uses `BootstrapClient` for all API calls
- Full path to venv Python in ENTRYPOINT (required for Cloud Run gen2 compatibility)
- Must build with `--platform linux/amd64` on Apple Silicon

### Build command

```bash
# From the repository root:
docker buildx build --platform linux/amd64 \
  -f agents/gemini/Dockerfile.sdk \
  -t us-central1-docker.pkg.dev/PROJECT/REPO/gemini-agent-sdk:latest \
  --load .

docker push us-central1-docker.pkg.dev/PROJECT/REPO/gemini-agent-sdk:latest
```
