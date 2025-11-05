# Smoke tests for deterministic placement
$here  = Split-Path -Parent $MyInvocation.MyCommand.Path
$start = Join-Path $here "start-dashboard-fixed.ps1"
$move  = Join-Path $here "move-window.ps1"
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"

function Test-ColdStart {
  Write-Host "Test-ColdStart"
  & $start -Port 5556 -Url "about:blank" -ProfileDir "$env:TEMP\vms_test_profile_cold" `
          -X -300 -Y 120 -W 900 -H 700 | Out-Null
}

function Test-WarmStartWithPrefs {
  Write-Host "Test-WarmStartWithPrefs"
  $pdir = "$env:TEMP\vms_test_profile_warm"
  New-Item -ItemType Directory -Force -Path $pdir | Out-Null
  $pref = Join-Path $pdir "Default\Preferences"
  $obj = @{ app_window_placement = @{ bounds = @{ left = 0; top = 0; right = 500; bottom = 500 } } }
  $obj | ConvertTo-Json -Depth 10 | Set-Content -Path $pref -Encoding UTF8
  & $start -Port 5557 -Url "about:blank" -ProfileDir $pdir -X 100 -Y 100 -W 1000 -H 600 | Out-Null
}

function Test-MoveOnly {
  Write-Host "Test-MoveOnly"
  $p = Start-Process -FilePath $chrome -ArgumentList "--new-window","about:blank" -PassThru
  Start-Sleep -Milliseconds 800
  & $move -Pid $p.Id -X 200 -Y 200 -W 800 -H 600 -TimeoutMs 6000 | Out-Null
}

Test-ColdStart
Test-WarmStartWithPrefs
Test-MoveOnly
Write-Host "All tests completed."
