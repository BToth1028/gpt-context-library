@echo off

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

:: Stop MkDocs
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 2^>nul') do taskkill /F /PID %%a >nul 2>&1

:: Stop Backstage
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 2^>nul') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :7007 2^>nul') do taskkill /F /PID %%a >nul 2>&1

:: Stop Docker containers (preserve volumes for data persistence)
cd /d C:\DEV\sourcegraph 2>nul
docker compose stop >nul 2>&1
for /f "tokens=*" %%i in ('docker ps -q --filter "ancestor=structurizr/lite" 2^>nul') do docker stop %%i >nul 2>&1

:: Close all related terminal windows more aggressively
for /f "tokens=2" %%a in ('tasklist /V /FI "WindowTitle eq MkDocs*" ^| findstr cmd.exe') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=2" %%a in ('tasklist /V /FI "WindowTitle eq Backstage*" ^| findstr cmd.exe') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=2" %%a in ('tasklist /V /FI "WindowTitle eq Sourcegraph*" ^| findstr cmd.exe') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=2" %%a in ('tasklist /V /FI "WindowTitle eq Structurizr*" ^| findstr cmd.exe') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=2" %%a in ('tasklist /V /FI "WindowTitle eq *Monitor*" ^| findstr cmd.exe') do taskkill /F /PID %%a >nul 2>&1

:: Give processes time to close
timeout /t 2 /nobreak >nul

echo Cleanup complete.
echo.

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

:: Start Sourcegraph (minimized)
echo [2/4] Starting Sourcegraph...
if exist "C:\DEV\sourcegraph\docker-compose.yaml" (
    start /min "Sourcegraph" cmd /k "cd C:\DEV\sourcegraph && docker compose up"
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

:: Wait a bit for services to start
echo Waiting 5 seconds for services to initialize...
timeout /t 5 /nobreak >nul

:: Start aggregate monitor (MINIMIZED)
echo.
echo [5/5] Starting Aggregate Monitor (minimized)...
start /min "Monitor - All Services" cmd /k "cd C:\DEV && monitor-all.bat"
timeout /t 1 /nobreak >nul
echo   Monitor window minimized in taskbar

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

:: Automatically open browsers with delays for startup
echo.
echo Waiting 15 seconds for services to initialize before opening browsers...
echo (Services may take 1-2 minutes to fully start)
echo.
timeout /t 15 /nobreak >nul
echo.
echo Opening all portals in browser...
echo.

if %VENV_EXISTS% equ 1 (
    echo   Opening MkDocs...
    start "" http://localhost:8000
    timeout /t 1 /nobreak >nul
)

if %BACKSTAGE_CAN_RUN% equ 1 (
    echo   Opening Backstage...
    start "" http://localhost:3000
    timeout /t 1 /nobreak >nul
)

echo   Opening Sourcegraph...
start "" http://localhost:7080
timeout /t 1 /nobreak >nul

if %STRUCTURIZR_RUNNING% equ 1 (
    echo   Opening Structurizr...
    start "" http://localhost:8081
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
echo This window will close in 5 seconds...
timeout /t 5 /nobreak >nul
