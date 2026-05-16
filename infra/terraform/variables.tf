variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "deepsecure-saas"
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "us-central1"
}

variable "domain" {
  description = "Domain name for the application"
  type        = string
  default     = "app.deepsecure.one"
}

variable "db_tier" {
  description = "Cloud SQL machine tier"
  type        = string
  default     = "db-f1-micro"
}

variable "db_password" {
  description = "Password for the Cloud SQL postgres user"
  type        = string
  sensitive   = true
}

variable "google_sso_client_id" {
  description = "Google SSO OAuth client ID (for Keycloak identity brokering)"
  type        = string
  sensitive   = true
}

variable "google_sso_client_secret" {
  description = "Google SSO OAuth client secret (for Keycloak identity brokering)"
  type        = string
  sensitive   = true
}

variable "google_hd" {
  description = "Google hosted domain restriction for SSO"
  type        = string
  default     = "deeptrail.com"
}

variable "notion_client_id" {
  description = "Notion OAuth integration client ID"
  type        = string
  sensitive   = true
}

variable "notion_client_secret" {
  description = "Notion OAuth integration client secret"
  type        = string
  sensitive   = true
}

variable "slack_client_id" {
  description = "Slack OAuth app client ID"
  type        = string
  sensitive   = true
}

variable "slack_client_secret" {
  description = "Slack OAuth app client secret"
  type        = string
  sensitive   = true
}

variable "google_oauth_client_id" {
  description = "Google OAuth client ID (for service connections)"
  type        = string
  sensitive   = true
}

variable "google_oauth_client_secret" {
  description = "Google OAuth client secret (for service connections)"
  type        = string
  sensitive   = true
}
