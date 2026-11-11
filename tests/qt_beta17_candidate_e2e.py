"""Windows CI: verify upgrading the published Beta16 portable package to a Beta17 candidate.

This is isolated from the user's machine and does not publish any release.
The target is a real unpacked published Beta16; candidate ZIP comes from the
same CI build that is about to become the Beta17 prerelease.
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
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def run(previous: Path, candidate: Path) -> None:
    assert sys.platform == "win32", "Windows runner required"
    assert updater.CURRENT_TAG == "v2.28.0-qt-beta.17"
    previous = previous.resolve()
    candidate = candidate.resolve()
    verify_download(previous)
    verify_download(candidate)

    with tempfile.TemporaryDirectory(prefix="DBD Beta16 to Beta17 E2E - ") as folder:
        root = Path(folder)
        prior_folder = root / "extract-beta16"
        prior_folder.mkdir()
        install = updater._unpack_verified(previous, prior_folder)
        destination = root / "Installed DBD With Spaces"
        install.rename(destination)

        previous_exe = destination / updater.APP_EXE
        smoke(previous_exe, destination, "published Beta16")

        cfg = core.default_config()
        cfg["options"]["side"] = "KILLER"
        cfg["options"]["perk_mode_mixed_default_v22"] = True
        cfg["coords"]["slot1"]["x"] = "425"
        cfg["publish"]["nickname"] = "PERSIST-BETA16-TO-17"
        config = destination / "dbd_randomizer_config.json"
        config.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        favorite = destination / "my_private_favorites.json"
        favorite.write_text('{"preserve":true}', encoding="utf-8")

        candidate_dir = root / (updater.STAGE_PREFIX + "candidate17")
        candidate_dir.mkdir()
        staged = updater._unpack_verified(candidate, candidate_dir)
        candidate_exe_hash = sha256(staged / updater.APP_EXE)
        candidate_dll_hash = sha256(staged / "_internal" / "python312.dll")
        assert candidate_exe_hash != sha256(previous_exe), "Same EXE before/after candidate update"

        install_script = root / "apply_beta17.ps1"
        install_script.write_text(updater.UPGRADE_SCRIPT, encoding="utf-8-sig")
        process = subprocess.run([
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(install_script),
            "-WaitFor", "0", "-TargetDir", str(destination),
            "-StagedDir", str(staged), "-SkipLaunch",
        ], capture_output=True, text=True, errors="replace", timeout=150)
        if process.returncode != 0:
            errorfile = destination / "dbd_update_error.log"
            reason = errorfile.read_text(encoding="utf-8-sig", errors="replace") if errorfile.is_file() else "(no log)"
            raise AssertionError(
                "Beta17 upgrade failed: " + process.stderr[-2000:] + " | " + reason[-2000:]
            )
        assert sha256(destination / updater.APP_EXE) == candidate_exe_hash
        assert sha256(destination / "_internal" / "python312.dll") == candidate_dll_hash
        assert not (destination / ".dbd_qt_previous.exe").exists()
        assert not (destination / ".dbd_qt_previous_internal").exists()
        assert not (destination / "dbd_update_error.log").exists()
        assert not candidate_dir.exists()
        assert favorite.read_text(encoding="utf-8") == '{"preserve":true}'
        assert "SUCCESS: installed portable Qt update" in (
            destination / "dbd_update_progress.log").read_text(encoding="utf-8-sig")

        smoke(destination / updater.APP_EXE, destination, "candidate Beta17")
        retained = json.loads(config.read_text(encoding="utf-8-sig"))
        assert retained["publish"]["nickname"] == "PERSIST-BETA16-TO-17"
        assert retained["options"]["side"] == "KILLER"
        assert retained["coords"]["slot1"]["x"] == "425"
        print("PASS: real Beta16 portable → candidate Beta17 portable; both EXEs launched, "
              "PowerShell install replaced both EXE/runtime, and settings survived", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-zip", type=Path, required=True)
    parser.add_argument("--new-zip", type=Path, required=True)
    a = parser.parse_args()
    run(a.old_zip, a.new_zip)
