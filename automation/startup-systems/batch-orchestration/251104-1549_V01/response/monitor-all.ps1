#!/usr/bin/env pwsh
param(
  [int]$RefreshSec = 5
)
Write-Host ""
Write-Host "Project Context OS — Monitor" -ForegroundColor Cyan
while ($true) {
  Clear-Host
  Write-Host "== Docker ==================================================" -ForegroundColor Yellow
  try { docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" } catch { Write-Host "(docker not available)" }
  Write-Host ""
  Write-Host "== Health files ===========================================" -ForegroundColor Yellow
  Get-ChildItem -Path ".\40_runtime\health" -Filter *.ok -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host ("{0}`t{1}" -f $_.Name, (Get-Content $_.FullName -ErrorAction SilentlyContinue))
  }
  Write-Host ""
  Write-Host "== Recent logs ============================================" -ForegroundColor Yellow
  Get-ChildItem -Path ".\40_runtime\logs" -Filter *.log -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 3 | ForEach-Object {
    Write-Host "--- $($_.Name) ---"
    Get-Content $_.FullName -Tail 10 -ErrorAction SilentlyContinue
  }
  Start-Sleep -Seconds $RefreshSec
}
