# code/stop-all-services.ps1
#!/usr/bin/env pwsh
<#
Stops Project Context OS services safely and fast on Windows 11 + PowerShell 7+.

Targets:
- MkDocs (port 8000; python.exe -m mkdocs serve)
- Backstage frontend (port 3000; node/yarn) and backend (port 7007)
- Sourcegraph frontend (port 7080; docker compose stack at -SourcegraphComposeDir)
- Structurizr Lite (port 8081; container 'structurizr/lite')

Rules:
- Kill by port owner PID, then kill the process tree.
- For dockerized services, stop only their stack/container; do not 'down -v'.
- Verify all target ports are free before returning (≤ TimeoutSec).
#>

param(
  [string]$SourcegraphComposeDir = "C:\DEV\sourcegraph",
  [int[]]$Ports = @(8000,3000,7007,7080,8081),
  [int]$TimeoutSec = 10
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-PortOwnerPids([int[]]$ports) {
  try {
    Get-NetTCPConnection -ErrorAction SilentlyContinue |
      Where-Object { $_.LocalPort -in $ports } |
      Select-Object -ExpandProperty OwningProcess -Unique |
      Where-Object { $_ -and $_ -gt 0 } |
      Sort-Object -Unique
  } catch { @() }
}

function Stop-PidTree([int]$pid) {
  if (-not $pid) { return }
  try {
    Start-Process -FilePath "taskkill.exe" -ArgumentList "/PID $pid /T /F" -WindowStyle Hidden -NoNewWindow | Out-Null
  } catch { }
}

function Stop-ByCommandMatch([string[]]$patterns) {
  try {
    Get-CimInstance Win32_Process | ForEach-Object {
      $cmd = $_.CommandLine
      $path = $_.ExecutablePath
      foreach ($pat in $patterns) {
        if (($cmd -and $cmd -match $pat) -or ($path -and $path -match $pat)) {
          Stop-PidTree $_.ProcessId
          break
        }
      }
    }
  } catch { }
}

function Stop-StructurizrContainers {
  try {
    & docker ps --format "{{.ID}} {{.Image}}" 2>$null |
      Where-Object { $_ -match "structurizr/lite" } |
      ForEach-Object { ($_ -split " ")[0] } |
      ForEach-Object { & docker stop $_ 2>$null | Out-Null }
  } catch { }
}

function Stop-SourcegraphStack([string]$dir) {
  if (-not (Test-Path $dir)) { return }
  try {
    Push-Location $dir
    & docker compose ps --status running --services 2>$null | ForEach-Object {
      & docker compose stop $_ 2>$null | Out-Null
    }
  } catch { } finally { Pop-Location }
}

function Ports-Free([int[]]$ports) {
  -not (Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in $ports })
}

function Stop-AllProjectContextServices {
  param(
    [int[]]$TargetPorts = $Ports,
    [string]$ComposeDir = $SourcegraphComposeDir,
    [int]$VerifyTimeoutSec = $TimeoutSec
  )

  # 1) Stop dockerized services first
  Stop-StructurizrContainers
  Stop-SourcegraphStack -dir $ComposeDir

  # 2) Kill known process families by command pattern
  Stop-ByCommandMatch @(
    "mkdocs\s+serve",            # MkDocs
    "\\backstage\\",             # Backstage path hint
    "yarn(\.cjs)?\s+start",      # Backstage front-end runner
    "node\.exe.*backstage",      # Backstage node
    "monitor-all\.bat",          # legacy monitor
    "start-backstage\.bat"       # legacy backstage starter
  )

  # 3) Kill owners of target ports and their trees
  foreach ($pid in (Get-PortOwnerPids -ports $TargetPorts)) { Stop-PidTree $pid }

  # 4) Verify ports are free with bounded backoff (≤ VerifyTimeoutSec)
  $deadline = (Get-Date).AddSeconds($VerifyTimeoutSec)
  $attempt = 0
  while ((Get-Date) -lt $deadline) {
    if (Ports-Free -ports $TargetPorts) { return $true }
    $delay = [math]::Min(800, [math]::Pow(2,[math]::Min($attempt,5)) * 50)  # 50..800ms
    Start-Sleep -Milliseconds $delay
    $attempt++
  }
  return (Ports-Free -ports $TargetPorts)
}

# Allow direct invocation: exit nonzero on failure for pipeline use
if ($MyInvocation.InvocationName -ne '.') {
  if (-not (Stop-AllProjectContextServices)) {
    Write-Error "Cleanup failed: some target ports still busy."
    exit 1
  }
}
