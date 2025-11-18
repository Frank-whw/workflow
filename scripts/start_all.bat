@echo off
setlocal
if not exist "%LOCALAPPDATA%\Workflow" mkdir "%LOCALAPPDATA%\Workflow"
pushd "%LOCALAPPDATA%\Workflow"
start "" "%~dp0workflow-worker.exe"
timeout /t 1 >nul
start "" "%~dp0workflow-web.exe"
popd