@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0..\CRM_Launcher.exe" call "%~dp0build_launcher.bat"
if errorlevel 1 pause & exit /b 1
start "" "%~dp0..\CRM_Launcher.exe"
