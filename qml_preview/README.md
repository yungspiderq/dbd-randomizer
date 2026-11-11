# DBD Randomizer Qt Beta 11 — Portable Windows Fix

Beta 11 переходит на **Windows `--onedir`**, чтобы исправить проблемы запуска с `python312.dll`, которые могли возникать при однофайловой распаковке Beta 10.

## Установка

1. Скачайте `DBDRandomizerQtBeta.zip` из GitHub Releases.
2. Извлеките **всю** папку `DBDRandomizerQtBeta`.
3. Запустите `DBDRandomizerQtBeta.exe` из папки, не переносите его отдельно.
4. Для переноса предпочтений и координат после резервного копирования перенесите `dbd_randomizer_config.json` из папки прежней версии рядом с новым EXE.

Структура:
```text
DBDRandomizerQtBeta/
  DBDRandomizerQtBeta.exe
  _internal/
    python312.dll
    ... (Qt, Python и ресурсы)
  dbd_randomizer_config.json   <- ваш файл, если он нужен
```

**Из старой Beta 10 может потребоваться ручная установка**, особенно если она падает до появления интерфейса. Последующие Qt ZIP-релизы будут скачиваться и устанавливаться через обновлятор с проверкой SHA-256, заменой только EXE и `_internal`, резервным копированием старой версии на время установки и попыткой отката при сбое.

## Разработка

Python 3.12+:
```powershell
py -m pip install -r qml_preview/requirements.txt
py qml_preview/main.py
```

Windows portable build:
```powershell
py -m pip install pyinstaller
py qml_preview/build_icon.py
pyinstaller --noconfirm --clean --onedir --contents-directory _internal --windowed --name DBDRandomizerQtBeta --paths . --add-data "qml_preview/Main.qml;qml_preview" --add-data "qml_preview/assets/app_icon.png;qml_preview/assets" --icon "qml_preview/assets/app_icon.ico" --hidden-import pydirectinput --hidden-import pyautogui --hidden-import keyboard --hidden-import PIL --hidden-import PySide6.QtQuick --hidden-import PySide6.QtQuickControls2 --hidden-import PySide6.QtQuickLayouts qml_preview/main.py
```

Контрольные проверки в GitHub Actions: Python/Qt unit-тесты, QML smoke, `python312.dll` в `_internal`, запуск готового EXE, структура и безопасная распаковка ZIP, SHA-256.

Основные функции предыдущих Beta сохранены. Внутриигровые клики сначала проверяйте в режиме «Сухой прогон», F9 останавливает автоматизацию.
