Write-Host "Testing Monitor 3 Position" -ForegroundColor Cyan

# Kill all existing browser instances first
Get-Process chrome,msedge -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$testUrl = "http://localhost:5555"

Write-Host "`nTest 3: X=-400 (M3 Right Edge)" -ForegroundColor Yellow
Start-Process -FilePath $chrome -ArgumentList "--app=$testUrl","--user-data-dir=$env:TEMP\chrome_test3","--window-position=-400,100","--window-size=600,400"
Start-Sleep -Seconds 4

Write-Host "`nDone!" -ForegroundColor Green

