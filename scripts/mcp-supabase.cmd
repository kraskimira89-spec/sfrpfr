@echo off
setlocal EnableExtensions
REM Stdio-safe launcher for Cursor MCP (@supabase/mcp-server-supabase).
REM Секреты: secrets\supabase-access.env (SUPABASE_ACCESS_TOKEN, SUPABASE_PROJECT_REF)
REM Запись в БД: задать SUPABASE_MCP_READ_ONLY=0 в env-файле.

set "ROOT=%~dp0.."
set "ENVFILE=%ROOT%\secrets\supabase-access.env"
if not exist "%ENVFILE%" (
  echo Missing %ENVFILE% 1>&2
  exit /b 1
)

for /f "usebackq tokens=1,* delims== eol=#" %%A in ("%ENVFILE%") do (
  if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
)

if not defined SUPABASE_ACCESS_TOKEN (
  echo SUPABASE_ACCESS_TOKEN missing in supabase-access.env 1>&2
  exit /b 1
)
if not defined SUPABASE_PROJECT_REF (
  echo SUPABASE_PROJECT_REF missing in supabase-access.env 1>&2
  exit /b 1
)

set "RO=--read-only"
if "%SUPABASE_MCP_READ_ONLY%"=="0" set "RO="

npx -y @supabase/mcp-server-supabase@latest --project-ref=%SUPABASE_PROJECT_REF% %RO%
exit /b %ERRORLEVEL%
