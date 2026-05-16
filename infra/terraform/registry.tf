resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = "deepsecure"
  format        = "DOCKER"
  description   = "DeepSecure container images"

  depends_on = [google_project_service.apis["artifactregistry.googleapis.com"]]
}
