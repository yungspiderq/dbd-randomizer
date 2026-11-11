"""Real release-to-release portable installer verification (Windows CI).

Downloads happen in the workflow via gh CLI. This script receives only existing
release files, operates in a temporary directory, and never touches user files
or the real game. No GitHub update is published by this test.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qt_updater as updater

PREVIOUS = "v2.28.0-qt-beta.15"
CURRENT = "v2.28.0-qt-beta.16"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def verify_download(archive: Path) -> None:
    checksum_file = archive.with_name(archive.name + ".sha256")
    if not checksum_file.is_file():
        raise AssertionError(f"Missing public release checksum: {checksum_file}")
    line = checksum_file.read_text(encoding="utf-8-sig").strip()
    expected, _, recorded_name = line.partition("  ")
    if recorded_name.lstrip("*") != archive.name:
        raise AssertionError(f"Checksum references the wrong archive: {recorded_name}")
    if expected.lower() != digest(archive):
        raise AssertionError(f"Release archive SHA-256 mismatch: {archive}")


def smoke(executable: Path, work_dir: Path, label: str) -> None:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [str(executable), "--smoke"], cwd=work_dir, env=env,
        capture_output=True, text=True, timeout=150,
        errors="replace",
    )
    if result.returncode:
        raise AssertionError(
            f"{label} EXE smoke returned {result.returncode}:\n"
            f"STDOUT: {result.stdout[-1600:]}\nSTDERR: {result.stderr[-2500:]}"
        )
    print(f"{label} portable EXE smoke OK", flush=True)


def run(old_zip: Path, new_zip: Path) -> None:
    if sys.platform != "win32":
        raise RuntimeError("This test requires a Windows runner")
    if updater.CURRENT_TAG != CURRENT:
        raise AssertionError(f"Test version drift: {updater.CURRENT_TAG}")

    old_zip = old_zip.resolve()
    new_zip = new_zip.resolve()
    verify_download(old_zip)
    verify_download(new_zip)
    print("Both published release checksums verified", flush=True)

    with tempfile.TemporaryDirectory(prefix="DBD portable release upgrade - ") as d:
        root = Path(d)
        unpack_old = root / "old_unpacked"
        unpack_old.mkdir()
        installed = updater._unpack_verified(old_zip, unpack_old)
        target = root / "Installed DBD Randomizer"
        installed.rename(target)
        old_exe = target / updater.APP_EXE
        old_runtime = target / "_internal" / "python312.dll"
        assert old_exe.is_file() and old_runtime.is_file()
        smoke(old_exe, target, PREVIOUS)

        config = target / "dbd_randomizer_config.json"
        archive_data = target / "my_custom_settings.json"
        icon_data = target / "icons_saved_by_user.json"
        files = {
            config: '{"language":"ru","private":"do not erase"}',
            archive_data: '{"my_builds":[1,2,3]}',
            icon_data: '{"test":"persist"}',
        }
        for path, value in files.items():
            path.write_text(value, encoding="utf-8")

        staged_dir = root / (updater.STAGE_PREFIX + "published_beta16")
        staged_dir.mkdir()
        staged = updater._unpack_verified(new_zip, staged_dir)
        staged_exe = staged / updater.APP_EXE
        staged_dll = staged / "_internal" / "python312.dll"
        expected_exe_sha = digest(staged_exe)
        expected_dll_sha = digest(staged_dll)

        ps1 = root / "apply_release_update.ps1"
        ps1.write_text(updater.UPGRADE_SCRIPT, encoding="utf-8-sig")
        cmd = [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(ps1),
            "-WaitFor", "0", "-TargetDir", str(target),
            "-StagedDir", str(staged), "-SkipLaunch",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=150)
        if result.returncode:
            logfile = target / "dbd_update_error.log"
            explanation = logfile.read_text(encoding="utf-8-sig", errors="replace") if logfile.exists() else "(no log)"
            raise AssertionError(
                "Release install failed: "
                + str(result.returncode)
                + "\nstdout=" + result.stdout[-2500:]
                + "\nstderr=" + result.stderr[-2500:]
                + "\ninstaller=" + explanation[-2500:]
            )

        assert digest(target / updater.APP_EXE) == expected_exe_sha
        assert digest(target / "_internal" / "python312.dll") == expected_dll_sha
        assert not (target / ".dbd_qt_previous.exe").exists()
        assert not (target / ".dbd_qt_previous_internal").exists()
        assert not (target / "dbd_update_error.log").exists()
        assert not staged_dir.exists()
        for path, original in files.items():
            assert path.read_text(encoding="utf-8") == original, f"Changed user file: {path}"
        progress = target / "dbd_update_progress.log"
        assert "SUCCESS: installed portable Qt update" in progress.read_text(encoding="utf-8-sig")

        smoke(target / updater.APP_EXE, target, CURRENT)
        print(
            "PASS: real Beta 15 archive upgraded to published Beta 16; "
            "new EXE and runtime verified, all settings preserved", flush=True
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-zip", required=True, type=Path)
    parser.add_argument("--new-zip", required=True, type=Path)
    args = parser.parse_args()
    run(args.old_zip, args.new_zip)
