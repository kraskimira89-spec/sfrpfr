# YC CLI + OpenTofu plan (staging)

**Статус:** tooling готов; `plan` ждёт OAuth с scope `cloud:auth`.  
**Apply:** только после явного «apply» и баланса > 0.

## Что уже сделано в репо

| Компонент | Путь |
|-----------|------|
| Terraform | `infra/yandex-cloud/` |
| OpenTofu | `tools/opentofu/` (gitignore) |
| YC CLI | `tools/yandex-cloud/bin/yc.exe` (gitignore) |
| Auth script | `scripts/yc_cloud_auth.ps1` |
| Plan script | `scripts/tofu_plan_staging.ps1` |
| tfvars | `infra/yandex-cloud/terraform.tfvars` (gitignore) |

## Почему Workspace / AI Studio ключи не работают

| Секрет | Почему нельзя для Terraform |
|--------|-----------------------------|
| `YANDEX_OAUTH_ACCESS_TOKEN` (Workspace) | Нет scope `cloud:auth` |
| `YANDEX_API_KEY` (AI Studio) | Только Foundation Models, не Resource Manager / Compute |

Нужен отдельный OAuth клиента Yandex Cloud CLI  
(`client_id=1a6990aa636648e9b2ef855fa7bec2fb`) или JSON-ключ SA.

## Шаги

### 1. Cloud OAuth (один раз)

```powershell
cd C:\Users\user\Documents\Cursor\SFRFR
.\scripts\yc_cloud_auth.ps1
```

Скрипт откроет браузер → после входа скопируйте `#access_token=...` из URL → вставьте в консоль.  
Токен сохранится в `secrets/yc-cloud.env` (не в git).

### 2. Plan (без apply)

```powershell
.\scripts\tofu_plan_staging.ps1
# опционально сохранить план:
.\scripts\tofu_plan_staging.ps1 -SavePlan
```

### 3. Apply — только явно

Когда баланс > 0 и нет баннера «Облако заблокировано»:

```text
напишите агенту: apply
```

Оценка ~3.8k ₽/мес. Прод-VPS `91.229.11.147` не трогаем.

## Ручная альтернатива

```powershell
$env:PATH = "C:\Users\user\Documents\Cursor\SFRFR\tools\yandex-cloud\bin;C:\Users\user\Documents\Cursor\SFRFR\tools\opentofu;$env:PATH"
yc init   # или yc config set token <cloud-oauth>
cd infra\yandex-cloud
tofu plan -input=false
```
