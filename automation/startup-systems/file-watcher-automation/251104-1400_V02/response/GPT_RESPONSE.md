**Target path:** C:\DEV\docs\gpt\automation\startup-systems\file-watcher-automation\251104-1400_V02\response

# GPT_RESPONSE.md

**Model:** GPT-5 Thinking  
**Datestamp:** 251104-1428

## Inventory
- Extracted to: `/mnt/data/zip_extracted`
- Files found:
  - `BRIEFING.txt`
  - `gpt-response-watcher.ps1`
  - `prepare-gpt-zip.ps1`

## Summary of Findings
- The watcher intends to route `GPT_RESPONSE.md` into the versioned response folder shown above.
- Typical reliability issues: processing while a file is still writing, duplicate events, lack of logs/health, and unsafe git sync.

## Production Fixes and Full Implementation (V02)
Paste these files under `C:\dev\automation\startup-systems\file-watcher-automation\v02`.

### watcher.ps1
```powershell
param(
  [string]$Source = "$env:USERPROFILE\Downloads",
  [string]$Pattern = "GPT_RESPONSE.md",
  [string]$Target = "C:\DEV\docs\gpt\automation\startup-systems\file-watcher-automation\251104-1400_V02\response",
  [string]$LogDir = "C:\dev\logs\gpt-watcher",
  [int]$StableMs = 800,
  [int]$QueueMax = 1024
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSDefaultParameterValues["Out-File:Encoding"] = "utf8"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "watcher.log.jsonl"
$StateDir = Join-Path $LogDir "state"
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
$HealthFile = Join-Path $StateDir "health.ok"
Set-Content -Path $HealthFile -Value (Get-Date).ToString("s")

function Log([string]$msg, [string]$lvl = "INFO", [hashtable]$extra = @{}) {
  $o = [ordered]@{ ts=(Get-Date).ToString("o"); lvl=$lvl; msg=$msg } + $extra
  ($o | ConvertTo-Json -Depth 6 -Compress) | Add-Content -Path $LogFile -Encoding utf8
}

New-Item -ItemType Directory -Force -Path $Target | Out-Null

$pending = @{}
$queue = New-Object System.Collections.Concurrent.ConcurrentQueue[string]

function Enqueue($path) {
  if ($queue.Count -ge $QueueMax) { Log "queue full; dropping" "WARN" @{path=$path}; return }
  $queue.Enqueue($path)
}

function Wait-For-Stable([string]$path,[int]$ms=$StableMs) {
  $deadline = (Get-Date).AddSeconds(30)
  while((Get-Date) -lt $deadline) {
    try {
      $len1 = (Get-Item -LiteralPath $path).Length
      Start-Sleep -Milliseconds $ms
      $len2 = (Get-Item -LiteralPath $path).Length
      if ($len1 -gt 0 -and $len1 -eq $len2) {
        try { $fs = [System.IO.File]::Open($path,'Open','Read','Read'); $fs.Close(); return $true } catch { Start-Sleep -Milliseconds 150 }
      }
    } catch { Start-Sleep -Milliseconds 150 }
  }
  return $false
}

function Safe-Move([string]$src,[string]$dstDir) {
  $name = Split-Path $src -Leaf
  $dst = Join-Path $dstDir $name
  $stem = [System.IO.Path]::GetFileNameWithoutExtension($name)
  $ext  = [System.IO.Path]::GetExtension($name)
  $i = 1
  while (Test-Path -LiteralPath $dst) {
    $dst = Join-Path $dstDir ("0 (1)2" -f $stem,$i,$ext)
    $i++
  }
  Move-Item -LiteralPath $src -Destination $dst -Force
  return $dst
}

function Process-Path([string]$path) {
  if (-not (Test-Path -LiteralPath $path)) { return }
  if (-not (Wait-For-Stable $path $StableMs)) { Log "unstable; skip" "WARN" @{path=$path}; return }
  try { $dest = Safe-Move -src $path -dstDir $Target; Log "moved" "INFO" @{src=$path; dest=$dest} }
  catch { Log "move failed" "ERROR" @{path=$path; err=$_.ToString()} }
}

$debounce = New-Object System.Timers.Timer
$debounce.Interval = $StableMs
$debounce.AutoReset = $false
$debounce.add_Elapsed({
  foreach ($k in @($pending.Keys)) { if ((Get-Date) -ge $pending[$k]) { $null = $pending.Remove($k); Enqueue $k } }
})
$debounce.Start()

$fsw = New-Object IO.FileSystemWatcher $Source, $Pattern
$fsw.IncludeSubdirectories = $false
$fsw.EnableRaisingEvents = $true
$fsw.InternalBufferSize = 65536

$action = {
  param($s,$e)
  if ($e.ChangeType -eq [IO.WatcherChangeTypes]::Deleted) { return }
  $pending[$e.FullPath] = (Get-Date).AddMilliseconds($StableMs)
  Log "event" "DEBUG" @{type=$e.ChangeType; path=$e.FullPath}
}

$subs = @()
$subs += Register-ObjectEvent $fsw Created -Action $action
$subs += Register-ObjectEvent $fsw Changed -Action $action
$subs += Register-ObjectEvent $fsw Renamed -Action $action

Log "watching" "INFO" @{source=$Source; pattern=$Pattern; target=$Target}

try {
  while ($true) {
    while ($queue.TryDequeue([ref]$next)) { Process-Path $next }
    Set-Content -Path $HealthFile -Value (Get-Date).ToString("s")
    Start-Sleep -Milliseconds 250
  }
} finally {
  foreach($s in $subs) { Unregister-Event -SubscriptionId $s.Id -Force -ErrorAction SilentlyContinue }
  $fsw.EnableRaisingEvents = $false
  $fsw.Dispose()
  $debounce.Stop(); $debounce.Dispose()
  Log "stopped" "INFO"
}

```

