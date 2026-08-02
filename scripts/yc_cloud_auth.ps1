# Аутентификация YC CLI для Terraform (scope cloud:auth).
# Workspace OAuth (ТЗ-14) НЕ подходит — у него нет cloud:auth.
#
# Использование:
#   .\scripts\yc_cloud_auth.ps1
#   .\scripts\yc_cloud_auth.ps1 -Token "y0_...."
#   # или положить токен в secrets/yc-cloud.env: YC_TOKEN=y0_...

param(
    [string]$Token = "",
    [string]$CloudId = "b1gkscu5sqpjtf5d5rbi",
    [string]$FolderId = "b1g0mhpm9tr4lrurk1bu",
    [string]$Profile = "sfrfr",
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Yc = Join-Path $Root "tools\yandex-cloud\bin\yc.exe"
$EnvFile = Join-Path $Root "secrets\yc-cloud.env"
$OauthUrl = "https://oauth.yandex.ru/authorize?response_type=token&client_id=1a6990aa636648e9b2ef855fa7bec2fb"

if (-not (Test-Path $Yc)) {
    throw "YC CLI не найден: $Yc (скачайте: storage.yandexcloud.net/yandexcloud-yc/release/stable)"
}

function Read-TokenFromEnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    $found = $null
    Get-Content $Path | ForEach-Object {
        if ($_ -match '^\s*YC_TOKEN=(.+)\s*$') {
            $found = $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $found
}

if (-not $Token) {
    $Token = Read-TokenFromEnvFile -Path $EnvFile
}

if (-not $Token) {
    if ($OpenBrowser -or -not $PSBoundParameters.ContainsKey("Token")) {
        Write-Host "Открываю OAuth Yandex Cloud (нужен scope cloud:auth)..."
        Start-Process $OauthUrl
        Write-Host ""
        Write-Host "После входа скопируйте access_token из адресной строки"
        Write-Host "(фрагмент #access_token=...&token_type=bearer) и вставьте ниже."
        Write-Host "Либо сохраните в secrets\yc-cloud.env строку: YC_TOKEN=..."
        Write-Host ""
    }
    $Token = Read-Host "Вставьте Yandex Cloud OAuth token"
}

if (-not $Token -or $Token.Length -lt 20) {
    throw "Пустой или слишком короткий токен"
}

# Не печатаем токен
$profiles = & $Yc config profile list 2>&1 | Out-String
if ($profiles -notmatch "(?m)^\s*$Profile\b") {
    & $Yc config profile create $Profile | Out-Null
}
& $Yc config profile activate $Profile | Out-Null
& $Yc config set token $Token | Out-Null
& $Yc config set cloud-id $CloudId | Out-Null
& $Yc config set folder-id $FolderId | Out-Null

# Сохранить в secrets (gitignore), без вывода значения
$secretsDir = Join-Path $Root "secrets"
New-Item -ItemType Directory -Force -Path $secretsDir | Out-Null
@(
    "# Yandex Cloud OAuth / IAM — НЕ коммитить",
    "# Получить: $OauthUrl",
    "YC_TOKEN=$Token",
    "YC_CLOUD_ID=$CloudId",
    "YC_FOLDER_ID=$FolderId"
) | Set-Content -Path $EnvFile -Encoding UTF8

Write-Host "Проверка: resource-manager cloud list..."
& $Yc resource-manager cloud list --format text
if ($LASTEXITCODE -ne 0) {
    throw "Токен не принят Cloud IAM (нужен OAuth с cloud:auth, не Workspace)"
}

Write-Host "OK: профиль '$Profile', cloud=$CloudId, folder=$FolderId"
Write-Host "Дальше: .\scripts\tofu_plan_staging.ps1"
