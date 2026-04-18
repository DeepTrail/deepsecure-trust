# DeepSecure Services Setup Guide

Welcome! This guide explains how to set up the complete DeepSecure services infrastructure locally. DeepSecure uses a **dual-service architecture** with both the Control Plane and Data Plane services working together, plus a dedicated Identity Provider (IdP) for single sign-on, to provide comprehensive AI agent security.

## Architecture Overview

DeepSecure consists of three backend services and two supporting infrastructure components:

**Services:**

- **🧠 Control Plane (`deeptrail-control`)** — Agent identity management, policy engine, credential issuance, audit logging, and SSO orchestration.
- **🚀 Data Plane (`deeptrail-gateway`)** — Secret injection, policy enforcement, split-key security, MCP gateway, and external-API proxying.
- **🔐 Identity Provider (`keycloak`)** — OIDC-compliant IdP backing the SSO flow. Ships with a pre-seeded `deepsecure` realm for zero-config local development. Replaceable with Google Workspace (or any OIDC IdP) via a Compose override — see [IdP Selection](#idp-selection).

**Infrastructure:**

- **PostgreSQL Database** — Stores agent identities, policies, audit logs, connected services, scoped permissions, and vault tokens.
- **Redis** — Serves two purposes:
  - Gateway: split-key storage (JIT key reassembly)
  - Control Plane: pub/sub channel for policy/permission cache invalidation

## Quickstart: Running All Services

Follow these steps from the repository root to get the complete backend infrastructure running.

### 1. Start the DeepSecure Services (default: Keycloak IdP)

This command builds the Docker images and starts all five containers in the background:

```bash
docker-compose down --volumes --rmi all

docker system prune -a --volumes -f

docker compose up -d --build
```

On first run, this will:
- Build the `deeptrail-control` and `deeptrail-gateway` service images
- Start Keycloak and import the pre-seeded `deepsecure` realm from `config/keycloak/deepsecure-realm.json`
- Create and initialize the PostgreSQL database with proper schema
- Start Redis (used by both services)
- Apply all database migrations automatically

> **Alternative: start with Google Workspace as the IdP.** See [IdP Selection](#idp-selection) below.

### 2. Verify All Services Are Running

Check that all five containers are running and healthy:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected output:
```
NAMES                     STATUS                   PORTS
deeptrail_control_app     Up 2 minutes             0.0.0.0:8000->8001/tcp
deeptrail_gateway_app     Up 2 minutes             0.0.0.0:8002->8001/tcp
deeptrail_keycloak        Up 2 minutes (healthy)   0.0.0.0:8080->8080/tcp
deeptrail_control_db      Up 2 minutes (healthy)   0.0.0.0:5434->5432/tcp
deeptrail_gateway_redis   Up 2 minutes (healthy)   0.0.0.0:6380->6379/tcp
```

### 3. Verify Services Health

Test that all three services are responding:

**Control Plane Health Check:**
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "service": "DeepSecure Control Plane",
  "version": "0.1.12",
  "status": "ok",
  "dependencies": {
    "database": "connected"
  }
}
```

**Gateway Health Check:**
```bash
curl http://localhost:8002/health
```

Expected response:
```json
{
  "service": "DeepSecure Gateway",
  "version": "0.1.12",
  "status": "ok",
  "dependencies": {
    "control_plane": "connected",
    "redis": "connected"
  }
}
```

**Keycloak Health Check:**
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/health/ready
```

Expected response: `200`

Admin console: <http://localhost:8080/admin> — login with `admin` / `admin` (dev credentials set in `docker-compose.yml`).

### 4. Verify Database Schema (Optional)

To confirm the database schema was created automatically:

```bash
docker exec -it deeptrail_control_db psql -U deepsecure_user -d deeptrail_controldb
```

At the `deeptrail_controldb=#` prompt, list the tables:
```sql
\dt
```

You should see tables including:

| Table | Purpose |
|-------|---------|
| `agents` | Agent identity registrations (public key, metadata) |
| `credentials` | Ephemeral credentials issued to agents |
| `policies` | Authorization policies (who can do what) |
| `scoped_permissions` | Fine-grained per-service/action permissions |
| `attestation_policies` | Platform attestation rules (K8s, AWS, Azure, Docker) |
| `connected_services` | User-authorized 3rd-party service connections (Notion, Slack, etc.) |
| `vault_tokens` | Vault-backed token references for injected secrets |
| `tasks` | Task-scoped authorization records |
| `nonces` | One-time challenge nonces for anti-replay |
| `secrets` | Encrypted secret storage |
| `alembic_version` | Schema migration version |

Type `\q` and press Enter to exit.

### 5. Verify Redis Storage (Optional)

To confirm Redis is working for both split-key storage and cache-invalidation pub/sub:

```bash
docker exec -it deeptrail_gateway_redis redis-cli ping
```

Expected response: `PONG`

### 6. Verify Keycloak Realm (Optional)

Confirm the `deepsecure` realm was imported successfully:

```bash
curl -s http://localhost:8080/realms/deepsecure/.well-known/openid-configuration | jq '.issuer'
```

Expected response: `"http://localhost:8080/realms/deepsecure"`

## 🎉 Success! Your Backend is Ready

Your complete DeepSecure backend infrastructure is now running:

- **Control Plane**: <http://localhost:8000> (Management operations, SSO, agent auth)
- **Gateway**: <http://localhost:8002> (Runtime operations, secret injection, MCP)
- **Keycloak**: <http://localhost:8080> (Identity Provider / OIDC)
- **Database**: `localhost:5434` (PostgreSQL)
- **Redis**: `localhost:6380` (Split-key storage + cache pub/sub)

You can now proceed with:
- The [30-second quickstart](../README.md#-30-second-quickstart) in the main README
- Running the [examples](../examples/) to see DeepSecure in action
- Using the `deepsecure` CLI and SDK for development

## IdP Selection

DeepSecure supports multiple OIDC identity providers. Keycloak is the default for local development; Google Workspace is available via a Compose override for teams who want to demo SSO against a real IdP.

### Default: Keycloak

No extra steps — `docker compose up -d` wires the Control Plane to Keycloak automatically.

| Setting | Value |
|---------|-------|
| Issuer | `http://keycloak:8080/realms/deepsecure` (internal) / `http://localhost:8080/realms/deepsecure` (host) |
| Client ID | `deepsecure-control` |
| Redirect URI | `http://localhost:8000/api/v1/auth/sso/callback` |
| Realm JSON | `config/keycloak/deepsecure-realm.json` (auto-imported on container start) |

### Optional: Google Workspace

The `docker-compose.google.yml` override swaps the Control Plane's IdP env vars from Keycloak to Google. Credentials come from your shell environment — never commit them.

```bash
# 1. Copy the template and fill in credentials from Google Cloud Console
cp .env.google.example .env.google
# Edit .env.google — set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_HD (optional)

# 2. Start with Google IdP
source .env.google
docker compose -f docker-compose.yml -f docker-compose.google.yml up -d --build
```

`.env.google` is git-ignored. Keycloak still runs in the background but is not used. The demo script in `scripts/demo_sarah_journey.sh` respects the `IDP_NAME` environment variable — set `IDP_NAME=google` when running end-to-end flows against Google.

## Service Details

### Control Plane (Port 8000)

**Purpose:** Policy Decision Point (PDP) and agent/user management.

Responsibilities:
- User login and SSO orchestration
- Agent identity creation and Ed25519 challenge-response authentication
- Policy and scoped-permission storage
- Credential issuance (JWT tokens)
- Audit logging and compliance
- Delegation issuance and verification

**Key Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/health` | Service health check |
| `POST` | `/api/v1/auth/login` | User password login (returns `.token`) |
| `GET`  | `/api/v1/auth/sso/{idp}/authorize` | Start SSO flow (returns authorization URL) |
| `GET`  | `/api/v1/auth/sso/{idp}/callback` | SSO callback (exchanges code for tokens) |
| `POST` | `/api/v1/auth/sso/logout` | SSO logout |
| `POST` | `/api/v1/auth/agent/challenge` | Request Ed25519 challenge for agent auth |
| `POST` | `/api/v1/auth/agent/verify` | Submit signed challenge, receive Agent JWT |
| `POST` | `/api/v1/auth/delegate` | Issue a delegation to an agent |
| `POST` | `/api/v1/agents/` | Register an agent (with public key) |
| `GET`  | `/api/v1/policies` | List policies |
| `POST` | `/api/v1/oauth/{provider}/authorize` | Connect a 3rd-party service (Notion, Slack, HubSpot) |
| `GET`  | `/api/v1/vault/tokens/*` | Vault token retrieval (requires Agent JWT) |

Full OpenAPI spec: <http://localhost:8000/docs> when the service is running.

### Gateway (Port 8002)

**Purpose:** Policy Enforcement Point (PEP), data plane, and MCP gateway.

Responsibilities:
- Secret injection into external API calls
- Real-time policy enforcement (per-request)
- Split-key security (just-in-time key reassembly from Redis)
- Request proxying and traffic management
- MCP (Model Context Protocol) gateway for tool invocation
- Rate limiting and request filtering

**Key Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/health` | Service health check |
| `POST` | `/mcp` | MCP JSON-RPC entrypoint (requires Agent JWT; call `initialize` before `tools/call`) |
| `ANY`  | `/proxy/*` | Proxied external API calls with injected credentials |
| `GET`  | `/api/v1/tools/*` | Tool metadata endpoints |

See `docs/SARAH_JOURNEY_API_REFERENCE.md` for full MCP protocol sequences.

### Keycloak (Port 8080)

**Purpose:** OIDC Identity Provider backing the SSO flow.

- **Image:** `quay.io/keycloak/keycloak:24.0` (dev mode: `start-dev --import-realm`)
- **Admin Console:** <http://localhost:8080/admin> (admin / admin)
- **Realm:** `deepsecure` (pre-seeded from `config/keycloak/deepsecure-realm.json`)
- **Health:** `http://localhost:8080/health/ready`

The realm JSON bootstraps a dev client (`deepsecure-control`), sample users, and roles so SSO works immediately after `docker compose up`. To customize, edit `config/keycloak/deepsecure-realm.json` and restart the `keycloak` container.

## Development Notes

### Container Communication

- All services share the Docker network `deepsecure_network`.
- Gateway → Control Plane: `http://deeptrail-control:8001` (internal)
- Gateway → Redis: `redis://redis:6379`
- Control Plane → Database: `postgresql://deepsecure_user:deepsecure_password@db/deeptrail_controldb`
- Control Plane → Redis: `redis://redis:6379` (cache-invalidation pub/sub)
- Control Plane → Keycloak: `http://keycloak:8080/realms/deepsecure`

### Data Persistence

- Database data: `postgres_data` Docker volume
- Redis data: `redis_data` Docker volume
- Keycloak realm: re-imported from `config/keycloak/deepsecure-realm.json` on each start (dev mode does not persist admin-console changes across `down -v`)
- Data persists across container restarts (but is wiped by `docker compose down -v`)

### Key Environment Variables

Defined in `docker-compose.yml`:

**Control Plane (`deeptrail-control`):**

| Variable | Example | Purpose |
|----------|---------|---------|
| `DEEPSECURE_VERSION` | `0.1.12` | Current package version surfaced in `/health` |
| `DATABASE_URL` | `postgresql://.../deeptrail_controldb` | PostgreSQL connection |
| `REDIS_URL` | `redis://redis:6379` | Pub/sub channel for policy cache invalidation |
| `SECRET_KEY` | (dev value) | JWT signing key |
| `GATEWAY_URL` | `http://deeptrail-gateway:8001` | Internal gateway URL |
| `GATEWAY_INTERNAL_API_TOKEN` | `gateway-internal-secret-token` | Mutual auth token for control↔gateway |
| `BACKEND_API_TOKEN` | `DEFAULT_QUICKSTART_TOKEN` | Quickstart token for initial configuration |
| `POLICY_PATH` | `/app/policies.yml` | Bootstrap policy file (read-only mount) |
| `IDP_PROVIDER` | `keycloak` (default) / `google` | Active IdP |
| `IDP_ISSUER_URL` | `http://keycloak:8080/realms/deepsecure` | OIDC issuer |
| `IDP_CLIENT_ID` | `deepsecure-control` | OIDC client ID |
| `IDP_CLIENT_SECRET` | `control-secret` (dev) | OIDC client secret |
| `IDP_REALM` | `deepsecure` | Keycloak realm (Keycloak only) |
| `IDP_REDIRECT_URI` | `http://localhost:8000/api/v1/auth/sso/callback` | OAuth redirect |
| `IDP_HD` | *(unset)* | Google Workspace hosted-domain restriction (Google only) |
| `OAUTH_REDIRECT_BASE_URL` | `http://localhost:8000` | Base URL for 3rd-party OAuth callbacks |
| `NOTION_CLIENT_ID` / `NOTION_CLIENT_SECRET` | test values | Notion OAuth connector |
| `SLACK_CLIENT_ID` / `SLACK_CLIENT_SECRET` | test values | Slack OAuth connector |
| `HUBSPOT_CLIENT_ID` / `HUBSPOT_CLIENT_SECRET` | test values | HubSpot OAuth connector |

**Gateway (`deeptrail-gateway`):**

| Variable | Example | Purpose |
|----------|---------|---------|
| `DEEPSECURE_VERSION` | `0.1.12` | Current package version surfaced in `/health` |
| `CONTROL_PLANE_URL` | `http://deeptrail-control:8001` | Internal control-plane URL |
| `REDIS_URL` | `redis://redis:6379` | Split-key storage |
| `GATEWAY_ENCRYPTION_KEY` | (32-char dev value) | Symmetric encryption key for split-key |
| `GATEWAY_INTERNAL_API_TOKEN` | `gateway-internal-secret-token` | Must match Control Plane's value |
| `SECRET_KEY` | (dev value) | JWT validation key (must match Control) |

> **Security note:** All values shipped in `docker-compose.yml` are **dev-only** placeholders. Production deployments MUST override every `*_TOKEN`, `*_KEY`, `*_SECRET`, and `ADMIN_PASSWORD` via a secret manager or environment injection.

---

## Troubleshooting

<details>
<summary><b>🔧 Service Startup Issues</b></summary>

If services fail to start, check the logs:

```bash
# View all service logs
docker compose logs

# View specific service logs
docker logs deeptrail_control_app
docker logs deeptrail_gateway_app
docker logs deeptrail_keycloak
docker logs deeptrail_control_db
docker logs deeptrail_gateway_redis
```

Common issues:
- **Port conflicts**: Ensure ports `8000`, `8002`, `8080`, `5434`, `6380` are not in use.
- **Database connection**: Wait for the database to be fully healthy before services start.
- **Keycloak slow start**: Keycloak can take 30–60 seconds on first boot to import the realm — the healthcheck accounts for this.
- **Memory**: Ensure Docker has sufficient memory allocation (Keycloak alone needs ~512 MB).
</details>

<details>
<summary><b>🔐 Keycloak / IdP Issues</b></summary>

SSO or Keycloak problems:

```bash
# Verify the realm was imported
curl -s http://localhost:8080/realms/deepsecure/.well-known/openid-configuration | jq '.issuer'
# Expected: "http://localhost:8080/realms/deepsecure"

# Check Keycloak logs
docker logs deeptrail_keycloak 2>&1 | tail -50

# Re-import the realm (wipes the container's admin-console state)
docker compose restart keycloak

# Switch to Google IdP (see IdP Selection section)
source .env.google
docker compose -f docker-compose.yml -f docker-compose.google.yml up -d --build
```

Common issues:
- **`issuer not found`**: Realm file not mounted or invalid JSON — check `config/keycloak/deepsecure-realm.json`.
- **SSO redirect fails with `invalid_client`**: `IDP_CLIENT_ID` or `IDP_CLIENT_SECRET` mismatch between Control Plane env and realm definition.
- **Google override doesn't apply**: `.env.google` not sourced, or `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` not exported to the shell before `docker compose up`.
</details>

<details>
<summary><b>🗄️ Database Issues</b></summary>

Database connection problems:

```bash
# Check database container health
docker inspect deeptrail_control_db --format='{{.State.Health.Status}}'

# Connect to database manually
docker exec -it deeptrail_control_db psql -U deepsecure_user -d deeptrail_controldb

# Reset database (⚠️ destroys data)
docker compose down -v
docker compose up -d
```
</details>

<details>
<summary><b>🔄 Redis Issues</b></summary>

Redis connection problems:

```bash
# Check Redis health
docker exec deeptrail_gateway_redis redis-cli ping

# View Redis info
docker exec deeptrail_gateway_redis redis-cli info

# Watch cache-invalidation pub/sub traffic from Control Plane
docker exec deeptrail_gateway_redis redis-cli psubscribe '*'

# Clear Redis data (⚠️ destroys cached keys and split-key halves)
docker exec deeptrail_gateway_redis redis-cli flushall
```
</details>

<details>
<summary><b>🌐 Network Issues</b></summary>

Service communication problems:

```bash
# Check Docker network
docker network ls
docker network inspect deepsecure_network

# Test internal connectivity
docker exec deeptrail_gateway_app curl http://deeptrail-control:8001/health
docker exec deeptrail_control_app curl http://keycloak:8080/health/ready
```
</details>

## Stopping Services

To stop all services:

```bash
# Stop services (keeps data)
docker compose down

# Stop services and remove volumes (⚠️ destroys data)
docker compose down -v

# Stop services started with Google IdP override
docker compose -f docker-compose.yml -f docker-compose.google.yml down
```
