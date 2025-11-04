@echo on

:: Start Everything - Project Context OS
:: =====================================

echo.
echo ================================================
echo   Starting Project Context OS
echo ================================================
echo.

:: First, stop any existing services
echo Cleaning up any existing services...
echo.

:: PowerShell-based cleanup (fast, reliable, process-tree aware)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$ports = @(8000,3000,7007,7080,8081); ^
 try { docker ps --format '{{.ID}} {{.Image}}' 2^>$null ^| Where-Object { $_ -match 'structurizr/lite' } ^| ForEach-Object { docker stop ($_ -split ' ')[0] 2^>$null ^| Out-Null } } catch {}; ^
 try { cd C:\DEV\sourcegraph 2^>$null; docker compose stop 2^>$null ^| Out-Null } catch {}; ^
 try { Get-CimInstance Win32_Process ^| Where-Object { $cmd = $_.CommandLine; ($cmd -match 'mkdocs\s+serve') -or ($cmd -match 'yarn.*start') -or ($cmd -match 'backstage') -or ($cmd -match 'monitor-all') -or ($cmd -match 'Project Context OS.*Live Status') -or ($cmd -match 'docker compose.*sourcegraph.*logs') -or ($cmd -match 'docker run.*structurizr') -or ($cmd -match 'docker compose up') } ^| ForEach-Object { taskkill /PID $_.ProcessId /T /F 2^>$null ^| Out-Null } } catch {}; ^
 try { Get-Process cmd,powershell -ErrorAction SilentlyContinue ^| Where-Object { $_.MainWindowTitle -match 'Monitor.*All Services' -or $_.MainWindowTitle -match '^MkDocs$' -or $_.MainWindowTitle -match '^Backstage$' -or $_.MainWindowTitle -match '^Sourcegraph$' -or $_.MainWindowTitle -match '^Structurizr$' } ^| ForEach-Object { taskkill /PID $_.Id /T /F 2^>$null ^| Out-Null } } catch {}; ^
 try { $pids = Get-NetTCPConnection -ErrorAction SilentlyContinue ^| Where-Object { $_.LocalPort -in $ports } ^| Select-Object -ExpandProperty OwningProcess -Unique; foreach ($pid in $pids) { taskkill /PID $pid /T /F 2^>$null ^| Out-Null } } catch {}; ^
 $deadline = (Get-Date).AddSeconds(10); while ((Get-Date) -lt $deadline) { if (-not (Get-NetTCPConnection -ErrorAction SilentlyContinue ^| Where-Object { $_.LocalPort -in $ports })) { Write-Host 'Ports verified free.' -ForegroundColor Green; break }; Start-Sleep -Milliseconds 200 }; exit 0"

if %errorlevel% neq 0 (
    echo WARNING: Cleanup had issues, but continuing...
)
echo Cleanup complete.
echo.

:: Brief pause to ensure all processes fully terminate
timeout /t 1 /nobreak >nul

:: Check prerequisites
echo Checking prerequisites...
echo.

:: Check if Backstage Yarn exists
if exist "C:\DEV\backstage\.yarn\releases\yarn-4.4.1.cjs" (
    echo [OK] Backstage Yarn found
    set BACKSTAGE_CAN_RUN=1
) else (
    echo WARNING: Backstage Yarn not found
    echo Backstage will be skipped.
    echo.
    set BACKSTAGE_CAN_RUN=0
)

:: Check if Python venv exists
if exist "C:\DEV\.venv\Scripts\activate.bat" (
    echo [OK] Python venv exists
    set VENV_EXISTS=1
) else (
    echo WARNING: Python venv not found
    echo MkDocs will be skipped.
    echo.
    set VENV_EXISTS=0
)

echo.

:: Check if Docker is running
echo Checking Docker status...
docker info >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Docker is already running!
    echo.
    goto start_services
)

:: Docker not running - start it
echo Docker is not running. Starting it now...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo.
echo Waiting for Docker to be ready...
echo (Checking every 3 seconds)
echo.

:: Check every 3 seconds until Docker is ready
set /a counter=0
:check_docker
set /a counter+=1
timeout /t 3 /nobreak >nul

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo   Check %counter%: Docker not ready yet...
    if %counter% LSS 40 goto check_docker
    echo.
    echo ERROR: Docker did not start after 2 minutes.
    echo Please start Docker Desktop manually and run this again.
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Docker is ready!
echo.

:start_services
echo ================================================
echo   Starting Services (in background)
echo ================================================
echo.

:: Start MkDocs (minimized)
if %VENV_EXISTS% equ 1 (
    echo [1/4] Starting MkDocs...
    start /min "MkDocs" cmd /k "cd C:\DEV && .venv\Scripts\activate.bat && mkdocs serve"
    timeout /t 2 /nobreak >nul
    echo   Started on http://localhost:8000
) else (
    echo [1/4] Skipping MkDocs (venv not found)
)
echo.

:: Start Sourcegraph (minimized, detached)
echo [2/4] Starting Sourcegraph...
if exist "C:\DEV\sourcegraph\docker-compose.yaml" (
    cd /d C:\DEV\sourcegraph
    docker compose up -d
    if errorlevel 1 (
        echo WARNING: docker compose failed, but continuing...
    )
    cd /d C:\DEV
    timeout /t 2 /nobreak >nul
    echo   Started on http://localhost:7080
) else (
    echo   WARNING: docker-compose.yaml not found
)
echo.

