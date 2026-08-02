# Аутентификация для Terraform / yc (после 2026-06-01).
#
# OAuth YandexID → IAM БОЛЬШЕ НЕ РАБОТАЕТ для новых токенов:
#   "OAuth token ... issued after '2026-06-01' is not supported for IAM token exchange"
#
# Рабочие варианты:
#   1) JSON authorized key SA  (рекомендуется для plan/apply)
#   2) yc init --dpop          (интерактивно, если включены refresh tokens в org)
#
# Использование:
#   .\scripts\yc_cloud_auth.ps1 -KeyFile .\secrets\yc-sa-terraform.json
#   .\scripts\tofu_plan_staging.ps1

param(
    [string]$KeyFile = "",
    [string]$CloudId = "b1gkscu5sqpjtf5d5rbi",
    [string]$FolderId = "b1g0mhpm9tr4lrurk1bu",
    [string]$Profile = "sfrfr"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Yc = Join-Path $Root "tools\yandex-cloud\bin\yc.exe"
$DefaultKey = Join-Path $Root "secrets\yc-sa-terraform.json"
$EnvFile = Join-Path $Root "secrets\yc-cloud.env"

if (-not (Test-Path $Yc)) {
    throw "YC CLI не найден: $Yc"
}

if (-not $KeyFile) {
    if (Test-Path $DefaultKey) {
        $KeyFile = $DefaultKey
    }
}

if (-not $KeyFile -or -not (Test-Path $KeyFile)) {
    Write-Host @"
Нужен JSON-ключ сервисного аккаунта (authorized key).

В консоли Yandex Cloud (облако sfrfr-ai / каталог default):
  1. IAM → Сервисные аккаунты → создать sfrfr-terraform (или взять существующий)
  2. Роли на каталог: editor (для staging Terraform) + storage.uploader при необходимости
  3. Создать новый ключ → JSON → сохранить как:
       secrets\yc-sa-terraform.json
  4. Снова: .\scripts\yc_cloud_auth.ps1

OAuth-токен (y0_...) после 2026-06-01 для Cloud IAM не принимается.
"@
    throw "Нет файла ключа SA"
}

$KeyFile = (Resolve-Path $KeyFile).Path

$plist = & $Yc config profile list 2>&1 | Out-String
if ($plist -notmatch "(?m)^\s*$Profile\b") {
    & $Yc config profile create $Profile | Out-Null
}
& $Yc config profile activate $Profile | Out-Null
# token и SA key взаимоисключающие — unset token
& $Yc config unset token 2>$null | Out-Null
& $Yc config set service-account-key $KeyFile | Out-Null
& $Yc config set cloud-id $CloudId | Out-Null
& $Yc config set folder-id $FolderId | Out-Null

@(
    "# Yandex Cloud auth для Terraform — НЕ коммитить",
    "# OAuth YC_TOKEN после 2026-06-01 не использовать",
    "YC_SERVICE_ACCOUNT_KEY_FILE=$KeyFile",
    "YC_CLOUD_ID=$CloudId",
    "YC_FOLDER_ID=$FolderId"
) | Set-Content -Path $EnvFile -Encoding UTF8

Write-Host "Проверка: resource-manager cloud list..."
& $Yc resource-manager cloud list --format text
if ($LASTEXITCODE -ne 0) {
    throw "Ключ SA не принят Cloud IAM (проверьте роли и JSON authorized key)"
}

Write-Host "OK: профиль '$Profile', key=$KeyFile"
Write-Host "Дальше: .\scripts\tofu_plan_staging.ps1"
