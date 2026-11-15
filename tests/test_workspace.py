from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from bugfix_benchmark.models import BenchmarkCase
from bugfix_benchmark.workspace import WorkspaceError, prepare_workspace


class WorkspaceTests(unittest.TestCase):
    def test_clone_failure_omits_url_and_subprocess_output(self) -> None:
        case = BenchmarkCase.from_record({
            "case_id": "case-1", "repository": "owner/repo",
            "source_url": "https://secret-in-url@example.invalid/repo.git",
            "base_commit": "abcdef", "problem_statement": "Fix bug.",
            "fail_to_pass": ["false"],
        })
        failed = subprocess.CompletedProcess([], 1, stdout="secret-in-output")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("bugfix_benchmark.workspace.subprocess.run", return_value=failed):
                with self.assertRaises(WorkspaceError) as caught:
                    prepare_workspace(case, root / "workspace", root)
        self.assertIn("cannot clone", str(caught.exception))
        self.assertNotIn("secret-in-url", str(caught.exception))
        self.assertNotIn("secret-in-output", str(caught.exception))

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
