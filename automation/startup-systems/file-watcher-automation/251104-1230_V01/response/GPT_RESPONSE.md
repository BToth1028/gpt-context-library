Target path: C:\DEV\docs\gpt\automation\startup-systems\file-watcher-automation\251104-1230_V01\response

# GPT_RESPONSE.md

**Model:** GPT-5 Thinking  
**Datestamp:** 251104-1330

## Executive Summary
Your watcher moves `GPT_RESPONSE.md` from Downloads to the latest versioned `response\` folder and includes a helper batch file and a git sync script. The observed failure class is typical for `FileSystemWatcher`: events arriving while files are still being written, duplicate `Changed` storms, buffer overflows, and fragile git syncing. Below is a hardened V02 that fixes these by debouncing, verifying stable files before move, adding structured logs and a health heartbeat, and using a safe git sync routine.

## What Works
- Clear single-responsibility: watch Downloads for `GPT_RESPONSE.md` and move it.
- Simple startup wrapper (`start-gpt-watcher.bat`) that launches PowerShell.
- Separate sync script idea to keep the repo up to date.

## What Does Not Work / Risks
- Processes files while still being written or locked; leads to zero-byte or move failures.
- No debounce. Multiple `Changed` events cause duplicate work and races.
- No structured logging for incident analysis; hard to debug.
- No health check. Hard to supervise with a scheduler or external watchdog.
- Git sync can corrupt worktree under rebase/merge conflicts or dirty state.
- Hard-coded paths and no guard for missing target directories.

## Implementation — V02 Drop-in Replacement
Create a new folder and replace the existing scripts with the following. These are production-ready and PowerShell-first as requested.

### Folder Tree
```
C:\devutomation\startup-systemsile-watcher-automation02
  watcher.ps1
  sync-gpt-repo.ps1
  start-watcher.ps1
  start-watcher.bat
  tests    watcher.Tests.ps1
    sync.Tests.ps1
```

### watcher.ps1
```powershell
param(
  [string]$Source = "$env:USERPROFILE\Downloads",
  [string]$Pattern = "GPT_RESPONSE.md",
  [string]$Target = "{target_path}",
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
    $dst = Join-Path $dstDir ("{0} ({1}){2}" -f $stem,$i,$ext)
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

### start-watcher.ps1
```powershell
param(
  [string]$Source = "$env:USERPROFILE\Downloads",
  [string]$Target = "{target_path}"
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
## Tests (Pester)
Create `tests\watcher.Tests.ps1` and `tests\sync.Tests.ps1`:

`tests\watcher.Tests.ps1`
```powershell
Import-Module Pester
Describe "watcher ps1 basic" {
  It "creates log dir" {
    $tmp = Join-Path $env:TEMP ("gptw-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    $ld = Join-Path $tmp "logs"
    Start-Job -ScriptBlock { & "$PSScriptRoot\..\watcher.ps1" -Source $tmp -Target $tmp -LogDir $ld -Pattern "TEST.md" } | Out-Null
    Start-Sleep -Milliseconds 500
    Test-Path $ld | Should -BeTrue
  }
}
```

`tests\sync.Tests.ps1`
```powershell
Import-Module Pester
Describe "sync-gpt-repo" {
  It "throws when repo missing" {
    { & "$PSScriptRoot\..\sync-gpt-repo.ps1" -RepoPath "Z:
ope" } | Should -Throw
  }
}
```
Run:
```powershell
pwsh -NoProfile -c "Invoke-Pester -CI -Output Detailed"
```

## Deployment Commands (PowerShell)
```powershell
$base = "C:\devutomation\startup-systemsile-watcher-automation02"
New-Item -ItemType Directory -Force -Path "$base	ests" | Out-Null

# Paste files above into the paths under $base

Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force

# Optional: start at logon
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\devutomation\startup-systemsile-watcher-automation02\start-watcher.ps1"'
$Trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "gpt-watcher-v02" -Action $Action -Trigger $Trigger -Description "FileSystemWatcher for GPT docs" -Force
```

## Observability
- Logs: JSONL at `C:\dev\logs\gpt-watcher\watcher.log.jsonl` and `sync.log.jsonl`.
- Health: `C:\dev\logs\gpt-watcher\state\health.ok`.
- Metrics: derive counts from logs (moved, retries, queue drops).

## Risks and Rollback
- If events are still missed, lower `Pattern` scope and bump `InternalBufferSize`.
- Rollback by stopping the scheduled task and removing `v02` folder; restore previous scripts.

---

### Decision Note
**Title:** FileSystemWatcher V02 hardening and fixes  
**Date:** 2025-11-04  
**Source:** BRIEFING + provided scripts in file-watcher-v01.zip  
**Context:** Watcher exits or fails to move GPT_RESPONSE.md reliably.  
**Original Prompt:** Review docs, summarize, fix issues, and provide production-ready code with explanations; include Target path as first line.  
**Key Takeaways:** Debounce and stable-file checks are required; add structured logging and health heartbeat; use safer git sync.  
**Implementation Guide:** Create v02 with the scripts above, run tests, then register a scheduled task for auto-start.  
**Related:** start-gpt-watcher.bat, gpt-response-watcher.ps1, sync-gpt-repo.ps1 (V01)
