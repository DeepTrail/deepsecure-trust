resource "google_service_account" "runner" {
  account_id   = "deepsecure-runner"
  display_name = "DeepSecure Cloud Run Service Account"
  project      = var.project_id
}

locals {
  runner_roles = [
    "roles/secretmanager.secretAccessor",
    "roles/cloudsql.client",
    "roles/logging.logWriter",
    "roles/iam.serviceAccountTokenCreator",
    "roles/cloudscheduler.admin",
  ]
}

resource "google_project_iam_member" "runner" {
  for_each = toset(local.runner_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.runner.email}"
}
