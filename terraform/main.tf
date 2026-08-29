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

# 2. Cloud Run Service: BFA Gateway (Backend for Agents / IRC-A Gateway)
resource "google_cloud_run_v2_service" "bfa_gateway" {
  name     = "irc-a-gateway"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = var.bfa_gateway_image

      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }

      env {
        name  = "BFA_GATEWAY_HOST"
        value = "0.0.0.0"
      }
      env {
        name  = "BFA_GATEWAY_PORT"
        value = "8000"
      }
      env {
        name  = "BFA_API_KEY"
        value = var.bfa_api_key
      }
      env {
        name  = "GOOGLE_API_KEY"
        value = var.gemini_api_key
      }

      ports {
        container_port = 8000
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }

  depends_on = [google_project_service.cloud_run_api]
}

# Allow public unauthenticated invocation on BFA Gateway
resource "google_cloud_run_v2_service_iam_member" "bfa_gateway_public" {
  location = google_cloud_run_v2_service.bfa_gateway.location
  name     = google_cloud_run_v2_service.bfa_gateway.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# 3. Cloud Run Service: Fortified Healthcare Fleet (Streamlit Dual UI & Google ADK Agents)
resource "google_cloud_run_v2_service" "healthcare_app" {
  name     = "fortified-healthcare-fleet"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = var.app_image

      resources {
        limits = {
          cpu    = "2000m"
          memory = "1024Mi"
        }
      }

      # Dynamically pass the deployed BFA Gateway URL
      env {
        name  = "BFA_GATEWAY_URL"
        value = google_cloud_run_v2_service.bfa_gateway.uri
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

      ports {
        container_port = 8080
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }

  depends_on = [google_cloud_run_v2_service.bfa_gateway]
}

# Allow public unauthenticated invocation on Fortified Healthcare Fleet UI
resource "google_cloud_run_v2_service_iam_member" "healthcare_app_public" {
  location = google_cloud_run_v2_service.healthcare_app.location
  name     = google_cloud_run_v2_service.healthcare_app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
