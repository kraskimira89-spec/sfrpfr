locals {
  vpc_name       = "${var.project_name}-${var.environment}"
  subnet_name    = "${var.project_name}-${var.environment}-subnet"
  sg_name        = "${var.project_name}-${var.environment}-sg"
  vm_name        = "${var.project_name}-${var.environment}-supabase"
  boot_disk_name = "${var.project_name}-${var.environment}-boot"
  data_disk_name = "${var.project_name}-${var.environment}-data"
  static_ip_name = "${var.project_name}-${var.environment}-ip"
  kms_key_name   = "${var.project_name}-${var.environment}-kms"
  sa_vm_name     = "${var.project_name}-${var.environment}-vm-sa"
  sa_backup_name = "${var.project_name}-${var.environment}-backup-writer"
  data_device    = "sfrfr-data"

  labels = merge(var.labels, {
    environment = var.environment
  })

  ssh_public_key = file(var.ssh_public_key_path)
}
