Write-Host "Testing Fresh App Windows on Monitor 3" -ForegroundColor Cyan

# Kill all existing browser instances first
Get-Process chrome,msedge -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$testUrl = "http://localhost:5555"

Write-Host "`nTest 1: X=-2400 (M3 Left Edge)" -ForegroundColor Yellow
Start-Process -FilePath $chrome -ArgumentList "--app=$testUrl","--user-data-dir=$env:TEMP\chrome_test1","--window-position=-2400,100","--window-size=600,400"
Start-Sleep -Seconds 4

Write-Host "`nTest 2: X=-1280 (M3 Center)" -ForegroundColor Yellow
Start-Process -FilePath $chrome -ArgumentList "--app=$testUrl","--user-data-dir=$env:TEMP\chrome_test2","--window-position=-1280,100","--window-size=600,400"
Start-Sleep -Seconds 4

Write-Host "`nTest 3: X=-400 (M3 Right Edge)" -ForegroundColor Yellow
Start-Process -FilePath $chrome -ArgumentList "--app=$testUrl","--user-data-dir=$env:TEMP\chrome_test3","--window-position=-400,100","--window-size=600,400"
Start-Sleep -Seconds 4

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Which windows are on Monitor 3?" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
