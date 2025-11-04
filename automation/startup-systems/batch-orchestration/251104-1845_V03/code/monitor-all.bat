@echo off
echo.
echo ================================================
echo   Project Context OS - Aggregate Monitor
echo ================================================
echo.
echo Showing logs from all running services...
echo Press Ctrl+C to stop monitoring
echo.
timeout /t 2 /nobreak >nul

powershell -Command "& { while($true) { Clear-Host; Write-Host '================================================' -ForegroundColor Cyan; Write-Host '  Project Context OS - Live Status' -ForegroundColor Cyan; Write-Host '  ' (Get-Date -Format 'HH:mm:ss') -ForegroundColor Cyan; Write-Host '================================================' -ForegroundColor Cyan; Write-Host ''; Write-Host 'DOCKER CONTAINERS:' -ForegroundColor Yellow; docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>$null; Write-Host ''; Write-Host 'RECENT LOGS (last 20 lines):' -ForegroundColor Yellow; Write-Host ''; Write-Host '--- Sourcegraph ---' -ForegroundColor Green; docker compose -f C:\DEV\sourcegraph\docker-compose.yaml logs --tail=5 2>$null; Write-Host ''; Write-Host '--- Structurizr ---' -ForegroundColor Green; docker logs --tail=5 (docker ps -q --filter 'ancestor=structurizr/lite') 2>$null; Write-Host ''; Write-Host '================================================' -ForegroundColor Cyan; Start-Sleep -Seconds 5; } }"
