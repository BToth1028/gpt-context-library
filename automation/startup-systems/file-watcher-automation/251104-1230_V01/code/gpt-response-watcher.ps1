#!/usr/bin/env pwsh
<#
.SYNOPSIS
Watches Downloads folder and automatically moves GPT responses to correct version folder

.DESCRIPTION
File system watcher that monitors Downloads for GPT_RESPONSE.md files and
moves them to the most recent GPT summary version's response/ folder.

.EXAMPLE
.\scripts\gpt-response-watcher.ps1

.EXAMPLE
# Register as startup task
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\DEV\scripts\gpt-response-watcher.ps1"'
$Trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "gpt-response-watcher" -Action $Action -Trigger $Trigger -Description "Auto-move GPT responses to correct version folder" -Force
#>

param(
    [string]$Source = "$env:USERPROFILE\Downloads",
    [string]$BaseTarget = "C:\DEV\docs\gpt",
    [string]$Pattern = "GPT_RESPONSE.md"
)

# Structured logging
function Log([string]$msg, [string]$lvl="INFO") {
    $o = [pscustomobject]@{
        ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        level = $lvl
        msg = $msg
    }
    Write-Host "[$($o.ts)] $($o.level): $($o.msg)" -ForegroundColor $(
        switch($lvl) {
            "INFO" { "Cyan" }
            "WARN" { "Yellow" }
            "ERROR" { "Red" }
            "SUCCESS" { "Green" }
        }
    )
}

# Find most recent version folder
function Get-LatestVersionFolder {
    $versionFolders = Get-ChildItem -Path $BaseTarget -Recurse -Directory | Where-Object {
        $_.Name -match '^\d{6}-\d{4}_V\d{2}$'
    } | Sort-Object FullName -Descending

    if ($versionFolders.Count -eq 0) {
        return $null
    }

    return $versionFolders[0]
}

# Extract target path from document
function Get-TargetPathFromFile([string]$filePath) {
    try {
        $content = Get-Content -Path $filePath -Raw
        if ($content -match '\*\*Target path:\*\*\s*(.+?)(?:\r?\n|$)') {
            return $matches[1].Trim()
        }
        Log "No target path found in document" "WARN"
        return $null
    } catch {
        Log "Error reading file: $_" "ERROR"
        return $null
    }
}

# Move with retry and backoff
function Move-WithRetry([string]$path, [int]$max=6) {
    $delay = 0.5
    for($i=1; $i -le $max; $i++) {
        try {
            # Wait for file to be fully written
            Start-Sleep -Milliseconds 500

            # Extract target path from document
            $targetPath = Get-TargetPathFromFile $path
            if (-not $targetPath) {
                Log "Cannot determine target path from document" "ERROR"
                return
            }

            # Create target directory if needed
            if (-not (Test-Path $targetPath)) {
                New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
                Log "Created directory: $targetPath" "INFO"
            }

            $name = Split-Path $path -Leaf
            $dest = Join-Path $targetPath $name

            # Wait a moment for file to be fully written
            Start-Sleep -Milliseconds 500

            Move-Item -LiteralPath $path -Destination $dest -Force

            # Extract version name from path for display
            $versionMatch = $targetPath -match '(\\d{6}-\d{4}_V\d{2})'
            $versionName = if ($matches) { $matches[1] } else { "response folder" }

            Log "Moved '$name' -> '$versionName/response/'" "SUCCESS"

            # Show notification
            $title = "GPT Response Saved"
            $message = "File saved to: $versionName/response/"

            # Windows notification (optional, won't break if fails)
            try {
                Add-Type -AssemblyName System.Windows.Forms
                $notification = New-Object System.Windows.Forms.NotifyIcon
                $notification.Icon = [System.Drawing.SystemIcons]::Information
                $notification.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
                $notification.BalloonTipText = $message
                $notification.BalloonTipTitle = $title
                $notification.Visible = $true
                $notification.ShowBalloonTip(3000)
            } catch {
                # Silently fail notification, not critical
            }

            # Signal success - watcher will exit after moving file
            return $true
        } catch {
            if ($i -eq $max) {
                Log "Failed to move '$path' after $max attempts: $_" "ERROR"
                return $false
            }
            Start-Sleep -Seconds $delay
            $delay = [Math]::Min($delay * 2, 8)
        }
    }
    return $false
}

# Create watcher
$fsw = New-Object IO.FileSystemWatcher $Source, $Pattern
$fsw.IncludeSubdirectories = $false
$fsw.EnableRaisingEvents = $true

# Store script path and success flag
$scriptPath = $PSCommandPath
$global:fileMovedSuccessfully = $false

# Register event handler
Register-ObjectEvent $fsw Created -Action {
    $path = $Event.SourceEventArgs.FullPath

    # Re-import functions
    $scriptContent = Get-Content $using:scriptPath -Raw
    Invoke-Expression $scriptContent

    # Move file and check result
    $result = Move-WithRetry $path

    # Signal parent script to exit if successful
    if ($result) {
        $global:fileMovedSuccessfully = $true
    }
} | Out-Null

Log "Watcher started (one-shot mode)" "INFO"
Log "Source: $Source" "INFO"
Log "Pattern: $Pattern" "INFO"
Log "Waiting for GPT_RESPONSE.md file..." "INFO"
Log "Will automatically exit after moving file" "INFO"

# Check every second for file move completion
$timeout = 3600 # 1 hour max wait
$elapsed = 0

while (-not $global:fileMovedSuccessfully -and $elapsed -lt $timeout) {
    Start-Sleep -Seconds 1
    $elapsed++

    # Show a "still alive" message every 5 minutes
    if ($elapsed % 300 -eq 0) {
        Log "Still waiting for GPT_RESPONSE.md... ($([math]::Round($elapsed/60)) minutes elapsed)" "INFO"
    }
}

if ($global:fileMovedSuccessfully) {
    Log "File moved successfully. Shutting down watcher." "SUCCESS"
} else {
    Log "Timeout reached without receiving file. Shutting down watcher." "WARN"
}

# Cleanup
$fsw.Dispose()
Log "Watcher stopped" "INFO"
