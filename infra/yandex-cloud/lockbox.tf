# Пустые контейнеры Lockbox. Значения — только вручную после apply (не в state).

resource "yandex_lockbox_secret" "supabase" {
  name                = "${var.project_name}-${var.environment}-supabase"
  description         = "JWT_SECRET, ANON_KEY, SERVICE_ROLE_KEY (fill after apply)"
  folder_id           = var.folder_id
  kms_key_id          = yandex_kms_symmetric_key.staging.id
  deletion_protection = true
  labels              = local.labels
}

resource "yandex_lockbox_secret" "database" {
  name                = "${var.project_name}-${var.environment}-database"
  description         = "POSTGRES_PASSWORD / DATABASE_URL (fill after apply)"
  folder_id           = var.folder_id
  kms_key_id          = yandex_kms_symmetric_key.staging.id
  deletion_protection = true
  labels              = local.labels
}
