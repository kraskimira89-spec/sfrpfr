@echo off
setlocal EnableExtensions
REM Stdio-safe launcher for Cursor MCP (aikts/yandex-tracker-mcp).
REM Секреты: secrets\yandex-tracker.env

set "ROOT=%~dp0.."
set "ENVFILE=%ROOT%\secrets\yandex-tracker.env"
if not exist "%ENVFILE%" (
  echo Missing %ENVFILE% — run scripts\bootstrap_yandex_tracker_mcp.ps1 1>&2
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

set "VPY=%ROOT%\.venv\Scripts\python.exe"
if exist "%VPY%" (
  "%VPY%" -m mcp_tracker 2>nul
  if %ERRORLEVEL% equ 0 exit /b 0
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
  if exist "%VPY%" (
    "%VPY%" -m mcp_tracker
    set "EC=%ERRORLEVEL%"
    popd
    exit /b %EC%
  )
  popd
)

echo Install: .venv\Scripts\pip install -e tools\yandex-tracker-mcp 1>&2
exit /b 1
