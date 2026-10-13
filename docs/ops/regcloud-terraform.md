# Рег.облако (reg.cloud) + Terraform / OpenTofu

Дата: 2026-10-13

## Цель

Воспроизводимое описание резервной ВМ `sfrfr-supabase-db-regru` для self-hosted Supabase.
Код: `infra/regcloud/`. ТЗ по стеку: [tz-regru-assistant-supabase-reserve.md](tz-regru-assistant-supabase-reserve.md).

## Официальная документация

- [Начало работы с Terraform](https://reg.cloud/support/cloud/instrumenty/terraform/rabota-s-terraform/nachalo-raboty-s-terraform)
- Панель: [cloud.reg.ru/panel](https://cloud.reg.ru/panel/)

## Провайдер (канон из доки)

```hcl
terraform {
  required_providers {
    regcloud = {
      source = "tf.reg.cloud/regru/regcloud"
    }
  }
}

provider "regcloud" {
  token   = var.token
  api_url = var.api_url
}
```

- `api_url` по умолчанию: `https://api.cloudvps.reg.ru`
- Управляемые ресурсы (на момент доки): облачные серверы, GPU-серверы, снэпшоты, SSH-ключи.
- **Нет** Terraform-ресурса firewall/UFW — порты 22/80/443 настраиваются на ВМ после создания.

## Как получить API-токен

1. Войти в [панель Рег.облака](https://cloud.reg.ru/panel/).
2. Открыть **Настройки**.
3. Создать / скопировать **токен для API**.
4. Сохранить локально:
   - `secrets/regcloud.env` (каталог `secrets/` в gitignore), поле `REGCLOUD_API_TOKEN=...`
   - или `infra/regcloud/terraform.tfvars` → `token = "..."` (файл в gitignore)
   - или сессия PowerShell: `$env:TF_VAR_token = "..."`

**Не** коммитить токен. **Не** путать с DNS API-паролем из `secrets/regru.env` (это другой API — домены reg.ru).

Если токена у агента нет — остановиться на `init`/`validate`; `plan`/`apply` без токена невозможны.

## Локальные команды

В репозитории: OpenTofu `tools/opentofu/tofu.exe`.

```powershell
cd infra\regcloud
..\..\tools\opentofu\tofu.exe init
..\..\tools\opentofu\tofu.exe validate
# только с токеном и согласием владельца на plan:
..\..\tools\opentofu\tofu.exe plan
# apply — ТОЛЬКО после явного «можно apply» от владельца
```

## Параметры ВМ (цель)

| Параметр | Значение по умолчанию в модуле |
|----------|--------------------------------|
| name | `sfrfr-supabase-db-regru` |
| size | `base-8` (8 vCPU / 8 GB / 120 GB; сверить `GET /v1/sizes`) |
| image | `ubuntu-22-04-amd64` (Docker ставим после create; slug *-docker в API нет) |
| region | `msk1` (Москва; не `openstack-msk1`) |
| SSH | fingerprint ключа `regru_terraform_vm` (ed25519); `manage_ssh_key=false` — ключ уже в панели |

Если `plan` ругается на `size`/`image` — взять актуальные slug со [страницы заказа сервера](https://cloud.reg.ru/panel/) и поправить `terraform.tfvars`.

## Что не делать

- Не `apply` / `destroy` без явного согласия владельца.
- Не трогать прод-VPS `91.229.11.147`.
- Не менять DNS `supabase.proverkastaza.ru` из этого модуля.
- Не класть JWT/Postgres-секреты в tfvars.
