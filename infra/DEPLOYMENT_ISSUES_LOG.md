# GCP SaaS Deployment: Issues and Fixes Log

Complete chronological record of every issue encountered deploying the DeepSecure SaaS stack to GCP — from initial `terraform apply` through a fully working production app on `https://app.deepsecure.one`.

**Date:** May 13-14, 2026
**Started:** ~3:00 PM PDT (first `terraform apply`)
**Completed:** ~8:00 PM PDT (all dashboard pages working on `app.deepsecure.one`)
**Total time:** ~5 hours
**Total issues resolved:** 29
**Terraform apply attempts:** 12+ (initial deploy) + 5 (post-deploy fixes)
**Docker image rebuilds:** 7 (Keycloak x2, Control Plane x3, Frontend x2)
**Final result:** All 4 Cloud Run services deployed, Global LB with SSL, Google SSO login, Notion/Slack/Google service connections, all dashboard pages functional.

```
Live URL:    https://app.deepsecure.one
LB IP:       34.117.112.181
Domain:      app.deepsecure.one (Namecheap A record → LB IP)

Cloud Run services:
  control    = "https://deeptrail-control-flhiwg2wfa-uc.a.run.app"
  frontend   = "https://frontend-flhiwg2wfa-uc.a.run.app"
  gateway    = "https://deeptrail-gateway-flhiwg2wfa-uc.a.run.app"
  keycloak   = "https://keycloak-flhiwg2wfa-uc.a.run.app"
```

---

## Table of Contents

