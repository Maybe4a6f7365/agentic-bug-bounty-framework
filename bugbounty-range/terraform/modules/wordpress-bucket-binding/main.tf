resource "google_storage_bucket_iam_member" "bootstrap_reader" {
  bucket = var.bucket_name
  role   = var.role
  member = var.member
}
