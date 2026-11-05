@echo off
rem Copy your API key first, then double-click this file. The key is never shown.
powershell -NoProfile -Command Get-Clipboard | wsl -d Ubuntu-22.04 --cd "%~dp0." -- bash set_key.sh
echo.
pause
