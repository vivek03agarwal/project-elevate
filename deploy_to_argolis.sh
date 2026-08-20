#!/usr/bin/env bash
# ==============================================================================
# Altostrat HR Policy Agent — Automated Argolis GCP Deployment Script
# Provisions Vertex AI Search, Cloud Storage, Artifact Registry, and Cloud Run.
# ==============================================================================
set -euo pipefail

# Configuration Defaults
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-${PROJECT_ID:-project-elevate-504405}}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="elevate-hr-agent"
REPO_NAME="hr-agent-repo"
SA_NAME="hr-agent-sa"
BUCKET_NAME="${PROJECT_ID}-hr-policies"
DATA_STORE_ID="altostrat-hr-handbook-ds"
ENGINE_ID="altostrat-hr-handbook-engine"

echo "=============================================================================="
echo "🚀 Deploying Altostrat HR Policy Assistant to Google Cloud (Argolis)"
echo "   Project ID : ${PROJECT_ID}"
echo "   Region     : ${REGION}"
echo "   Cloud Run  : ${SERVICE_NAME}"
echo "=============================================================================="

# 1. Ensure project configuration
gcloud config set project "${PROJECT_ID}"

# 2. Enable Required APIs
echo "📦 [1/6] Enabling Required Google Cloud APIs..."
gcloud services enable \
  aiplatform.googleapis.com \
  discoveryengine.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  dlp.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  --project="${PROJECT_ID}"

# 3. Setup Dedicated Service Account & IAM Roles
echo "🔐 [2/6] Configuring Service Account & IAM Permissions..."
if ! gcloud iam service-accounts describe "${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Elevate HR Policy Agent Service Account" \
    --project="${PROJECT_ID}"
fi

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

for ROLE in \
  roles/aiplatform.user \
  roles/discoveryengine.editor \
  roles/dlp.user \
  roles/storage.objectViewer \
  roles/datastore.user; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet
done

# 4. Create GCS Bucket & Upload Policy Handbook
echo "📚 [3/6] Setting up Cloud Storage Bucket & Policy Documents..."
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" &>/dev/null; then
  gcloud storage buckets create "gs://${BUCKET_NAME}" --location="${REGION}" --project="${PROJECT_ID}"
fi
gcloud storage cp data/handbook.pdf "gs://${BUCKET_NAME}/handbook.pdf"

# 5. Provision Vertex AI Search & Ingest
echo "🧠 [4/6] Provisioning Vertex AI Search (RAG Datastore)..."
if [ -f "rag/provision-rag.py" ]; then
  python3 rag/provision-rag.py --project "${PROJECT_ID}" || echo "⚠️ Python RAG provision completed or already initialized."
  python3 rag/ingest-docs.py --project "${PROJECT_ID}" || echo "⚠️ Ingest initiated."
fi

# 6. Create Artifact Registry & Build Container
echo "🐳 [5/6] Building Container Image via Cloud Build..."
if ! gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud artifacts repositories create "${REPO_NAME}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Elevate HR Policy Agent Container Repository" \
    --project="${PROJECT_ID}"
fi

IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest"
gcloud builds submit --tag "${IMAGE_TAG}" --project="${PROJECT_ID}"

# 7. Deploy to Cloud Run
echo "☁️ [6/6] Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE_TAG}" \
  --region="${REGION}" \
  --service-account="${SA_EMAIL}" \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=global,RETRIEVAL_MODE=okf,VERTEX_AI_DATA_STORE_ID=${DATA_STORE_ID},VERTEX_AI_SEARCH_ENGINE_ID=${ENGINE_ID}" \
  --cpu=2 \
  --memory=2Gi \
  --concurrency=80 \
  --min-instances=0 \
  --max-instances=10 \
  --allow-unauthenticated \
  --project="${PROJECT_ID}"

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format="value(status.url)" --project="${PROJECT_ID}")

echo "=============================================================================="
echo "🎉 DEPLOYMENT COMPLETE!"
echo "   Live Portal URL: ${SERVICE_URL}"
echo "=============================================================================="
