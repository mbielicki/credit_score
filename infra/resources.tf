# Artifact Registry with Cleanup Policy for $0 Budget
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "credit-score-repo"
  description   = "Docker repository for Credit Score Engine"
  format        = "DOCKER"
  depends_on    = [google_project_service.services]

  # Keep only the last 2 versions of each image to stay under 0.5GB
  cleanup_policies {
    id     = "keep-recent-versions"
    action = "KEEP"
    most_recent_versions {
      keep_count = 2
    }
  }

  cleanup_policies {
    id     = "delete-old-versions"
    action = "DELETE"
    condition {
      older_than = "604800s" # 7 days
    }
  }
}

# CD Service Account
resource "google_service_account" "github_actions" {
  account_id   = "github-actions-cd"
  display_name = "GitHub Actions CD Account"
}

# IAM Permissions for GitHub Actions
resource "google_project_iam_member" "github_actions_roles" {
  for_each = toset([
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/iam.serviceAccountUser",
    "roles/secretmanager.secretAccessor"
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

# Secret Manager (0 to 6 are free)
resource "google_secret_manager_secret" "database_url" {
  secret_id = "DATABASE_URL"
  replication {
    auto {}
  }
}

output "registry_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
}

output "github_sa_email" {
  value = google_service_account.github_actions.email
}
