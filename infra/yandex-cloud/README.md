# SFRFR staging — Terraform (Yandex Cloud)

ТЗ: [docs/specs/16-yandex-cloud-terraform.md](../../docs/specs/16-yandex-cloud-terraform.md)  
Self-host: [docs/ops/supabase-selfhost-yandex-cloud.md](../../docs/ops/supabase-selfhost-yandex-cloud.md)  
Биллинг: [docs/ops/yandex-cloud-billing-unblock.md](../../docs/ops/yandex-cloud-billing-unblock.md)

## Архитектура

```text
Internet → :443 → Static IP → VM Ubuntu
                              ├── Caddy/Nginx
                              ├── Supabase Docker Compose
                              │     └── Postgres on /data (100 GB)
                              └── backups → private Object Storage (SSE-KMS)
```

**Не в первом apply:** Managed PG, k8s, ALB, Functions, prod DNS/cutover.

## Быстрый старт

```bash
cd infra/yandex-cloud
cp terraform.tfvars.example terraform.tfvars
# Правки: allowed_ssh_cidrs, ssh_public_key_path, backup_bucket_name

yc init   # или YC_TOKEN
terraform init
terraform fmt -check
terraform validate
terraform plan
# terraform apply   # только после явного подтверждения и проверки биллинга
```

## После apply

1. Заполнить Lockbox-версии (JWT / Postgres) через `yc` или консоль — **не** через `.tfvars`.
2. SSH: `terraform output -raw ssh_command`
3. Studio только туннелем: `terraform output -raw ssh_tunnel_studio`
4. Compose Supabase в `/opt/sfrfr-supabase` — см. ops runbook.
5. DNS `supabase.proverkastaza.ru A <ip>` — **вручную**, не автоматически.

## Destroy / rollback

```bash
terraform destroy
```

Прод-VPS `91.229.11.147` этим проектом не управляется.

## Оценка стоимости (ориентир)

| Ресурс | ~₽/мес |
|--------|--------|
| VM 4 vCPU / 8 GB | ~2500 |
| Boot 30 GB SSD | ~240 |
| Data 100 GB SSD | ~800 |
| Static IP | ~200 |
| KMS + Object Storage | по факту |
| **Итого** | **~3800+** |

Перед apply: нет баннера «Облако заблокировано».

## Безопасность

- Нет публичного `5432` / Studio
- SSH только `allowed_ssh_cidrs` (валидация запрещает `0.0.0.0/0`)
- Bucket private + versioning + lifecycle + SSE-KMS
- Секреты Supabase не в Terraform state
- Регион только `ru-central1`
