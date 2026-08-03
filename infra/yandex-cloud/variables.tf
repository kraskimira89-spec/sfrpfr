variable "cloud_id" {
  description = "ID облака Yandex Cloud (sfrfr-ai)"
  type        = string
}

variable "folder_id" {
  description = "ID каталога default"
  type        = string
}

variable "zone" {
  description = "Зона доступности"
  type        = string
  default     = "ru-central1-a"
}

variable "environment" {
  description = "Окружение"
  type        = string
  default     = "staging"
}

variable "project_name" {
  description = "Кодовое имя проекта"
  type        = string
  default     = "sfrfr"
}

variable "network_cidr" {
  description = "CIDR подсети staging"
  type        = string
  default     = "10.10.10.0/24"
}

variable "allowed_ssh_cidrs" {
  description = "CIDR для SSH. Нельзя 0.0.0.0/0. Обязательно задать в terraform.tfvars."
  type        = list(string)

  validation {
    condition     = length(var.allowed_ssh_cidrs) > 0
    error_message = "Укажите allowed_ssh_cidrs, например [\"x.x.x.x/32\"]."
  }

  validation {
    condition = alltrue([
      for c in var.allowed_ssh_cidrs : c != "0.0.0.0/0" && c != "::/0"
    ])
    error_message = "SSH с 0.0.0.0/0 и ::/0 запрещён."
  }
}

variable "allowed_postgres_cidrs" {
  description = "CIDR для Postgres 5432 (dbt/DATABASE_URL). Пусто = порт закрыт. Нельзя 0.0.0.0/0."
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for c in var.allowed_postgres_cidrs : c != "0.0.0.0/0" && c != "::/0"
    ])
    error_message = "Postgres с 0.0.0.0/0 и ::/0 запрещён — только VPS/admin /32."
  }
}

variable "ssh_username" {
  description = "Непривилегированный пользователь SSH"
  type        = string
  default     = "sfrfr"
}

variable "ssh_public_key_path" {
  description = "Путь к публичному SSH-ключу"
  type        = string
}

variable "vm_platform_id" {
  type    = string
  default = "standard-v3"
}

variable "vm_cores" {
  type    = number
  default = 4
}

variable "vm_memory" {
  description = "RAM в GB"
  type        = number
  default     = 8
}

variable "vm_core_fraction" {
  type    = number
  default = 100
}

variable "vm_boot_disk_size" {
  type    = number
  default = 30
}

variable "vm_data_disk_size" {
  type    = number
  default = 100
}

variable "backup_bucket_name" {
  description = "Глобально уникальное имя private backup-бакета"
  type        = string
}

variable "backup_retention_days" {
  type    = number
  default = 90
}

variable "labels" {
  type = map(string)
  default = {
    project     = "sfrfr"
    environment = "staging"
    managed_by  = "terraform"
  }
}
