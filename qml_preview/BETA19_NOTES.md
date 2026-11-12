# DBD Ultimate Search Randomizer — Qt Beta 19 (candidate)

## Auto-equip reliability
- Keeps Beta 18's manual window selection after a minimum three-second countdown. There is **no game EXE or window-title lookup**.
- Checks captured foreground HWND during cursor movement and before/during click, Ctrl+A and Ctrl+V operations.
- Releases the mouse button and keyboard modifiers even if input is interrupted by F9 or loss of focus.
- Rejects configured coordinates outside the physical Windows virtual desktop, including multi-monitor setups.
- Opens the coordinate capture overlay on the cursor's monitor and captures a physical cursor position, when DirectInput is available.
- Successful input does not imply successful in-game equipment: verify manually inside the game.

## Windows auto-updater
- Beta 18 can detect a published Beta 19 prerelease and checksum metadata.
- Retains verified SHA-256 staging, onedir EXE/runtime replacement, rollback, and user settings.
- Cleans up the generated PowerShell installer helper after executing it.
- Windows CI tests an actual published Beta 18 portable ZIP upgraded to the candidate Beta 19 ZIP.

## Release gate
This is a **candidate**. Publishing a prerelease requires CI success. Stable release requires real-game testing and a complete Windows upgrade test.
