@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo Starting Dealership CRM (Docker)...
echo.

REM 1) Local LLM container
start "Local LLM" /D "%ROOT%" cmd /k bash run_local_llm.sh

REM 2) CRM service container (db + backend + frontend)
start "CRM Service" /D "%ROOT%" cmd /k bash run_service.sh

echo.
echo Launched 2 windows: Local LLM, CRM Service.
echo App URL: http://localhost:8756
echo You can close this launcher window.
timeout /t 5 >nul
