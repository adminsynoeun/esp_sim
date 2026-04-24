@echo off
chcp 65001 >nul
REM ===================================================
REM  RFID Cut Station - Build Single EXE
REM
REM  Run this ONCE on any Windows machine with Python.
REM  Produces: dist\RFID_CutStation.exe  (single file!)
REM
REM  Then copy that EXE + config.ini to any PC. Done.
REM ===================================================

title Building RFID Cut Station EXE...
echo.
echo   +-----------------------------------------------+
echo   ^|   Building RFID Cut Station EXE...            ^|
echo   +-----------------------------------------------+
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Python not found!
    echo   Download from https://python.org
    echo   Check "Add Python to PATH" during install!
    pause
    exit /b
)

echo   [1/4] Installing build tools...
pip install pyserial pyinstaller pyodbc keyboard --quiet

echo   [2/4] Creating EXE (no console window)...
cd /d "%~dp0app"

pyinstaller --noconfirm --onefile --noconsole ^
    --name "RFID_CutStation" ^
    --icon=NUL ^
    --add-data "dashboard.html;." ^
    --hidden-import serial ^
    --hidden-import serial.tools ^
    --hidden-import serial.tools.list_ports ^
    --hidden-import serial.tools.list_ports_common ^
    --hidden-import serial.tools.list_ports_windows ^
    --hidden-import keyboard ^
    main.py

echo   [3/4] Copying config files...
copy /Y config.ini dist\config.ini >nul
copy /Y setup_db.py dist\setup_db.py >nul 2>nul

echo   [4/4] Cleaning up build files...
rmdir /S /Q build >nul 2>nul
del /Q *.spec >nul 2>nul

cd /d "%~dp0"

echo.
echo   +-----------------------------------------------+
echo   ^|   BUILD COMPLETE!                             ^|
echo   ^|                                               ^|
echo   ^|   Your EXE is ready:                          ^|
echo   ^|     app\dist\RFID_CutStation.exe              ^|
echo   ^|     app\dist\config.ini                       ^|
echo   ^|                                               ^|
echo   ^|   Copy BOTH files to any Windows PC.          ^|
echo   ^|   Double-click the EXE. That's it!            ^|
echo   +-----------------------------------------------+
echo.

REM Open the output folder
explorer "%~dp0app\dist"

pause
