# ==============================================================================
# Altostrat HR Policy Agent — Production Terraform Blueprint (SDD Sec. 2 & Sec. 5)
# Provisions Cloud Run, Dual-Region Firestore, Secret Manager, GCS, and IAM.
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
  default     = "project-elevate-504405"
}

variable "region" {
  description = "Primary Deployment Region"
  type        = string
  default     = "us-central1"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ------------------------------------------------------------------------------
# 1. Cloud Storage Policy Documents Bucket
# ------------------------------------------------------------------------------
resource "google_storage_bucket" "policy_docs" {
  name                        = "${var.project_id}-hr-policies"
  location                    = var.region
  uniform_bucket_level_access = true
  versioning {
    enabled = true
  }
}

# ------------------------------------------------------------------------------
# 2. Secret Manager for Corporate OAuth & API Keys
# ------------------------------------------------------------------------------
resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "gemini-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "ite_signing_key" {
  secret_id = "ite-rsa-signing-key"
  replication {
    auto {}
  }
}

# ------------------------------------------------------------------------------
# 3. Dual-Region Firestore Database (Session State)
# ------------------------------------------------------------------------------
resource "google_firestore_database" "session_db" {
  name        = "(default)"
  location_id = "nam5" # Dual-region US (Iowa/South Carolina) RPO < 1s
  type        = "FIRESTORE_NATIVE"
}

# ------------------------------------------------------------------------------
# 4. Service Account & IAM
# ------------------------------------------------------------------------------
resource "google_service_account" "agent_sa" {
  account_id   = "hr-agent-sa"
  display_name = "Elevate HR Policy Agent Service Account"
}

resource "google_project_iam_member" "aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "discoveryengine_editor" {
  project = var.project_id
  role    = "roles/discoveryengine.editor"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "dlp_user" {
  project = var.project_id
  role    = "roles/dlp.user"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "datastore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

# ------------------------------------------------------------------------------
# 5. Cloud Run Application Service
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "agent_service" {
  name     = "elevate-hr-agent"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.agent_sa.email
    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/hr-agent-repo/elevate-hr-agent:latest"
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = "global"
      }
      env {
        name  = "RETRIEVAL_MODE"
        value = "okf"
      }
    }
  }
}

output "cloud_run_url" {
  value       = google_cloud_run_v2_service.agent_service.uri
  description = "The live HTTPS URL of the deployed Cloud Run service"
}
