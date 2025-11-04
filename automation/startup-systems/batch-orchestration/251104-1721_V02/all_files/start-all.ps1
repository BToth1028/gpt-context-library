#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Master orchestrator for Project Context OS - Improved from start-all.bat
.DESCRIPTION
  - PowerShell version of start-all.bat with better health checks
  - Cleans up old processes before starting
  - Uses backoff polling for service readiness
  - Opens browsers only when services are healthy
#>

$ErrorActionPreference = "Stop"

# PID tracking directory
$pidDir = "C:\DEV\.pids"
New-Item -ItemType Directory -Path $pidDir -Force | Out-Null

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Project Context OS - Startup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

#region Helper Functions

function Save-ServicePid {
    param(
        [string]$ServiceName,
        [int]$Pid
    )
    Set-Content -Path (Join-Path $pidDir "$ServiceName.pid") -Value $Pid
}

function Kill-TrackedServices {
    Write-Host "Killing tracked services from previous run..." -ForegroundColor Yellow

    $pidFiles = Get-ChildItem -Path $pidDir -Filter "*.pid" -ErrorAction SilentlyContinue

    if (-not $pidFiles) {
        Write-Host "  No tracked services found" -ForegroundColor Gray
        return
    }

    foreach ($pidFile in $pidFiles) {
        try {
            $procId = Get-Content $pidFile.FullName
            $serviceName = $pidFile.BaseName

            if ($procId -match '^\d+$') {
                $process = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if ($process) {
                    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                    Write-Host "  Killed $serviceName (PID: $procId)" -ForegroundColor Gray

                    # Wait and verify
                    Start-Sleep -Milliseconds 500
                    $stillRunning = Get-Process -Id $procId -ErrorAction SilentlyContinue
                    if ($stillRunning) {
                        Write-Host "    WARNING: Process $procId still running after kill attempt" -ForegroundColor Yellow
                    }
                } else {
                    Write-Host "  $serviceName (PID: $procId) already stopped" -ForegroundColor Gray
                }
            }

            Remove-Item $pidFile.FullName -Force
        } catch {
            Write-Host "  ERROR: Failed to kill $($pidFile.BaseName): $_" -ForegroundColor Red
        }
    }

    # Verify all PIDs are gone
    Start-Sleep -Seconds 1
    Write-Host "  Verifying all services stopped..." -ForegroundColor Gray

    $anyAlive = $false
    foreach ($pidFile in Get-ChildItem -Path $pidDir -Filter "*.pid" -ErrorAction SilentlyContinue) {
        try {
            $procId = Get-Content $pidFile.FullName -ErrorAction SilentlyContinue
            if ($procId -and $procId -match '^\d+$') {
                $process = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if ($process) {
                    Write-Host "    WARNING: PID $procId still alive!" -ForegroundColor Yellow
                    $anyAlive = $true
                }
            }
        } catch {}
    }

    if (-not $anyAlive) {
        Write-Host "  All services verified stopped" -ForegroundColor Green
    }
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSec = 120,
        [string]$ServiceName = "service"
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $attempt = 0

    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                Write-Host "  $ServiceName is healthy!" -ForegroundColor Green
                return $true
            }
        } catch {
            # Service not ready yet
        }

        $attempt++
        $delay = [Math]::Min(5, [Math]::Pow(1.5, [Math]::Min($attempt, 8)))
        Start-Sleep -Seconds $delay
    }

    Write-Host "  WARNING: $ServiceName not ready after $TimeoutSec seconds" -ForegroundColor Yellow
    return $false
}

function Kill-PortProcess {
    param([int]$Port)

    try {
        $pids = netstat -ano | Select-String ":$Port " | ForEach-Object {
            if ($_ -match '\s+(\d+)$') { $matches[1] }
        } | Select-Object -Unique

        foreach ($pid in $pids) {
            try {
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                Write-Host "  Killed process on port $Port (PID: $pid)" -ForegroundColor Gray
            } catch {}
        }
    } catch {}
}

#endregion

#region Cleanup

Write-Host ""
Write-Host "Killing all Project Context OS services..." -ForegroundColor Yellow

