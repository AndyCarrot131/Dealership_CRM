@echo off
setlocal
cd /d "%~dp0"
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" (
  echo ERROR: C# compiler not found.
  exit /b 1
)
"%CSC%" /nologo /target:winexe /optimize+ /out:"..\CRM_Launcher.exe" /resource:"crm_launcher.ps1",CrmLauncher.Script /reference:System.dll /reference:System.Drawing.dll /reference:System.Windows.Forms.dll "CrmLauncher.cs"
if errorlevel 1 exit /b 1
echo Built CRM_Launcher.exe successfully.
