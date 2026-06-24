##
## Pre-provisioned agent identity slots.
##
## Each slot creates: Service Account, IAM bindings, Cloud Run Job, and
## Cloud Scheduler trigger (paused). The Control Plane's composite provision
## endpoint resumes the scheduler when an agent claims a slot.
##
## Slot count is configurable via terraform.tfvars — default 5 for MVP.
##

resource "google_service_account" "agent_slot" {
  count        = var.agent_slot_count
  account_id   = "agent-slot-${count.index + 1}-sa"
  display_name = "DeepSecure Agent Slot ${count.index + 1}"
  project      = var.project_id
}

locals {
  agent_slot_roles = [
    "roles/run.developer",
    "roles/secretmanager.secretAccessor",
    "roles/iam.serviceAccountTokenCreator",
    "roles/run.invoker",
  ]
}

resource "google_project_iam_member" "agent_slot_roles" {
  count   = var.agent_slot_count * length(local.agent_slot_roles)
  project = var.project_id
  role    = local.agent_slot_roles[count.index % length(local.agent_slot_roles)]
  member  = "serviceAccount:${google_service_account.agent_slot[floor(count.index / length(local.agent_slot_roles))].email}"
}

resource "google_cloud_run_v2_job" "agent_slot" {
  count    = var.agent_slot_count
  name     = "agent-slot-${count.index + 1}-deepsecure-agent-job"
  location = var.region

  template {
    template {
      service_account = google_service_account.agent_slot[count.index].email
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/deepsecure/gemini-agent:latest"
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_scheduler_job" "agent_slot" {
  count    = var.agent_slot_count
  name     = "trigger-agent-slot-${count.index + 1}-deepsecure-agent"
  region   = var.region
  schedule = "0 */2 * * *"
  paused   = true

  http_target {
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/agent-slot-${count.index + 1}-deepsecure-agent-job:run"
    http_method = "POST"
    oauth_token {
      service_account_email = google_service_account.agent_slot[count.index].email
    }
  }

  depends_on = [google_project_service.apis]
}

output "agent_slots_json" {
  description = "JSON array of agent slot metadata, piped to AGENT_SLOTS_JSON env var"
  value = jsonencode([
    for i in range(var.agent_slot_count) : {
      name           = "agent-slot-${i + 1}"
      sa_email       = google_service_account.agent_slot[i].email
      job_name       = google_cloud_run_v2_job.agent_slot[i].name
      scheduler_name = google_cloud_scheduler_job.agent_slot[i].name
      schedule       = "0 */2 * * *"
    }
  ])
  sensitive = false
}
