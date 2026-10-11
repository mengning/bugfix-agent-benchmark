from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bugfix_benchmark.adapters import PatchDirectoryAdapter
from bugfix_benchmark.models import BenchmarkCase


PATCH = """diff --git a/calc.py b/calc.py
--- a/calc.py
+++ b/calc.py
@@ -1 +1 @@
-value = 1
+value = 2
"""


def make_case() -> BenchmarkCase:
    return BenchmarkCase.from_record(
        {
            "case_id": "owner__repo-1",
            "repository": "owner/repo",
            "source_url": "https://example.invalid/owner/repo.git",
            "base_commit": "abc123",
            "problem_statement": "Fix the regression.",
            "fail_to_pass": ["python -m unittest test_fix"],
        }
    )


class PatchDirectoryAdapterTests(unittest.TestCase):
    def test_reads_exact_case_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "owner__repo-1.patch"
            path.write_text(PATCH, encoding="utf-8")

            artifact = PatchDirectoryAdapter(Path(directory)).run(make_case())

        self.assertEqual(PATCH, artifact.patch)
        self.assertEqual("patch-dir", artifact.adapter)

    def test_missing_patch_returns_empty_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = PatchDirectoryAdapter(Path(directory)).run(make_case())

        self.assertEqual("", artifact.patch)
if __name__ == "__main__":
    unittest.main()
