@echo off
setlocal

cd /d "%~dp0"
git pull origin e2

if errorlevel 1 (
    echo.
    echo Update failed.
    pause
    exit /b 1
)

echo.
echo Update complete.
pause
