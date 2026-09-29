@echo off
REM Сборка DBDRandomizer.exe для машин БЕЗ Python (Windows).
REM Нужно: Python 3.9+ с галкой "Add python.exe to PATH" и pip.
cd /d "%~dp0"
pip install -r requirements.txt pyinstaller || goto :err
pyinstaller --noconfirm --onefile --windowed --name DBDRandomizer ^
  --hidden-import pydirectinput --hidden-import pyautogui ^
  --hidden-import keyboard --hidden-import PIL ^
  dbd_randomizer.py || goto :err
echo.
echo Готово: dist\DBDRandomizer.exe  — кладите его в любую папку и запускайте.
echo Конфиг, база и кэш иконок будут создаваться РЯДОМ с exe.
pause
exit /b 0
:err
echo Сборка не удалась — смотрите вывод выше.
pause
exit /b 1
