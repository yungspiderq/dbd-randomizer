# DBD Randomizer — QML redesign preview

**Experimental UI preview, not a replacement for the stable app.** This folder is intentionally isolated from the legacy Python/Tkinter application, so the existing Windows build and automation remain unchanged.

## What's new

- PySide6 + Qt Quick interface with custom dark UI
- No emoji; custom vector-inspired geometric artwork drawn by QML Canvas
- Redesigned navigation, four large perk tiles, role switch, interactive demo settings
- Demo build generation, per-slot reroll and lock, clipboard copy, recent history

**Important limitations:** All perks in the preview are fictional placeholders. Original DBD databases, real perks/icons, character roster, community builds, skins, 2v8 classes, OCR, auto-equipping and Windows packaging have **not** been migrated. The existing application in the root directory retains these features.

## Run on Windows 11

1. Install Python 3.12+.
2. Open a terminal in this `qml_preview` directory.
3. Run `py -m pip install -r requirements.txt`.
4. Run `py main.py`.

The UI has not yet been tested on a Windows machine with Qt installed. Python syntax is intended to be compatible with Python 3.12+.

**Keyboard:** F5 — generate sample; F6 — copy; F9 — placeholder (not a working emergency stop).

## Next steps

Split the existing application's game generation, persistence and automation logic from Tkinter widgets, then bind them through a thread-safe Qt/Python bridge. Test every existing feature before changing the default launcher or creating a stable release. Do not enable auto-equip until working emergency stop and worker cancellation have been verified.

## Security

No GitHub access tokens or credentials are included. Revoke previously exposed credentials through GitHub settings.