:: Start Structurizr (minimized)
echo [3/4] Starting Structurizr...
if exist "C:\DEV\docs\architecture\c4\workspace.dsl" (
    start /min "Structurizr" cmd /k "cd C:\DEV\docs\architecture\c4 && docker run -it --rm -p 8081:8080 -v C:\DEV\docs\architecture\c4:/usr/local/structurizr structurizr/lite"
    timeout /t 2 /nobreak >nul
    echo   Started on http://localhost:8081
    set STRUCTURIZR_RUNNING=1
) else (
    echo   WARNING: workspace.dsl not found
    set STRUCTURIZR_RUNNING=0
)
echo.

:: Start Backstage (minimized, disable auto-browser-open)
if %BACKSTAGE_CAN_RUN% equ 1 (
    echo [4/4] Starting Backstage...
    if exist "C:\DEV\backstage\start-backstage.bat" (
        start /min "Backstage" cmd /k "cd C:\DEV\backstage && start-backstage.bat"
        timeout /t 2 /nobreak >nul
        echo   Started on http://localhost:3000
    ) else (
        echo   WARNING: Backstage start script not found
    )
) else (
    echo [4/4] Skipping Backstage (Yarn not found)
)
echo.

:: Start aggregate monitor (MINIMIZED) - shows live status as services come up
echo [5/5] Starting Aggregate Monitor (minimized)...
start /min "Monitor - All Services" cmd /k "cd C:\DEV && monitor-all.bat"
timeout /t 1 /nobreak >nul
echo   Monitor window minimized in taskbar
echo.

:: Wait for services to report healthy
echo.
echo Waiting for services to report healthy...
echo (Max 20-30 seconds, then opening browsers)
echo.

:: Sourcegraph health check (max 20 seconds)
echo Checking Sourcegraph health...
set SG_HEALTHY=0
for /l %%i in (1,1,10) do (
    powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -Uri http://localhost:7080/healthz -TimeoutSec 1 -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        echo   Sourcegraph is healthy!
        set SG_HEALTHY=1
        goto sg_ok
    )
    timeout /t 2 /nobreak >nul
)
echo   Sourcegraph still starting (this is normal)
:sg_ok

:: Structurizr health check
if %STRUCTURIZR_RUNNING% equ 1 (
    echo Checking Structurizr health...
    set STRUCT_HEALTHY=0
    for /l %%i in (1,1,30) do (
        powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -Uri http://localhost:8081 -TimeoutSec 2 -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
        if not errorlevel 1 (
            echo   Structurizr is healthy!
            set STRUCT_HEALTHY=1
            goto struct_ok
        )
        timeout /t 2 /nobreak >nul
    )
    echo   WARNING: Structurizr not responding after 60s
    :struct_ok
)

:: Summary
echo.
echo ================================================
echo   Startup Complete!
echo ================================================
echo.
echo Services Running (all minimized in taskbar):
if %VENV_EXISTS% equ 1 (
    echo   - MkDocs:      http://localhost:8000
)
echo   - Sourcegraph: http://localhost:7080 (takes 2-3 min)
if %STRUCTURIZR_RUNNING% equ 1 (
    echo   - Structurizr: http://localhost:8081 (takes 30-60 sec)
)
if %BACKSTAGE_CAN_RUN% equ 1 (
    echo   - Backstage:   http://localhost:3000 (takes 1-2 min)
)
echo.
echo   Monitor: Minimized in taskbar (restore to see live logs)
echo.

:: Show fixes if needed
if %BACKSTAGE_CAN_RUN% equ 0 (
    echo.
    echo TO FIX BACKSTAGE:
    echo   cd C:\DEV\backstage
    echo   yarn install
    echo.
)

if %VENV_EXISTS% equ 0 (
    echo.
    echo TO FIX MKDOCS:
    echo   cd C:\DEV
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install mkdocs-material
    echo.
)

:: Open browsers (services are now healthy)
echo.
echo Opening all portals in browser...
echo.

if %VENV_EXISTS% equ 1 (
    echo   Opening MkDocs...
    powershell -Command "Start-Process 'http://localhost:8000'"
    timeout /t 1 /nobreak >nul
)

if %BACKSTAGE_CAN_RUN% equ 1 (
    echo   Opening Backstage...
    powershell -Command "Start-Process 'http://localhost:3000'"
    timeout /t 1 /nobreak >nul
)

echo   Opening Sourcegraph...
powershell -Command "Start-Process 'http://localhost:7080'"
timeout /t 1 /nobreak >nul

if %STRUCTURIZR_RUNNING% equ 1 (
    echo   Opening Structurizr...
    powershell -Command "Start-Process 'http://localhost:8081'"
    timeout /t 1 /nobreak >nul
)

echo.
echo ================================================
echo   All browsers opened!
echo ================================================
echo.
echo NOTE: Services are still starting up.
echo Wait 1-2 minutes, then refresh pages if needed.
echo.
echo Press any key to close this window...
pause >nul
