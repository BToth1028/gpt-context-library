#!/usr/bin/env pwsh
<#
.SYNOPSIS
Watches Downloads folder and automatically moves GPT responses to correct version folder

.DESCRIPTION
Polls Downloads folder for GPT_RESPONSE.md and moves it to the target path specified in the file.
Runs in one-shot mode - exits after successfully moving a file.

.EXAMPLE
.\scripts\gpt-response-watcher.ps1
#>

param(
    [string]$Source = "$env:USERPROFILE\Downloads",
    [string]$Pattern = "GPT_RESPONSE.md",
    [int]$CheckInterval = 2
)

# Structured logging
function Log([string]$msg, [string]$lvl="INFO") {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $lvl`: $msg" -ForegroundColor $(
        switch($lvl) {
            "INFO" { "Cyan" }
            "WARN" { "Yellow" }
            "ERROR" { "Red" }
            "SUCCESS" { "Green" }
        }
    )
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
function Move-FileToTarget([string]$path) {
    $maxRetries = 6
    $delay = 0.5

    for($i=1; $i -le $maxRetries; $i++) {
        try {
            # Wait for file to be fully written
            Start-Sleep -Milliseconds 500

            # Extract target path from document
            $targetPath = Get-TargetPathFromFile $path
            if (-not $targetPath) {
                Log "Cannot determine target path from document" "ERROR"
                return $false
            }

            # Create target directory if needed
            if (-not (Test-Path $targetPath)) {
                New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
                Log "Created directory: $targetPath" "INFO"
            }

            $name = Split-Path $path -Leaf
            $dest = Join-Path $targetPath $name

            # Move the file
            Move-Item -LiteralPath $path -Destination $dest -Force

            # Extract version name from path for display
            $versionMatch = $targetPath -match '(\d{6}-\d{4}_V\d{2})'
            $versionName = if ($matches) { $matches[1] } else { "response folder" }

            Log "Moved '$name' -> '$versionName/response/'" "SUCCESS"

            # Show Windows notification
            try {
                Add-Type -AssemblyName System.Windows.Forms
                $notification = New-Object System.Windows.Forms.NotifyIcon
                $notification.Icon = [System.Drawing.SystemIcons]::Information
                $notification.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
                $notification.BalloonTipText = "File saved to: $versionName/response/"
                $notification.BalloonTipTitle = "GPT Response Saved"
                $notification.Visible = $true
                $notification.ShowBalloonTip(3000)
            } catch {
                # Silently fail notification, not critical
            }

            return $true
        } catch {
            if ($i -eq $maxRetries) {
                Log "Failed to move '$path' after $maxRetries attempts: $_" "ERROR"
                return $false
            }
            Start-Sleep -Seconds $delay
            $delay = [Math]::Min($delay * 2, 8)
        }
    }
    return $false
}

Log "Watcher started (one-shot mode)" "INFO"
Log "Source: $Source" "INFO"
Log "Pattern: $Pattern" "INFO"
Log "Check interval: $CheckInterval seconds" "INFO"
Log "Waiting for GPT_RESPONSE.md file..." "INFO"

$timeout = 3600 # 1 hour max wait
$elapsed = 0
$found = $false

while (-not $found -and $elapsed -lt $timeout) {
    # Check if file exists
    $targetFile = Join-Path $Source $Pattern

    if (Test-Path $targetFile) {
        Log "Found $Pattern in Downloads!" "INFO"

        # Try to move it
        $result = Move-FileToTarget $targetFile

        if ($result) {
            Log "File moved successfully. Shutting down watcher." "SUCCESS"
            $found = $true
        } else {
            Log "Failed to move file. Will retry..." "WARN"
        }
    }

    if (-not $found) {
        Start-Sleep -Seconds $CheckInterval
        $elapsed += $CheckInterval

        # Show a "still alive" message every 5 minutes
        if ($elapsed % 300 -eq 0) {
            Log "Still waiting for $Pattern... ($([math]::Round($elapsed/60)) minutes elapsed)" "INFO"
        }
    }
}

if (-not $found) {
    Log "Timeout reached without receiving file. Shutting down watcher." "WARN"
}

Log "Watcher stopped" "INFO"
