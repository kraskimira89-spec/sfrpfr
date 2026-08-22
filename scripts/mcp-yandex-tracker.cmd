@echo off
setlocal EnableExtensions
REM Stdio-safe launcher for Cursor MCP (aikts/yandex-tracker-mcp).
REM Читает secrets\yandex-tracker.env рядом с репозиторием.

set "ROOT=%~dp0.."
set "ENVFILE=%ROOT%\secrets\yandex-tracker.env"
if not exist "%ENVFILE%" (
  echo Missing %ENVFILE% — copy from secrets\yandex-tracker.env.example 1>&2
  exit /b 1
)

for /f "usebackq tokens=1,* delims== eol=#" %%A in ("%ENVFILE%") do (
  if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
)

if not defined TRACKER_TOKEN (
  echo TRACKER_TOKEN missing in yandex-tracker.env 1>&2
  exit /b 1
)
if not defined TRACKER_CLOUD_ORG_ID if not defined TRACKER_ORG_ID (
  echo TRACKER_CLOUD_ORG_ID or TRACKER_ORG_ID required in yandex-tracker.env 1>&2
  exit /b 1
)

where uvx >nul 2>&1
if %ERRORLEVEL% equ 0 (
  uvx yandex-tracker-mcp@latest
  exit /b %ERRORLEVEL%
)

where uv >nul 2>&1
if %ERRORLEVEL% equ 0 (
  uv tool run yandex-tracker-mcp@latest
  exit /b %ERRORLEVEL%
)

set "LOCAL=%ROOT%\tools\yandex-tracker-mcp"
if exist "%LOCAL%\pyproject.toml" (
  pushd "%LOCAL%"
  python -m yandex_tracker_mcp 2>nul
  if %ERRORLEVEL% neq 0 python -m server 2>nul
  set "EC=%ERRORLEVEL%"
  popd
  exit /b %EC%
)

echo Install uv (https://github.com/astral-sh/uv) or clone aikts/yandex-tracker-mcp to tools\yandex-tracker-mcp 1>&2
exit /b 1
