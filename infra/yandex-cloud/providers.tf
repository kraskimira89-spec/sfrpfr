provider "yandex" {
  # Аутентификация (не коммитить токены):
  #   A) yc CLI: yc init / yc config list — провайдер подхватит профиль
  #   B) export YC_TOKEN=$(yc iam create-token)
  #   C) service_account_key_file = "/path/outside/git/sa-key.json"
  #
  # Не задавайте token= в .tf / .tfvars.

  cloud_id  = var.cloud_id
  folder_id = var.folder_id
  zone      = var.zone
}
