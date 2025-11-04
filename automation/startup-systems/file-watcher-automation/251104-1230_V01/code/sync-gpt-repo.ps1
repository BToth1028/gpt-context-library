#!/usr/bin/env pwsh
<#
.SYNOPSIS
Sync GPT Context Library to GitHub

.DESCRIPTION
Commits and pushes any new GPT summaries to the public GitHub repository.
Use this after creating new GPT summaries to keep the public repo updated.

.PARAMETER Message
Commit message (optional, will prompt if not provided)

.EXAMPLE
.\scripts\sync-gpt-repo.ps1 -Message "Add: startup-cleanup GPT summary"

.EXAMPLE
.\scripts\sync-gpt-repo.ps1
#>

param(
    [string]$Message = ""
)

$gptPath = "C:\DEV\docs\gpt"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Sync GPT Context Library" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if git repo exists
if (-not (Test-Path "$gptPath\.git")) {
    Write-Host "✗ Git repository not initialized" -ForegroundColor Red
    Write-Host ""
    Write-Host "Run this first:" -ForegroundColor Yellow
    Write-Host "  .\scripts\init-gpt-repo.ps1" -ForegroundColor Gray
    exit 1
}

# Navigate to gpt folder
Push-Location $gptPath

# Check for changes
Write-Host "Checking for changes..." -ForegroundColor Cyan
$status = git status --porcelain

if (-not $status) {
    Write-Host "✓ No changes to commit" -ForegroundColor Green
    Write-Host ""
    Write-Host "Repository is up to date!" -ForegroundColor Green
    Pop-Location
    exit 0
}

# Show changes
Write-Host ""
Write-Host "Changes to be committed:" -ForegroundColor Yellow
git status --short
Write-Host ""

# Get commit message if not provided
if (-not $Message) {
    $Message = Read-Host "Enter commit message (or press Enter for auto-generated)"
    if (-not $Message) {
        # Auto-generate message based on changes
        $added = (git status --porcelain | Where-Object { $_ -match '^\?\?' }).Count
        $modified = (git status --porcelain | Where-Object { $_ -match '^ M' }).Count
        $Message = "Update: $added new files, $modified modified"
    }
}

# Stage all changes
Write-Host "→ Staging changes..." -ForegroundColor Cyan
git add .

# Commit
Write-Host "→ Committing..." -ForegroundColor Cyan
git commit -m $Message

# Push
Write-Host "→ Pushing to GitHub..." -ForegroundColor Cyan
$pushResult = git push 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "✗ Push failed" -ForegroundColor Red
    Write-Host $pushResult -ForegroundColor Red
    Write-Host ""
    Write-Host "If you haven't set up the remote yet:" -ForegroundColor Yellow
    Write-Host "  git remote add origin https://github.com/YOUR_USERNAME/gpt-context-library.git" -ForegroundColor Gray
    Write-Host "  git push -u origin main" -ForegroundColor Gray
    Pop-Location
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Successfully synced to GitHub!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Get commit hash and URL
$commitHash = git log -1 --format=%H
$commitUrl = "https://github.com/BToth1028/gpt-context-library/commit/$commitHash"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  COPY THIS PROMPT FOR CHATGPT" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Please review this GPT summary commit:"
Write-Host "$commitUrl"
Write-Host ""
Write-Host "**Tasks:**"
Write-Host "1. Review all documentation in the zip/ folder (note the **Target path:** in the briefing)"
Write-Host "2. Summarize what works ✅ and what doesn't work ❌"
Write-Host "3. Provide complete code fixes for all apparent issues"
Write-Host "4. Suggest improvements and additional features that would enhance the system"
Write-Host "5. Include implementation code for all suggestions"
Write-Host ""
Write-Host "Please be thorough and provide production-ready code with explanations."
Write-Host ""
Write-Host "**IMPORTANT**: When creating your response document:" -ForegroundColor Yellow
Write-Host "- Name it: GPT_RESPONSE.md" -ForegroundColor Green
Write-Host "- Include the **Target path:** from the briefing as the FIRST LINE of your response" -ForegroundColor Green
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Start the watcher automatically
Write-Host "Starting response watcher..." -ForegroundColor Cyan

# Kill any existing watcher processes
Get-Process | Where-Object {
    try {
        $_.MainModule.FileName -like "*powershell.exe" -and
        (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like "*gpt-response-watcher*"
    } catch {
        $false
    }
} | Stop-Process -Force -ErrorAction SilentlyContinue

# Start new watcher in background
$watcherScript = Join-Path $PSScriptRoot "gpt-response-watcher.ps1"
Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$watcherScript`"" -WindowStyle Minimized

Write-Host "✓ Watcher started (one-shot mode)" -ForegroundColor Green
Write-Host "  - Waiting for GPT_RESPONSE.md in Downloads" -ForegroundColor Gray
Write-Host "  - Will auto-move and exit when file arrives" -ForegroundColor Gray
Write-Host ""

Pop-Location
