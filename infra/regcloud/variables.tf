variable "token" {
  type        = string
  description = "API-токен Рег.облака (панель → Настройки). Или TF_VAR_token."
  sensitive   = true
}

variable "api_url" {
  type        = string
  description = "Точка входа API Рег.облака"
  default     = "https://api.cloudvps.reg.ru"
}

variable "server_name" {
  type        = string
  description = "Имя облачного сервера"
  default     = "sfrfr-supabase-db-regru"
}

variable "server_size" {
  type        = string
  description = <<-EOT
    Тариф size (формат c{CPU}-m{RAM}-d{DISK}-{line}).
    Цель: ≥2vCPU/4GB/40GB, предпочтительно 4/8/40.
    Пример из доки: c1-m1-d10-hp. Значение c4-m8-d40-hp нужно
    сверить в панели заказа сервера — не все size доступны в регионе.
  EOT
  default     = "c4-m8-d40-hp"
}

variable "server_image" {
  type        = string
  description = "Образ ОС (Ubuntu 22.04/24.04). Сверить в панели."
  default     = "ubuntu-24-04-amd64-docker"
}

variable "region_slug" {
  type        = string
  description = "Регион РФ. Пример из доки: openstack-msk1 (Москва-1)."
  default     = "openstack-msk1"
}

variable "ssh_key_name" {
  type        = string
  description = "Имя SSH-ключа в Рег.облаке"
  default     = "sfrfr-owner-ed25519"
}

variable "ssh_public_key" {
  type        = string
  description = "Публичный SSH-ключ владельца (ed25519)"
  default     = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILMuJ08egqt1pIwlLDJH0XbSTyvZjnKU97GEne15UaTm user.kraskimira89@gmail.com"
}

variable "enable_backups" {
  type        = bool
  description = "Автобэкапы Рег.облака (платно). По умолчанию выкл."
  default     = false
}
