resource "google_compute_global_address" "private_ip_range" {
  name          = "google-managed-services-default"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = "projects/${var.project_id}/global/networks/default"
  project       = var.project_id
}

resource "google_service_networking_connection" "private_vpc" {
  network                 = "projects/${var.project_id}/global/networks/default"
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
}

resource "google_sql_database_instance" "main" {
  name             = "deepsecure-db"
  database_version = "POSTGRES_15"
  region           = var.region
  project          = var.project_id

  deletion_protection = false

  settings {
    tier              = var.db_tier
    availability_type = "ZONAL"
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    ip_configuration {
      ipv4_enabled                                  = true
      private_network                               = "projects/${var.project_id}/global/networks/default"
      enable_private_path_for_google_cloud_services = true
    }
  }

  depends_on = [
    google_project_service.apis["sqladmin.googleapis.com"],
    google_service_networking_connection.private_vpc,
  ]
}

resource "google_sql_database" "control" {
  name     = "deeptrail_controldb"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_database" "keycloak" {
  name     = "keycloak_db"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "main" {
  name     = "deepsecure_user"
  instance = google_sql_database_instance.main.name
  password = var.db_password
}
