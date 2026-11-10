# DBD Ultimate Search Randomizer — Qt Beta 3

PySide6 / Qt Quick frontend for the original DBD Randomizer game database and generation logic. Unlike the first preview, the application no longer creates a hidden Tkinter window.

## What's included

- Custom dark interface and vector UI controls, without emoji navigation.
- Original perk and character data, available DLC filters, killer/survivor roles, rerolls, addons, items, challenges and 2v8 classes.
- **Characters:** two independent lists (Killers / Survivors), actual portraits downloaded from wiki.gg using the existing icon cache, live search, individual checkboxes and per-side All / None / Invert commands.
- **Cosmetics:** character selector with portraits and separate killer/survivor switch; 256px cosmetic previews, a large preview pane, rarity/type/date, searchable catalog, ownership selection, random owned outfit and bulk select tools.
- Main build artwork: character portrait, power/item image, addon thumbnails and perk icons.
- Custom builds, community builds, Firebase publishing, compatible settings, coordinate capture, timings, OCR support, DirectInput game equip and hotkey stop.
- Opt-in update checks and verified Windows EXE updates from future Qt Releases.

Portraits and cosmetic thumbnails are **not bundled** in the EXE. They are downloaded on demand into `icons_cache` using the URLs already present in `dbd_icons.py` and `dbd_skins.py`. Requires an internet connection for first-time images; cached images work offline. Missing wiki images show a custom text placeholder.

## Installation / usage

Windows 11: download `DBDRandomizerQtBeta.exe` from the GitHub Release and put it next to your old `dbd_randomizer_config.json` to preserve coordinates and preferences. Keep a backup and retain your old EXE until you have tested the new version.

From source (Python 3.12+):
```powershell
py -m pip install -r qml_preview/requirements.txt
py qml_preview/main.py
```

F5 generate, F6 copy, F9 stop automation (also globally registered by `keyboard` on Windows if permitted).

## Beta limitations

The interface and packaged EXE are checked in Windows CI, but automatic equipment has **not** been tested with a real Dead by Daylight match and varying screen resolutions. Test in dry-run first. The previous Tkinter EXE cannot automatically migrate itself; one manual installation is required. The executable is a prerelease and does not replace the stable v2.28.0 in `main`.

Do not provide GitHub tokens in messages; no GitHub credentials are needed to run the application.
