@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Stdio-safe: OpenSSH -L (ssh.exe, исключение AdGuard) → DBHub readonly на 127.0.0.1.
REM Секреты: secrets\supabase-selfhost-mcp.env
REM Официальный mcp.supabase.com сюда НЕ подходит (только Cloud project_ref).

set "ROOT=%~dp0.."
set "ENVFILE=%ROOT%\secrets\supabase-selfhost-mcp.env"
set "TOML=%ROOT%\scripts\dbhub-supabase-selfhost.toml"

if not exist "%ENVFILE%" (
  echo Missing %ENVFILE% — run scripts\bootstrap_supabase_selfhost_mcp.ps1 1>&2
  exit /b 1
)
if not exist "%TOML%" (
  echo Missing %TOML% 1>&2
  exit /b 1
)

REM UTF-8 BOM ломает первую переменную в for /f — читаем через PowerShell.
for /f "usebackq delims=" %%L in (`powershell -NoProfile -Command "Get-Content -LiteralPath '%ENVFILE%' -Encoding utf8 | ForEach-Object { $_.TrimEnd() } | Where-Object { $_ -and ($_ -notmatch '^\s*#') -and ($_ -match '=') }"`) do (
  for /f "tokens=1,* delims==" %%A in ("%%L") do (
    if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
  )
)

if not defined DB_PASSWORD (
  echo DB_PASSWORD missing in supabase-selfhost-mcp.env 1>&2
  exit /b 1
)
if not defined SSH_HOST set "SSH_HOST=51.250.69.237"
if not defined SSH_USER set "SSH_USER=sfrfr"
if not defined SSH_LOCAL_PORT set "SSH_LOCAL_PORT=15433"
if not defined SSH_REMOTE_PORT set "SSH_REMOTE_PORT=5433"
if not defined DB_USER set "DB_USER=postgres"
if not defined DB_NAME set "DB_NAME=postgres"
if not defined SSH_KEY set "SSH_KEY=%USERPROFILE%\.ssh\id_ed25519"

REM DBHub всегда на localhost-туннель (не на публичный :5433 — он закрыт SG/UFW).
set "DB_HOST=127.0.0.1"
set "DB_PORT=%SSH_LOCAL_PORT%"

set "SSH_BIN=%SystemRoot%\System32\OpenSSH\ssh.exe"
if not exist "%SSH_BIN%" set "SSH_BIN=ssh"

REM Уже слушает локальный порт — не поднимаем второй туннель.
netstat -an | findstr /R /C:":%SSH_LOCAL_PORT% .*LISTENING" >nul 2>&1
if errorlevel 1 (
  REM Windows OpenSSH не умеет -f: запускаем фоном, stdio отвязан от MCP.
  start "" /b "%SSH_BIN%" -N -o ExitOnForwardFailure=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o ServerAliveInterval=30 -i "%SSH_KEY%" -o IdentitiesOnly=yes -L 127.0.0.1:%SSH_LOCAL_PORT%:127.0.0.1:%SSH_REMOTE_PORT% %SSH_USER%@%SSH_HOST% <nul >nul 2>&1
  set /a TRIES=0
  :wait_tunnel
  netstat -an | findstr /R /C:":%SSH_LOCAL_PORT% .*LISTENING" >nul 2>&1
  if not errorlevel 1 goto tunnel_ok
  set /a TRIES+=1
  if !TRIES! GEQ 20 (
    echo OpenSSH tunnel failed: %SSH_USER%@%SSH_HOST% -L %SSH_LOCAL_PORT% 1>&2
    echo Check: AdGuard exclusion for ssh.exe; SG TCP/22 for home IP; key …UaTm 1>&2
    exit /b 1
  )
  ping -n 2 127.0.0.1 >nul
  goto wait_tunnel
)
:tunnel_ok

npx -y @bytebase/dbhub@latest --transport stdio --config "%TOML%"
set "EC=!ERRORLEVEL!"

REM Снести туннель этого порта (best-effort; не трогаем чужие ssh).
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%SSH_LOCAL_PORT% .*LISTENING"') do (
  taskkill /F /PID %%P >nul 2>&1
)

exit /b %EC%
