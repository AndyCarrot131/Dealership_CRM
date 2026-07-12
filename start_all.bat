@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo Starting Dealership CRM...
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
    if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
        echo Docker Desktop is not running. Starting it now...
        start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
        for /L %%I in (1,1,60) do (
            docker info >nul 2>&1 && goto :docker_ready
            powershell.exe -NoProfile -Command "Start-Sleep -Seconds 2"
        )
    )
    echo ERROR: Docker did not become ready within 2 minutes.
    goto :fail
)

:docker_ready
docker network inspect dealer_crm_net >nul 2>&1
if errorlevel 1 (
    docker network create dealer_crm_net >nul
    if errorlevel 1 goto :fail
)

echo [1/4] Starting Qwen3.5-4B-Instruct Q4_K_M local LLM...
REM Remove the retired two-container vision companion, if present.
docker rm -f dealer_crm_local_vision >nul 2>&1
%COMPOSE% -f docker-compose.llm.yml up -d --build
if errorlevel 1 goto :fail

echo [2/4] Waiting for the local LLM API...
for /L %%I in (1,1,120) do (
    curl.exe -fsS http://localhost:8080/health >nul 2>&1 && goto :llm_ready
    powershell.exe -NoProfile -Command "Start-Sleep -Seconds 2"
)
echo ERROR: Local LLM did not become healthy within 4 minutes.
%COMPOSE% -f docker-compose.llm.yml logs --tail=100 local_llm
goto :fail

:llm_ready
echo [3/4] Starting database and CRM application...
%COMPOSE% up -d --build
if errorlevel 1 goto :fail

echo [4/4] Running database migrations...
%COMPOSE% exec -T app alembic upgrade head
if errorlevel 1 goto :fail

echo.
echo Dealership CRM is ready.
echo   App:      http://localhost:8756
echo   API docs: http://localhost:8756/docs
echo   LLM API:  http://localhost:8080/v1
echo.
pause
exit /b 0

:fail
echo.
echo Startup failed. Review the error above, then run start_all.bat again.
pause
exit /b 1
