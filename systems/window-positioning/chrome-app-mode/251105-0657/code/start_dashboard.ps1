#!/usr/bin/env pwsh
# Launch Vector Management Dashboard in app mode on Monitor 3

$port = 5555
$url = "http://127.0.0.1:$port"
$dashScript = Join-Path $PSScriptRoot "..\src\dashboard_comprehensive.py"
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$userDataDir = "$env:TEMP\vms_dashboard"

# Kill any existing dashboard process
Get-Process pythonw,python -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        if ($cmdline -like "*dashboard*.py*") {
            Write-Host "Killing existing dashboard process (PID: $($_.Id))"
            Stop-Process -Id $_.Id -Force -ErrorAction Stop
        }
    } catch {}
}

# Kill ONLY dashboard Chrome instances (not all Chrome)
Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        if ($cmdline -like "*$userDataDir*") {
            Write-Host "Killing existing dashboard Chrome (PID: $($_.Id))"
            Stop-Process -Id $_.Id -Force -ErrorAction Stop
        }
    } catch {}
}

Start-Sleep -Seconds 1

# Start dashboard server in background
Write-Host "Starting dashboard server..."
Start-Process -FilePath "pythonw" -ArgumentList $dashScript -WindowStyle Hidden

# Wait for server to be ready
Write-Host "Waiting for server..."
$maxWait = 10
$waited = 0
while ($waited -lt $maxWait) {
    try {
        $response = Invoke-WebRequest -Uri "$url/api/board" -TimeoutSec 1 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host "Server ready!"
            break
        }
    } catch {
        Start-Sleep -Milliseconds 500
        $waited += 0.5
    }
}

if ($waited -ge $maxWait) {
    Write-Error "Dashboard server failed to start"
    exit 1
}

# Ensure Chrome is running (needed for window positioning to work)
$chromeRunning = Get-Process chrome -ErrorAction SilentlyContinue
if (-not $chromeRunning) {
    Write-Host "Starting Chrome first (required for window positioning)..."
    Start-Process -FilePath $chrome -ArgumentList "about:blank"
    Start-Sleep -Seconds 2
}

# Launch using EXACT working test 3 code
Write-Host "Launching dashboard on Monitor 3..."
Start-Process -FilePath $chrome -ArgumentList "--app=$url","--user-data-dir=$userDataDir","--window-position=-400,100","--window-size=1200,800"

Write-Host "Dashboard launched!"
Write-Host "URL: $url"
