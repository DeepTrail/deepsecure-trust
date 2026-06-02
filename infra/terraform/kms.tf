# ---------------------------------------------------------------------------
# GCP KMS resources for encrypting secrets at rest
# ---------------------------------------------------------------------------

resource "google_kms_key_ring" "deepsecure" {
  name     = "deepsecure"
  location = var.region
  project  = var.project_id

  depends_on = [google_project_service.apis["cloudkms.googleapis.com"]]
}

resource "google_kms_crypto_key" "service_credentials" {
  name     = "service-credentials"
  key_ring = google_kms_key_ring.deepsecure.id

  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key" "vault_tokens" {
  name     = "vault-tokens"
  key_ring = google_kms_key_ring.deepsecure.id

  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key_iam_member" "runner_service_credentials" {
  crypto_key_id = google_kms_crypto_key.service_credentials.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.runner.email}"
}

resource "google_kms_crypto_key_iam_member" "runner_vault_tokens" {
  crypto_key_id = google_kms_crypto_key.vault_tokens.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.runner.email}"
}
