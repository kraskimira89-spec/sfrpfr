data "yandex_compute_image" "ubuntu" {
  family = "ubuntu-2404-lts"
}

resource "yandex_compute_disk" "boot" {
  name     = local.boot_disk_name
  type     = "network-ssd"
  zone     = var.zone
  size     = var.vm_boot_disk_size
  image_id = data.yandex_compute_image.ubuntu.id
  folder_id = var.folder_id
  labels   = local.labels
}

resource "yandex_compute_disk" "data" {
  name      = local.data_disk_name
  type      = "network-ssd"
  zone      = var.zone
  size      = var.vm_data_disk_size
  folder_id = var.folder_id
  labels    = local.labels
}

resource "yandex_compute_instance" "supabase" {
  name               = local.vm_name
  description        = "Self-hosted Supabase staging (Compose)"
  platform_id        = var.vm_platform_id
  zone               = var.zone
  folder_id          = var.folder_id
  service_account_id = yandex_iam_service_account.vm.id
  labels             = local.labels

  resources {
    cores         = var.vm_cores
    memory        = var.vm_memory
    core_fraction = var.vm_core_fraction
  }

  boot_disk {
    disk_id     = yandex_compute_disk.boot.id
    auto_delete = false
  }

  secondary_disk {
    disk_id     = yandex_compute_disk.data.id
    auto_delete = false
    device_name = local.data_device
  }

  network_interface {
    subnet_id          = yandex_vpc_subnet.staging.id
    security_group_ids = [yandex_vpc_security_group.staging.id]
    nat                = true
    nat_ip_address     = yandex_vpc_address.staging.external_ipv4_address[0].address
  }

  metadata = {
    user-data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
      ssh_username     = var.ssh_username
      ssh_public_key   = local.ssh_public_key
      data_device_name = local.data_device
      data_disk_mount  = "/data"
      supabase_dir     = "/opt/sfrfr-supabase"
    })
    serial-port-enable = "0"
  }

  scheduling_policy {
    preemptible = false
  }

  allow_stopping_for_update = true
}
