from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from bugfix_benchmark.catalog import load_cases
from bugfix_benchmark.workspace import prepare_workspace


ROOT = Path(__file__).resolve().parents[1]


class CuratedDatasetTests(unittest.TestCase):
    def test_v1_cases_have_reproducible_red_and_green_baselines(self) -> None:
        cases = load_cases(ROOT / "datasets/bugfix-v1/manifest.jsonl")
        self.assertEqual(
            {"url-host-validation", "tenant-cache-isolation", "pagination-boundary"},
            {case.case_id for case in cases},
        )
        with tempfile.TemporaryDirectory() as directory:
            for case in cases:
                with self.subTest(case=case.case_id):
                    self.assertEqual(("tests",), case.protected_paths)
                    workspace = prepare_workspace(case, Path(directory) / case.case_id, ROOT)
                    for command in case.fail_to_pass:
                        completed = subprocess.run(command, shell=True, cwd=workspace, capture_output=True, text=True)
                        self.assertNotEqual(0, completed.returncode, completed.stdout + completed.stderr)
                    for command in case.pass_to_pass:
                        completed = subprocess.run(command, shell=True, cwd=workspace, capture_output=True, text=True)
                        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
