# Документация: https://reg.cloud/support/cloud/instrumenty/terraform/rabota-s-terraform/nachalo-raboty-s-terraform
# Токен: панель Рег.облака → Настройки (не коммитить).
# Альтернатива: $env:TF_VAR_token = "..."

provider "regcloud" {
  token   = var.token
  api_url = var.api_url
}
