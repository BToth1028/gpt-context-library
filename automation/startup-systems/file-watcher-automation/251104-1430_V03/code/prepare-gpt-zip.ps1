#!/usr/bin/env pwsh
<#
.SYNOPSIS
Prepare latest GPT briefing zip and start watcher

.DESCRIPTION
Creates zip.zip for the most recent version folder and starts the response watcher.
Use this when you want to send the zip directly to ChatGPT without GitHub sync.
#>

$gptPath = "C:\DEV\docs\gpt"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Prepare GPT Zip" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Find the most recent version folder
$latestVersion = Get-ChildItem -Path $gptPath -Recurse -Directory | Where-Object {
    $_.Name -match '^\d{6}-\d{4}_V\d{2}$'
} | Sort-Object Name -Descending | Select-Object -First 1

if (-not $latestVersion) {
    Write-Host "[ERROR] No version folders found" -ForegroundColor Red
    exit 1
}

Write-Host "Latest version: $($latestVersion.Name)" -ForegroundColor Cyan
Write-Host ""

# Create zip.zip
$versionPath = $latestVersion.FullName
$zipFile = Join-Path $versionPath "zip.zip"

Write-Host "Creating zip.zip..." -ForegroundColor Cyan

# Get all files from subfolders (code, request, logs, response, etc.)
$filesToZip = Get-ChildItem -Path $versionPath -Recurse -File | Where-Object {
    $_.Directory.Name -ne $_.Directory.Parent.Name -and
    $_.FullName -ne $zipFile
}

if (-not $filesToZip) {
    Write-Host "[ERROR] No files found to zip" -ForegroundColor Red
    exit 1
}

# Remove old zip if exists
if (Test-Path $zipFile) {
    Remove-Item $zipFile -Force
}

# Create new zip
Compress-Archive -Path ($filesToZip | Select-Object -ExpandProperty FullName) -DestinationPath $zipFile -Force
Write-Host "[OK] Created zip.zip" -ForegroundColor Green
Write-Host ""

# Kill any existing watcher using PID file
Write-Host "Starting response watcher..." -ForegroundColor Cyan
$pidFile = "C:\DEV\.watcher.pid"
if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($oldPid) {
        Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# Start new watcher in background and capture PID
$watcherScript = Join-Path $PSScriptRoot "gpt-response-watcher.ps1"
$argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $watcherScript)
$process = Start-Process powershell -ArgumentList $argList -WindowStyle Minimized -PassThru

# Save PID to file
$process.Id | Out-File -FilePath $pidFile -Force

Write-Host "[OK] Watcher started (PID: $($process.Id))" -ForegroundColor Green
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host "  Ready!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Read the briefing to get the target path
$briefingPath = Join-Path $versionPath "request\BRIEFING.txt"
$targetPath = "Unknown"
if (Test-Path $briefingPath) {
    $briefingContent = Get-Content $briefingPath -Raw
    if ($briefingContent -match '\*\*Target path:\*\*\s*(.+?)(?:\r?\n|$)') {
        $targetPath = $matches[1].Trim()
    }
}

# Build the prompt text
$prompt = @"
Please review the attached zip file containing a GPT briefing.

Tasks:
1. Review all documentation (note the Target path in the briefing)
2. Summarize what works and what does not work
3. Provide complete code fixes for all apparent issues
4. Suggest improvements and additional features
5. Include implementation code for all suggestions

Please be thorough and provide production-ready code with explanations.

IMPORTANT: When creating your response document:
- Name it: GPT_RESPONSE.md
- Include this as the FIRST LINE: **Target path:** $targetPath
"@

# Copy prompt to clipboard
Set-Clipboard -Value $prompt

# Open the version folder in Explorer and select the zip file
explorer /select,"$zipFile"

Write-Host "========================================" -ForegroundColor Green
Write-Host "  READY TO SEND TO CHATGPT" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "[OK] Prompt copied to clipboard!" -ForegroundColor Green
Write-Host "[OK] Explorer opened with zip.zip" -ForegroundColor Green
Write-Host "[OK] Watcher ready for response" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Upload zip.zip to ChatGPT" -ForegroundColor White
Write-Host "2. Paste (Ctrl+V) the prompt" -ForegroundColor White
Write-Host "3. Save response as GPT_RESPONSE.md in Downloads" -ForegroundColor White
Write-Host ""
