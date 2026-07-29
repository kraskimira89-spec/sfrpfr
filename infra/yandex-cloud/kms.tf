resource "yandex_kms_symmetric_key" "staging" {
  name              = local.kms_key_name
  description       = "KMS for backup bucket SSE and Lockbox"
  folder_id         = var.folder_id
  default_algorithm = "AES_256"
  rotation_period   = "2160h" # 90 days
  labels            = local.labels
}
