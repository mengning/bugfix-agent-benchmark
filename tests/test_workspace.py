from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from bugfix_benchmark.models import BenchmarkCase
from bugfix_benchmark.workspace import prepare_workspace


class WorkspaceTests(unittest.TestCase):
    def test_local_fixture_changes_are_visible_as_a_git_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture"
            fixture.mkdir()
            (fixture / "calc.py").write_text("value = 1\n", encoding="utf-8")
            case = BenchmarkCase.from_record(
                {
                    "case_id": "fixture-1",
                    "repository": "smoke/fixture-1",
                    "source_path": "fixture",
                    "base_commit": "fixture",
                    "problem_statement": "Change the value.",
                    "fail_to_pass": ["python3 -m unittest"],
                }
            )
            workspace = prepare_workspace(case, root / "workspace", root)

            (workspace / "calc.py").write_text("value = 2\n", encoding="utf-8")
            diff = subprocess.run(
                ["git", "diff", "--no-ext-diff", "--binary"],
                cwd=workspace,
                text=True,
                capture_output=True,
                check=True,
            ).stdout

        self.assertIn("diff --git a/calc.py b/calc.py", diff)
        self.assertIn("-value = 1", diff)
        self.assertIn("+value = 2", diff)


if __name__ == "__main__":
    unittest.main()
