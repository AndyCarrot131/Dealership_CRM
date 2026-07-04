@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo Stopping Dealership CRM (Docker)...
echo.

echo Stopping CRM service (db + backend + frontend)...
docker compose down --remove-orphans
if errorlevel 1 (
    echo Warning: failed to stop CRM service stack.
)

echo.
echo Stopping local LLM...
docker compose -f docker-compose.llm.yml down
if errorlevel 1 (
    echo Warning: failed to stop local LLM stack.
)

echo.
echo All containers stopped.
pause
