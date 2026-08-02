@echo off
setlocal
cd /d "%~dp0"
set "TASK_NAME=PLTS Inverter Gateway"
set "RUNNER=%~dp0run_gateway.bat"
schtasks /Create /TN "%TASK_NAME%" /TR "\"%RUNNER%\"" /SC ONLOGON /RL LIMITED /F
if errorlevel 1 exit /b 1
echo Scheduled Task "%TASK_NAME%" berhasil dipasang.

