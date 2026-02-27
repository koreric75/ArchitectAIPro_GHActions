# =====================================================
# Cloud Run Service - Architecture Gallery
# =====================================================
# Hosts the BlueFalconInk LLC Architecture Gallery
# at arch.bluefalconink.com
# =====================================================

resource "google_cloud_run_v2_service" "architecture_gallery" {
  name     = "architecture-gallery"
  location = var.region

  template {
    service_account = google_service_account.foreman_sa.email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/bluefalconink-apps/architecture-gallery:latest"

      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }

      env {
        name  = "GITHUB_ORG"
        value = "koreric75"
      }

      env {
        name = "GITHUB_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.github_token.secret_id
            version = "latest"
          }
        }
      }

      ports {
        container_port = 8080
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# Allow unauthenticated access (public gallery)
resource "google_cloud_run_v2_service_iam_member" "gallery_public" {
  name     = google_cloud_run_v2_service.architecture_gallery.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Custom domain mapping
resource "google_cloud_run_domain_mapping" "gallery_domain" {
  name     = "arch.bluefalconink.com"
  location = var.region

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.architecture_gallery.name
  }
}

# -------------------------------------------
# Outputs
# -------------------------------------------

output "gallery_url" {
  description = "Architecture Gallery URL"
  value       = google_cloud_run_v2_service.architecture_gallery.uri
}

# =====================================================
# Cloud Run Service - CHAD Dashboard
# =====================================================
# Centralized Hub for Architectural Decision-making
# Serves audit dashboard + deploy-workflow API
# Scale-to-zero: $0 when idle
# =====================================================

resource "google_cloud_run_v2_service" "chad_dashboard" {
  name     = "chad-dashboard"
  location = var.region

  template {
    service_account = google_service_account.foreman_sa.email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/bluefalconink-apps/chad-dashboard:latest"

      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      env {
        name  = "GITHUB_OWNER"
        value = var.github_org
      }

      env {
        name = "GITHUB_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.github_token.secret_id
            version = "latest"
          }
        }
      }

      ports {
        container_port = 8080
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# Allow unauthenticated access (public dashboard)
resource "google_cloud_run_v2_service_iam_member" "chad_public" {
  name     = google_cloud_run_v2_service.chad_dashboard.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "chad_dashboard_url" {
  description = "CHAD Dashboard URL"
  value       = google_cloud_run_v2_service.chad_dashboard.uri
}
