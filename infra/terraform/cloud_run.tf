locals {
  registry_prefix = "${var.region}-docker.pkg.dev/${var.project_id}/deepsecure"
  secret_ref      = "projects/${var.project_id}/secrets"
}

# ---------------------------------------------------------------------------
# Keycloak
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "keycloak" {
  name     = "keycloak"
  location = var.region
  project  = var.project_id



  template {
    service_account = google_service_account.runner.email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    vpc_access {
      connector = google_vpc_access_connector.serverless.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${local.registry_prefix}/keycloak:latest"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          memory = "1Gi"
          cpu    = "1"
        }
      }

      env {
        name  = "KC_DB"
        value = "postgres"
      }
      env {
        name  = "KC_DB_URL"
        value = "jdbc:postgresql://${google_sql_database_instance.main.private_ip_address}:5432/keycloak_db"
      }
      env {
        name  = "KC_DB_USERNAME"
        value = google_sql_user.main.name
      }
      env {
        name = "KC_DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.user["db-password"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "KC_HEALTH_ENABLED"
        value = "true"
      }
      env {
        name  = "KC_HOSTNAME_STRICT"
        value = "false"
      }
      env {
        name  = "KC_HTTP_ENABLED"
        value = "true"
      }
      env {
        name  = "KC_PROXY_HEADERS"
        value = "xforwarded"
      }
      env {
        name = "KEYCLOAK_ADMIN_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.auto["keycloak-admin-password"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "KEYCLOAK_ADMIN"
        value = "admin"
      }
      env {
        name  = "KC_PRODUCTION_DOMAIN"
        value = var.domain
      }

      startup_probe {
        http_get {
          path = "/health/ready"
        }
        initial_delay_seconds = 30
        period_seconds        = 15
        failure_threshold     = 20
        timeout_seconds       = 30
      }
    }
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_secret_manager_secret_version.user["db-password"],
    google_secret_manager_secret_version.auto["keycloak-admin-password"],
  ]
}

