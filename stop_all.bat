@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo Stopping Dealership CRM...
echo.

docker compose version >nul 2>&1
if not errorlevel 1 (
    set "COMPOSE=docker compose"
) else (
    docker-compose version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Docker Compose is not installed.
        goto :fail
    )
    set "COMPOSE=docker-compose"
)

docker info >nul 2>&1
if errorlevel 1 (
    echo Docker is not running; there are no reachable containers to stop.
    goto :success
)

echo [1/2] Stopping CRM application and database...
%COMPOSE% down
if errorlevel 1 goto :fail

echo [2/2] Stopping local LLM...
%COMPOSE% -f docker-compose.llm.yml down
if errorlevel 1 goto :fail
REM Clean up the retired vision companion from older installs.
docker rm -f dealer_crm_local_vision >nul 2>&1

:success
echo.
echo All Dealership CRM containers are stopped.
pause
exit /b 0

:fail
echo.
echo Shutdown encountered an error. Review the output above.
pause
exit /b 1
