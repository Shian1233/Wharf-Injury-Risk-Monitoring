@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0set-password.ps1"
if errorlevel 1 pause
