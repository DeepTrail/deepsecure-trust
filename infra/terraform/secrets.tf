# ---------------------------------------------------------------------------
# Auto-generated secrets (random values managed by Terraform)
# ---------------------------------------------------------------------------

locals {
  auto_secrets = {
    jwt-secret              = "JWT signing secret for deeptrail-control"
    gateway-internal-token  = "Internal token for gateway-to-control communication"
    backend-api-token       = "Backend API token"
    gateway-encryption-key  = "Encryption key for gateway payload encryption"
    fernet-key              = "Fernet key for encrypting OAuth credentials in DB"
    session-secret          = "Frontend session cookie secret"
    csrf-secret             = "Frontend CSRF protection secret"
    keycloak-admin-password = "Keycloak admin console password"
    idp-client-secret       = "Keycloak OIDC client secret for DeepSecure realm"
  }
}

resource "random_password" "auto" {
  for_each = local.auto_secrets

  length  = 32
  special = true
}

resource "google_secret_manager_secret" "auto" {
  for_each = local.auto_secrets

  secret_id = each.key
  project   = var.project_id

  replication {
    auto {}
  }

  labels = {
    managed_by = "terraform"
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "auto" {
  for_each = local.auto_secrets

  secret      = google_secret_manager_secret.auto[each.key].id
  secret_data = random_password.auto[each.key].result
}

# ---------------------------------------------------------------------------
# User-provided secrets (values from variables)
# ---------------------------------------------------------------------------

locals {
  user_secrets = {
    db-password            = var.db_password
    google-sso-client-id   = var.google_sso_client_id
    google-sso-secret      = var.google_sso_client_secret
    notion-client-id       = var.notion_client_id
    notion-client-secret   = var.notion_client_secret
    slack-client-id        = var.slack_client_id
    slack-client-secret    = var.slack_client_secret
    google-oauth-client-id = var.google_oauth_client_id
    google-oauth-secret    = var.google_oauth_client_secret
  }
}

resource "google_secret_manager_secret" "user" {
  for_each = local.user_secrets

  secret_id = each.key
  project   = var.project_id

  replication {
    auto {}
  }

  labels = {
    managed_by = "terraform"
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "user" {
  for_each = local.user_secrets

  secret      = google_secret_manager_secret.user[each.key].id
  secret_data = each.value
}
