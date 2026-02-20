# =====================================================
# Workload Identity Federation (WIF)
# =====================================================
# Enables keyless, zero-trust authentication between
# GitHub Actions and Google Cloud Platform.
# No static JSON keys required.
# =====================================================

# -------------------------------------------
# 1. Workload Identity Pool
# -------------------------------------------

resource "google_iam_workload_identity_pool" "github_pool" {
  workload_identity_pool_id = "bluefalcon-github-pool"
  display_name              = "BlueFalconInk GitHub Pool"
  description               = "WIF pool for GitHub Actions OIDC authentication"
}

# -------------------------------------------
# 2. OIDC Provider for GitHub
# -------------------------------------------

resource "google_iam_workload_identity_pool_provider" "github_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub Actions Provider"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }

  attribute_condition = "assertion.repository_owner == '${var.github_org}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# -------------------------------------------
# 3. Allow GitHub to impersonate the Foreman SA
# -------------------------------------------

resource "google_service_account_iam_member" "wif_impersonation" {
  service_account_id = google_service_account.foreman_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository_owner/${var.github_org}"
}

# -------------------------------------------
# Per-repository bindings (optional - more restrictive)
# -------------------------------------------

resource "google_service_account_iam_member" "wif_architect_ai" {
  service_account_id = google_service_account.foreman_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${var.github_org}/architect-ai-pro"
}

# -------------------------------------------
# Outputs
# -------------------------------------------

output "wif_provider_name" {
  description = "Full WIF provider resource name (use in GitHub Actions)"
  value       = google_iam_workload_identity_pool_provider.github_provider.name
}

output "wif_pool_name" {
  description = "Workload Identity Pool name"
  value       = google_iam_workload_identity_pool.github_pool.name
}
