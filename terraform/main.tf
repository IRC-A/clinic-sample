terraform {
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Enable Required GCP Services
resource "google_project_service" "cloud_run_api" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifact_registry_api" {
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

# 2. Data Source: Reference Existing Production BFA Gateway Cloud Run Service
data "google_cloud_run_v2_service" "bfa_gateway" {
  name     = "irc-a-gateway"
  location = var.region

  depends_on = [google_project_service.cloud_run_api]
}

# 3. Cloud Run Service: Fortified Healthcare Fleet (Streamlit Dual UI & Google ADK Agents)
resource "google_cloud_run_v2_service" "healthcare_app" {
  name     = "fortified-healthcare-fleet"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    timeout = "300s"

    containers {
      image = var.app_image

      resources {
        limits = {
          cpu    = "2000m"
          memory = "1024Mi"
        }
      }

      # Dynamically reference the existing production BFA Gateway URI from GCP
      env {
        name  = "BFA_GATEWAY_URL"
        value = data.google_cloud_run_v2_service.bfa_gateway.uri
      }
      env {
        name  = "BFA_API_KEY"
        value = var.bfa_api_key
      }
      env {
        name  = "GEMINI_API_KEY"
        value = var.gemini_api_key
      }
      env {
        name  = "GOOGLE_API_KEY"
        value = var.gemini_api_key
      }
      env {
        name  = "OPENAI_API_KEY"
        value = var.openai_api_key
      }

      ports {
        container_port = 8080
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }

  depends_on = [google_project_service.cloud_run_api]
}

# Allow public unauthenticated invocation on Fortified Healthcare Fleet UI
resource "google_cloud_run_v2_service_iam_member" "healthcare_app_public" {
  location = google_cloud_run_v2_service.healthcare_app.location
  name     = google_cloud_run_v2_service.healthcare_app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
