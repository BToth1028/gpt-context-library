# Deterministic Chrome app-mode placement to X=-400, Y=100.
param(
  [int]$Port = 5555,
  [string]$Url = $( "http://127.0.0.1:{0}" -f $Port ),
  [int]$X = -400, [int]$Y = 100, [int]$W = 1200, [int]$H = 800,
  [string]$ChromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe",
  [string]$ProfileDir = "$env:TEMP\vms_dashboard_profile",
  [string]$ServerCmd = "pythonw",
  [string]$ServerArg = "C:\DEV\tools\vector-management\src\dashboard_comprehensive.py"
)

New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null

# Kill previous dashboard server if PID file exists
$pidFile = "$env:TEMP\vms_dashboard.pid"
if (Test-Path $pidFile) {
  try {
    $oldPid = Get-Content $pidFile
    Stop-Process -Id $oldPid -Force -ErrorAction Stop
    Write-Host "Killed previous dashboard server (PID: $oldPid)"
  } catch { }
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$prefPath = Join-Path $ProfileDir "Default\Preferences"
if (Test-Path $prefPath) {
  try {
    $json = Get-Content $prefPath -Raw | ConvertFrom-Json
    if ($null -ne $json.app_window_placement) {
      $json.PSObject.Properties.Remove('app_window_placement') | Out-Null
      $json | ConvertTo-Json -Depth 50 | Set-Content -Path $prefPath -Encoding UTF8
    }
  } catch { }
}

# Kill only dashboard Chrome instances (using our specific user-data-dir)
$userDataDir = "$env:TEMP\vms_dashboard"
Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object {
  try {
    $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
    if ($cmdline -like "*$userDataDir*") {
      Stop-Process -Id $_.Id -Force -ErrorAction Stop
    }
  } catch { }
}
Start-Sleep -Milliseconds 500

# Delete user-data-dir to prevent cached window positions
if (Test-Path $userDataDir) {
  Remove-Item -Path $userDataDir -Recurse -Force -ErrorAction SilentlyContinue
}

$serverProc = Start-Process -FilePath $ServerCmd -ArgumentList $ServerArg -WindowStyle Hidden -PassThru
$serverProc.Id | Set-Content $pidFile
Write-Host "Started dashboard server (PID: $($serverProc.Id))"

$deadline = (Get-Date).AddSeconds(12)
while ((Get-Date) -lt $deadline) {
  try {
    $r = Invoke-WebRequest -Uri "$Url/api/board" -TimeoutSec 1
    if ($r.StatusCode -eq 200) { break }
  } catch { Start-Sleep -Milliseconds 200 }
}
if ((Get-Date) -ge $deadline) { Write-Error "Dashboard server failed to start"; exit 1 }

Start-Process -FilePath $ChromePath -ArgumentList "--app=http://localhost:5555","--user-data-dir=$env:TEMP\vms_dashboard","--window-position=-550,177","--window-size=534,338"
Write-Host "Dashboard launched at $Url"
