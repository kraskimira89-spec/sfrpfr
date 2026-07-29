resource "yandex_storage_bucket" "backup" {
  bucket    = var.backup_bucket_name
  folder_id = var.folder_id
  max_size  = 107374182400 # 100 GiB soft cap

  anonymous_access_flags {
    read        = false
    list        = false
    config_read = false
  }

  versioning {
    enabled = true
  }

  lifecycle_rule {
    id      = "backup-retention"
    enabled = true

    expiration {
      days = var.backup_retention_days
    }

    noncurrent_version_expiration {
      days = var.backup_retention_days
    }
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = yandex_kms_symmetric_key.staging.id
        sse_algorithm     = "aws:kms"
      }
    }
  }

  # Website hosting не включаем (private backups only).
}
