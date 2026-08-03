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

Подробно: [docs/ops/yandex-cloud-terraform-plan.md](../../docs/ops/yandex-cloud-terraform-plan.md)

```powershell
# из корня репо (Windows)
.\scripts\yc_cloud_auth.ps1          # Cloud OAuth (не Workspace!)
.\scripts\tofu_plan_staging.ps1      # plan без apply
```

```bash
cd infra/yandex-cloud
cp terraform.tfvars.example terraform.tfvars
# Правки: allowed_ssh_cidrs, ssh_public_key_path, backup_bucket_name

yc init   # или YC_TOKEN / service_account_key_file
terraform init   # или tofu init (OpenTofu), если HashiCorp releases недоступны
terraform fmt -check
terraform validate
terraform plan
# terraform apply   # только после явного подтверждения и проверки биллинга
```

`YANDEX_OAUTH_*` (Workspace), `YANDEX_API_KEY` (AI Studio) и новые OAuth `y0_…` **не** подходят для Terraform (с 2026-06-01 OAuth→IAM отключён). Нужен JSON **authorized key** SA → `secrets/yc-sa-terraform.json`.

### РФ / блокировка HashiCorp registry

Если `terraform`/`tofu init` даёт 403 к registry:

1. Скачать [OpenTofu](https://github.com/opentofu/opentofu/releases) windows_amd64.
2. Скачать [terraform-provider-yandex](https://github.com/yandex-cloud/terraform-provider-yandex/releases) `*_windows_amd64.zip`.
3. Распаковать provider в  
   `tools/tf-providers/registry.opentofu.org/yandex-cloud/yandex/<ver>/windows_amd64/`.
4. `tofu.rc` с `filesystem_mirror` на `tools/tf-providers` (см. `%APPDATA%\tofu\tofu.rc`).
5. `tofu init -backend=false && tofu validate`.

`plan`/`apply` без `yc` или `YC_TOKEN` не заработают.

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

- `5432` только из `allowed_postgres_cidrs` (VPS/admin `/32`), иначе закрыт; Studio наружу нет
- SSH только `allowed_ssh_cidrs` (валидация запрещает `0.0.0.0/0`)
- Bucket private + versioning + lifecycle + SSE-KMS
- Секреты Supabase не в Terraform state
- Регион только `ru-central1`
