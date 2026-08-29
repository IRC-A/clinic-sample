#!/usr/bin/env bash
# Automated Google Cloud Run Deployment Script using gcloud & Terraform
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "================================================================================"
echo "🚀 THE FORTIFIED HEALTHCARE FLEET — GOOGLE CLOUD TERRAFORM DEPLOYMENT"
echo "================================================================================"

# Check for gcloud and terraform
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: 'gcloud' CLI is not installed or not in PATH."
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    echo "❌ Error: 'terraform' CLI is not installed or not in PATH."
    exit 1
fi

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    read -p "Enter your GCP Project ID: " PROJECT_ID
fi

REGION="us-central1"
APP_IMAGE="gcr.io/${PROJECT_ID}/fortified-healthcare-fleet:latest"

echo "📌 Target GCP Project ID: ${PROJECT_ID}"
echo "📌 Target GCP Region: ${REGION}"
echo "📌 Building App Container Image: ${APP_IMAGE}"
echo "--------------------------------------------------------------------------------"

# 1. Build and push Docker container image using Cloud Build
gcloud builds submit --tag "${APP_IMAGE}" -f Dockerfile.app .

# 2. Prepare Terraform execution
cd terraform

if [ ! -f "terraform.tfvars" ]; then
    echo "Creating terraform.tfvars from example..."
    cp terraform.tfvars.example terraform.tfvars
    sed -i '' "s/your-gcp-project-id/${PROJECT_ID}/g" terraform.tfvars 2>/dev/null || sed -i "s/your-gcp-project-id/${PROJECT_ID}/g" terraform.tfvars
    sed -i '' "s|gcr.io/your-gcp-project-id/fortified-healthcare-fleet:latest|${APP_IMAGE}|g" terraform.tfvars 2>/dev/null || sed -i "s|gcr.io/your-gcp-project-id/fortified-healthcare-fleet:latest|${APP_IMAGE}|g" terraform.tfvars
fi

echo "--------------------------------------------------------------------------------"
echo "🛠️ Initializing Terraform..."
terraform init

echo "--------------------------------------------------------------------------------"
echo "🚀 Applying Terraform Infrastructure Plan to GCP Cloud Run..."
terraform apply -auto-approve

echo "--------------------------------------------------------------------------------"
echo "🎉 DEPLOYMENT TO GOOGLE CLOUD PLATFORM COMPLETED!"
terraform output
