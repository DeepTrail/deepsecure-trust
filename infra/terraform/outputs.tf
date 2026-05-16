output "lb_ip_address" {
  description = "Global load-balancer IP — point DNS A record here"
  value       = google_compute_global_address.lb.address
}

output "control_url" {
  description = "Cloud Run URL for deeptrail-control"
  value       = google_cloud_run_v2_service.control.uri
}

output "gateway_url" {
  description = "Cloud Run URL for deeptrail-gateway"
  value       = google_cloud_run_v2_service.gateway.uri
}

output "frontend_url" {
  description = "Cloud Run URL for frontend"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "keycloak_url" {
  description = "Cloud Run URL for Keycloak"
  value       = google_cloud_run_v2_service.keycloak.uri
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL instance connection name (for Auth Proxy)"
  value       = google_sql_database_instance.main.connection_name
}

output "artifact_registry_url" {
  description = "Artifact Registry Docker URL prefix"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/deepsecure"
}
