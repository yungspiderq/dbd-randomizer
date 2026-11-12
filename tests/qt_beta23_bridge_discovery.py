"""Check the real published RC1 release and the Beta23 bridge's update decision.

The workflow obtains the release JSON through the authenticated GitHub API.
No actual user installation is changed by this script.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "qml_preview"))
import qt_updater as updater

OLD_TAG = "v2.28.0-qt-beta.22"
BRIDGE_TAG = "v2.28.0-qt-beta.23"
RC1_TAG = "v3.0.0-qt-rc.1"


def legacy_beta22_key(tag):
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)-qt-beta\.(\d+)", str(tag))
    return tuple(map(int, match.groups())) if match else None


def check(release: dict) -> None:
    assert updater.CURRENT_TAG == BRIDGE_TAG
    assert legacy_beta22_key(BRIDGE_TAG) > legacy_beta22_key(OLD_TAG), (
        "Published Beta22 cannot recognize the proposed bridge tag"
    )
    assert legacy_beta22_key(RC1_TAG) is None, "Unexpected legacy RC recognition"
    assert release.get("tag_name") == RC1_TAG
    assert release.get("draft") is False and release.get("prerelease") is True
    assets = release.get("assets") or []
    by_name = {a.get("name"): a for a in assets if isinstance(a, dict)}
    zip_asset = by_name.get(updater.ASSET)
    sha_asset = by_name.get(updater.ASSET + ".sha256")
    assert zip_asset and isinstance(zip_asset.get("size"), int) and zip_asset["size"] > 1_000_000
    assert sha_asset and isinstance(sha_asset.get("size"), int) and sha_asset["size"] >= 64
    assert zip_asset.get("browser_download_url", "").startswith(
        "https://github.com/" + updater.REPO + "/releases/download/" + RC1_TAG + "/"
    )
    # Simulate the exact public API record with the network fetch mocked:
    # no fabricated release URLs or timestamps.
    with patch.object(updater, "_get", return_value=io.BytesIO(
            json.dumps([release], ensure_ascii=False).encode("utf-8"))):
        found = updater.check()
    assert found and found["tag"] == RC1_TAG, "Bridge cannot discover published RC1"
    assert found["checksum_url"].endswith(updater.ASSET + ".sha256")
    print("PASS: shipped Beta22 parser accepts Beta23; Beta23 recognizes real "
          "published RC1 with portable ZIP and SHA-256.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-json", type=Path, required=True)
    args = parser.parse_args()
    check(json.loads(args.release_json.read_text(encoding="utf-8-sig")))
