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
        case = BenchmarkCase(
            case_id="case-1", repository="owner/repo", base_commit="abcdef",
            problem_statement="Fix bug.", source_url="https://secret-in-url@example.invalid/repo.git",
        )
        failed = subprocess.CompletedProcess([], 1, stdout="secret-in-output")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("bugfix_benchmark.workspace.subprocess.run", return_value=failed):
                with self.assertRaises(WorkspaceError) as caught:
                    prepare_workspace(case, root / "workspace", root)
        self.assertIn("cannot clone", str(caught.exception))
        self.assertNotIn("secret-in-url", str(caught.exception))
        self.assertNotIn("secret-in-output", str(caught.exception))



if __name__ == "__main__":
    unittest.main()
