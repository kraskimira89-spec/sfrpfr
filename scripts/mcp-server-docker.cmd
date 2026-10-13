@echo off
setlocal EnableExtensions
REM Stdio-safe launcher: ensure Docker Desktop is up, then start mcp-server-docker.
REM Do NOT write to stdout (MCP JSON-RPC uses stdin/stdout).

set "MCP_EXE=D:\Cursor\mcp-server-docker-venv\Scripts\mcp-server-docker.exe"
set "DOCKER_DESKTOP=%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe"
set "DOCKER_BIN=%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe"

if not exist "%MCP_EXE%" (
  echo mcp-server-docker.exe not found: %MCP_EXE% 1>&2
  exit /b 1
)

REM Already ready?
if exist "%DOCKER_BIN%" (
  "%DOCKER_BIN%" info >nul 2>&1
  if %ERRORLEVEL% equ 0 goto :run
) else (
  where docker >nul 2>&1
  if %ERRORLEVEL% equ 0 (
    docker info >nul 2>&1
    if %ERRORLEVEL% equ 0 goto :run
  )
)

if not exist "%DOCKER_DESKTOP%" (
  echo Docker Desktop not found: %DOCKER_DESKTOP% 1>&2
  exit /b 1
)

echo Starting Docker Desktop for mcp-server-docker... 1>&2
start "" "%DOCKER_DESKTOP%"

set /a _i=0
:wait
set /a _i+=1
if %_i% gtr 60 (
  echo Docker daemon did not become ready in time 1>&2
  exit /b 1
)
ping -n 4 127.0.0.1 >nul
if exist "%DOCKER_BIN%" (
  "%DOCKER_BIN%" info >nul 2>&1
) else (
  docker info >nul 2>&1
)
if %ERRORLEVEL% neq 0 goto :wait

:run
"%MCP_EXE%"
exit /b %ERRORLEVEL%
