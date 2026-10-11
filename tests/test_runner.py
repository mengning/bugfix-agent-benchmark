from __future__ import annotations

import difflib
import json
from pathlib import Path
import tempfile
import unittest

from bugfix_benchmark.adapters import PatchDirectoryAdapter
from bugfix_benchmark.runner import BenchmarkRunner


BUGGY = "def double(value):\n    return value + value + 1\n"
FIXED = "def double(value):\n    return value + value\n"
TESTS = """import unittest
from value import double

class ValueTests(unittest.TestCase):
    def test_double(self):
        self.assertEqual(4, double(2))
"""


class RunnerTests(unittest.TestCase):
    def test_writes_patch_case_result_and_aggregate_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fixture"
            source.mkdir()
            (source / "value.py").write_text(BUGGY, encoding="utf-8")
            (source / "test_value.py").write_text(TESTS, encoding="utf-8")
            manifest = root / "manifest.jsonl"
            manifest.write_text(
                json.dumps(
                    {
                        "case_id": "double-value",
                        "repository": "fixture",
                        "source_path": "fixture",
                        "base_commit": "fixture",
                        "problem_statement": "Double without adding one.",
                        "fail_to_pass": ["python3 -m unittest test_value.ValueTests.test_double"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            patches = root / "patches"
            patches.mkdir()
            patch = "".join(
                difflib.unified_diff(
                    BUGGY.splitlines(keepends=True),
                    FIXED.splitlines(keepends=True),
                    fromfile="a/value.py",
                    tofile="b/value.py",
                )
            )
            (patches / "double-value.patch").write_text(patch, encoding="utf-8")

            score = BenchmarkRunner(root).run(
                manifest,
                PatchDirectoryAdapter(patches),
                root / "results",
                run_id="test-run",
            )

            run_dir = root / "results/test-run"
            persisted = json.loads((run_dir / "score.json").read_text(encoding="utf-8"))
            case_result = json.loads(
                (run_dir / "cases/double-value/result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(1, score["passed"])
            self.assertEqual(1.0, score["pass_rate"])
            self.assertEqual(score, persisted)
            self.assertEqual("passed", case_result["status"])
            self.assertEqual(patch, (run_dir / "patches/double-value.patch").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
