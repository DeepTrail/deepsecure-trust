# ---------------------------------------------------------------------------
# Cloud Tasks queue for proactive OAuth token refresh
# ---------------------------------------------------------------------------

resource "google_cloud_tasks_queue" "token_refresh" {
  name     = "token-refresh"
  location = var.region
  project  = var.project_id

  retry_config {
    max_attempts       = 5
    min_backoff        = "10s"
    max_backoff        = "300s"
    max_doublings      = 3
    max_retry_duration = "3600s"
  }

  rate_limits {
    max_concurrent_dispatches = 10
    max_dispatches_per_second = 5
  }

  depends_on = [
    google_project_service.apis,
  ]
}

# IAM: allow the Cloud Run service account to enqueue and cancel tasks
resource "google_project_iam_member" "runner_cloud_tasks_enqueuer" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.runner.email}"
}

resource "google_project_iam_member" "runner_cloud_tasks_deleter" {
  project = var.project_id
  role    = "roles/cloudtasks.taskDeleter"
  member  = "serviceAccount:${google_service_account.runner.email}"
}
