output "bfa_gateway_url" {
  value       = google_cloud_run_v2_service.bfa_gateway.uri
  description = "Public URL of the deployed GCP BFA Gateway Cloud Run service"
}

output "healthcare_app_url" {
  value       = google_cloud_run_v2_service.healthcare_app.uri
  description = "Public URL of the Fortified Healthcare Fleet Streamlit Web Application"
}
