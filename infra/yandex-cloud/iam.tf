resource "yandex_iam_service_account" "vm" {
  name        = local.sa_vm_name
  description = "VM SA: Lockbox payload + KMS decrypt"
  folder_id   = var.folder_id
}

resource "yandex_lockbox_secret_iam_member" "vm_supabase" {
  secret_id = yandex_lockbox_secret.supabase.id
  role      = "lockbox.payloadViewer"
  member    = "serviceAccount:${yandex_iam_service_account.vm.id}"
}

resource "yandex_lockbox_secret_iam_member" "vm_database" {
  secret_id = yandex_lockbox_secret.database.id
  role      = "lockbox.payloadViewer"
  member    = "serviceAccount:${yandex_iam_service_account.vm.id}"
}

resource "yandex_kms_symmetric_key_iam_member" "vm" {
  symmetric_key_id = yandex_kms_symmetric_key.staging.id
  role             = "kms.keys.decrypter"
  member           = "serviceAccount:${yandex_iam_service_account.vm.id}"
}

resource "yandex_iam_service_account" "backup_writer" {
  name        = local.sa_backup_name
  description = "Backup writer for private Object Storage"
  folder_id   = var.folder_id
}

# Права на бакет через Storage Object User на уровне folder — узже storage.editor.
# Доступ ограничен использованием только backup_bucket_name в job'ах.
resource "yandex_resourcemanager_folder_iam_member" "backup_storage" {
  folder_id = var.folder_id
  role      = "storage.uploader"
  member    = "serviceAccount:${yandex_iam_service_account.backup_writer.id}"
}

resource "yandex_kms_symmetric_key_iam_member" "backup_writer" {
  symmetric_key_id = yandex_kms_symmetric_key.staging.id
  role             = "kms.keys.encrypterDecrypter"
  member           = "serviceAccount:${yandex_iam_service_account.backup_writer.id}"
}
