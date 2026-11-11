"""Windows E2E: click the *real QML update buttons* and upgrade published Beta 15.

This uses the source Qt Beta 16 UI/backend as a test harness with the installed
version set to Beta 15, the real published Beta 15 installation on disk, and
genuine released Beta 16 ZIP bytes. GitHub responses are cached locally so
the test is repeatable and cannot exhaust unauthenticated API limits.

The worker replaces ONLY a disposable installation under TemporaryDirectory.
The PowerShell helper relaunches the real published Beta 16 EXE with --smoke.
No releases, user files or real game installations are modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "qml_preview"))
import qt_updater as updater
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from qt_release_upgrade_e2e import verify_download, smoke, PREVIOUS, CURRENT

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify_cache(releases_file: Path, new_zip: Path) -> None:
    releases = json.loads(releases_file.read_text(encoding="utf-8-sig"))
    found = [
        r for r in releases
        if r.get("tag_name") == CURRENT and not r.get("draft")
    ]
    if len(found) != 1:
        raise AssertionError("The published Beta 16 release was not returned by GitHub API")
    assets = found[0]["assets"]
    named = next(a for a in assets if a["name"] == updater.ASSET)
    if named["size"] != new_zip.stat().st_size:
        raise AssertionError("GitHub release metadata does not match downloaded ZIP size")


def _window_buttons(window):
    """Walk QQuickItems to locate user-visible custom UiButton rectangles."""
    from PySide6.QtQuick import QQuickItem
    stack = [window.contentItem()]
    result = []
    while stack:
        obj = stack.pop()
        if isinstance(obj, QQuickItem):
            label = obj.property("label")
            if isinstance(label, str) and label:
                result.append((label, obj))
            stack.extend(obj.childItems())
    return result


def _click_qml_button(window, label: str):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest

    matches = [item for text, item in _window_buttons(window) if text == label and item.isVisible()]
    if len(matches) != 1:
        raise AssertionError(f"Expected one visible QML button {label!r}, got {len(matches)}")

    button = matches[0]
    work = window.findChild(type(window.contentItem()), "workScroll")
    if work is None:
        from PySide6.QtCore import QObject
        work = window.findChild(QObject, "workScroll")
    if work is None:
        raise AssertionError("QML main Flickable is missing")
    viewport = work.property("contentItem")
    if viewport is None:
        raise AssertionError("Qt Flickable has no contentItem property")
    local = button.mapToItem(viewport, QPointF(button.width() / 2, button.height() / 2))
    target_y = max(0, min(
        float(work.property("contentHeight")) - work.height(),
        local.y() - work.height() / 2,
    ))
    work.setProperty("contentY", target_y)
    QTest.qWait(160)  # settle Flickable and dynamic settings layout
    pos = button.mapToItem(window.contentItem(), QPointF(button.width()/2, button.height()/2))
    in_view = work.mapFromItem(window.contentItem(), pos)
    if not (0 <= in_view.x() < work.width() and 0 <= in_view.y() < work.height()):
        raise AssertionError(f"QML button outside scroll viewport: {label}, {in_view}")
    window.requestActivate()
    QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, pos.toPoint())
    QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, pos.toPoint())
    print("Clicked visible Qt button:", label, flush=True)


def run_worker(target: Path, new_zip: Path, releases_json: Path):
    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from native_backend import QtBridge

    verify_cache(releases_json, new_zip)
    updater.CURRENT_TAG = PREVIOUS  # Test-only: simulate Beta15's current version.

    # Actual published release content is downloaded by the GitHub workflow
    # and provided to the same streaming/verification code as normal.
    original_get = updater._get
    def released_bytes(url, timeout=30):
        if url == updater.BASE + "?per_page=30":
            return releases_json.open("rb")
        if url.startswith(f"https://github.com/{updater.REPO}/releases/download/{CURRENT}/"):
            if url.endswith("/" + updater.ASSET):
                return new_zip.open("rb")
            if url.endswith("/" + updater.ASSET + ".sha256"):
                return new_zip.with_name(new_zip.name + ".sha256").open("rb")
        raise AssertionError("Unexpected updater URL: " + url)
    updater._get = released_bytes

    # Only on the E2E test: wait for the relaunched Beta16 EXE to finish --smoke.
    # Shipping installers retain the ordinary nonblocking Start-Process.
    actual_launch = "Start-Process -FilePath $exe -WorkingDirectory $TargetDir -ErrorAction Stop"
    smoke_launch = (
        '$smoked = Start-Process -FilePath $exe -ArgumentList "--smoke" '
        '-WorkingDirectory $TargetDir -Wait -PassThru -ErrorAction Stop\n'
        '        if ($smoked.ExitCode -ne 0) { throw "Relaunched app smoke failed" }'
    )
    if updater.UPGRADE_SCRIPT.count(actual_launch) != 2:
        raise AssertionError("The release PowerShell installer changed; check relaunch steps")
    updater.UPGRADE_SCRIPT = updater.UPGRADE_SCRIPT.replace(actual_launch, smoke_launch)

    app = QApplication(["dbd-qt-update-button-e2e"])
    QQuickStyle.setStyle("Basic")
    backend = QtBridge()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(ROOT / "qml_preview" / "Main.qml")))
    if not engine.rootObjects():
        raise AssertionError("Unable to load real Qt settings page")
    window = engine.rootObjects()[0]
    window.setProperty("page", "Клики и тайминги")
    app.processEvents()

    errors = []
    state = {"phase": "navigate", "start": time.monotonic()}

    def fail(err):
        print("Qt updater E2E FAILED:", repr(err), flush=True)
        errors.append(str(err))
        app.quit()

    def tick():
        if time.monotonic() - state["start"] > 240:
            fail("Timeout waiting for UI/downloader/PowerShell hand-off")
            return
        try:
            phase = state["phase"]
            if phase == "navigate":
                _click_qml_button(window, "ПРОВЕРИТЬ ОБНОВЛЕНИЯ")
                if not backend.updateBusy:
                    raise AssertionError("Qt check button did not start checkUpdate")
                state["phase"] = "check"
            elif phase == "check":
                if not backend.updateBusy:
                    if not backend.updateAvailable:
                        raise AssertionError("No new update displayed: " + backend.updateText)
                    if backend._update_info["tag"] != CURRENT:
                        raise AssertionError("Update button selected wrong release")
                    print("QML detected published update:", backend.updateText, flush=True)
                    state["phase"] = "install"
            elif phase == "install":
                # The source Qt app has the same UI, but to exercise the portable
                # branch of installUpdate we point this isolated test harness at
                # a real extracted Beta15 EXE. Nothing else is changed.
                sys.frozen = True
                sys.executable = str(target / updater.APP_EXE)
                _click_qml_button(window, "СКАЧАТЬ И УСТАНОВИТЬ")
                if not backend.updateBusy:
                    raise AssertionError("Qt install button did not start installUpdate")
                print("Qt install button launched real stage() / SHA-256 flow", flush=True)
                state["phase"] = "handoff"
            elif phase == "handoff":
                if not backend.updateBusy:
                    if "Не удалось" in backend.updateText:
                        raise AssertionError(backend.updateText)
                    raise AssertionError("Download or install stopped unexpectedly: " + backend.updateText)
                # qt_updater.install_staged is called in backend._drain(), then
                # QApplication.quit ends this process and unblocks PowerShell.
        except Exception as exc:
            fail(exc)

    timer = QTimer()
    timer.setInterval(90)
    timer.timeout.connect(tick)
    timer.start()
    app.aboutToQuit.connect(backend.close)
    result = app.exec()
    if errors:
        return 1
    if state["phase"] != "handoff":
        print("Worker exited before update handoff", flush=True)
        return 2
    print("Qt source UI closed after starting portable installer", flush=True)
    return result


def run_parent(old_zip: Path, new_zip: Path, releases_json: Path):
    if sys.platform != "win32":
        raise RuntimeError("Windows CI required")
    old_zip, new_zip, releases_json = (
        old_zip.resolve(), new_zip.resolve(), releases_json.resolve())
    verify_download(old_zip)
    verify_download(new_zip)
    verify_cache(releases_json, new_zip)

    with tempfile.TemporaryDirectory(prefix="Qt UI button upgrade with spaces - ") as d:
        root = Path(d)
        old_dir = root / "old unpacked"
        old_dir.mkdir()
        unpacked = updater._unpack_verified(old_zip, old_dir)
        target = root / "DBD Installed With Spaces"
        unpacked.rename(target)
        smoke(target / updater.APP_EXE, target, PREVIOUS)
        userfiles = {
            target / "dbd_randomizer_config.json": '{"language":"ru","owned":["do not lose"]}',
            target / "custom_favorites.json": '{"preserve":true}',
        }
        for path, value in userfiles.items():
            path.write_text(value, encoding="utf-8")

        expected_new = root / "new_unpacked"
        expected_new.mkdir()
        staged = updater._unpack_verified(new_zip, expected_new)
        exe_hash = digest(staged / updater.APP_EXE)
        dll_hash = digest(staged / "_internal" / "python312.dll")

        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8")
        command = [
            sys.executable, str(Path(__file__).resolve()),
            "--worker", "--target", str(target), "--new-zip", str(new_zip),
            "--release-json", str(releases_json),
        ]
        print("Spawning Qt app and actual QML button test", flush=True)
        worker = subprocess.run(
            command, env=env, cwd=ROOT, capture_output=True, text=True,
            timeout=350, errors="replace",
        )
        print("Qt worker STDOUT:\n" + worker.stdout[-5000:], flush=True)
        if worker.returncode:
            raise AssertionError(
                f"Qt worker failed: {worker.returncode}; stderr={worker.stderr[-3000:]}"
            )

        # Powershell waits for the *worker* process to exit before replacing.
        last_progress = None
        end = time.monotonic() + 130
        while time.monotonic() < end:
            progress = target / "dbd_update_progress.log"
            if progress.is_file():
                last_progress = progress.read_text(encoding="utf-8-sig", errors="replace")
                if "SUCCESS: installed portable Qt update" in last_progress:
                    break
                if "FAILED:" in last_progress:
                    raise AssertionError("PowerShell installer failed: " + last_progress[-2500:])
            time.sleep(.5)
        else:
            raise AssertionError("No installer SUCCESS after real button flow: " + str(last_progress))

        if digest(target / updater.APP_EXE) != exe_hash:
            raise AssertionError("EXE has not been updated")
        if digest(target / "_internal" / "python312.dll") != dll_hash:
            raise AssertionError("Python runtime was not updated")
        for path, original in userfiles.items():
            if path.read_text(encoding="utf-8") != original:
                raise AssertionError(f"User file changed: {path}")
        if (target / "dbd_update_error.log").exists():
            raise AssertionError("Installer recorded an error despite successful hand-off")
        print("PASS: QML check button -> published release metadata -> "
              "QML install button -> real archive verification and extraction -> "
              "PowerShell file replacement -> Beta16 --smoke relaunch; user files intact", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--target", type=Path)
    parser.add_argument("--old-zip", type=Path)
    parser.add_argument("--new-zip", type=Path, required=True)
    parser.add_argument("--release-json", type=Path, required=True)
    args = parser.parse_args()
    if args.worker:
        return run_worker(args.target.resolve(), args.new_zip.resolve(),
                          args.release_json.resolve())
    run_parent(args.old_zip, args.new_zip, args.release_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
