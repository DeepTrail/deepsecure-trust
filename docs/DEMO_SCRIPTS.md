# Demo Scripts — Command Reference

Two demo scripts walk through the full DeepSecure platform (9 acts each).
All service connections use **OAuth redirect** — the scripts never handle raw tokens.

| Script | Services | SSO |
|--------|----------|-----|
| `demo_sarah_journey.sh` | Notion + Slack | Keycloak or Google |
| `demo_sarah_journey_v2.sh` | Notion + Slack + Google Drive/Calendar/Gmail | Keycloak or Google |

---

## Prerequisites

### Tools

```bash
pip install pynacl    # Ed25519 crypto for agent authentication
which jq curl docker  # Must be available
```

### TLS certs for OAuth callbacks (one-time setup)

Slack requires HTTPS redirect URIs. We use **mkcert** to generate locally-trusted TLS certificates, served by a **Caddy** reverse proxy on port 8443.

```bash
brew install mkcert
mkcert -install                    # installs local CA in system trust store (needs password)
mkdir -p config/certs
mkcert -cert-file config/certs/localhost.pem \
       -key-file config/certs/localhost-key.pem \
       localhost 127.0.0.1
```

> **Note:** If you skip `mkcert -install`, OAuth callbacks still work but the browser shows a certificate warning on the first callback. Click **Advanced → Proceed** to continue.
>
> **When the frontend arrives, Caddy gets replaced and the mkcert certs stay.**

### Service credentials (`.env.services`)

Both scripts source `.env.services` during PRE-DEMO SETUP to inject OAuth client credentials into the Docker container.

```bash
cp .env.services.example .env.services
# Edit .env.services with your real Notion and Slack OAuth credentials
```

### Google credentials (`.env.google`)

Only needed when `IDP_NAME=google`:

```bash
cp .env.google.example .env.google
# Edit .env.google with your Google Cloud OAuth credentials
```

### OAuth redirect URIs to register

Register these in each provider's developer console before running with real OAuth:

| Provider | Redirect URI | Where to register |
|----------|-------------|-------------------|
| Notion | `https://localhost:8443/api/v1/oauth/notion/callback` | notion.so/my-integrations → OAuth settings |
| Slack | `https://localhost:8443/api/v1/oauth/slack/callback` | api.slack.com/apps → OAuth & Permissions → Redirect URLs |
| Google SSO | `http://localhost:8000/api/v1/auth/sso/google/callback` | Google Cloud Console → Credentials → OAuth client |
| Google Drive | `https://localhost:8443/api/v1/oauth/gdrive/callback` | Google Cloud Console → Credentials → OAuth client |
| Google Calendar | `https://localhost:8443/api/v1/oauth/gcalendar/callback` | Google Cloud Console → Credentials → OAuth client |
| Gmail | `https://localhost:8443/api/v1/oauth/gmail/callback` | Google Cloud Console → Credentials → OAuth client |

---

## `demo_sarah_journey.sh` (Notion + Slack)

### With Keycloak (default)

```bash
# Full run — starts containers, runs all 9 acts with pauses
./scripts/demo_sarah_journey.sh

# Skip container restart (services already running)
./scripts/demo_sarah_journey.sh --skip-setup

# Non-interactive (no pauses between acts)
./scripts/demo_sarah_journey.sh --skip-setup --no-pause

# Start from a specific act (e.g., ACT 5 onward)
./scripts/demo_sarah_journey.sh --skip-setup --act 5
```

### With Google Workspace SSO

```bash
# Full run with Google SSO (opens browser for login)
IDP_NAME=google ./scripts/demo_sarah_journey.sh

# Skip setup (Google containers already running)
IDP_NAME=google ./scripts/demo_sarah_journey.sh --skip-setup --no-pause
```

---

## `demo_sarah_journey_v2.sh` (Notion + Slack + Google)

### Service Profiles

| Profile | Services | Flag |
|---------|----------|------|
| `classic` | Notion, Slack | `--services classic` (default) |
| `google` | Google Drive, Calendar, Gmail | `--services google` |
| `all` | Notion, Slack, Drive, Calendar, Gmail | `--services all` |
| custom | Any combination | `--services notion,gdrive,gmail` |

### With Keycloak SSO + Classic Services

```bash
# Same as main script (Notion + Slack, Keycloak SSO)
./scripts/demo_sarah_journey_v2.sh

# Skip setup, no pauses
./scripts/demo_sarah_journey_v2.sh --skip-setup --no-pause
```

### With Google SSO + Google Services (real API calls)

```bash
# Google-only services — opens browser for SSO + 3 OAuth consents
IDP_NAME=google ./scripts/demo_sarah_journey_v2.sh --services google

# Skip setup (Google containers already running)
IDP_NAME=google ./scripts/demo_sarah_journey_v2.sh --skip-setup --services google --no-pause

# All services (Notion + Slack + Google)
IDP_NAME=google ./scripts/demo_sarah_journey_v2.sh --skip-setup --services all --no-pause

# Mix and match
IDP_NAME=google ./scripts/demo_sarah_journey_v2.sh --skip-setup --services notion,gdrive,gmail

# Start from a specific act
IDP_NAME=google ./scripts/demo_sarah_journey_v2.sh --skip-setup --services google --act 5
```

---

## Container Management

```bash
# Start services (Keycloak mode)
docker compose up -d

# Start services (Google mode) — requires .env.google and .env.services
source .env.services
source .env.google
docker compose -f docker-compose.yml -f docker-compose.google.yml up -d

# Rebuild after code changes
source .env.services
source .env.google
docker compose -f docker-compose.yml -f docker-compose.google.yml up -d --build deeptrail-control

# Stop services (keep data)
docker compose down

# Stop services (clean slate)
docker compose down -v
```

---

## CLI Flags Reference

| Flag | Description | Default |
|------|-------------|---------|
| `--skip-setup` | Skip `docker compose down/up` | Containers restarted |
| `--no-pause` | No interactive pauses between acts | Pauses enabled |
| `--act N` | Start from ACT N onward | ACT 0 (all) |
| `--services PROFILE` | Service profile (v2 only) | `classic` |

---

## Architecture

- **Secrets**: How OAuth credentials work across development and production — [docs/design/secrets-architecture.md](design/secrets-architecture.md)
- **TLS termination**: Why Caddy is used, how mkcert works, and the end-to-end callback flow — [docs/design/tls-termination-oauth-callbacks.md](design/tls-termination-oauth-callbacks.md)
