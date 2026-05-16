# DeepSecure GCP SaaS Deployment

Deploy the full DeepSecure stack to GCP Cloud Run with managed PostgreSQL, Redis, and a global load balancer.

## Prerequisites

| Tool | Install | Verify |
|------|---------|--------|
| Terraform | `brew install terraform` | `terraform --version` |
| gcloud CLI | `brew install --cask google-cloud-sdk` | `gcloud --version` |
| Docker | Docker Desktop for Mac | `docker --version` |

### One-Time GCP Authentication

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project deepsecure-saas
```

### One-Time GCP Console Steps

1. Create project `deepsecure-saas` at console.cloud.google.com
2. Link a billing account to the project
3. Create Google Workspace OAuth Client ID (for SSO login)
4. Create Google OAuth Client ID (for service connections: GDrive, GCal, Gmail)
5. Create Notion integration at api.notion.com
6. Create Slack app at api.slack.com

## Deployment

### Step 1: Configure Secrets

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with real secret values from the console steps above
```

### Step 2: Create Infrastructure

```bash
cd infra/terraform
terraform init
terraform plan          # Review what will be created
terraform apply         # Create Cloud SQL, Redis, secrets, LB, etc.
```

> First apply creates infrastructure but Cloud Run services will reference images
> that don't exist yet. This is expected.

### Step 3: Build and Push Docker Images

```bash
cd ../..                # Back to repo root
./infra/build-and-push.sh
```

This builds 4 images (control, gateway, frontend, keycloak) and pushes them to
Artifact Registry.

### Step 4: Deploy Cloud Run Services

```bash
cd infra/terraform
terraform apply         # Now Cloud Run services deploy with real images
```

### Step 5: Configure DNS

Get the load balancer IP:

```bash
terraform output lb_ip_address
```

Add an A record at your DNS provider:

```
app.deepsecure.io  ->  <LB_IP>
```

Wait 15-60 minutes for Google-managed SSL certificate provisioning.

### Step 6: Run Database Migrations

```bash
cd ../..
./infra/migrate.sh              # Via Cloud Run Job (recommended)
# or
./infra/migrate.sh local        # Via local cloud-sql-proxy
```

### Step 7: Register OAuth Redirect URIs

In each OAuth app's settings, add the production redirect URIs:

| App | Redirect URI |
|-----|-------------|
| Google SSO | `https://app.deepsecure.io/api/v1/auth/sso/google/callback` |
| Google OAuth (services) | `https://app.deepsecure.io/api/v1/oauth/google/callback` |
| Notion | `https://app.deepsecure.io/api/v1/oauth/notion/callback` |
| Slack | `https://app.deepsecure.io/api/v1/oauth/slack/callback` |

### Step 8: Validate

```bash
# Health checks
curl https://app.deepsecure.io/api/v1/health
curl https://app.deepsecure.io/realms/deepsecure/.well-known/openid-configuration

# CORS check
curl -sI -H "Origin: https://app.deepsecure.io" \
  https://app.deepsecure.io/api/v1/health | grep access-control

# Browser: open https://app.deepsecure.io and test SSO login
```

## Teardown

```bash
cd infra/terraform
terraform destroy       # Deletes all GCP resources
```

For partial teardown (keep database, remove services):

```bash
terraform destroy -target=google_cloud_run_v2_service.control
terraform destroy -target=google_cloud_run_v2_service.gateway
terraform destroy -target=google_cloud_run_v2_service.frontend
terraform destroy -target=google_cloud_run_v2_service.keycloak
```

## Architecture

```
Internet -> Global LB (app.deepsecure.io, managed SSL)
              |
              ├── /           -> Frontend (Cloud Run, Next.js)
              ├── /api/v1/*   -> Control Plane (Cloud Run, FastAPI)
              ├── /mcp/*      -> Gateway (Cloud Run, FastAPI)
              └── /realms/*   -> Keycloak (Cloud Run)

Control + Keycloak -> Cloud SQL PostgreSQL 15 (via Auth Proxy)
Control + Gateway  -> Memorystore Redis 7 (via VPC connector)
```

## File Structure

```
infra/
├── terraform/
│   ├── providers.tf          # GCP provider config
│   ├── variables.tf          # Input variables
│   ├── terraform.tfvars.example  # Template (copy to terraform.tfvars)
│   ├── apis.tf               # Enable GCP APIs
│   ├── iam.tf                # Service account + roles
│   ├── network.tf            # VPC connector
│   ├── database.tf           # Cloud SQL + databases
│   ├── redis.tf              # Memorystore
│   ├── registry.tf           # Artifact Registry
│   ├── secrets.tf            # Secret Manager entries
│   ├── cloud_run.tf          # 4 Cloud Run services
│   ├── lb.tf                 # Load balancer + SSL + path routing
│   ├── dns.tf                # Cloud DNS (optional)
│   └── outputs.tf            # Service URLs, LB IP
├── build-and-push.sh         # Build + push Docker images
├── migrate.sh                # Run Alembic migrations
└── README.md                 # This file
```

## Cost Estimate (Dev/Staging)

| Service | Monthly Est. |
|---------|-------------|
| Cloud SQL (db-f1-micro) | ~$10 |
| Memorystore (1GB Basic) | ~$35 |
| Cloud Run x4 (scale-to-zero) | ~$5-15 |
| Load Balancer | ~$18 |
| Other (AR, secrets) | ~$1 |
| **Total** | **~$70-80** |
