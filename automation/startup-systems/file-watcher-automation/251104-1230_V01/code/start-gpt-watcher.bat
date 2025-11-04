@echo off
:: Start GPT Response Watcher
:: Monitors Downloads folder for GPT_RESPONSE.md and auto-moves to correct version

echo Starting GPT Response Watcher...
echo.
echo This will monitor: %USERPROFILE%\Downloads
echo Looking for: GPT_RESPONSE.md
echo.
echo Press Ctrl+C to stop
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "C:\DEV\scripts\gpt-response-watcher.ps1"