resource "google_cloud_run_v2_service_iam_member" "keycloak_public" {
  name     = google_cloud_run_v2_service.keycloak.name
  location = var.region
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------------------------------------------------------------------------
# deeptrail-control (Control Plane)
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "control" {
  name     = "deeptrail-control"
  location = var.region
  project  = var.project_id



  template {
    service_account = google_service_account.runner.email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    vpc_access {
      connector = google_vpc_access_connector.serverless.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${local.registry_prefix}/deeptrail-control:latest"

      ports {
        container_port = 8001
      }

      # --- Database ---
      env {
        name  = "DATABASE_URL"
        value = "postgresql://${google_sql_user.main.name}:@${google_sql_database_instance.main.private_ip_address}:5432/deeptrail_controldb"
      }
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.user["db-password"].secret_id
            version = "latest"
          }
        }
      }

      # --- Redis ---
      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.main.host}:${google_redis_instance.main.port}/0"
      }

      # --- Identity Provider (primary = Keycloak) ---
      env {
        name  = "IDP_PROVIDER"
        value = "keycloak"
      }
      env {
        name  = "IDP_ISSUER_URL"
        value = "${google_cloud_run_v2_service.keycloak.uri}/realms/deepsecure"
      }
      env {
        name  = "IDP_BROWSER_URL"
        value = "https://${var.domain}/realms/deepsecure"
      }
      env {
        name = "IDP_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.auto["idp-client-secret"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "IDP_REDIRECT_URI"
        value = "https://${var.domain}/api/v1/auth/sso/callback"
      }

      # --- JWT & Internal Tokens ---
      env {
        name = "JWT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.auto["jwt-secret"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GATEWAY_INTERNAL_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.auto["gateway-internal-token"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "BACKEND_API_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.auto["backend-api-token"].secret_id
            version = "latest"
          }
        }
      }

      # --- OAuth Integrations ---
      # GOOGLE_CLIENT_ID is used by both SSO (idp_config.py) and service
      # connections (oauth_service.py). Using the Services client which has
      # scopes for Drive, Calendar, Gmail plus openid/email/profile for SSO.
      env {
        name = "GOOGLE_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.user["google-oauth-client-id"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GOOGLE_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.user["google-oauth-secret"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "GOOGLE_HD"
        value = var.google_hd
      }
      env {
        name = "NOTION_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.user["notion-client-id"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "NOTION_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.user["notion-client-secret"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "SLACK_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.user["slack-client-id"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "SLACK_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.user["slack-client-secret"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GOOGLE_OAUTH_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.user["google-oauth-client-id"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GOOGLE_OAUTH_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.user["google-oauth-secret"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "OAUTH_REDIRECT_BASE_URL"
        value = "https://${var.domain}"
      }

      # --- Runtime ---
      env {
        name  = "CLOUD_RUN"
        value = "true"
      }
      env {
        name  = "CORS_ALLOWED_ORIGINS"
        value = "https://${var.domain}"
      }
      env {
        name  = "FRONTEND_ORIGIN"
        value = "https://${var.domain}"
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 5
      }
    }
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_secret_manager_secret_version.user,
    google_secret_manager_secret_version.auto,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "control_public" {
  name     = google_cloud_run_v2_service.control.name
  location = var.region
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------------------------------------------------------------------------
# deeptrail-gateway (Data Plane)
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "gateway" {
  name     = "deeptrail-gateway"
  location = var.region
  project  = var.project_id



  template {
    service_account = google_service_account.runner.email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    vpc_access {
      connector = google_vpc_access_connector.serverless.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${local.registry_prefix}/deeptrail-gateway:latest"

      ports {
        container_port = 8001
      }

      env {
        name  = "CONTROL_PLANE_URL"
        value = google_cloud_run_v2_service.control.uri
      }
      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.main.host}:${google_redis_instance.main.port}/0"
      }
      env {
        name = "GATEWAY_INTERNAL_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.auto["gateway-internal-token"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GATEWAY_ENCRYPTION_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.auto["gateway-encryption-key"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "CLOUD_RUN"
        value = "true"
      }
      env {
        name  = "CORS_ALLOWED_ORIGINS"
        value = "https://${var.domain}"
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 5
      }
    }
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_secret_manager_secret_version.auto,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "gateway_public" {
  name     = google_cloud_run_v2_service.gateway.name
  location = var.region
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------------------------------------------------------------------------
# Frontend (Next.js)
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "frontend" {
  name     = "frontend"
  location = var.region
  project  = var.project_id



  template {
    service_account = google_service_account.runner.email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    vpc_access {
      connector = google_vpc_access_connector.serverless.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${local.registry_prefix}/frontend:latest"

      ports {
        container_port = 3000
      }

      env {
        name  = "DEEPTRAIL_CONTROL_INTERNAL_URL"
        value = google_cloud_run_v2_service.control.uri
      }
      env {
        name  = "DEEPTRAIL_GATEWAY_INTERNAL_URL"
        value = google_cloud_run_v2_service.gateway.uri
      }
      env {
        name  = "NEXT_PUBLIC_IDP_DEFAULT"
        value = "google"
      }
      env {
        name = "SESSION_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.auto["session-secret"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "CSRF_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.auto["csrf-secret"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "BACKEND_API_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.auto["backend-api-token"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "FRONTEND_ORIGIN"
        value = "https://${var.domain}"
      }
      env {
        name  = "IDP_ISSUER_URL"
        value = "${google_cloud_run_v2_service.keycloak.uri}/realms/deepsecure"
      }
      env {
        name  = "IDP_BROWSER_URL"
        value = "https://${var.domain}/realms/deepsecure"
      }

      startup_probe {
        http_get {
          path = "/"
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 5
      }
    }
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_secret_manager_secret_version.auto,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  name     = google_cloud_run_v2_service.frontend.name
  location = var.region
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "allUsers"
}
