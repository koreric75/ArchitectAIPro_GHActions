# =====================================================
# Cloud Run Service - Architecture Gallery
# =====================================================
# Hosts the BlueFalconInk Architecture Gallery
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
      image = "gcr.io/${var.project_id}/architecture-gallery:latest"

      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }

      env {
        name  = "GITHUB_ORG"
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
