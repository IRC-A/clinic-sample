variable "project_id" {
  type        = string
  description = "Google Cloud Platform (GCP) Project ID"
}

variable "region" {
  type        = string
  description = "GCP Region for Cloud Run deployment"
  default     = "us-central1"
}

variable "bfa_gateway_image" {
  type        = string
  description = "Container image URI for the BFA Gateway Cloud Run service"
  default     = "gcr.io/google-samples/hello-app:1.0"
}

variable "app_image" {
  type        = string
  description = "Container image URI for the Fortified Healthcare Fleet Streamlit App"
}

variable "gemini_api_key" {
  type        = string
  description = "Google Gemini API Key for Google ADK agents"
  sensitive   = true
}

variable "bfa_api_key" {
  type        = string
  description = "API Key for BFA Gateway authentication"
  default     = "bfa_gcp_hackathon_demo_key_2026"
  sensitive   = true
}