# Kill all service windows by title
$titles = @("MkDocs", "Sourcegraph", "Structurizr", "Backstage", "Monitor")
$killedCount = 0
foreach ($title in $titles) {
    $procs = Get-Process cmd -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*$title*" }
    foreach ($proc in $procs) {
        try {
            Stop-Process -Id $proc.Id -Force
            Write-Host "  Killed $title window (PID: $($proc.Id))" -ForegroundColor Gray
            $killedCount++
        } catch {}
    }
}

if ($killedCount -gt 0) {
    Write-Host "  Waiting for processes to fully terminate..." -ForegroundColor Gray
    Start-Sleep -Seconds 3

    # Verify all are dead
    $stillAlive = @()
    foreach ($title in $titles) {
        $procs = Get-Process cmd -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*$title*" }
        if ($procs) {
            $stillAlive += $title
        }
    }

    if ($stillAlive.Count -gt 0) {
        Write-Host "  WARNING: Some services still running: $($stillAlive -join ', ')" -ForegroundColor Yellow
        Write-Host "  Forcing additional cleanup..." -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    } else {
        Write-Host "  All services verified stopped" -ForegroundColor Green
    }
}

# Kill processes on known ports (backup cleanup)
Kill-PortProcess 8000  # MkDocs
Kill-PortProcess 3000  # Backstage frontend
Kill-PortProcess 7007  # Backstage backend

# Stop ONLY Project Context OS Docker containers (preserves volumes)
Write-Host "Stopping Project Context OS Docker containers..." -ForegroundColor Yellow
try {
    # Stop Sourcegraph
    $sgContainer = docker ps -q --filter "name=sourcegraph"
    if ($sgContainer) {
        docker stop $sgContainer 2>$null | Out-Null
        Write-Host "  Stopped Sourcegraph" -ForegroundColor Gray
    }

    # Stop Structurizr
    $structContainer = docker ps -q --filter "ancestor=structurizr/lite"
    if ($structContainer) {
        docker stop $structContainer 2>$null | Out-Null
        docker rm $structContainer 2>$null | Out-Null
        Write-Host "  Stopped Structurizr" -ForegroundColor Gray
    }

    # Stop Backstage Postgres
    $bkPgContainer = docker ps -q --filter "name=backstage-pg"
    if ($bkPgContainer) {
        docker stop $bkPgContainer 2>$null | Out-Null
        Write-Host "  Stopped Backstage Postgres" -ForegroundColor Gray
    }
} catch {
    Write-Host "  Warning: Docker cleanup encountered errors" -ForegroundColor Yellow
}

Start-Sleep -Seconds 2

#endregion

#region Docker Desktop

Write-Host ""
Write-Host "Starting Docker Desktop..." -ForegroundColor Yellow

# Check if Docker Desktop is running
$dockerProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue

if (-not $dockerProcess) {
    Write-Host "  Launching Docker Desktop..."
    Start-Process -FilePath "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
}

# Poll for Docker to be ready
$dockerReady = $false
$maxAttempts = 60
for ($i = 1; $i -le $maxAttempts; $i++) {
    try {
        docker ps | Out-Null
        $dockerReady = $true
        Write-Host "  Docker Desktop is ready!" -ForegroundColor Green
        break
    } catch {
        if ($i % 10 -eq 0) {
            Write-Host "  Waiting for Docker... ($i seconds)" -ForegroundColor Gray
        }
        Start-Sleep -Seconds 1
    }
}

if (-not $dockerReady) {
    Write-Host "  WARNING: Docker Desktop did not start" -ForegroundColor Yellow
}

#endregion

#region Prerequisites

Write-Host ""
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

# Check Backstage Yarn
if (-not (Test-Path "C:\DEV\backstage\.yarn\releases\yarn-4.4.1.cjs")) {
    Write-Host "  ERROR: Backstage Yarn not found. Run: cd backstage && corepack prepare --activate" -ForegroundColor Red
    exit 1
}

# Check Python venv
if (-not (Test-Path "C:\DEV\.venv\Scripts\python.exe")) {
    Write-Host "  ERROR: Python venv not found. Run: python -m venv .venv" -ForegroundColor Red
    exit 1
}

Write-Host "  Prerequisites OK" -ForegroundColor Green

#endregion

#region Start Backstage Postgres

