"""Windows E2E: install published Qt RC1 using the Beta23 *bridge* updater.

This checks the real EXEs, real published RC1 SHA-256, preserved user data and
shortcut repair helpers. It never modifies a user's installed program or Desktop.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "qml_preview"))
sys.path.insert(0, str(ROOT))
from qt_release_upgrade_e2e import verify_download, smoke
import qt_updater as updater
import dbd_randomizer as core


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(bridge_zip: Path, rc1_zip: Path) -> None:
    assert sys.platform == "win32", "Windows runner required"
    assert updater.CURRENT_TAG == "v2.28.0-qt-beta.23"
    verify_download(bridge_zip)
    verify_download(rc1_zip)

    with tempfile.TemporaryDirectory(prefix="DBD Beta23 to RC1 E2E ") as folder:
        root = Path(folder)
        unpack_bridge = root / "bridge_portable"
        unpack_bridge.mkdir()
        bridge = updater._unpack_verified(bridge_zip, unpack_bridge)
        target = root / "Installed DBD With Spaces"
        bridge.rename(target)
        smoke(target / updater.APP_EXE, target, "candidate Beta23")

        config = target / "dbd_randomizer_config.json"
        user = core.default_config()
        user["publish"]["nickname"] = "PERSIST-BETA23-TO-RC1"
        user["coords"]["slot1"]["x"] = "553"
        owner, ids = next(
            (name, values) for name, values in core.SKINS.CHAR_SKINS.items()
            if len(values) >= 2
        )
        user.setdefault("skins", {})[owner] = [ids[0]]
        config.write_text(json.dumps(user, ensure_ascii=False, indent=2), encoding="utf-8")
        favorites = target / "dbd_user_favorites.json"
        favorites.write_text('{"my-sets":[1,2]}', encoding="utf-8")

        stage_folder = root / (updater.STAGE_PREFIX + "rc1")
        stage_folder.mkdir()
        candidate = updater._unpack_verified(rc1_zip, stage_folder)
        icon_helpers = (
            "Repair DBD Randomizer Shortcut.ps1",
            "Update DBD Randomizer Shortcut.cmd",
        )
        for helper in icon_helpers:
            assert (candidate / helper).is_file(), "RC1 ZIP missing " + helper
        expected_exe_hash = sha256(candidate / updater.APP_EXE)
        expected_dll_hash = sha256(candidate / "_internal" / "python312.dll")

        install_script = root / "beta23_installer.ps1"
        install_script.write_text(updater.UPGRADE_SCRIPT, encoding="utf-8-sig")
        process = subprocess.run([
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(install_script),
            "-WaitFor", "0", "-TargetDir", str(target),
            "-StagedDir", str(candidate), "-SkipLaunch",
        ], capture_output=True, text=True, errors="replace", timeout=150)
        if process.returncode:
            errorfile = target / "dbd_update_error.log"
            details = errorfile.read_text(encoding="utf-8-sig", errors="replace") if errorfile.exists() else ""
            raise AssertionError(
                "Bridge installation failed: " + process.stderr[-1600:] + "\n" + details[-1600:]
            )
        assert sha256(target / updater.APP_EXE) == expected_exe_hash
        assert sha256(target / "_internal" / "python312.dll") == expected_dll_hash
        assert not (target / ".dbd_qt_previous.exe").exists()
        assert not (target / ".dbd_qt_previous_internal").exists()
        assert not stage_folder.exists()
        for helper in icon_helpers:
            assert (target / helper).is_file(), "RC1 shortcut helper was dropped: " + helper

        desktop = root / "Fake Desktop"
        desktop.mkdir()
        repair = subprocess.run([
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-File", str(target / icon_helpers[0]),
            "-InstallDir", str(target), "-ShortcutDirectory", str(desktop),
        ], capture_output=True, text=True, errors="replace", timeout=35)
        assert repair.returncode == 0, repair.stderr
        assert (desktop / "DBD Randomizer.lnk").is_file()

        updated = json.loads(config.read_text(encoding="utf-8-sig"))
        assert updated["publish"]["nickname"] == "PERSIST-BETA23-TO-RC1"
        assert updated["coords"]["slot1"]["x"] == "553"
        assert updated["skins"][owner] == [ids[0]]
        assert favorites.read_text(encoding="utf-8") == '{"my-sets":[1,2]}'
        smoke(target / updater.APP_EXE, target, "published RC1")
        print("PASS: Beta23 candidate -> published RC1 portable; EXE/runtime, "
              "settings and shortcut repair tools retained.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bridge-zip", required=True, type=Path)
    parser.add_argument("--rc1-zip", required=True, type=Path)
    args = parser.parse_args()
    run(args.bridge_zip.resolve(), args.rc1_zip.resolve())
