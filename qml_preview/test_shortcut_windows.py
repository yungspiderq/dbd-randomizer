"""Windows-only shortcut regression checks; never modify the runner's real Desktop."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPAIR = HERE / "Repair DBD Randomizer Shortcut.ps1"


@unittest.skipUnless(sys.platform == "win32", "Windows shortcut COM required")
class ShortcutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dbd shortcut test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / "Installed DBD Randomizer"
        self.install.mkdir()
        self.desktop = self.root / "Redirected Desktop With Spaces"
        self.desktop.mkdir()
        self.exe = self.install / "DBDRandomizerQtBeta.exe"
        self.exe.write_bytes(b"MZtest")
        self.link = self.desktop / "DBD Randomizer.lnk"

    def repair(self):
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", str(REPAIR),
             "-InstallDir", str(self.install),
             "-ShortcutDirectory", str(self.desktop)],
            capture_output=True, text=True, errors="replace", timeout=35)

    def read_shortcut(self):
        inspect = self.root / "inspect_shortcut.ps1"
        inspect.write_text(
            "param([string]$Path)\n"
            "$link = (New-Object -ComObject WScript.Shell).CreateShortcut($Path)\n"
            "[pscustomobject]@{target=$link.TargetPath; work=$link.WorkingDirectory; "
            "icon=$link.IconLocation; arguments=$link.Arguments} | ConvertTo-Json -Compress\n",
            encoding="utf-8")
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
             str(inspect), "-Path", str(self.link)],
            capture_output=True, text=True, errors="replace", timeout=35)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.strip())

    def test_creates_and_repairs_named_shortcut_with_current_qt_exe(self):
        unrelated = self.desktop / "Other App.lnk"
        unrelated.write_bytes(b"do not touch")
        result = self.repair()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(self.link.is_file())
        first = self.read_shortcut()
        self.assertEqual(Path(first["target"]).resolve(), self.exe.resolve())
        self.assertEqual(Path(first["work"]).resolve(), self.install.resolve())
        self.assertIn("DBDRandomizerQtBeta.exe", first["icon"])
        self.assertEqual(first["arguments"], "")
        # Repeat from the same directory: this must repair, not create copies.
        self.assertEqual(self.repair().returncode, 0)
        self.assertEqual(len(list(self.desktop.glob("DBD Randomizer*.lnk"))), 1)
        self.assertEqual(unrelated.read_bytes(), b"do not touch")

    def test_missing_executable_does_not_create_shortcut(self):
        self.exe.unlink()
        result = self.repair()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.link.exists())


if __name__ == "__main__":
    unittest.main()
