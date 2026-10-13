output "ssh_key_fingerprint" {
  description = "Fingerprint загруженного SSH-ключа"
  value       = regcloud_ssh_key.owner.fingerprint
}

output "server_id" {
  description = "ID сервера в Рег.облаке"
  value       = regcloud_server.supabase.server_id
}

output "server_name" {
  description = "Имя сервера"
  value       = regcloud_server.supabase.name
}

output "server_size" {
  description = "Тариф size"
  value       = regcloud_server.supabase.size
}

output "public_ip" {
  description = "Публичный IPv4 сервера (атрибут ip_address провайдера regcloud)"
  value       = regcloud_server.supabase.ip_address
}

output "created_at" {
  description = "Время создания сервера"
  value       = regcloud_server.supabase.created_at
}
