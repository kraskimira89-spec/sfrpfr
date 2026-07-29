output "vm_public_ip" {
  description = "Public IPv4 of staging VM"
  value       = yandex_vpc_address.staging.external_ipv4_address[0].address
}

output "vm_name" {
  value = yandex_compute_instance.supabase.name
}

output "vm_id" {
  value = yandex_compute_instance.supabase.id
}

output "network_id" {
  value = yandex_vpc_network.staging.id
}

output "subnet_id" {
  value = yandex_vpc_subnet.staging.id
}

output "security_group_id" {
  value = yandex_vpc_security_group.staging.id
}

output "backup_bucket_name" {
  value = yandex_storage_bucket.backup.bucket
}

output "kms_key_id" {
  value = yandex_kms_symmetric_key.staging.id
}

output "sa_vm_id" {
  value = yandex_iam_service_account.vm.id
}

output "sa_backup_writer_id" {
  value = yandex_iam_service_account.backup_writer.id
}

output "lockbox_supabase_secret_id" {
  value = yandex_lockbox_secret.supabase.id
}

output "lockbox_database_secret_id" {
  value = yandex_lockbox_secret.database.id
}

output "dns_recommendation" {
  description = "Do NOT apply DNS automatically"
  value       = "supabase.proverkastaza.ru A ${yandex_vpc_address.staging.external_ipv4_address[0].address}"
}

output "ssh_command" {
  value = "ssh ${var.ssh_username}@${yandex_vpc_address.staging.external_ipv4_address[0].address}"
}

output "ssh_tunnel_studio" {
  description = "Studio only via tunnel; never open publicly"
  value       = "ssh -L 8000:localhost:8000 ${var.ssh_username}@${yandex_vpc_address.staging.external_ipv4_address[0].address}"
}
