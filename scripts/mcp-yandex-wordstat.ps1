# Запуск Yandex Wordstat MCP для Cursor.
# Читает secrets/wordstat.env (не в git) и стартует npx yandex-wordstat-mcp.

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $RepoRoot "secrets\wordstat.env"

if (-not (Test-Path $EnvFile)) {
    Write-Error "Нет $EnvFile — создайте YANDEX_SEARCH_API_KEY + YANDEX_FOLDER_ID (см. docs/ops/yandex-wordstat-mcp.md)"
}

Get-Content $EnvFile -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $i = $line.IndexOf("=")
    if ($i -lt 1) { return }
    $name = $line.Substring(0, $i).Trim()
    $value = $line.Substring($i + 1).Trim().Trim('"').Trim("'")
    if ($name) {
        Set-Item -Path "Env:$name" -Value $value
    }
}

if (-not $env:YANDEX_SEARCH_API_KEY -and $env:YANDEX_WORDSTAT_API_KEY) {
    $env:YANDEX_SEARCH_API_KEY = $env:YANDEX_WORDSTAT_API_KEY
}
if (-not $env:YANDEX_FOLDER_ID -and $env:YANDEX_WORDSTAT_FOLDER_ID) {
    $env:YANDEX_FOLDER_ID = $env:YANDEX_WORDSTAT_FOLDER_ID
}

if (-not $env:YANDEX_SEARCH_API_KEY -or -not $env:YANDEX_FOLDER_ID) {
    Write-Error "В wordstat.env нужны YANDEX_SEARCH_API_KEY и YANDEX_FOLDER_ID"
}

$npx = Join-Path $env:ProgramFiles "nodejs\npx.cmd"
if (-not (Test-Path $npx)) {
    $npx = "npx.cmd"
}
& $npx -y yandex-wordstat-mcp
