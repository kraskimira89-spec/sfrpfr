@echo off
setlocal EnableExtensions
REM Stdio-safe launcher: DBHub read-only → self-host Supabase (YC) via SSH jump (app-VPS).
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

for /f "usebackq tokens=1,* delims== eol=#" %%A in ("%ENVFILE%") do (
  if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
)

if not defined DB_PASSWORD (
  echo DB_PASSWORD missing in supabase-selfhost-mcp.env 1>&2
  exit /b 1
)
if not defined DB_HOST set "DB_HOST=51.250.13.240"
if not defined DB_PORT set "DB_PORT=5433"
if not defined DB_USER set "DB_USER=postgres"
if not defined DB_NAME set "DB_NAME=postgres"
if not defined SSH_HOST set "SSH_HOST=91.229.11.147"
if not defined SSH_USER set "SSH_USER=root"

REM Опционально: SSH_KEY=C:\Users\...\id_ed25519 — иначе DBHub сам ищет ~/.ssh/*
if defined SSH_KEY (
  rem pass through
)

npx -y @bytebase/dbhub@latest --transport stdio --config "%TOML%"
exit /b %ERRORLEVEL%
