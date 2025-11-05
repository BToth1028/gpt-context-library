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

Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object {
  try {
    $cl = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
    if ($cl -like "*--user-data-dir=$ProfileDir*") { Stop-Process -Id $_.Id -Force }
  } catch { }
}

Start-Process -FilePath $ServerCmd -ArgumentList $ServerArg -WindowStyle Hidden

$deadline = (Get-Date).AddSeconds(12)
while ((Get-Date) -lt $deadline) {
  try {
    $r = Invoke-WebRequest -Uri "$Url/api/board" -TimeoutSec 1
    if ($r.StatusCode -eq 200) { break }
  } catch { Start-Sleep -Milliseconds 200 }
}
if ((Get-Date) -ge $deadline) { Write-Error "Dashboard server failed to start"; exit 1 }

$args = @(
  "--app=$Url",
  "--user-data-dir=$ProfileDir",
  "--window-position=$X,$Y",
  "--window-size=$W,$H"
)
$proc = Start-Process -FilePath $ChromePath -ArgumentList $args -PassThru

& "$PSScriptRoot\move-window.ps1" -Pid $proc.Id -X $X -Y $Y -W $W -H $H -TimeoutMs 8000 | Out-Null
Write-Host "Dashboard launched at $Url"
