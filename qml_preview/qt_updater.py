"""Secure release updater for the standalone Qt Windows executable.

Updates are opt-in, fetched over HTTPS from the official GitHub Releases API,
verified with SHA-256, staged next to the executable, and replaced only after
the running process exits. Existing configuration is never changed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = "yungspiderq/dbd-randomizer"
BASE = f"https://api.github.com/repos/{REPO}/releases"
CURRENT_TAG = "v2.28.0-qt-beta.5"
ASSET = "DBDRandomizerQtBeta.exe"
LIMIT_BYTES = 650 * 1024 * 1024


def _get(url, timeout=30):
    if not url.startswith("https://github.com/" + REPO + "/") and not url.startswith(BASE):
        raise ValueError("Blocked foreign update URL")
    request = urllib.request.Request(url, headers={
        "User-Agent": "DBDRandomizerQtUpdater/" + CURRENT_TAG,
        "Accept": "application/vnd.github+json",
    })
    return urllib.request.urlopen(request, timeout=timeout)


def _key(tag):
    result = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)-qt-beta\.(\d+)", str(tag))
    if result:
        return tuple(map(int, result.groups()))
    return None


def check():
    with _get(BASE + "?per_page=30") as response:
        releases = json.load(response)
    if not isinstance(releases, list):
        raise RuntimeError("Invalid release response")
    current = _key(CURRENT_TAG)
    newest = None
    for release in releases:
        if release.get("draft"):
            continue
        version = _key(release.get("tag_name"))
        if not version or (current is not None and version <= current):
            continue
        assets = [a for a in release.get("assets", [])
                  if a.get("name") == ASSET and a.get("size", 0) > 1_000_000]
        if not assets:
            continue
        if newest is None or version > _key(newest["tag_name"]):
            newest = release
    if newest is None:
        return None
    a = next(x for x in newest["assets"] if x["name"] == ASSET)
    return {
        "tag": newest["tag_name"],
        "name": newest.get("name") or newest["tag_name"],
        "url": newest["html_url"],
        "asset_url": a["browser_download_url"],
        "asset_size": a["size"],
        "digest": a.get("digest") or "",
        "checksum_url": next(
            (x["browser_download_url"] for x in newest["assets"] if x["name"] == ASSET + ".sha256"), ""
        ),
    }


def _sha256_for(info):
    digest = info.get("digest") or ""
    if digest.startswith("sha256:") and re.fullmatch(r"[0-9a-fA-F]{64}", digest[7:]):
        return digest[7:].lower()
    url = info.get("checksum_url")
    if not url:
        raise RuntimeError("Release is missing SHA-256 checksum")
    with _get(url) as response:
        line = response.read(512).decode("ascii").strip()
    match = re.search(r"\b([0-9a-fA-F]{64})\b", line)
    if not match:
        raise RuntimeError("Invalid release checksum")
    return match.group(1).lower()


def stage(info, target_dir):
    target = Path(target_dir) / ASSET
    staged = target.with_name(target.name + ".new")
    expected = _sha256_for(info)
    hasher = hashlib.sha256()
    size = 0
    try:
        with _get(info["asset_url"], timeout=75) as stream, staged.open("wb") as out:
            while True:
                chunk = stream.read(256 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > LIMIT_BYTES:
                    raise RuntimeError("Update exceeds file size limit")
                out.write(chunk)
                hasher.update(chunk)
        if size != info["asset_size"] or hasher.hexdigest() != expected:
            raise RuntimeError("Update file verification failed: size / SHA-256")
        if staged.open("rb").read(2) != b"MZ":
            raise RuntimeError("Downloaded file is not a Windows executable")
        return staged
    except Exception:
        staged.unlink(missing_ok=True)
        raise


UPGRADE_SCRIPT = r'''
param([int]$WaitFor, [string]$Target, [string]$Staged)
$ErrorActionPreference = "Stop"
try { Wait-Process -Id $WaitFor -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Milliseconds 900
$backup = $Target + ".bak"
try {
    if (Test-Path -LiteralPath $Target) {
        Copy-Item -LiteralPath $Target -Destination $backup -Force
        Remove-Item -LiteralPath $Target -Force
    }
    Move-Item -LiteralPath $Staged -Destination $Target -Force
    Start-Process -FilePath $Target -WorkingDirectory (Split-Path -Parent $Target)
} catch {
    if ((Test-Path -LiteralPath $backup) -and (-not (Test-Path -LiteralPath $Target))) {
        Copy-Item -LiteralPath $backup -Destination $Target -Force
    }
    Write-Error $_
}
'''


def install_staged(staged):
    if not getattr(sys, "frozen", False) or sys.platform != "win32":
        raise RuntimeError("Automatic replacement works only in the packaged Windows EXE")
    target = Path(sys.executable).resolve()
    # Update in place to preserve adjacent settings/database, never overwrite config.
    if staged.parent.resolve() != target.parent or staged.name != ASSET + ".new":
        raise ValueError("Staged file must reside beside running EXE")
    script = target.with_name(".dbd_qt_update.ps1")
    script.write_text(UPGRADE_SCRIPT, encoding="utf-8-sig")
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "Bypass", "-File", str(script),
         "-WaitFor", str(os.getpid()), "-Target", str(target),
         "-Staged", str(staged)],
        cwd=str(target.parent),
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
