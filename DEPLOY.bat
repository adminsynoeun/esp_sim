@echo off
chcp 65001 >nul
REM RFID Cut Station - Quick Deploy (no Python needed)
REM Place next to: RFID_CutStation.exe + config.ini

title RFID Cut Station - Deploy
echo.
echo   ========================================
echo     RFID Cut Station - Quick Deploy
echo   ========================================
echo.

if not exist "%~dp0RFID_CutStation.exe" (
    echo   [FAIL] RFID_CutStation.exe not found!
    echo   Put this script next to the EXE.
    pause
    exit /b 1
)

echo   [1/4] Copying to C:\RFID_CutStation ...
if not exist "C:\RFID_CutStation" mkdir "C:\RFID_CutStation"
copy /Y "%~dp0RFID_CutStation.exe" "C:\RFID_CutStation\RFID_CutStation.exe" >nul
copy /Y "%~dp0config.ini"          "C:\RFID_CutStation\config.ini"          >nul

if not exist "C:\RFID_CutStation\RFID_CutStation.exe" (
    echo   [FAIL] Copy failed! Run as Administrator.
    pause
    exit /b 1
)
echo   [OK] Files installed

REM --- Create a silent VBScript launcher (hides any console window) ---
echo   [2/4] Creating silent launcher...
set "LAUNCHER=C:\RFID_CutStation\launch.vbs"
(
    echo Set ws = CreateObject("WScript.Shell"^)
    echo ws.Run """C:\RFID_CutStation\RFID_CutStation.exe""", 0, False
) > "%LAUNCHER%"
echo   [OK] Silent launcher created: %LAUNCHER%

echo   [3/4] Creating Desktop shortcut...
set "VBS=%TEMP%\rfid_d.vbs"
(
    echo Set ws = CreateObject("WScript.Shell"^)
    echo Set sc = ws.CreateShortcut(ws.SpecialFolders("Desktop"^) ^& "\RFID Cut Station.lnk"^)
    echo sc.TargetPath = "wscript.exe"
    echo sc.Arguments = "//nologo ""C:\RFID_CutStation\launch.vbs"""
    echo sc.WorkingDirectory = "C:\RFID_CutStation"
    echo sc.Description = "RFID Cut Station"
    echo sc.Save
) > "%VBS%"
cscript //nologo "%VBS%"
del "%VBS%" 2>nul
echo   [OK] Desktop shortcut created

echo   [4/4] Adding to Windows Startup (silent background)...
set "STARTDIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS=%TEMP%\rfid_s.vbs"
(
    echo Set ws = CreateObject("WScript.Shell"^)
    echo Set sc = ws.CreateShortcut("%STARTDIR%\RFID_CutStation.lnk"^)
    echo sc.TargetPath = "wscript.exe"
    echo sc.Arguments = "//nologo ""C:\RFID_CutStation\launch.vbs"""
    echo sc.WorkingDirectory = "C:\RFID_CutStation"
    echo sc.WindowStyle = 0
    echo sc.Description = "RFID Cut Station"
    echo sc.Save
) > "%VBS%"
cscript //nologo "%VBS%"
del "%VBS%" 2>nul
echo   [OK] Auto-start enabled (runs silently on boot)

echo.
echo   ========================================
echo     DONE! Installed on this PC.
echo   ========================================
echo.
echo   Desktop shortcut : ready (no terminal)
echo   Auto-start       : runs silently on boot
echo.

set /p STARTNOW="  Launch now silently? (Y/N): "
if /i "%STARTNOW%"=="Y" (
    wscript //nologo "C:\RFID_CutStation\launch.vbs"
    echo   [OK] App started in background. Browser will open.
)
pause
