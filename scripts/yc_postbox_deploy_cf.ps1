# Deploy Postbox → Data Streams → Cloud Function → SFRFR webhook.
# Requires: yc authenticated (.\scripts\yc_cloud_auth.ps1), secrets/yandex-postbox.env
#
# Usage:
#   .\scripts\yc_postbox_deploy_cf.ps1

param(
    [string]$FolderId = "b1g0mhpm9tr4lrurk1bu",
    [string]$FunctionName = "sfrfr-postbox-webhook",
    [string]$StreamName = "sfrfr-postbox-events"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Yc = Join-Path $Root "tools\yandex-cloud\bin\yc.exe"
$EnvFile = Join-Path $Root "secrets\yandex-postbox.env"
$HandlerDir = Join-Path $Root "scripts\assets\postbox_cf"
$Zip = Join-Path $env:TEMP "sfrfr-postbox-cf.zip"

if (-not (Test-Path $Yc)) { throw "yc not found: $Yc" }
if (-not (Test-Path $EnvFile)) { throw "missing $EnvFile" }

$cfg = @{}
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^(POSTBOX_WEBHOOK_USER|POSTBOX_WEBHOOK_PASSWORD)=(.*)$') {
        $cfg[$Matches[1]] = $Matches[2]
    }
}
if (-not $cfg['POSTBOX_WEBHOOK_USER'] -or -not $cfg['POSTBOX_WEBHOOK_PASSWORD']) {
    throw "POSTBOX_WEBHOOK_* missing in secrets"
}

$pair = "{0}:{1}" -f $cfg['POSTBOX_WEBHOOK_USER'], $cfg['POSTBOX_WEBHOOK_PASSWORD']
$basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$webhookUrl = "https://api.proverkastaza.ru/api/webhooks/email/postbox"

# SA for function runtime (reuse postbox SA or create dedicated)
$saId = (& $Yc iam service-account get --name sfrfr-postbox --format json | ConvertFrom-Json).id
& $Yc resource-manager folder add-access-binding $FolderId --role serverless.functions.invoker --subject "serviceAccount:$saId" 2>$null | Out-Null
& $Yc resource-manager folder add-access-binding $FolderId --role yds.editor --subject "serviceAccount:$saId" 2>$null | Out-Null
& $Yc resource-manager folder add-access-binding $FolderId --role ydb.editor --subject "serviceAccount:$saId" 2>$null | Out-Null

# Zip handler
if (Test-Path $Zip) { Remove-Item $Zip -Force }
Compress-Archive -Path (Join-Path $HandlerDir "*") -DestinationPath $Zip -Force

# Create / update function
$fnExists = & $Yc serverless function get --name $FunctionName --format json 2>$null
if ($LASTEXITCODE -ne 0) {
    & $Yc serverless function create --name $FunctionName --description "Postbox events → SFRFR webhook"
}
& $Yc serverless function version create `
    --function-name $FunctionName `
    --runtime python312 `
    --entrypoint index.handler `
    --memory 128m `
    --execution-timeout 30s `
    --source-path $Zip `
    --service-account-id $saId `
    --environment "SFRFR_POSTBOX_WEBHOOK_URL=$webhookUrl,SFRFR_POSTBOX_BASIC=$basic"

Write-Host "Function $FunctionName version created."
Write-Host "Next (console or yc): create Data Streams topic '$StreamName', Postbox event destination → stream, trigger function on stream."
Write-Host "See docs/ops/yandex-postbox-setup.md § CF/YDS."
