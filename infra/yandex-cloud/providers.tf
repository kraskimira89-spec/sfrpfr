provider "yandex" {
  # JSON authorized key SA (gitignore: secrets/).
  # Путь от infra/yandex-cloud → ../../secrets/...
  # Альтернатива: YC_TOKEN=$(yc iam create-token) без этого файла.
  service_account_key_file = abspath("${path.root}/../../secrets/yc-sa-terraform.json")

  cloud_id  = var.cloud_id
  folder_id = var.folder_id
  zone      = var.zone
}
