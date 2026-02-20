# =====================================================
# BlueFalconInk LLC Infrastructure - Core Configuration
# =====================================================
# Provisions service accounts, secrets, and IAM roles
# for the Architect AI Pro automation pipeline.
# =====================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "bluefalconink-terraform-state"
    prefix = "architect-ai-pro"
  }
}

# -------------------------------------------
# Variables
# -------------------------------------------

variable "project_id" {
  description = "The GCP project ID"
  type        = string
  default     = "bluefalconink-prod"
}

variable "region" {
  description = "The GCP region"
  type        = string
  default     = "us-central1"
}

variable "github_org" {
  description = "The GitHub organization name"
  type        = string
  default     = "bluefalconink"
}

# -------------------------------------------
# Provider Configuration
# -------------------------------------------

provider "google" {
  project = var.project_id
  region  = var.region
}

# -------------------------------------------
# 1. Foreman Service Account
# -------------------------------------------

resource "google_service_account" "foreman_sa" {
  account_id   = "architect-ai-foreman"
  display_name = "Architect AI Foreman Service Account"
  description  = "Service account for Architect AI Pro automation pipeline"
}

# -------------------------------------------
# 2. Cloud Run Admin Permissions
# -------------------------------------------

resource "google_project_iam_member" "cloud_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.foreman_sa.email}"
}

resource "google_project_iam_member" "cloud_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.foreman_sa.email}"
}

resource "google_project_iam_member" "artifact_registry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.foreman_sa.email}"
}

# -------------------------------------------
# 3. Secret Manager - API Keys
# -------------------------------------------

resource "google_secret_manager_secret" "github_token" {
  secret_id = "GITHUB_PAT"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "arch_ai_key" {
  secret_id = "ARCHITECT_AI_API_KEY"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "stripe_secret" {
  secret_id = "STRIPE_SECRET_KEY"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "stripe_webhook_secret" {
  secret_id = "STRIPE_WEBHOOK_SECRET"

  replication {
    auto {}
  }
}

# Grant Foreman SA access to secrets
resource "google_secret_manager_secret_iam_member" "foreman_github_token" {
  secret_id = google_secret_manager_secret.github_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.foreman_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "foreman_arch_ai_key" {
  secret_id = google_secret_manager_secret.arch_ai_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.foreman_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "foreman_stripe_key" {
  secret_id = google_secret_manager_secret.stripe_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.foreman_sa.email}"
}

# -------------------------------------------
# Outputs
# -------------------------------------------

output "foreman_sa_email" {
  description = "Email of the Foreman service account"
  value       = google_service_account.foreman_sa.email
}

output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}
