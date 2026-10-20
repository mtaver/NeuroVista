@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-NeuroVista.ps1"
if errorlevel 1 (
  echo.
  echo NeuroVista did not start. Review the error and log paths above.
  pause
  exit /b 1
)

endlocal
