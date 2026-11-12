"""Verified GitHub Releases updater for Windows *onedir* Qt builds.

A portable release ZIP contains DBDRandomizerQtBeta/ with an EXE and _internal.
The archive is downloaded with a release SHA-256 check, unpacked safely in a
sibling staging folder (same drive), and installed only after the Qt process
exits. Only the EXE and _internal directory are replaced; adjacent JSON,
database, icon cache, and user files remain untouched.

Migration from beta.10's broken --onefile EXE requires a one-time manual ZIP
download, because an executable that cannot launch cannot self-update.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

REPO = "yungspiderq/dbd-randomizer"
BASE = f"https://api.github.com/repos/{REPO}/releases"
CURRENT_TAG = "v3.0.0-qt-rc.1"
ASSET = "DBDRandomizerQtBeta.zip"
APP_EXE = "DBDRandomizerQtBeta.exe"
PACKAGE_ROOT = "DBDRandomizerQtBeta"
MAX_DOWNLOAD = 950 * 1024 * 1024
MAX_UNPACKED = 2 * 1024 * 1024 * 1024
MAX_FILES = 20000
STAGE_PREFIX = ".dbd_qt_stage_"


def _get(url, timeout=30):
    allowed = (url.startswith("https://github.com/" + REPO + "/releases/download/") or
               url.startswith(BASE + "?"))
    if not allowed:
        raise ValueError("Blocked foreign or unexpected update URL")
    req = urllib.request.Request(url, headers={
        "User-Agent": "DBDRandomizerQtUpdater/" + CURRENT_TAG,
        "Accept": "application/vnd.github+json",
    })
    return urllib.request.urlopen(req, timeout=timeout)


def _key(tag):
    """Order old beta, new Qt RC and stable tags without accepting unknown channels.

    Numeric components are always compared as numbers:
    beta.22 < rc.1 < final for the same major/minor/patch.
    The stable tag is vMAJOR.MINOR.PATCH (without an extra Qt suffix).
    """
    match = re.fullmatch(
        r"v(\d+)\.(\d+)\.(\d+)(?:-qt-(beta|rc)\.(\d+))?", str(tag)
    )
    if not match:
        return None
    major, minor, patch, channel, sequence = match.groups()
    # Historic v2.x Stable releases use the legacy Tk UI, not the Qt portable
    # installation. Never offer them as updates for the Qt channel.
    if channel is None and int(major) < 3:
        return None
    rank = {"beta": 0, "rc": 1, None: 2}[channel]
    return (int(major), int(minor), int(patch), rank, int(sequence or 0))


def check():
    with _get(BASE + "?per_page=30") as response:
        releases = json.load(response)
    if not isinstance(releases, list):
        raise RuntimeError("Invalid release list")
    current = _key(CURRENT_TAG)
    if current is None:
        raise RuntimeError("Invalid installed version tag")
    newest = None
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        version = _key(release.get("tag_name"))
        if not version or version <= current:
            continue
        assets = release.get("assets")
        if not isinstance(assets, list):
            continue
        archive = next((a for a in assets if isinstance(a, dict)
                        and a.get("name") == ASSET
                        and isinstance(a.get("size"), int)
                        and 1_000_000 < a["size"] <= MAX_DOWNLOAD), None)
        if not archive:
            continue
        # Never advertise an incomplete upload that cannot pass stage()'s
        # mandatory SHA-256 verification. Without this gate, the UI shows
        # "Update available" but installation immediately fails.
        checksum = next(
            (a.get("browser_download_url") for a in assets
             if isinstance(a, dict) and a.get("name") == ASSET + ".sha256"
             and isinstance(a.get("browser_download_url"), str)), ""
        )
        digest = str(archive.get("digest") or "")
        if not (re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest) or checksum):
            continue
        if newest is None or version > _key(newest["tag_name"]):
            newest = release
    if newest is None:
        return None
    archive = next(a for a in newest["assets"] if a.get("name") == ASSET)
    return {
        "tag": newest["tag_name"],
        "name": newest.get("name") or newest["tag_name"],
        "url": newest["html_url"],
        "asset_url": archive["browser_download_url"],
        "asset_size": archive["size"],
        "digest": archive.get("digest") or "",
        "checksum_url": next(
            (x.get("browser_download_url") for x in newest["assets"]
             if isinstance(x, dict) and x.get("name") == ASSET + ".sha256"), ""
        ),
    }


def _sha256_for(info):
    digest = str(info.get("digest") or "")
    if digest.startswith("sha256:") and re.fullmatch(r"[0-9a-fA-F]{64}", digest[7:]):
        return digest[7:].lower()
    url = info.get("checksum_url")
    if not url:
        raise RuntimeError("Release missing SHA-256 checksum")
    with _get(url) as response:
        value = response.read(512).decode("ascii")
    # Require the checksum to name the correct archive, not some other file.
    line = value.strip().splitlines()[0] if value.strip() else ""
    match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?" +
                         re.escape(ASSET), line)
    if not match:
        raise RuntimeError("Invalid release checksum file")
    return match.group(1).lower()


def _unpack_verified(archive, staging):
    """Reject path traversal, symlinks, duplicate entries, and oversized ZIPs."""
    root = staging / PACKAGE_ROOT
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if not members or len(members) > MAX_FILES:
            raise RuntimeError("Unexpected number of files in update")
        total = 0
        seen = set()
        for member in members:
            name = member.filename
            parts = PurePosixPath(name).parts
            if (not parts or parts[0] != PACKAGE_ROOT or
                    name.startswith("/") or "\\" in name or
                    any(x in ("", ".", "..") or ":" in x for x in parts)):
                raise RuntimeError("Unsafe path in update ZIP")
            if parts in seen:
                raise RuntimeError("Duplicate entry in update ZIP")
            seen.add(parts)
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise RuntimeError("Symlinks are not permitted in update ZIP")
            total += member.file_size
            if total > MAX_UNPACKED:
                raise RuntimeError("Update ZIP expands beyond size limit")
            path = staging.joinpath(*parts)
            if member.is_dir():
                path.mkdir(parents=True, exist_ok=True)
                continue
            if member.file_size > MAX_UNPACKED:
                raise RuntimeError("Oversized ZIP entry")
            path.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with bundle.open(member) as source, path.open("xb") as output:
                while chunk := source.read(256 * 1024):
                    written += len(chunk)
                    if written > member.file_size:
                        raise RuntimeError("ZIP entry exceeds declared size")
                    output.write(chunk)
            if written != member.file_size:
                raise RuntimeError("Incomplete ZIP member")
    if not (root / APP_EXE).is_file():
        raise RuntimeError("ZIP does not contain the portable EXE")
    internal = root / "_internal"
    if not internal.is_dir() or not (internal / "python312.dll").is_file():
        raise RuntimeError("ZIP is missing _internal/python312.dll")
    return root


def stage(info, target_dir, progress=None):
    """Download, hash-check and unpack a release with optional progress callback.

    The callback receives brief status messages; it never reports verified
    completion before size/hash validation and safe archive extraction.
    """
    def notify(message):
        if progress is not None:
            progress(message)

    target_dir = Path(target_dir).resolve()
    if not target_dir.is_dir():
        raise RuntimeError("Application installation folder not found")
    expected = _sha256_for(info)
    staging = Path(tempfile.mkdtemp(prefix=STAGE_PREFIX, dir=target_dir.parent))
    archive = staging / ASSET
    amount = 0
    digest = hashlib.sha256()
    last_bucket = -1
    expected_size = int(info["asset_size"])
    try:
        notify("Подключение к GitHub Releases…")
        with _get(info["asset_url"], timeout=120) as stream, archive.open("wb") as out:
            while chunk := stream.read(256 * 1024):
                amount += len(chunk)
                if amount > MAX_DOWNLOAD:
                    raise RuntimeError("Update exceeds download size limit")
                digest.update(chunk)
                out.write(chunk)
                bucket = min(10, (amount * 10) // max(expected_size, 1))
                if bucket > last_bucket:
                    last_bucket = bucket
                    notify(f"Скачивание обновления: {min(100, bucket * 10)}%")
        notify("Сверяю размер и SHA-256 загруженного архива…")
        if amount != expected_size or digest.hexdigest() != expected:
            raise RuntimeError("Update size / SHA-256 verification failed")
        notify("Проверка пройдена. Распаковываю обновление…")
        result = _unpack_verified(archive, staging)
        archive.unlink(missing_ok=True)
        notify("Распаковка завершена. Подготавливаю установщик…")
        return result
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


# The script is launched from the installed EXE and waits until that process exits.
# Only _internal and the EXE are moved. Configs/databases remain in place.
# If any move fails, restore the old runtime before reporting failure.
UPGRADE_SCRIPT = r'''
param(
    [int]$WaitFor,
    [string]$TargetDir,
    [string]$StagedDir,
    [switch]$SkipLaunch
)
$ErrorActionPreference = "Stop"
$exe = Join-Path $TargetDir "DBDRandomizerQtBeta.exe"
$runtime = Join-Path $TargetDir "_internal"
$exeBackup = Join-Path $TargetDir ".dbd_qt_previous.exe"
$runtimeBackup = Join-Path $TargetDir ".dbd_qt_previous_internal"
$sourceExe = Join-Path $StagedDir "DBDRandomizerQtBeta.exe"
$sourceRuntime = Join-Path $StagedDir "_internal"
$errorLog = Join-Path $TargetDir "dbd_update_error.log"
$progressLog = Join-Path $TargetDir "dbd_update_progress.log"
$phase = "initializing"
$oldExeMoved = $false
$oldRuntimeMoved = $false
$newExeMoved = $false
$newRuntimeMoved = $false
$success = $false
$failed = $false

function Write-Progress([string]$message) {
    try {
        "$([DateTime]::Now.ToString('s')) $message" |
            Out-File -FilePath $progressLog -Encoding utf8 -Append -ErrorAction Stop
    } catch { }
}

function Move-WithRetry([string]$from, [string]$to) {
    for ($attempt = 0; $attempt -lt 6; $attempt++) {
        try {
            Move-Item -LiteralPath $from -Destination $to -ErrorAction Stop
            return
        } catch {
            if ($attempt -eq 5) { throw }
            Start-Sleep -Milliseconds (250 * ($attempt + 1))
        }
    }
}

try {
    $phase = "waiting for old application"
    Write-Progress $phase
    if ($WaitFor -gt 0) {
        $oldProcess = Get-Process -Id $WaitFor -ErrorAction SilentlyContinue
        if ($null -ne $oldProcess) {
            Wait-Process -Id $WaitFor -Timeout 90 -ErrorAction Stop
        }
    }
    Start-Sleep -Milliseconds 500

    $phase = "validating staged files"
    Write-Progress $phase
    if (-not (Test-Path -LiteralPath $sourceExe -PathType Leaf) -or
        -not (Test-Path -LiteralPath $sourceRuntime -PathType Container) -or
        -not (Test-Path -LiteralPath (Join-Path $sourceRuntime "python312.dll") -PathType Leaf)) {
        throw "Staged portable application is incomplete"
    }
    if ((Test-Path -LiteralPath $exeBackup) -or (Test-Path -LiteralPath $runtimeBackup)) {
        throw "Previous update backup exists; inspect the old installation before retrying"
    }

    $phase = "backing up old runtime"
    Write-Progress $phase
    if (Test-Path -LiteralPath $runtime) {
        Move-WithRetry $runtime $runtimeBackup
        $oldRuntimeMoved = $true
    }
    $phase = "backing up old executable"
    Write-Progress $phase
    if (Test-Path -LiteralPath $exe) {
        Move-WithRetry $exe $exeBackup
        $oldExeMoved = $true
    }
    $phase = "installing new runtime"
    Write-Progress $phase
    Move-WithRetry $sourceRuntime $runtime
    $newRuntimeMoved = $true
    $phase = "installing new executable"
    Write-Progress $phase
    Move-WithRetry $sourceExe $exe
    $newExeMoved = $true

    # Optional shortcut tools never affect the transactional EXE/runtime swap.
    # Preserve them in the installed portable folder for a manually repaired
    # desktop shortcut after extracting RC1 in a fresh directory.
    foreach ($helper in @("Repair DBD Randomizer Shortcut.ps1", "Update DBD Randomizer Shortcut.cmd")) {
        $from = Join-Path $StagedDir $helper
        if (Test-Path -LiteralPath $from -PathType Leaf) {
            try {
                Copy-Item -LiteralPath $from -Destination (Join-Path $TargetDir $helper) -Force -ErrorAction Stop
            } catch {
                Write-Progress ("Shortcut helper copy failed: " + $_.Exception.Message)
            }
        }
    }
    $phase = "launching updated application"
    Write-Progress $phase
    if (-not $SkipLaunch) {
        # An in-place update may retain an old shortcut targeting pythonw or
        # a removed Tk script. Repair it after EXE validation, without failing
        # the program installation if Windows denies shortcut access.
        $repair = Join-Path $TargetDir "Repair DBD Randomizer Shortcut.ps1"
        if (Test-Path -LiteralPath $repair -PathType Leaf) {
            try {
                & $repair -InstallDir $TargetDir | Out-Null
            } catch {
                Write-Progress ("Shortcut repair failed: " + $_.Exception.Message)
            }
        }
        Start-Process -FilePath $exe -WorkingDirectory $TargetDir -ErrorAction Stop
    }
    $success = $true
} catch {
    $failed = $true
    $errorText = "$phase : $($_.Exception.Message)"
    Write-Progress ("FAILED: " + $errorText)
    try {
        if ($newExeMoved -and (Test-Path -LiteralPath $exe)) {
            Remove-Item -LiteralPath $exe -Force -ErrorAction Stop
        }
        if ($newRuntimeMoved -and (Test-Path -LiteralPath $runtime)) {
            Remove-Item -LiteralPath $runtime -Recurse -Force -ErrorAction Stop
        }
        if ($oldExeMoved -and (Test-Path -LiteralPath $exeBackup)) {
            Move-Item -LiteralPath $exeBackup -Destination $exe -ErrorAction Stop
        }
        if ($oldRuntimeMoved -and (Test-Path -LiteralPath $runtimeBackup)) {
            Move-Item -LiteralPath $runtimeBackup -Destination $runtime -ErrorAction Stop
        }
    } catch {
        $errorText += " | Rollback failed: " + $_.Exception.Message
    }
    try {
        "$([DateTime]::Now.ToString('s')) $errorText" |
            Out-File -FilePath $errorLog -Encoding utf8 -Append -ErrorAction Stop
    } catch {
        Write-Progress ("Cannot write error log: " + $_.Exception.Message)
    }
    # If rollback succeeded, reopen the previous app so its UI can explain
    # the failed update rather than leaving the user with a closed window.
    if (-not $SkipLaunch -and (Test-Path -LiteralPath $exe -PathType Leaf)) {
        try {
            Start-Process -FilePath $exe -WorkingDirectory $TargetDir -ErrorAction Stop
        } catch {
            Write-Progress ("Could not restart old application: " + $_.Exception.Message)
        }
    }
} finally {
    if ($success) {
        # Backups are never deleted before the new EXE has been placed.
        try {
            if (Test-Path -LiteralPath $exeBackup) {
                Remove-Item -LiteralPath $exeBackup -Force -ErrorAction Stop
            }
            if (Test-Path -LiteralPath $runtimeBackup) {
                Remove-Item -LiteralPath $runtimeBackup -Recurse -Force -ErrorAction Stop
            }
            if (Test-Path -LiteralPath $errorLog) {
                Remove-Item -LiteralPath $errorLog -Force -ErrorAction Stop
            }
        } catch {
            Write-Progress ("Installed, but cleanup needs attention: " + $_.Exception.Message)
        }
        $stageParent = Split-Path -Parent $StagedDir
        if (Test-Path -LiteralPath $stageParent) {
            Remove-Item -LiteralPath $stageParent -Recurse -Force -ErrorAction SilentlyContinue
        }
        Write-Progress "SUCCESS: installed portable Qt update"
    }
}
# Clean up only the helper generated by install_staged, never manually run scripts.
if ($PSCommandPath -and [IO.Path]::GetFileName($PSCommandPath) -like ".dbd_qt_install_*.ps1") {
    try {
        Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction Stop
    } catch {
        Write-Progress ("Installer helper cleanup needs attention: " + $_.Exception.Message)
    }
}
if ($failed) { exit 1 }
exit 0
'''



def last_install_error(target_dir):
    """Surface a failed installer attempt when the application next opens."""
    path = Path(target_dir) / "dbd_update_error.log"
    try:
        if path.is_file():
            lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            if lines:
                return ("Предыдущее обновление не установилось: " + lines[-1][:440] +
                        " (подробнее в dbd_update_error.log)")
    except OSError:
        pass
    return ""


def install_staged(staged):
    if not getattr(sys, "frozen", False) or sys.platform != "win32":
        raise RuntimeError("Automatic installation requires the Windows portable EXE")
    target_dir = Path(sys.executable).resolve().parent
    app = Path(staged).resolve()
    if (app.name != PACKAGE_ROOT or not app.parent.name.startswith(STAGE_PREFIX) or
            app.parent.parent != target_dir.parent or not app.is_dir()):
        raise ValueError("Staged update must be adjacent to the installed app folder")
    if not (app / APP_EXE).is_file() or not (app / "_internal" / "python312.dll").is_file():
        raise RuntimeError("Staged update is incomplete")
    # Helper remains outside both the running directory and the _internal tree.
    fd, script_name = tempfile.mkstemp(prefix=".dbd_qt_install_", suffix=".ps1",
                                      dir=target_dir.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig") as output:
            output.write(UPGRADE_SCRIPT)
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", script_name,
             "-WaitFor", str(os.getpid()),
             "-TargetDir", str(target_dir), "-StagedDir", str(app)],
            cwd=str(target_dir),
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    except Exception:
        Path(script_name).unlink(missing_ok=True)
        raise
