@echo off
setlocal EnableExtensions
REM Stdio-safe launcher for Cursor MCP (не PowerShell).
REM Читает secrets\wordstat.env рядом с репозиторием.

set "ROOT=%~dp0.."
set "ENVFILE=%ROOT%\secrets\wordstat.env"
if not exist "%ENVFILE%" (
  echo Missing %ENVFILE% 1>&2
  exit /b 1
)

for /f "usebackq tokens=1,* delims== eol=#" %%A in ("%ENVFILE%") do (
  if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
)

if not defined YANDEX_SEARCH_API_KEY if defined YANDEX_WORDSTAT_API_KEY set "YANDEX_SEARCH_API_KEY=%YANDEX_WORDSTAT_API_KEY%"
if not defined YANDEX_FOLDER_ID if defined YANDEX_WORDSTAT_FOLDER_ID set "YANDEX_FOLDER_ID=%YANDEX_WORDSTAT_FOLDER_ID%"

if not defined YANDEX_SEARCH_API_KEY (
  echo YANDEX_SEARCH_API_KEY missing in wordstat.env 1>&2
  exit /b 1
)
if not defined YANDEX_FOLDER_ID (
  echo YANDEX_FOLDER_ID missing in wordstat.env 1>&2
  exit /b 1
)

set "NPX=C:\Program Files\nodejs\npx.cmd"
if not exist "%NPX%" set "NPX=npx.cmd"
"%NPX%" -y yandex-wordstat-mcp
