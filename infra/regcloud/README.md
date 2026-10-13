# SFRFR — Terraform / OpenTofu для Рег.облака (reg.cloud)

Резервная ВМ `sfrfr-supabase-db-regru` под self-hosted Supabase.

- Дока провайдера: [Начало работы с Terraform](https://reg.cloud/support/cloud/instrumenty/terraform/rabota-s-terraform/nachalo-raboty-s-terraform)
- ТЗ резерва: [docs/ops/tz-regru-assistant-supabase-reserve.md](../../docs/ops/tz-regru-assistant-supabase-reserve.md)
- Ops: [docs/ops/regcloud-terraform.md](../../docs/ops/regcloud-terraform.md)

**Yandex Cloud** (`infra/yandex-cloud/`) этим модулем **не** трогаем.

## Провайдер

| Параметр | Значение |
|----------|----------|
| source | `tf.reg.cloud/regru/regcloud` |
| auth | `token` + `api_url` |
| API URL | `https://api.cloudvps.reg.ru` |
| Ресурсы | `regcloud_ssh_key`, `regcloud_server` (+ snapshot/GPU — не в этом модуле) |

## Инструмент

В репозитории уже есть **OpenTofu** `tools/opentofu/tofu.exe` (как для Yandex). HashiCorp Terraform тоже подойдёт, если доступен.

## Быстрый старт (без apply)

```powershell
# из корня репо
$Tofu = ".\tools\opentofu\tofu.exe"
cd infra\regcloud

copy terraform.tfvars.example terraform.tfvars
# Вписать token ИЛИ:
# $env:TF_VAR_token = "<token из панели → Настройки>"

& $Tofu init
& $Tofu validate
# plan только при наличии токена:
& $Tofu plan
```

Секреты также можно держать в `secrets/regcloud.env` (см. `secrets/regcloud.env.example`) и подставлять `TF_VAR_token`.

## Важно

- **`plan` / `apply` только с явного согласия владельца.** Этот README не является разрешением на apply.
- Прод-VPS `91.229.11.147` этим модулем **не** управляется.
- Firewall UFW 22/80/443 провайдер Terraform не описывает — после создания ВМ (или через ассистента reg.ru по ТЗ).
- `size` / `image` сверить в панели: не все тарифы есть в каждом регионе.

## Outputs

После успешного apply: `public_ip`, `server_id`, `ssh_key_fingerprint`.
DNS `supabase.proverkastaza.ru` меняет **только владелец** после готовности стека.
