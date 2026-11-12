@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Repair DBD Randomizer Shortcut.ps1" -InstallDir "%~dp0"
if errorlevel 1 (
    echo.
    echo Shortcut update failed. Keep both files next to DBDRandomizerQtBeta.exe.
    pause
    exit /b 1
)
echo.
echo DBD Randomizer shortcut now points to this Qt application.
pause
