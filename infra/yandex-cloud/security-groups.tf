resource "yandex_vpc_security_group" "staging" {
  name        = local.sg_name
  description = "SG ${var.project_name} ${var.environment}: 443/80 public, SSH/PG allowlist, no Studio"
  folder_id   = var.folder_id
  network_id  = yandex_vpc_network.staging.id
  labels      = local.labels

  ingress {
    description    = "HTTPS"
    protocol       = "TCP"
    port           = 443
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description    = "HTTP redirect/ACME"
    protocol       = "TCP"
    port           = 80
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description    = "SSH allowlist only"
    protocol       = "TCP"
    port           = 22
    v4_cidr_blocks = var.allowed_ssh_cidrs
  }

  dynamic "ingress" {
    for_each = length(var.allowed_postgres_cidrs) > 0 ? [1] : []
    content {
      description    = "Postgres allowlist (dbt / DATABASE_URL) — never 0.0.0.0/0"
      protocol       = "TCP"
      port           = 5432
      v4_cidr_blocks = var.allowed_postgres_cidrs
    }
  }

  dynamic "ingress" {
    for_each = length(var.allowed_postgres_cidrs) > 0 ? [1] : []
    content {
      description    = "Direct Postgres 5433 (bypass Supavisor) — never 0.0.0.0/0"
      protocol       = "TCP"
      port           = 5433
      v4_cidr_blocks = var.allowed_postgres_cidrs
    }
  }

  ingress {
    description       = "Intra-SG"
    protocol          = "ANY"
    from_port         = 0
    to_port           = 65535
    predefined_target = "self_security_group"
  }

  # Staging: полный egress (явно). Ужесточить после стабилизации.
  egress {
    description    = "Staging full egress"
    protocol       = "ANY"
    from_port      = 0
    to_port        = 65535
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}