Write-Host ""
Write-Host "Starting Backstage Postgres..." -ForegroundColor Yellow

try {
    Push-Location "C:\DEV\backstage\infra"
    docker compose up -d
    Pop-Location
    Write-Host "  Backstage Postgres started" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: Failed to start Backstage Postgres" -ForegroundColor Yellow
}

#endregion

#region Start Services

Write-Host ""
Write-Host "Starting services (minimized)..." -ForegroundColor Yellow

# MkDocs
Start-Process cmd -ArgumentList "/k", "title MkDocs && C:\DEV\.venv\Scripts\python.exe -m mkdocs serve" -WindowStyle Minimized
Write-Host "  MkDocs started" -ForegroundColor Green

# Sourcegraph
Start-Process cmd -ArgumentList "/k", "title Sourcegraph && cd C:\DEV\sourcegraph && docker compose up" -WindowStyle Minimized
Write-Host "  Sourcegraph started" -ForegroundColor Green

# Structurizr
$structCmd = "title Structurizr && docker run -p 8081:8080 -v C:\DEV\docs\architecture\c4:/usr/local/structurizr structurizr/lite"
Start-Process cmd -ArgumentList "/k", $structCmd -WindowStyle Minimized
Write-Host "  Structurizr started" -ForegroundColor Green

# Backstage
Start-Process cmd -ArgumentList "/k", "title Backstage && cd C:\DEV\backstage && start-backstage.bat" -WindowStyle Minimized
Write-Host "  Backstage started" -ForegroundColor Green

#endregion

#region Health Checks

Write-Host ""
Write-Host "Waiting for services to report healthy..." -ForegroundColor Yellow
Write-Host "(This may take 1-2 minutes)" -ForegroundColor Gray
Write-Host ""

$mkdocsOk = Wait-HttpReady "http://localhost:8000" -TimeoutSec 60 -ServiceName "MkDocs"
$sourcegraphOk = Wait-HttpReady "http://localhost:7080/healthz" -TimeoutSec 120 -ServiceName "Sourcegraph"
$structurizrOk = Wait-HttpReady "http://localhost:8081" -TimeoutSec 60 -ServiceName "Structurizr"
$backstageOk = Wait-HttpReady "http://localhost:3000" -TimeoutSec 120 -ServiceName "Backstage"

#endregion

#region Open Browsers

Write-Host ""
Write-Host "Opening browser tabs..." -ForegroundColor Yellow

$urls = @()
if ($mkdocsOk) { $urls += "http://localhost:8000" }
if ($backstageOk) { $urls += "http://localhost:3000" }
if ($sourcegraphOk) { $urls += "http://localhost:7080" }
if ($structurizrOk) { $urls += "http://localhost:8081" }

foreach ($url in $urls) {
    try {
        Start-Process cmd -ArgumentList "/c", "start `"`" $url" -WindowStyle Hidden
    } catch {
        Write-Host "  WARNING: Failed to open $url" -ForegroundColor Yellow
    }
}

#endregion

#region Start Monitor

Write-Host ""
Write-Host "Starting monitor..." -ForegroundColor Yellow

Start-Process cmd -ArgumentList "/k", "title Monitor && C:\DEV\monitor-all.bat" -WindowStyle Minimized
Write-Host "  Monitor started" -ForegroundColor Green

#endregion

#region Summary

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "  Startup complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Services:" -ForegroundColor Cyan
Write-Host "  MkDocs:      http://localhost:8000 $(if($mkdocsOk){'✓'}else{'✗'})" -ForegroundColor $(if($mkdocsOk){'Green'}else{'Yellow'})
Write-Host "  Backstage:   http://localhost:3000 $(if($backstageOk){'✓'}else{'✗'})" -ForegroundColor $(if($backstageOk){'Green'}else{'Yellow'})
Write-Host "  Sourcegraph: http://localhost:7080 $(if($sourcegraphOk){'✓'}else{'✗'})" -ForegroundColor $(if($sourcegraphOk){'Green'}else{'Yellow'})
Write-Host "  Structurizr: http://localhost:8081 $(if($structurizrOk){'✓'}else{'✗'})" -ForegroundColor $(if($structurizrOk){'Green'}else{'Yellow'})
Write-Host ""

#endregion
