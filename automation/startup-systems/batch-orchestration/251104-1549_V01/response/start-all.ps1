#!/usr/bin/env pwsh
<# 
.SYNOPSIS
  Master orchestrator for Project Context OS on Windows 11.
.DESIGN
  - PowerShell-first replacement for batch files.
  - Starts Docker Desktop, then individual services.
  - Polling with backoff and structured JSON logs.
  - Writes health heartbeats and opens browser once ready.
#>

param(
  [int]$OpenTimeoutSec = 180,
  [string]$LogDir = ".\40_runtime\logs",
  [string]$HealthDir = ".\40_runtime\health"
)

$ErrorActionPreference = "Stop"
$null = New-Item -ItemType Directory -Force -Path $LogDir,$HealthDir | Out-Null
$logFile = Join-Path $LogDir ("orchestrator-{0}.log" -f (Get-Date -Format "yyyyMMdd"))

function Log($level, $msg, $extra=@{}) {
  $line = @{ts=(Get-Date).ToString("o"); level=$level; msg=$msg}
  foreach ($k in $extra.Keys) { $line[$k] = $extra[$k] }
  ($line | ConvertTo-Json -Compress) | Add-Content -Path $logFile
}

function Heartbeat([string]$name) {
  Set-Content -Path (Join-Path $HealthDir "$name.ok") -Value ("ok " + (Get-Date).ToString("o"))
}

function Wait-HttpReady([string]$url, [int]$timeoutSec=120) {
  $deadline = (Get-Date).AddSeconds($timeoutSec)
  $n=0
  while ((Get-Date) -lt $deadline) {
    try {
      $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
      if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) { return $true }
    } catch {}
    $delay = [Math]::Min(5000, [Math]::Pow(2,[Math]::Min($n,6))*100) # 100,200,400,...
    Start-Sleep -Milliseconds $delay
    $n++
  }
  return $false
}

# 1) Ensure Docker Desktop is running
try {
  Log "INFO" "checking_docker"
  $dockersvc = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
  if (-not $dockersvc) {
    Log "INFO" "starting_docker_desktop"
    Start-Process -FilePath "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    Start-Sleep -Seconds 3
  }
} catch { Log "WARN" "docker_check_failed" @{error=$_.Exception.Message} }

# 2) Start Backstage (PS wrapper)
try {
  Log "INFO" "start_backstage"
  Start-Process pwsh -ArgumentList "-NoProfile","-Command","& './code/start-backstage.ps1'" -WindowStyle Minimized
} catch { Log "ERROR" "start_backstage_failed" @{error=$_.Exception.Message} }

# 3) Start Structurizr (if compose file exists)
if (Test-Path ".\infra\structurizr\docker-compose.yml") {
  try {
    Log "INFO" "start_structurizr_compose"
    Push-Location ".\infra\structurizr"
    docker compose up -d
    Pop-Location
  } catch { Log "ERROR" "structurizr_start_failed" @{error=$_.Exception.Message} }
}

# 4) Start MkDocs (dev server) if mkdocs.yml present
if (Test-Path ".\mkdocs.yml") {
  try {
    Log "INFO" "start_mkdocs"
    Start-Process pwsh -ArgumentList "-NoProfile","-Command","& 'mkdocs serve -a 127.0.0.1:8000'" -WindowStyle Minimized
  } catch { Log "WARN" "mkdocs_start_failed" @{error=$_.Exception.Message} }
}

# 5) Start Sourcegraph (compose single-node if present)
if (Test-Path ".\infra\sourcegraph\docker-compose.yml") {
  try {
    Log "INFO" "start_sourcegraph_compose"
    Push-Location ".\infra\sourcegraph"
    docker compose up -d
    Pop-Location
  } catch { Log "WARN" "sourcegraph_start_failed" @{error=$_.Exception.Message} }
}

# --- Health gates with backoff ---
$ok1 = Wait-HttpReady "http://127.0.0.1:8000"  $OpenTimeoutSec; if ($ok1) { Heartbeat "mkdocs"; Log "INFO" "mkdocs_ready" }
$ok2 = Wait-HttpReady "http://127.0.0.1:3000"  $OpenTimeoutSec; if ($ok2) { Heartbeat "backstage"; Log "INFO" "backstage_ready" }
$ok3 = Wait-HttpReady "http://127.0.0.1:7080"  $OpenTimeoutSec; if ($ok3) { Heartbeat "sourcegraph"; Log "INFO" "sourcegraph_ready" }
$ok4 = Wait-HttpReady "http://127.0.0.1:8081"  $OpenTimeoutSec; if ($ok4) { Heartbeat "structurizr"; Log "INFO" "structurizr_ready" }

# Open browser tabs once
try {
  $urls = @()
  if ($ok1) { $urls += "http://127.0.0.1:8000" }
  if ($ok2) { $urls += "http://127.0.0.1:3000" }
  if ($ok3) { $urls += "http://127.0.0.1:7080" }
  if ($ok4) { $urls += "http://127.0.0.1:8081" }
  if ($urls.Count -gt 0) {
    Log "INFO" "opening_browser" @{urls=$urls}
    Start-Process "cmd" "/c start " + ($urls -join " ")
  }
} catch { Log "WARN" "browser_open_failed" @{error=$_.Exception.Message} }

Log "INFO" "startup_complete"
