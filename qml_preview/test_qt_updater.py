"""Release updater regression tests: portable ZIP, SHA-256 and safe extraction.

All tests run offline and do not launch PowerShell or touch a real install.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qt_updater as u


class UpdaterTests(unittest.TestCase):
    @staticmethod
    def archive(*, traversal=False, symlink=False, runtime=True):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(u.PACKAGE_ROOT + "/" + u.APP_EXE, b"MZ" + b"\0" * 100)
            if runtime:
                z.writestr(u.PACKAGE_ROOT + "/_internal/python312.dll", b"MZ\0dll")
                z.writestr(u.PACKAGE_ROOT + "/_internal/qml_preview/Main.qml",
                           b"import QtQuick\n")
            if traversal:
                z.writestr(u.PACKAGE_ROOT + "/../escape.txt", b"not allowed")
            if symlink:
                member = zipfile.ZipInfo(u.PACKAGE_ROOT + "/_internal/link")
                member.create_system = 3
                member.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(member, b"outside")
        return data.getvalue()

    def test_installer_error_message_can_be_read_after_relaunch(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "dbd_update_error.log"
            self.assertEqual(u.last_install_error(folder), "")
            path.write_text("2026-11-11 first failure\n2026-11-11 Move-Item failed: Access denied\n", encoding="utf-8")
            self.assertIn("Access denied", u.last_install_error(folder))

    def test_version_parsing_preserves_beta_and_supports_rc(self):
        self.assertLess(u._key("v2.28.0-qt-beta.10"), u._key(u.CURRENT_TAG))
        self.assertLess(u._key("v2.28.0-qt-beta.22"), u._key(u.CURRENT_TAG))
        self.assertLess(u._key(u.CURRENT_TAG), u._key("v3.0.0-qt-rc.1"))
        self.assertLess(u._key("v3.0.0-qt-rc.1"), u._key("v3.0.0"))
        self.assertIsNone(u._key("v2.28.0"))  # Legacy Tk stable
        self.assertIsNone(u._key("v3.0.0-qt-preview.1"))
        self.assertIsNone(u._key("v999.0.0-malicious"))
        self.assertEqual(u.ASSET, "DBDRandomizerQtBeta.zip")

    def test_beta23_version_does_not_offer_itself(self):
        self.assertEqual(u.CURRENT_TAG, "v2.28.0-qt-beta.23")
        def release(tag):
            return {"draft": False, "tag_name": tag,
                    "name": tag, "html_url": "https://github.com/" + u.REPO + "/releases/tag/" + tag,
                    "assets": [
                        {"name": u.ASSET, "size": 20000000,
                         "browser_download_url": "https://github.com/" + u.REPO +
                         "/releases/download/" + tag + "/" + u.ASSET},
                        {"name": u.ASSET + ".sha256",
                         "browser_download_url": "https://github.com/" + u.REPO +
                         "/releases/download/" + tag + "/" + u.ASSET + ".sha256"},
                    ]}
        with patch.object(u, "_get", return_value=io.BytesIO(json.dumps([
                release(u.CURRENT_TAG), release("v2.28.0-qt-beta.22")]).encode())):
            self.assertIsNone(u.check())
        with patch.object(u, "_get", return_value=io.BytesIO(json.dumps([
                release("v3.0.0-qt-rc.1"), release(u.CURRENT_TAG)]).encode())):
            self.assertEqual(u.check()["tag"], "v3.0.0-qt-rc.1")

    def test_shipped_beta22_recognizes_beta23_bridge_but_not_rc1(self):
        # Reproduce the exact old _key grammar included in published Beta22.
        def legacy_key(tag):
            m = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)-qt-beta\.(\d+)", tag)
            return tuple(map(int, m.groups())) if m else None
        beta22 = "v2.28.0-qt-beta.22"
        beta23 = "v2.28.0-qt-beta.23"
        rc1 = "v3.0.0-qt-rc.1"
        self.assertIsNone(legacy_key(rc1))
        self.assertGreater(legacy_key(beta23), legacy_key(beta22))
        self.assertIsNotNone(u._key(rc1))

    def test_bridge_detects_existing_rc1_release_with_sha256(self):
        tag = "v3.0.0-qt-rc.1"
        release = {
            "draft": False, "prerelease": True, "tag_name": tag,
            "name": "Qt Release Candidate 1",
            "html_url": "https://github.com/" + u.REPO + "/releases/tag/" + tag,
            "assets": [
                {"name": u.ASSET, "size": 198892767,
                 "browser_download_url": "https://github.com/" + u.REPO +
                 "/releases/download/" + tag + "/" + u.ASSET},
                {"name": u.ASSET + ".sha256", "size": 91,
                 "browser_download_url": "https://github.com/" + u.REPO +
                 "/releases/download/" + tag + "/" + u.ASSET + ".sha256"},
            ],
        }
        with patch.object(u, "_get", return_value=io.BytesIO(
                json.dumps([release]).encode("utf-8"))):
            found = u.check()
        self.assertEqual(found["tag"], tag)
        self.assertTrue(found["checksum_url"].endswith(".sha256"))

    def test_bridge_ignores_unfinished_rc_upload(self):
        tag = "v3.0.0-qt-rc.2"
        release = {
            "draft": False, "tag_name": tag,
            "html_url": "https://github.com/" + u.REPO + "/releases/tag/" + tag,
            "assets": [{"name": u.ASSET, "size": 180000000,
                        "browser_download_url": "https://github.com/" + u.REPO +
                        "/releases/download/" + tag + "/" + u.ASSET}],
        }
        with patch.object(u, "_get", return_value=io.BytesIO(
                json.dumps([release]).encode("utf-8"))):
            self.assertIsNone(u.check())

    def test_beta19_discovers_beta20_prerelease_with_checksum(self):
        tag = "v2.28.0-qt-beta.20"
        release = {
            "draft": False, "prerelease": True, "tag_name": tag,
            "html_url": "https://github.com/" + u.REPO + "/releases/tag/" + tag,
            "assets": [
                {"name": u.ASSET, "size": 150000000,
                 "browser_download_url": "https://github.com/" + u.REPO +
                 "/releases/download/" + tag + "/" + u.ASSET},
                {"name": u.ASSET + ".sha256",
                 "browser_download_url": "https://github.com/" + u.REPO +
                 "/releases/download/" + tag + "/" + u.ASSET + ".sha256"}
            ]
        }
        with patch.object(u, "CURRENT_TAG", "v2.28.0-qt-beta.19"), \
             patch.object(u, "_get",
                          return_value=io.BytesIO(json.dumps([release]).encode())):
            info = u.check()
        self.assertEqual(info["tag"], tag)
        self.assertTrue(info["checksum_url"].endswith(".sha256"))

    def test_beta20_discovers_beta21_prerelease_with_checksum(self):
        tag = "v2.28.0-qt-beta.21"
        release = {
            "draft": False, "prerelease": True, "tag_name": tag,
            "html_url": "https://github.com/" + u.REPO + "/releases/tag/" + tag,
            "assets": [
                {"name": u.ASSET, "size": 150000000,
                 "browser_download_url": "https://github.com/" + u.REPO +
                 "/releases/download/" + tag + "/" + u.ASSET},
                {"name": u.ASSET + ".sha256",
                 "browser_download_url": "https://github.com/" + u.REPO +
                 "/releases/download/" + tag + "/" + u.ASSET + ".sha256"}
            ]
        }
        with patch.object(u, "CURRENT_TAG", "v2.28.0-qt-beta.20"), \
             patch.object(u, "_get", return_value=io.BytesIO(
                 json.dumps([release]).encode())):
            info = u.check()
        self.assertEqual(info["tag"], tag)
        self.assertTrue(info["checksum_url"].endswith(".sha256"))

    def test_beta21_discovers_beta22_prerelease_with_checksum(self):
        tag = "v2.28.0-qt-beta.22"
        release = {
            "draft": False, "prerelease": True, "tag_name": tag,
            "html_url": "https://github.com/" + u.REPO + "/releases/tag/" + tag,
            "assets": [
                {"name": u.ASSET, "size": 150000000,
                 "browser_download_url": "https://github.com/" + u.REPO +
                 "/releases/download/" + tag + "/" + u.ASSET},
                {"name": u.ASSET + ".sha256",
                 "browser_download_url": "https://github.com/" + u.REPO +
                 "/releases/download/" + tag + "/" + u.ASSET + ".sha256"}
            ]
        }
        with patch.object(u, "CURRENT_TAG", "v2.28.0-qt-beta.21"), \
             patch.object(u, "_get", return_value=io.BytesIO(
                 json.dumps([release]).encode())):
            info = u.check()
        self.assertEqual(info["tag"], tag)
        self.assertTrue(info["checksum_url"].endswith(".sha256"))

    def test_stage_valid_zip_sha_and_preserve_user_config(self):
        archive = self.archive()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "DBDRandomizerQtBeta"
            target.mkdir()
            config = target / "dbd_randomizer_config.json"
            config.write_text('{"retain":true}', encoding="utf-8")
            info = {
                "asset_url": "https://github.com/" + u.REPO +
                             "/releases/download/v2.28.0-qt-beta.12/" + u.ASSET,
                "asset_size": len(archive),
                "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
            }
            messages = []
            with patch.object(u, "_get", return_value=io.BytesIO(archive)):
                unpacked = u.stage(info, target, progress=messages.append)
            self.assertTrue(any("Скачивание обновления" in x for x in messages))
            self.assertTrue(any("SHA-256" in x for x in messages))
            self.assertTrue(any("Распаковка завершена" in x for x in messages))
            self.assertLessEqual(sum("Скачивание обновления" in x for x in messages), 11)
            self.assertTrue((unpacked / u.APP_EXE).is_file())
            self.assertTrue((unpacked / "_internal/python312.dll").is_file())
            self.assertEqual(config.read_text(encoding="utf-8"), '{"retain":true}')
            self.assertEqual(unpacked.parent.parent.resolve(), target.parent.resolve())
            self.assertFalse((unpacked.parent / u.ASSET).exists())
            shutil.rmtree(unpacked.parent)

    def test_wrong_hash_aborts_and_removes_staging(self):
        archive = self.archive()
        with tempfile.TemporaryDirectory() as folder:
            install = Path(folder) / "DBDRandomizerQtBeta"
            install.mkdir()
            info = {
                "asset_url": "https://github.com/" + u.REPO + "/releases/download/bad/" + u.ASSET,
                "asset_size": len(archive),
                "digest": "sha256:" + "0" * 64,
            }
            with patch.object(u, "_get", return_value=io.BytesIO(archive)):
                with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                    u.stage(info, install)
            self.assertFalse(any(Path(folder).glob(u.STAGE_PREFIX + "*")))

    def test_reject_traversal_and_symlinks(self):
        for label, data in (("traversal", self.archive(traversal=True)),
                            ("symlink", self.archive(symlink=True))):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(RuntimeError):
                    u._unpack_verified(self._write(Path(folder), data), Path(folder) / "out")
                self.assertFalse((Path(folder) / "escape.txt").exists())

    def test_reject_missing_python_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, "python312.dll"):
                u._unpack_verified(self._write(Path(folder), self.archive(runtime=False)),
                                   Path(folder) / "stage")

    @staticmethod
    def _write(folder, data):
        path = folder / "sample.zip"
        path.write_bytes(data)
        return path

    def test_verified_digest_and_fallback_checksum_filename(self):
        data = self.archive()
        sha = hashlib.sha256(data).hexdigest()
        self.assertEqual(u._sha256_for({"digest": "sha256:" + sha}), sha)
        source = (sha + "  " + u.ASSET + "\n").encode()
        with patch.object(u, "_get", return_value=io.BytesIO(source)):
            self.assertEqual(u._sha256_for({"checksum_url":
                "https://github.com/" + u.REPO + "/releases/download/v1/" +
                u.ASSET + ".sha256"}), sha)
        with patch.object(u, "_get", return_value=io.BytesIO(
                (sha + "  other.zip\n").encode())):
            with self.assertRaisesRegex(RuntimeError, "checksum"):
                u._sha256_for({"checksum_url": "https://github.com/" + u.REPO +
                               "/releases/download/v1/" + u.ASSET + ".sha256"})

    def test_only_bounded_official_https_urls_are_accepted(self):
        with self.assertRaises(ValueError):
            u._get("http://github.com/" + u.REPO + "/releases/download/x.zip")
        with self.assertRaises(ValueError):
            u._get("https://attacker.invalid/" + u.ASSET)
        with self.assertRaises(ValueError):
            u._get("https://github.com/" + u.REPO + "/issues/1")

    def test_newer_release_requires_portable_asset(self):
        base = {
            "draft": False, "tag_name": "v3.0.0-qt-rc.1",
            "name": "New Version",
            "html_url": "https://github.com/" + u.REPO + "/releases/tag/new",
            "assets": [
                {"name": u.ASSET, "size": 22_000_000,
                 "browser_download_url": "https://github.com/" + u.REPO +
                 "/releases/download/next/" + u.ASSET},
                {"name": u.ASSET + ".sha256", "size": 100,
                 "browser_download_url": "https://github.com/" + u.REPO +
                 "/releases/download/next/" + u.ASSET + ".sha256"}
            ]
        }
        latest = dict(base)
        latest["tag_name"] = "v3.0.0"
        latest["assets"] = [{"name": "DBDRandomizerQtBeta.exe", "size": 20000000}]
        with patch.object(u, "_get", return_value=io.BytesIO(
                json.dumps([base, latest]).encode())):
            choice = u.check()
        self.assertEqual(choice["tag"], base["tag_name"])
        self.assertEqual(choice["asset_size"], 22_000_000)

    def test_powershell_installer_keeps_user_data_and_rolls_back(self):
        script = u.UPGRADE_SCRIPT
        self.assertIn('"_internal"', script)
        self.assertIn('".dbd_qt_previous_internal"', script)
        self.assertIn("Wait-Process", script)
        self.assertIn("Rollback failed", script)
        self.assertNotIn("dbd_randomizer_config.json", script)
        self.assertNotIn("dbd_database.json", script)


if __name__ == "__main__":
    unittest.main()
