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
CURRENT_TAG = "v2.28.0-qt-beta.11"
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
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)-qt-beta\.(\d+)", str(tag))
    return tuple(map(int, match.groups())) if match else None


def check():
    with _get(BASE + "?per_page=30") as response:
        releases = json.load(response)
    if not isinstance(releases, list):
        raise RuntimeError("Invalid release list")
    current = _key(CURRENT_TAG)
    newest = None
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        version = _key(release.get("tag_name"))
        if not version or (current and version <= current):
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


def stage(info, target_dir):
    """Return a verified sibling staging folder's inner portable app directory."""
    target_dir = Path(target_dir).resolve()
    if not target_dir.is_dir():
        raise RuntimeError("Application installation folder not found")
    expected = _sha256_for(info)
    staging = Path(tempfile.mkdtemp(prefix=STAGE_PREFIX, dir=target_dir.parent))
    archive = staging / ASSET
    amount = 0
    digest = hashlib.sha256()
    try:
        with _get(info["asset_url"], timeout=120) as stream, archive.open("wb") as out:
            while chunk := stream.read(256 * 1024):
                amount += len(chunk)
                if amount > MAX_DOWNLOAD:
                    raise RuntimeError("Update exceeds download size limit")
                digest.update(chunk)
                out.write(chunk)
        if amount != info["asset_size"] or digest.hexdigest() != expected:
            raise RuntimeError("Update size / SHA-256 verification failed")
        result = _unpack_verified(archive, staging)
        archive.unlink(missing_ok=True)
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
    [string]$StagedDir
)
$ErrorActionPreference = "Stop"
try { Wait-Process -Id $WaitFor -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Milliseconds 800

$exe = Join-Path $TargetDir "DBDRandomizerQtBeta.exe"
$runtime = Join-Path $TargetDir "_internal"
$exeBackup = Join-Path $TargetDir ".dbd_qt_previous.exe"
$runtimeBackup = Join-Path $TargetDir ".dbd_qt_previous_internal"
$sourceExe = Join-Path $StagedDir "DBDRandomizerQtBeta.exe"
$sourceRuntime = Join-Path $StagedDir "_internal"

$oldExeMoved = $false
$oldRuntimeMoved = $false
$newExeMoved = $false
$newRuntimeMoved = $false
$success = $false

try {
    if (-not (Test-Path -LiteralPath $sourceExe -PathType Leaf) -or
        -not (Test-Path -LiteralPath $sourceRuntime -PathType Container) -or
        -not (Test-Path -LiteralPath (Join-Path $sourceRuntime "python312.dll") -PathType Leaf)) {
        throw "Staged portable application is incomplete"
    }
    if ((Test-Path -LiteralPath $exeBackup) -or (Test-Path -LiteralPath $runtimeBackup)) {
        throw "Previous update backup found; do not overwrite it"
    }
    if (Test-Path -LiteralPath $runtime) {
        Move-Item -LiteralPath $runtime -Destination $runtimeBackup -ErrorAction Stop
        $oldRuntimeMoved = $true
    }
    if (Test-Path -LiteralPath $exe) {
        Move-Item -LiteralPath $exe -Destination $exeBackup -ErrorAction Stop
        $oldExeMoved = $true
    }
    Move-Item -LiteralPath $sourceRuntime -Destination $runtime -ErrorAction Stop
    $newRuntimeMoved = $true
    Move-Item -LiteralPath $sourceExe -Destination $exe -ErrorAction Stop
    $newExeMoved = $true
    $success = $true
    Start-Process -FilePath $exe -WorkingDirectory $TargetDir
} catch {
    $errorText = $_.Exception.Message
    try {
        if ($newExeMoved -and (Test-Path -LiteralPath $exe)) {
            Remove-Item -LiteralPath $exe -Force
        }
        if ($newRuntimeMoved -and (Test-Path -LiteralPath $runtime)) {
            Remove-Item -LiteralPath $runtime -Recurse -Force
        }
        if ($oldExeMoved -and (Test-Path -LiteralPath $exeBackup)) {
            Move-Item -LiteralPath $exeBackup -Destination $exe -Force
        }
        if ($oldRuntimeMoved -and (Test-Path -LiteralPath $runtimeBackup)) {
            Move-Item -LiteralPath $runtimeBackup -Destination $runtime -Force
        }
    } catch {
        $errorText += " | Rollback failed: " + $_.Exception.Message
    }
    "$([DateTime]::Now.ToString('s')) $errorText" |
        Out-File -FilePath (Join-Path $TargetDir "dbd_update_error.log") -Encoding utf8 -Append
} finally {
    if ($success) {
        if (Test-Path -LiteralPath $exeBackup) { Remove-Item -LiteralPath $exeBackup -Force }
        if (Test-Path -LiteralPath $runtimeBackup) {
            Remove-Item -LiteralPath $runtimeBackup -Recurse -Force
        }
        $stageParent = Split-Path -Parent $StagedDir
        if (Test-Path -LiteralPath $stageParent) {
            Remove-Item -LiteralPath $stageParent -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
'''


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
