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
    Актуальные slug из GET /v1/sizes (2026-10): base-8 = 8vCPU/8GB/120GB.
    Старый формат cN-mN-dN-hp в API больше не принимается.
  EOT
  default     = "base-8"
}

variable "server_image" {
  type        = string
  description = "Образ ОС. В API (2026-10) нет *-docker; ставим Ubuntu LTS и Docker после apply."
  default     = "ubuntu-22-04-amd64"
}

variable "region_slug" {
  type        = string
  description = "Регион РФ. В /v1/sizes: msk1 (не openstack-msk1)."
  default     = "msk1"
}

variable "manage_ssh_key" {
  type        = bool
  description = "true = создать regcloud_ssh_key; false = использовать ssh_key_fingerprint (ключ уже в панели)"
  default     = false
}

variable "ssh_key_name" {
  type        = string
  description = "Имя нового SSH-ключа (без дефисов). Только при manage_ssh_key=true"
  default     = "regru_terraform_vm"
}

variable "ssh_public_key" {
  type        = string
  description = "Публичный SSH-ключ владельца (ed25519). Только при manage_ssh_key=true"
  default     = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILMuJ08egqt1pIwlLDJH0XbSTyvZjnKU97GEne15UaTm userznaskimira89@gmail.com"
}

variable "ssh_key_fingerprint" {
  type        = string
  description = "Fingerprint уже загруженного ключа (MD5). По умолчанию regru_terraform_vm"
  default     = "31:da:b1:9e:bf:9b:ec:79:6e:07:12:7f:fe:4b:8c:7d"
}

variable "enable_backups" {
  type        = bool
  description = "Автобэкапы Рег.облака (платно). По умолчанию выкл."
  default     = false
}