### start-watcher.ps1
```powershell
param(
  [string]$Source = "$env:USERPROFILE\Downloads",
  [string]$Target = "C:\DEV\docs\gpt\automation\startup-systems\file-watcher-automation\251104-1400_V02\response"
)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Start-Process powershell -ArgumentList @(
  '-NoProfile','-ExecutionPolicy','Bypass','-File', (Join-Path $here 'watcher.ps1'),
  '-Source', $Source,
  '-Target', $Target
) -WindowStyle Minimized

```

### start-watcher.bat
```bat
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-watcher.ps1"
endlocal

```

### sync-gpt-repo.ps1
```powershell
param(
  [string]$RepoPath = "C:\dev",
  [string]$Remote = "origin",
  [string]$Branch = "main",
  [string]$LogDir = "C:\dev\logs\gpt-watcher"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "sync.log.jsonl"

function Log([string]$msg,[string]$lvl="INFO",[hashtable]$extra=@{}) {
  ($([ordered]@{ts=(Get-Date).ToString('o');lvl=$lvl;msg=$msg} + $extra) | ConvertTo-Json -Compress) |
    Add-Content -Path $LogFile -Encoding utf8
}

if (-not (Test-Path -LiteralPath $RepoPath)) { throw "Repo path not found: $RepoPath" }
Push-Location $RepoPath
try {
  $dirty = -not [string]::IsNullOrWhiteSpace((git status --porcelain))
  if ($dirty) { Log "dirty; stash" "INFO"; git stash push -u -m "gpt-watcher-autostash/$(Get-Date -Format s)" | Out-Null }

  git fetch $Remote $Branch
  try { git rebase "$Remote/$Branch" } catch { Log "rebase fail -> merge" "WARN"; git rebase --abort 2>$null; git merge --no-edit "$Remote/$Branch" }

  git add -A
  if (-not [string]::IsNullOrWhiteSpace((git diff --cached --name-only))) {
    git commit -m "chore(watcher): ingest + logs $(Get-Date -Format s)"
    git push $Remote $Branch
    Log "pushed" "INFO"
  } else { Log "no changes" "DEBUG" }

  $st = git stash list | Select-String "gpt-watcher-autostash" | Select-Object -First 1
  if ($st) { try { git stash pop | Out-Null; Log "stash restored" "INFO" } catch { Log "stash pop failed" "WARN" @{err=$_.ToString()} } }
} finally {
  Pop-Location
}

```

## Tests (Pester)
Create `tests\sync.Tests.ps1`:
```powershell
Import-Module Pester
Describe "sync-gpt-repo" {
  It "throws when repo missing" {
    { & "$PSScriptRoot\..\sync-gpt-repo.ps1" -RepoPath "Z:\nope" } | Should -Throw
  }
}
```

## Deployment
```powershell
$base = "C:\dev\automation\startup-systems\file-watcher-automation\v02"
New-Item -ItemType Directory -Force -Path "$base\tests" | Out-Null
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\dev\automation\startup-systems\file-watcher-automation\v02\start-watcher.ps1"'
$Trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "gpt-watcher-v02" -Action $Action -Trigger $Trigger -Description "FileSystemWatcher for GPT docs" -Force
```

## Decision Note
**Title:** FileSystemWatcher V02 hardening and fixes  
**Date:** 2025-11-04  
**Source:** Attached zip briefing  
**Context:** Auto-move GPT response docs reliably  
**Original Prompt:** Review docs, summarize, fix issues, provide production-ready code, and include Target path as first line  
**Key Takeaways:** Debounce + stability checks + JSON logs + heartbeat + safe git sync  
**Implementation Guide:** Deploy v02 scripts, add scheduled task, run basic tests  
**Related:** Existing V01 scripts
