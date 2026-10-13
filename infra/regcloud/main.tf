# Резервная ВМ под Supabase (self-host).
# Цель/роль: docs/ops/tz-regru-assistant-supabase-reserve.md
# Firewall 22/80/443: провайдер Terraform Рег.облака (на 2026-10) не управляет
# UFW/SG — после apply настроить UFW на ВМ (см. README / docs/ops/regcloud-terraform.md).

# По умолчанию ключ уже в аккаунте (regru_terraform_vm). Создание нового —
# только если manage_ssh_key=true и pubkey ещё не загружен (иначе SSH_KEY_ALREADY_EXIST).
resource "regcloud_ssh_key" "owner" {
  count      = var.manage_ssh_key ? 1 : 0
  name       = var.ssh_key_name
  public_key = var.ssh_public_key
}

locals {
  ssh_key_fingerprint = var.manage_ssh_key ? regcloud_ssh_key.owner[0].fingerprint : var.ssh_key_fingerprint
}

resource "regcloud_server" "supabase" {
  name             = var.server_name
  size             = var.server_size
  image            = var.server_image
  region_slug      = var.region_slug
  ssh_keys         = [local.ssh_key_fingerprint]
  isp_license_size = null
  backups          = var.enable_backups
  floating_ip      = true # публичный IPv4 (default провайдера; фиксируем явно)
}