### Phase 1: Infrastructure Deploy (~3:00 – 5:06 PM)
- [Issue #1: gcloud auth scope error](#issue-1-gcloud-auth-scope-error)
- [Issue #2: VPC connector missing network field](#issue-2-vpc-connector-missing-network-field)
- [Issue #3: `deletion_protection` not supported in Cloud Run v2](#issue-3-deletion_protection-not-supported-in-cloud-run-v2)
- [Issue #4: Docker images not found](#issue-4-docker-images-not-found)
- [Issue #5: Keycloak wrong port, health check, and resources](#issue-5-keycloak-wrong-port-health-check-and-resources)
- [Issue #6: Docker images built for wrong architecture](#issue-6-docker-images-built-for-wrong-architecture)
- [Issue #7: Cloud SQL JDBC Socket Factory JAR download failed](#issue-7-cloud-sql-jdbc-socket-factory-jar-download-failed)
- [Issue #8: Keycloak `Connection to localhost:5432 refused`](#issue-8-keycloak-connection-to-localhost5432-refused)
- [Issue #9: Keycloak `cloudSqlInstance property not set`](#issue-9-keycloak-cloudsqlinstance-property-not-set)
- [Issue #10: Switched from Socket Factory to Private IP](#issue-10-switched-from-socket-factory-to-private-ip-architectural-change)
- [Issue #11: Terraform state lost after interrupted apply](#issue-11-terraform-state-lost-after-interrupted-terraform-apply)
- [Issue #12: Keycloak Cloud Run service also needed import](#issue-12-keycloak-cloud-run-service-also-needed-import)
- [Issue #13: Terraform "inconsistent final plan" for Cloud SQL private IP](#issue-13-terraform-inconsistent-final-plan-for-cloud-sql-private-ip)
- [Issue #14: Terraform "inconsistent final plan" for Keycloak URL](#issue-14-terraform-inconsistent-final-plan-for-keycloak-url)
- [Issue #15: `allUsers` IAM binding blocked by organization policy](#issue-15-allusers-iam-binding-blocked-by-organization-policy)
- [Issue #16: Control Plane `No module named 'asyncpg'`](#issue-16-control-plane-modulenotfounderror-no-module-named-asyncpg)
- [Issue #17: Control Plane `no password supplied`](#issue-17-control-plane-no-password-supplied)
- [Issue #18: `DATABASE_URL` used `+asyncpg` driver for sync app](#issue-18-database_url-used-asyncpg-driver-for-sync-app)
- [Issue #19: `build-and-push.sh` path errors](#issue-19-build-and-pushsh-path-errors-and-no-single-image-support)

### Phase 2: Domain, SSL, OAuth, Application (~5:06 – 8:00 PM)
- [Issue #20: SSL certificate swap — "resource in use"](#issue-20-ssl-certificate-swap--resource-in-use)
- [Issue #21: Google SSO — `invalid_client` (401)](#issue-21-google-sso--invalid_client-401)
- [Issue #22: Google SSO — `redirect_uri_mismatch` (400)](#issue-22-google-sso--redirect_uri_mismatch-400)
- [Issue #23: Google SSO — `redirect_uri_mismatch` with `localhost:3000`](#issue-23-google-sso--redirect_uri_mismatch-with-localhost3000)
- [Issue #24: Google service connections using wrong OAuth client](#issue-24-google-service-connections-using-wrong-oauth-client)
- [Issue #25: Onboarding wizard "Not Found" for service connections](#issue-25-onboarding-wizard-not-found-for-service-connections)
- [Issue #26: Agents, Policies, Tasks pages — "Failed to load (302)"](#issue-26-agents-policies-tasks-pages--failed-to-load-302)

### Reference
- [Summary: Issues by Category](#summary-issues-by-category)
- [Files Modified During Deployment](#files-modified-during-deployment)
- [Time Breakdown](#time-breakdown)
- [Lessons Learned](#lessons-learned)

---

## Phase 1: Infrastructure Deploy

---

## Issue #1: gcloud auth scope error

**When:** Before `terraform init`
**Error:** `https://www.googleapis.com/auth/cloud-platform` scope not consented
**Fix:**
```bash
gcloud auth application-default login \
  --scopes="openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform"
```

---

## Issue #2: VPC connector missing network field

**When:** `terraform apply` (first run)
**Error:** `"network": one of network,subnet.0.name must be specified`
**File:** `infra/terraform/network.tf`
**Fix:** Added `network = "default"` to `google_vpc_access_connector.serverless`

---

## Issue #3: `deletion_protection` not supported in Cloud Run v2

**When:** `terraform apply`
**Error:** `"deletion_protection" is not expected here`
**File:** `infra/terraform/cloud_run.tf`
**Fix:** Removed `deletion_protection = false` from all `google_cloud_run_v2_service` resources

---

## Issue #4: Docker images not found

**When:** `terraform apply` (Cloud Run service creation)
**Error:** `Image 'us-central1-docker.pkg.dev/deepsecure-saas/deepsecure/keycloak:latest' not found`
**Root cause:** `terraform apply` was run before `build-and-push.sh`
**Fix:** Run `./infra/build-and-push.sh` before the second `terraform apply`

---

## Issue #5: Keycloak wrong port, health check, and resources

**When:** Cloud Run Keycloak startup probe failed (~10s)
**Errors:**
- Keycloak listens on 8080, Terraform had 8001
- Health check path was `/health` instead of `/health/ready`
- Default Cloud Run memory/CPU too low for Keycloak JVM

**File:** `infra/terraform/cloud_run.tf`
**Fix:**
```hcl
container_port = 8080
path = "/health/ready"
limits = { memory = "1Gi", cpu = "1" }
initial_delay_seconds = 30
period_seconds = 15
failure_threshold = 20
timeout_seconds = 30
```

---

## Issue #6: Docker images built for wrong architecture

**When:** Cloud Run Keycloak startup (second attempt)
**Error:** `exec format error` (found via `gcloud logging read`)
**Root cause:** Docker Desktop on Apple Silicon builds ARM images by default; Cloud Run requires linux/amd64
**File:** `infra/build-and-push.sh`
**Fix:** Added `--platform linux/amd64` to all `docker build` commands

---

## Issue #7: Cloud SQL JDBC Socket Factory JAR download failed

**When:** `docker build` for Keycloak
**Error:** `invalid response status 403` / `404` when using `ADD https://storage.googleapis.com/...`
**Root cause:** Google Storage direct download URL was wrong/blocked
**File:** `config/keycloak/Dockerfile`
**Fix:** Changed to multi-stage Maven build to download `postgres-socket-factory` and all transitive dependencies:
```dockerfile
FROM maven:3.9-eclipse-temurin-17 AS builder
RUN echo '<project>...</project>' > /tmp/pom.xml && \
    mvn -f /tmp/pom.xml dependency:copy-dependencies -DoutputDirectory=/jars -q
```

---

## Issue #8: Keycloak `Connection to localhost:5432 refused`

**When:** Cloud Run Keycloak startup (third attempt)
**Error:** `Connection to localhost:5432 refused` in Keycloak logs
**Root cause:** `KC_DB_URL` was `jdbc:postgresql:///keycloak_db` which defaults to localhost:5432. The Cloud SQL Auth Proxy sidecar exposes Unix sockets, not TCP on localhost.
**Fix:** Added `KC_DB_URL_PROPERTIES` with `cloudSqlInstance` and `socketFactory` parameters.

---

## Issue #9: Keycloak `cloudSqlInstance property not set`

**When:** Cloud Run Keycloak startup (fourth attempt)
**Error:** `cloudSqlInstance property not set. Please specify this property in the JDBC URL`
**Root cause:** Keycloak's Quarkus/Agroal connection pool strips query parameters from the JDBC URL before passing them to the JDBC driver. The `socketFactory` class loaded, but `cloudSqlInstance` was never passed to it.
**Attempted fixes:**
1. Merged params into `KC_DB_URL` → Quarkus still stripped them
2. `KC_DB_URL_PROPERTIES` env var → Not a real Keycloak config property
3. `JAVA_OPTS_APPEND` with `-Dquarkus.datasource.jdbc.additional-jdbc-properties.*` → Untested

**Final resolution:** Abandoned Socket Factory approach entirely. See Issue #10.

---

## Issue #10: Switched from Socket Factory to Private IP (architectural change)

**When:** After 4 failed attempts with Socket Factory
**Decision:** Enable private IP on Cloud SQL via VPC Peering instead of using Socket Factory

**What was added:**
- `google_compute_global_address.private_ip_range` (IP range reservation for peering)
- `google_service_networking_connection.private_vpc` (VPC peering to Google's service VPC)
- `servicenetworking.googleapis.com` API enabled
- `private_network` on Cloud SQL `ip_configuration`

**What was removed:**
- `cloud_sql_instance` volumes from all Cloud Run services
- `volume_mounts` for `/cloudsql`
- Socket Factory env vars (`KC_DB_URL_PROPERTIES`, `JAVA_OPTS_APPEND`)
- Multi-stage Maven builder from Keycloak Dockerfile (reverted to stock image)

**New JDBC URLs:**
```
# Keycloak (before)
jdbc:postgresql:///keycloak_db?cloudSqlInstance=...&socketFactory=...

# Keycloak (after)
jdbc:postgresql://10.109.0.3:5432/keycloak_db

# Control Plane (before)
postgresql+asyncpg://user:@/deeptrail_controldb?host=/cloudsql/...

# Control Plane (after)
postgresql://user:@10.109.0.3:5432/deeptrail_controldb
```

---

## Issue #11: Terraform state lost after interrupted `terraform apply`

**When:** User Ctrl+C'd `terraform apply` mid-run, then re-ran it
**Error:** 25+ `Error 409: ... already exists` errors for Cloud SQL, service accounts, secrets, Redis, Artifact Registry, LB IP, SSL cert, VPC connector
**Root cause:** Terraform state only had APIs and random passwords; all infrastructure resources were missing from state
**Fix:** Manually imported all existing resources into Terraform state:
```bash
terraform import google_sql_database_instance.main deepsecure-db
terraform import google_service_account.runner projects/deepsecure-saas/serviceAccounts/deepsecure-runner@deepsecure-saas.iam.gserviceaccount.com
terraform import google_redis_instance.main projects/deepsecure-saas/locations/us-central1/instances/deepsecure-redis
terraform import google_vpc_access_connector.serverless projects/deepsecure-saas/locations/us-central1/connectors/deepsecure-vpc-cx
# ... and ~30 more resources (secrets, secret versions, databases, etc.)
```

---

## Issue #12: Keycloak Cloud Run service also needed import

**When:** `terraform apply` after importing other resources
**Error:** `Error 409: Resource 'keycloak' already exists`
**Fix:**
```bash
terraform import google_cloud_run_v2_service.keycloak \
  projects/deepsecure-saas/locations/us-central1/services/keycloak
```

---

## Issue #13: Terraform "inconsistent final plan" for Cloud SQL private IP

**When:** `terraform apply` after enabling private IP
**Error:** `was cty.StringVal("jdbc:postgresql://:5432/keycloak_db"), but now cty.StringVal("jdbc:postgresql://10.109.0.3:5432/keycloak_db")`
**Root cause:** During planning, Cloud SQL's private IP didn't exist yet (empty string). During apply, the IP was assigned, changing the computed value.
**Fix:** Just run `terraform apply` again. With the private IP now in state, the plan is consistent.

---

## Issue #14: Terraform "inconsistent final plan" for Keycloak URL

**When:** `terraform apply` (deploying Control Plane)
**Error:** `was cty.StringVal("/realms/deepsecure"), but now cty.StringVal("https://keycloak-flhiwg2wfa-uc.a.run.app/realms/deepsecure")`
**Root cause:** Same issue as #13. Keycloak's `.run.app` URL was unknown during planning, resolved during apply.
**Fix:** Run `terraform apply` again.

---

## Issue #15: `allUsers` IAM binding blocked by organization policy

**When:** `terraform apply` (creating IAM binding for Cloud Run)
**Error:** `One or more users named in the policy do not belong to a permitted customer, perhaps due to an organization policy`
**Root cause:** GCP organization `deeptrail.com` (ID: 30372715031) has `constraints/iam.allowedPolicyMemberDomains` policy that blocks `allUsers`
**Fix:**
```bash
# Grant yourself org policy admin
gcloud organizations add-iam-policy-binding 30372715031 \
  --member="user:mahendra@deeptrail.com" \
  --role="roles/orgpolicy.policyAdmin"

# Override the constraint for this project
gcloud resource-manager org-policies set-policy --project=deepsecure-saas /dev/stdin <<'EOF'
constraint: constraints/iam.allowedPolicyMemberDomains
restoreDefault: {}
EOF
```

---

## Issue #16: Control Plane `ModuleNotFoundError: No module named 'asyncpg'`

**When:** Cloud Run Control Plane startup (Alembic migration)
**Error:** `ModuleNotFoundError: No module named 'asyncpg'`
**Root cause:** `DATABASE_URL` used `postgresql+asyncpg://` but Alembic's `create_engine()` (sync) tried to import `asyncpg`, which isn't installed. The app only has `psycopg2-binary`.
**File:** `deeptrail-control/alembic/env.py`
**Fix:** Added URL driver swap in `get_url()`:
```python
db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
```

---

## Issue #17: Control Plane `no password supplied`

**When:** Cloud Run Control Plane startup (Alembic connecting to Cloud SQL)
**Error:** `psycopg2.OperationalError: connection to server at "10.109.0.3", port 5432 failed: fe_sendauth: no password supplied`
**Root cause:** `DATABASE_URL` was `postgresql://user:@10.109.0.3:5432/deeptrail_controldb` (empty password). The password was in a separate `DB_PASSWORD` env var from Secret Manager but never injected into the URL.
**File:** `deeptrail-control/run_service.sh`
**Fix:** Added password injection at container startup:
```bash
if [ -n "$DB_PASSWORD" ] && echo "$DATABASE_URL" | grep -q '://..*:@'; then
  export DATABASE_URL=$(echo "$DATABASE_URL" | sed "s|://\(.*\):@|://\1:${DB_PASSWORD}@|")
fi
```

---

## Issue #18: `DATABASE_URL` used `+asyncpg` driver for sync app

**When:** Cloud Run Control Plane startup (Uvicorn importing app)
**Error:** `ModuleNotFoundError: No module named 'asyncpg'` (this time from `app/db/session.py`, not Alembic)
**Root cause:** `DATABASE_URL` in Terraform was `postgresql+asyncpg://...` but the app uses synchronous `create_engine()` with `psycopg2-binary`. Zero `asyncpg` usage in the codebase.
**File:** `infra/terraform/cloud_run.tf`
**Fix:** Changed URL from `postgresql+asyncpg://` to `postgresql://`:
```hcl
value = "postgresql://${google_sql_user.main.name}:@${...private_ip_address}:5432/deeptrail_controldb"
```

---

## Issue #19: `build-and-push.sh` path errors and no single-image support

**When:** Running `./build-and-push.sh keycloak` from `infra/` directory
**Error:** `unable to prepare context: path "deeptrail-control/" not found`
**Root cause:** Build contexts were relative paths (`deeptrail-control/`) but the script was run from `infra/`, not repo root. Also, the script didn't support building individual images.
**File:** `infra/build-and-push.sh`
**Fix:**
- Resolved repo root from script location using `SCRIPT_DIR`/`REPO_ROOT`
- Made all build contexts absolute paths
- Added argument support: `./build-and-push.sh keycloak` builds only Keycloak

---

## Phase 2: Domain, SSL, OAuth, Application

---

## Issue #20: SSL certificate swap — "resource in use"

**When:** Switching domain from `app.deepsecure.io` to `app.deepsecure.one`
**Error:** `Error when reading or editing ManagedSslCertificate: resource 'deepsecure-cert' is already being used by 'deepsecure-https-proxy'`
**Root cause:** Can't delete an SSL cert that's still attached to the HTTPS proxy.
**File:** `infra/terraform/lb.tf`
**Fix:** Renamed cert from `deepsecure-cert` to `deepsecure-cert-v2` and added `lifecycle { create_before_destroy = true }` so Terraform creates the new cert before detaching the old one.

---

## Issue #21: Google SSO — `invalid_client` (401)

**When:** Clicking "Sign in with Google" on `app.deepsecure.one`
**Error:** `Access blocked: Authorization Error — The OAuth client was not found. Error 401: invalid_client`
**Root cause:** Terraform set `GOOGLE_SSO_CLIENT_ID` and `GOOGLE_SSO_CLIENT_SECRET` env vars, but the Control Plane code (`idp_config.py`) looks for `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` when `IDP_PROVIDER=keycloak` and the SSO provider override is `google`.
**File:** `infra/terraform/cloud_run.tf`
**Fix:** Changed env var names from `GOOGLE_SSO_CLIENT_ID`/`GOOGLE_SSO_CLIENT_SECRET` to `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`. Set `IDP_PROVIDER=keycloak` (primary), with correct Keycloak issuer/browser URLs.

---

## Issue #22: Google SSO — `redirect_uri_mismatch` (400)

**When:** After fixing #21, SSO redirect failed
**Error:** `Error 400: redirect_uri_mismatch`
**Root cause:** The frontend SSO route constructs a callback URL as `https://app.deepsecure.one/api/auth/sso/google/callback` (no `/v1/`), but Google Cloud Console only had `https://app.deepsecure.one/api/v1/auth/sso/google/callback`.
**Fix:** Added the correct redirect URI (without `/v1/`) to the Google Cloud Console OAuth client's Authorized redirect URIs.

---

## Issue #23: Google SSO — `redirect_uri_mismatch` with `localhost:3000`

**When:** After fixing #22, SSO still failed
**Error:** `redirect_uri_mismatch` — frontend was sending `http://localhost:3000` as origin
**Root cause:** Frontend Cloud Run service was missing `FRONTEND_ORIGIN` env var, so it defaulted to `http://localhost:3000`.
**File:** `infra/terraform/cloud_run.tf`
**Fix:** Added `FRONTEND_ORIGIN = "https://${var.domain}"` to the frontend Cloud Run service environment.

---

## Issue #24: Google service connections using wrong OAuth client

**When:** Trying to connect Gmail, Google Drive, Google Calendar
**Error:** Service connections failed — redirect URIs didn't match
**Root cause:** The Control Plane uses `GOOGLE_CLIENT_ID` for both SSO and service connections (Gmail, Drive, Calendar). Terraform had two separate Google OAuth clients (`google-sso-client-id` for login, `google-oauth-client-id` for services). The `GOOGLE_CLIENT_ID` env var pointed at the SSO client, which lacked service-specific redirect URIs and scopes.
**Fix:** Consolidated to one Google OAuth client (the "Services" client). Added all SSO + service redirect URIs to it. Updated `cloud_run.tf` so `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` point to the Services client.

---

## Issue #25: Onboarding wizard "Not Found" for service connections

**When:** Onboarding flow — clicking Connect for Notion/Slack/Gmail
**Error:** `404 Not Found`
**Root cause:** `WelcomeWizard.tsx` called `/api/proxy/sso/connect/${serviceId}` which doesn't exist. The Services page used the correct `apiClient("oauth/${serviceId}/authorize")` pattern.
**File:** `frontend/src/components/onboarding/WelcomeWizard.tsx`
**Fix:** Changed to use `apiClient` to call `oauth/${serviceId}/authorize` (same pattern as the Services page).

---

## Issue #26: Agents, Policies, Tasks pages — "Failed to load (302)"

**When:** Navigating to Agents, Policies, Tasks, Create Delegation pages on `app.deepsecure.one`
**Error:** `Failed to load agents (302)`, `Failed to load policies (302)`, `Failed to load tasks (302)`
**Root cause:** **FastAPI/Next.js trailing slash mismatch.** Three factors combined:

1. **FastAPI routes defined with `"/"`**: `@router.get("/")` at `prefix="/agents"` creates canonical path `/api/v1/agents/` (with trailing slash). Requests to `/api/v1/agents` (no slash) get a 307 redirect.
2. **Next.js strips trailing slashes**: The `[...path]` catch-all route receives `["agents"]` even when the browser requests `/api/proxy/agents/`. The proxy reconstructs the URL without trailing slash.
3. **FastAPI's 307 redirect URL is unreachable**: The redirect `Location` header uses the container-internal hostname (e.g., `http://0.0.0.0:8001/api/v1/agents/`), which the frontend container can't reach. The proxy's redirect-following code fails silently.

The proxy had redirect-following code (`redirect: "manual"` + manual 307 handling), which worked locally (redirect to `localhost:8000` is reachable) but failed on Cloud Run (redirect to `0.0.0.0:8001` is unreachable between containers).

**Files:**
- `deeptrail-control/app/api/v1/endpoints/agents.py`
- `deeptrail-control/app/api/v1/endpoints/policies.py`
- `deeptrail-control/app/api/v1/endpoints/tasks.py`
- `deeptrail-control/app/api/v1/endpoints/attestation_policies.py`

**Fix:** Changed route definitions from `@router.get("/", ...)` to `@router.get("", ...)` in all four files. This makes the canonical path `/api/v1/agents` (no trailing slash), which is what the proxy sends. No redirect needed.

**Bonus issue within this fix:** First rebuild attempt failed with `exec format error` because `docker build` was run without `--platform linux/amd64`. Second issue: `terraform apply` with `:latest` tag didn't trigger a new revision because the image reference string was unchanged. Used `gcloud run services update --image=...` instead.

---

## Issue #27: Keycloak "Invalid parameter: redirect_uri" after login

**When:** User logged in successfully via Google SSO, then after 2-3 minutes saw "We are sorry... Invalid parameter: redirect_uri"
**Error:** Keycloak error page — "We are sorry... Invalid parameter: redirect_uri"
**Root cause:** **Keycloak client `redirectUris` only contained `localhost` URLs.** The realm JSON (`config/keycloak/deepsecure-realm.json`) was imported on first Keycloak startup with only localhost redirect URIs. When the Control Plane sends `redirect_uri=https://app.deepsecure.one/api/v1/auth/sso/callback`, Keycloak rejects it because that URI isn't in the client's allowed list.

This manifested after 2-3 minutes because: (1) initial login used Google SSO (bypasses Keycloak), (2) session/token refresh or a subsequent navigation triggered the Keycloak IDP flow (since `IDP_PROVIDER=keycloak`), (3) Keycloak rejected the production redirect URI.

**Fix:**
1. **Immediate:** Updated the Keycloak client via Admin API to add `https://app.deepsecure.one/*` to `redirectUris` and `webOrigins`.
2. **Permanent:** Updated `config/keycloak/deepsecure-realm.json` with production URIs. Updated `keycloak-start.sh` to auto-sync production redirect URIs via `KC_PRODUCTION_DOMAIN` env var. Added `KC_PRODUCTION_DOMAIN` to Terraform `cloud_run.tf`.

**Files:**
- `config/keycloak/deepsecure-realm.json` — added production redirect URIs
- `config/keycloak/keycloak-start.sh` — auto-sync redirect URIs on startup
- `infra/terraform/cloud_run.tf` — added `KC_PRODUCTION_DOMAIN` env var

---

## Issue #28: Keycloak login page unstyled (missing CSS/JS)

**When:** Clicking "Sign in with Keycloak" — login page renders but with plain HTML, no styling
**Root cause:** **LB URL map missing `/resources/*` path rule.** Keycloak serves CSS/JS/images from `/resources/...` paths, but only `/realms/*` and `/admin/*` were routed to Keycloak. Asset requests fell through to the frontend (default backend) which returned 404/redirect.
**Fix:** Added `/resources/*` and `/js/*` path rules to the LB URL map in `lb.tf` pointing to the Keycloak backend.

**Files:**
- `infra/terraform/lb.tf` — added `/resources/*` and `/js/*` path rules

---

## Issue #29: Keycloak token exchange fails with 401

**When:** After Keycloak login page loads and user authenticates, redirect back to app fails with "Failed to exchange authorization code"
**Error:** `WARNING:app.api.v1.endpoints.sso:Code exchange failed for keycloak: Token exchange failed: 401`
**Root cause:** **`idp-client-secret` in GCP Secret Manager was auto-generated random string, not Keycloak's actual client secret.** Terraform auto-generates secrets for `idp-client-secret`, but the Keycloak client (`deepsecure-control`) expects `control-secret` (as set in `deepsecure-realm.json`). The Control Plane sent the wrong secret during the authorization code → token exchange.
**Fix:** Updated the `idp-client-secret` in GCP Secret Manager to `control-secret`, then restarted the Control Plane via `gcloud run services update`.

**Commands:**
```bash
echo -n "control-secret" | gcloud secrets versions add idp-client-secret --data-file=- --project=deepsecure-saas
gcloud run services update deeptrail-control --region=us-central1 --project=deepsecure-saas --image=...
```

---

## Summary: Issues by Category

| Category | Count | Issues |
|----------|-------|--------|
| **OAuth/SSO configuration** | 7 | #21, #22, #23, #24, #27, #28, #29 |
| **Cloud SQL connectivity** | 5 | #8, #9, #10, #17, #18 |
| **Terraform state/plan** | 4 | #11, #12, #13, #14 |
| **Docker/Cloud Run config** | 4 | #4, #5, #6, #19 |
| **FastAPI/Next.js routing** | 1 | #26 |
| **Frontend code bugs** | 1 | #25 |
| **SSL/Domain** | 1 | #20 |
| **Keycloak JDBC** | 2 | #7, #9 |
| **GCP permissions/policy** | 2 | #1, #15 |
| **Terraform resource config** | 2 | #2, #3 |
| **App code/dependencies** | 2 | #16, #18 |

## Files Modified During Deployment

### Phase 1: Infrastructure

| File | Changes Made |
|------|-------------|
| `infra/terraform/cloud_run.tf` | Port 8080, health check, resources, removed Cloud SQL volumes, private IP URLs, sync driver |
| `infra/terraform/database.tf` | Added private IP range, VPC peering, private_network |
| `infra/terraform/apis.tf` | Added `servicenetworking.googleapis.com` |
| `infra/terraform/network.tf` | Added `network = "default"` |
| `infra/build-and-push.sh` | `--platform linux/amd64`, absolute paths, single-image support |
| `config/keycloak/Dockerfile` | Socket Factory multi-stage build → reverted to stock image |
| `deeptrail-control/run_service.sh` | DB_PASSWORD injection into DATABASE_URL |
| `deeptrail-control/alembic/env.py` | `+asyncpg` → sync driver swap in `get_url()` |

### Phase 2: Domain, SSL, OAuth, Application

| File | Changes Made |
|------|-------------|
| `infra/terraform/lb.tf` | SSL cert rename to `v2`, `lifecycle { create_before_destroy = true }` |
| `infra/terraform/variables.tf` | Domain default `app.deepsecure.io` → `app.deepsecure.one` |
| `infra/terraform/terraform.tfvars` | Domain `app.deepsecure.io` → `app.deepsecure.one` |
| `infra/terraform/cloud_run.tf` | `GOOGLE_CLIENT_ID`/`SECRET` env var names, `IDP_PROVIDER=keycloak`, `FRONTEND_ORIGIN`, consolidated OAuth client |
| `frontend/src/components/onboarding/WelcomeWizard.tsx` | Fixed OAuth connect to use `apiClient("oauth/${serviceId}/authorize")` |
| `deeptrail-control/app/api/v1/endpoints/agents.py` | Route `"/"` → `""` for list/create endpoints |
| `deeptrail-control/app/api/v1/endpoints/policies.py` | Route `"/"` → `""` for list/create endpoints |
| `deeptrail-control/app/api/v1/endpoints/tasks.py` | Route `"/"` → `""` for list/create endpoints |
| `deeptrail-control/app/api/v1/endpoints/attestation_policies.py` | Route `"/"` → `""` for list/create endpoints |

## Time Breakdown

### Phase 1: Infrastructure Deploy

| Time (PDT) | Duration | Activity |
|-------------|----------|----------|
| ~3:00 PM | -- | First `terraform apply` (issues #1-#4 from earlier sessions already fixed) |
| 3:00 - 3:30 | ~30 min | Keycloak startup probe failures: wrong port, health path, resources, architecture (#5, #6) |
| 3:30 - 3:35 | ~5 min | Terraform state import after interrupted apply (#11, #12) -- 30+ resources imported |
| 3:35 - 3:47 | ~12 min | Keycloak Socket Factory: `localhost:5432 refused`, `cloudSqlInstance not set` (#8, #9) |
| 3:47 - 3:54 | ~7 min | Decision to switch to Private IP, Terraform config changes (#10) |
| 3:54 - 3:58 | ~4 min | Keycloak Dockerfile cleanup (back to stock image), `build-and-push.sh` fixes (#7, #19) |
| 3:58 - 4:10 | ~12 min | Cloud SQL Private IP provisioning (VPC peering + IP assignment -- normal GCP wait) |
| 4:10 - 4:25 | ~15 min | Terraform "inconsistent plan" errors -- two re-runs needed (#13, #14) |
| 4:25 - 4:29 | ~4 min | Keycloak successfully deployed (first service up!) |
| 4:29 - 4:37 | ~8 min | `allUsers` org policy block -- grant `orgpolicy.policyAdmin`, override constraint (#15) |
| 4:37 - 4:43 | ~6 min | Control Plane: `asyncpg` not found in Alembic (#16) |
| 4:43 - 4:45 | ~2 min | Control Plane: `no password supplied` -- DB_PASSWORD injection (#17) |
| 4:45 - 4:50 | ~5 min | Control Plane: `asyncpg` not found in app (wrong driver in URL) (#18) |
| 4:50 - 4:53 | ~3 min | Fix DATABASE_URL to `postgresql://`, rebuild control image |
| 4:53 - 5:06 | ~13 min | Final `terraform apply` -- all 4 services + LB + NEGs created successfully |
| **Phase 1** | **~2h 6m** | **19 issues resolved, 12 apply attempts** |

### Phase 2: Domain, SSL, OAuth, Application

| Time (PDT) | Duration | Activity |
|-------------|----------|----------|
| 5:06 - 5:20 | ~14 min | Domain switch to `app.deepsecure.one`, SSL cert swap (#20), DNS A record, SSL provisioning wait |
| 5:20 - 6:00 | ~40 min | Google SSO debugging: `invalid_client`, `redirect_uri_mismatch`, `localhost:3000` (#21, #22, #23) |
| 6:00 - 6:30 | ~30 min | Google service connections: wrong OAuth client, consolidated to single client (#24) |
| 6:30 - 6:45 | ~15 min | Onboarding wizard fix (#25), frontend rebuild |
| 6:45 - 7:30 | ~45 min | Agents/Policies/Tasks 302 errors: diagnosed FastAPI/Next.js trailing slash mismatch (#26) |
| 7:30 - 8:00 | ~30 min | Rebuild with `--platform linux/amd64`, `gcloud run services update` to force new revision, verify fix |
| **Phase 2** | **~2h 54m** | **7 issues resolved, 5 terraform applies + gcloud deploys** |

### Grand Total

| | Phase 1 | Phase 2 | Total |
|--|---------|---------|-------|
| **Duration** | ~2h 6m | ~2h 54m | **~5h** |
| **Issues resolved** | 19 | 7 | **26** |
| **Docker rebuilds** | 3 | 4 | **7** |

### Time by Category

| Category | Time Spent | Issues |
|----------|-----------|--------|
| OAuth/SSO configuration | ~85 min | #21, #22, #23, #24 |
| Cloud SQL connectivity (Socket Factory → Private IP) | ~45 min | #8, #9, #10, #17, #18 |
| FastAPI/Next.js routing + deploy cycle | ~75 min | #26 |
| Terraform state/plan reconciliation | ~20 min | #11, #12, #13, #14 |
| GCP infrastructure provisioning (normal wait times) | ~25 min | VPC peering, Cloud SQL, backend services |
| Docker/Cloud Run configuration | ~15 min | #5, #6, #7, #19 |
| Domain/SSL switch | ~14 min | #20 |
| Frontend code fix (onboarding) | ~15 min | #25 |
| GCP permissions/org policy | ~8 min | #1, #15 |
| App code/dependency fixes | ~8 min | #16, #18 |

## Lessons Learned

1. **Socket Factory + Keycloak is a dead end.** Keycloak's Quarkus/Agroal strips JDBC URL query params. Use Cloud SQL Private IP instead.
2. **Always build `--platform linux/amd64`** on Apple Silicon for Cloud Run.
3. **Never Ctrl+C `terraform apply`** mid-run. If you must, be prepared to import resources back.
4. **Terraform computed values cause "inconsistent plan"** when resources are created in the same apply. Just re-run.
5. **Check the actual DB driver** before writing `DATABASE_URL`. The app uses psycopg2 (sync), not asyncpg.
6. **Secret Manager values can't be embedded in Terraform strings.** Inject at container runtime instead.
7. **GCP org policies block `allUsers`** by default. Override at the project level for public-facing services.
8. **Cloud SQL private IP takes 5-12 minutes** to provision. This is normal.
9. **FastAPI `"/"` routes + Next.js proxy = trailing slash deadlock.** Next.js catch-all `[...path]` strips trailing slashes. FastAPI routes defined with `"/"` require them and 307-redirect. The redirect `Location` uses the container-internal hostname, unreachable between Cloud Run services. Fix: define routes as `""` not `"/"`.
10. **Terraform won't redeploy for `:latest` tag changes.** The image reference string is identical, so `terraform apply` sees no diff. Use `gcloud run services update --image=...` to force a new revision, or use unique image tags (commit hash, timestamp).
11. **Env var names must match the code, not the intent.** The Control Plane code looks for `GOOGLE_CLIENT_ID`, not `GOOGLE_SSO_CLIENT_ID`. Always trace the code path that reads the env var before naming it in Terraform.
12. **One Google OAuth client for all Google services.** The Control Plane uses `GOOGLE_CLIENT_ID` for SSO, Gmail, Drive, and Calendar. Don't split into separate OAuth clients — consolidate and add all redirect URIs to one client.
13. **SSL cert swaps need `lifecycle { create_before_destroy = true }`.** Can't delete a cert attached to an HTTPS proxy. Create the new one first, then swap.
14. **Keycloak realm import is one-shot.** `--import-realm` only runs when the realm doesn't exist in the DB. Updating the JSON and redeploying won't change existing clients. Use the Admin API or add a startup script that syncs critical config (like redirect URIs) on every boot.
15. **Auto-generated secrets must match the service that validates them.** Terraform auto-generates `idp-client-secret`, but Keycloak's client expects the secret from the realm JSON (`control-secret`). Always check what the target service expects.
16. **Keycloak needs `/resources/*` routed through the LB.** The login page HTML comes from `/realms/*`, but CSS/JS assets are at `/resources/*`. Missing this route results in an unstyled login page.
