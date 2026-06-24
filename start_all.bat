@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo Starting Dealership CRM services...
echo.

REM 1) Local LLM (llama-server) — same as local_model/qwen3-vl-4b/launch.sh
start "LLM Server" /D "%ROOT%local_model\qwen3-vl-4b" cmd /k llama-server -m Qwen3VL-4B-Instruct-Q4_K_M.gguf --mmproj mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf -c 8192 -ngl 99 --port 8080 --host 127.0.0.1

REM 2) Backend — same as 1_run_backend.sh
start "Backend" /D "%ROOT%" cmd /k "docker compose up -d && docker compose exec backend alembic upgrade head && echo. && echo Backend stack is up. && pause"

REM 3) Frontend — same as 2_run_frontend.sh
start "Frontend" /D "%ROOT%frontend" cmd /k npm run dev

echo.
echo Launched 3 windows: LLM Server, Backend, Frontend.
echo You can close this launcher window.
timeout /t 5 >nul
