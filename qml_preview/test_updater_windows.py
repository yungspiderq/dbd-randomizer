"""Integration checks for the real PowerShell installer on Windows.

These tests move tiny marker files in temporary folders. They never modify the
running test process, the user's installed app or a real DBD installation.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qt_updater as u


@unittest.skipUnless(sys.platform == "win32", "PowerShell 5.1/Windows required")
class WindowsInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dbd Qt updater test ")
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.target = self.parent / "DBD Installed With Spaces"
        self.target.mkdir()
        self.stage_parent = self.parent / (u.STAGE_PREFIX + "smoketest")
        self.staged = self.stage_parent / u.PACKAGE_ROOT
        self.staged.mkdir(parents=True)
        (self.target / "_internal").mkdir()
        (self.staged / "_internal").mkdir()
        (self.target / u.APP_EXE).write_bytes(b"OLD_EXE")
        (self.target / "_internal" / "python312.dll").write_bytes(b"OLD_DLL")
        (self.staged / u.APP_EXE).write_bytes(b"NEW_EXE")
        (self.staged / "_internal" / "python312.dll").write_bytes(b"NEW_DLL")
        (self.target / "dbd_randomizer_config.json").write_text('{"private":"keep"}', encoding="utf-8")
        (self.target / "my_mod_data.json").write_text("keep", encoding="utf-8")
        self.script = self.parent / "installer.ps1"
        self.script.write_text(u.UPGRADE_SCRIPT, encoding="utf-8-sig")

    def invoke(self):
        return subprocess.run([
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(self.script),
            "-WaitFor", "0", "-TargetDir", str(self.target),
            "-StagedDir", str(self.staged), "-SkipLaunch",
        ], capture_output=True, text=True, timeout=90)

    def test_installer_replaces_program_preserving_user_files(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual((self.target / u.APP_EXE).read_bytes(), b"NEW_EXE")
        self.assertEqual((self.target / "_internal" / "python312.dll").read_bytes(), b"NEW_DLL")
        self.assertEqual((self.target / "dbd_randomizer_config.json").read_text(encoding="utf-8"),
                         '{"private":"keep"}')
        self.assertEqual((self.target / "my_mod_data.json").read_text(encoding="utf-8"), "keep")
        self.assertFalse((self.target / ".dbd_qt_previous.exe").exists())
        self.assertFalse((self.target / ".dbd_qt_previous_internal").exists())
        self.assertFalse((self.target / "dbd_update_error.log").exists())
        self.assertFalse(self.stage_parent.exists())
        self.assertIn("SUCCESS", (self.target / "dbd_update_progress.log").read_text(encoding="utf-8-sig"))

    def test_generated_helper_is_removed_after_success(self):
        generated = self.parent / ".dbd_qt_install_testonly.ps1"
        generated.write_text(u.UPGRADE_SCRIPT, encoding="utf-8-sig")
        self.script = generated
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse(generated.exists())

    def test_installer_refuses_old_backup_without_destroying_files(self):
        (self.target / ".dbd_qt_previous.exe").write_bytes(b"PRECIOUS_BACKUP")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0, "Expected a safe refusal")
        self.assertEqual((self.target / u.APP_EXE).read_bytes(), b"OLD_EXE")
        self.assertEqual((self.target / "_internal" / "python312.dll").read_bytes(), b"OLD_DLL")
        self.assertEqual((self.target / ".dbd_qt_previous.exe").read_bytes(), b"PRECIOUS_BACKUP")
        self.assertTrue(self.staged.exists(), "Failed install should preserve its staged download")
        err = self.target / "dbd_update_error.log"
        self.assertTrue(err.exists(), result.stderr + result.stdout)
        self.assertIn("Previous update backup exists", err.read_text(encoding="utf-8-sig"))
        self.assertIn("Previous update backup exists", u.last_install_error(self.target))


if __name__ == "__main__":
    unittest.main()
