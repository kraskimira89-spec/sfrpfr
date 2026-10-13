# Резервная ВМ под Supabase (self-host).
# Цель/роль: docs/ops/tz-regru-assistant-supabase-reserve.md
# Firewall 22/80/443: провайдер Terraform Рег.облака (на 2026-10) не управляет
# UFW/SG — после apply настроить UFW на ВМ (см. README / docs/ops/regcloud-terraform.md).

resource "regcloud_ssh_key" "owner" {
  name       = var.ssh_key_name
  public_key = var.ssh_public_key
}

resource "regcloud_server" "supabase" {
  name             = var.server_name
  size             = var.server_size
  image            = var.server_image
  region_slug      = var.region_slug
  ssh_keys         = [regcloud_ssh_key.owner.fingerprint]
  isp_license_size = null
  backups          = var.enable_backups
  floating_ip      = true # публичный IPv4 (default провайдера; фиксируем явно)
}
