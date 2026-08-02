# YC CLI + OpenTofu plan (staging)

**Статус:** OAuth YandexID для Cloud IAM отключён с **2026-06-01**.  
**Apply:** только после явного «apply» и баланса > 0.

## Важно: ваш `y0_…` токен

Ошибка:

```text
OAuth token ... issued after '2026-06-01' is not supported for IAM token exchange
```

Значит токен **нельзя** использовать для `yc` / Terraform. Нужен **JSON authorized key** сервисного аккаунта.

Токен, присланный в чат, лучше **отозвать** в [Яндекс OAuth](https://oauth.yandex.ru/) (на всякий случай).

## Рабочий путь (SA key)

### 1. Консоль → ключ SA

Облако `sfrfr-ai` (`b1gkscu5sqpjtf5d5rbi`), каталог `default` (`b1g0mhpm9tr4lrurk1bu`):

1. **IAM** → **Сервисные аккаунты** → создать `sfrfr-terraform` (или отдельный от AI Studio).
2. Назначить на каталог роль **`editor`** (для первого staging plan/apply).
3. У SA: **Создать новый ключ** → тип **JSON** → скачать файл.
4. Сохранить локально (не в git):

```text
secrets/yc-sa-terraform.json
```

`YANDEX_API_KEY` из AI Studio — **другой** тип ключа, для Terraform не подходит.

### 2. Auth + plan

```powershell
cd C:\Users\user\Documents\Cursor\SFRFR
.\scripts\yc_cloud_auth.ps1
.\scripts\tofu_plan_staging.ps1
```

### 3. Apply — только явно

Когда баланс > 0 и нет баннера блокировки — напишите **«apply»**.

## Альтернатива

Интерактивно: `yc init --dpop` (если в организации включены refresh tokens / DPoP).

## Что уже в репо

| Компонент | Путь |
|-----------|------|
| Terraform | `infra/yandex-cloud/` |
| OpenTofu / YC CLI | `tools/` (gitignore) |
| Auth / plan scripts | `scripts/yc_cloud_auth.ps1`, `scripts/tofu_plan_staging.ps1` |
