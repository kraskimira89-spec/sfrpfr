resource "yandex_vpc_network" "staging" {
  name        = local.vpc_name
  description = "VPC ${var.project_name} ${var.environment}"
  folder_id   = var.folder_id
  labels      = local.labels
}

resource "yandex_vpc_subnet" "staging" {
  name           = local.subnet_name
  description    = "Subnet ${var.project_name} ${var.environment}"
  folder_id      = var.folder_id
  v4_cidr_blocks = [var.network_cidr]
  zone           = var.zone
  network_id     = yandex_vpc_network.staging.id
  labels         = local.labels
}

resource "yandex_vpc_address" "staging" {
  name        = local.static_ip_name
  description = "Static public IP for Supabase staging VM"
  folder_id   = var.folder_id
  labels      = local.labels

  external_ipv4_address {
    zone_id = var.zone
  }
}
