from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicScriptTests(unittest.TestCase):
    def test_fetch_script_exposes_portable_cli(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/fetch_swe_bench.py"), "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        self.assertEqual(0, completed.returncode, completed.stdout)
        self.assertIn("--instances-file", completed.stdout)
        self.assertNotIn("/Users/", completed.stdout)

    def test_grade_script_exposes_portable_cli(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/grade_swe_bench.py"), "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        self.assertEqual(0, completed.returncode, completed.stdout)
        self.assertIn("--patch-dir", completed.stdout)
        self.assertIn("--dry-run", completed.stdout)
        self.assertNotIn("/private/tmp", completed.stdout)


if __name__ == "__main__":
    unittest.main()
