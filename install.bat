@echo off
REM ============================================
REM  DBD Randomizer - установка зависимостей
 ============================================
echo Проверяю Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден. Установите с python.org и отметьте "Add to PATH"
    pause
    exit /b 1
)

echo Устанавливаю зависимости (pyautogui, pyperclip, pydirectinput)...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить зависимости
    pause
    exit /b 1
)

echo.
echo Готово! Запускаю программу...
start "" pythonw dbd_randomizer.py
