@echo off
REM ============================================================
REM  RFID Cut Station - Silent Background Deploy
REM  Run once as Administrator to:
REM    1. Copy app files to C:\RFID_CutStation
REM    2. Create a PowerShell silent launcher (no console window)
REM    3. Register auto-start via Windows Task Scheduler
REM    4. Optional: start the app right now silently
REM ============================================================
setlocal enabledelayedexpansion

title RFID Cut Station - Silent Deploy
echo.
echo   ========================================
echo     RFID Cut Station - Silent Deploy
echo   ========================================
echo.

REM ── Check admin rights ──────────────────────────────────────
net session >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Please run as Administrator!
    echo   Right-click this BAT and choose Run as administrator
    echo.
    pause
    exit /b 1
)
echo   [OK] Running as Administrator

REM ── Find pythonw.exe (no-console Python) ────────────────────
set "PYTHONW="
for /f "delims=" %%i in ('where pythonw 2^>nul') do (
    if not defined PYTHONW set "PYTHONW=%%i"
)
if not defined PYTHONW (
    for /f "delims=" %%i in ('where python 2^>nul') do (
        if not defined PYTHONW set "PYTHONW=%%i"
    )
    if not defined PYTHONW (
        echo   [FAIL] Python not found! Download from https://python.org
        pause
        exit /b 1
    )
    REM Try pythonw.exe in same folder as python.exe
    for %%p in ("!PYTHONW!") do set "TRYDIR=%%~dpp"
    if exist "!TRYDIR!pythonw.exe" set "PYTHONW=!TRYDIR!pythonw.exe"
)
echo   [OK] Python: !PYTHONW!

REM ── [1/4] Copy app files ────────────────────────────────────
echo.
echo   [1/4] Installing files to C:\RFID_CutStation ...
if not exist "C:\RFID_CutStation" mkdir "C:\RFID_CutStation"

xcopy /E /I /Y "%~dp0app" "C:\RFID_CutStation\app" >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Failed to copy app folder. Run as Administrator.
    pause
    exit /b 1
)
if exist "%~dp0factory.db" copy /Y "%~dp0factory.db" "C:\RFID_CutStation\factory.db" >nul
if exist "%~dp0config.ini" copy /Y "%~dp0config.ini" "C:\RFID_CutStation\config.ini" >nul
echo   [OK] Files installed

REM ── [2/4] Write PowerShell silent launcher ──────────────────
REM  Uses Start-Process with WindowStyle Hidden = no window at all.
REM  Single-quote strings in PS1 need no CMD escape tricks.
echo.
echo   [2/4] Creating silent launcher (start_silent.ps1) ...

set "PS1=C:\RFID_CutStation\start_silent.ps1"
REM Write PS1 using single quotes only - no CMD quoting conflict
echo $py = '!PYTHONW!' > "%PS1%"
echo $script = 'C:\RFID_CutStation\app\main.py' >> "%PS1%"
echo $wd = 'C:\RFID_CutStation\app' >> "%PS1%"
echo Start-Process -FilePath $py -ArgumentList $script -WorkingDirectory $wd -WindowStyle Hidden >> "%PS1%"

if not exist "%PS1%" (
    echo   [FAIL] Could not write PS1 launcher.
    pause
    exit /b 1
)
echo   [OK] Launcher: %PS1%

REM ── [3/4] Register Task Scheduler ───────────────────────────
REM  powershell.exe -WindowStyle Hidden keeps zero console visible.
REM  No inner quotes needed in /tr since PS1 path has no spaces.
echo.
echo   [3/4] Registering auto-start in Task Scheduler ...

schtasks /delete /tn "RFID_CutStation_AutoStart" /f >nul 2>&1

schtasks /create /tn "RFID_CutStation_AutoStart" /tr "powershell.exe -WindowStyle Hidden -NonInteractive -ExecutionPolicy Bypass -File C:\RFID_CutStation\start_silent.ps1" /sc ONLOGON /ru "%USERNAME%" /rl HIGHESTPRIVILEGE /delay 0000:10 /f >nul 2>&1

if errorlevel 1 (
    echo   [WARN] Task Scheduler failed - using Startup folder fallback ...
    REM Write a shortcut-creator PS1 and run it
    set "VBS=%TEMP%\rfid_sc.vbs"
    set "STARTDIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    echo Set ws = CreateObject("WScript.Shell") > "!VBS!"
    echo Set sc = ws.CreateShortcut("!STARTDIR!\RFID CutStation.lnk") >> "!VBS!"
    echo sc.TargetPath = "powershell.exe" >> "!VBS!"
    echo sc.Arguments = "-WindowStyle Hidden -NonInteractive -ExecutionPolicy Bypass -File C:\RFID_CutStation\start_silent.ps1" >> "!VBS!"
    echo sc.WorkingDirectory = "C:\RFID_CutStation\app" >> "!VBS!"
    echo sc.Save >> "!VBS!"
    cscript //nologo "!VBS!"
    del "!VBS!" 2>nul
    echo   [OK] Startup folder shortcut registered (fallback)
) else (
    echo   [OK] Task Scheduler registered - runs hidden at every login
)

REM ── [4/4] Desktop shortcut ───────────────────────────────────
echo.
echo   [4/4] Creating Desktop shortcut ...

set "VBS2=%TEMP%\rfid_desk.vbs"
echo Set ws = CreateObject("WScript.Shell") > "%VBS2%"
echo Set sc = ws.CreateShortcut(ws.SpecialFolders("Desktop") ^& "\RFID Cut Station.lnk") >> "%VBS2%"
echo sc.TargetPath = "powershell.exe" >> "%VBS2%"
echo sc.Arguments = "-WindowStyle Hidden -NonInteractive -ExecutionPolicy Bypass -File C:\RFID_CutStation\start_silent.ps1" >> "%VBS2%"
echo sc.WorkingDirectory = "C:\RFID_CutStation\app" >> "%VBS2%"
echo sc.Description = "RFID Cut Station Web App" >> "%VBS2%"
echo sc.Save >> "%VBS2%"
cscript //nologo "%VBS2%"
del "%VBS2%" 2>nul
echo   [OK] Desktop shortcut created

REM ── Done ─────────────────────────────────────────────────────
echo.
echo   ========================================
echo     DEPLOY COMPLETE!
echo   ========================================
echo.
echo   Install path : C:\RFID_CutStation
echo   Auto-start   : Task Scheduler (at login, hidden)
echo   No console   : powershell -WindowStyle Hidden
echo.
echo   Web app URL  : http://localhost:5000
echo.

REM ── Launch right now silently (optional) ─────────────────────
set /p STARTNOW=  Launch silently now? (Y/N): 
if /i "%STARTNOW%"=="Y" (
    powershell.exe -WindowStyle Hidden -NonInteractive -ExecutionPolicy Bypass -File "C:\RFID_CutStation\start_silent.ps1"
    echo   [OK] App started in background.
    echo   Open browser: http://localhost:5000
)

echo.
echo   Press any key to close ...
pause >nul
endlocal
