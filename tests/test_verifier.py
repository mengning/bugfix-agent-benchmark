from __future__ import annotations

import difflib
import os
from pathlib import Path
import tempfile
import unittest

from bugfix_benchmark.models import AgentArtifact, BenchmarkCase
from bugfix_benchmark.verifier import verify_case


BUGGY = """def average(values):
    if not values:
        return 0
    return sum(values) // len(values)
"""
FIXED = """def average(values):
    if not values:
        return 0
    return sum(values) / len(values)
"""
REGRESSED = """def average(values):
    if not values:
        return None
    return sum(values) / len(values)
"""
IRRELEVANT = BUGGY + "\nVERSION = 1\n"
TESTS = """import unittest
from calc import average

class CalcTests(unittest.TestCase):
    def test_average_keeps_fraction(self):
        self.assertEqual(5 / 3, average([1, 2, 2]))

    def test_empty_average_is_zero(self):
        self.assertEqual(0, average([]))
"""


def unified_patch(before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="a/calc.py",
            tofile="b/calc.py",
        )
    )


class VerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "calc.py").write_text(BUGGY, encoding="utf-8")
        (self.source / "test_calc.py").write_text(TESTS, encoding="utf-8")
        self.case = BenchmarkCase.from_record(
            {
                "case_id": "python-average",
                "repository": "fixtures/python-average",
                "source_path": str(self.source),
                "base_commit": "fixture",
                "problem_statement": "Preserve fractional averages.",
                "fail_to_pass": [
                    "python3 -m unittest test_calc.CalcTests.test_average_keeps_fraction"
                ],
                "pass_to_pass": [
                    "python3 -m unittest test_calc.CalcTests.test_empty_average_is_zero"
                ],
            }
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def verify(self, patch: str):
        return verify_case(
            self.case,
            AgentArtifact(patch=patch, adapter="test"),
            self.root / "run",
            repository_root=self.root,
        )

    def test_passes_only_after_replaying_patch_and_running_both_test_groups(self) -> None:
        result = self.verify(unified_patch(BUGGY, FIXED))

        self.assertEqual("passed", result.status)
        self.assertEqual("passed", result.fail_to_pass)
        self.assertEqual("passed", result.pass_to_pass)
        self.assertTrue((self.root / "run/logs/baseline-fail-to-pass-1.log").is_file())
        self.assertTrue((self.root / "run/logs/patched-pass-to-pass-1.log").is_file())

    def test_rejects_empty_patch_without_running_commands(self) -> None:
        result = self.verify("")

        self.assertEqual("no_patch", result.status)
        self.assertFalse((self.root / "run/workspace").exists())

    def test_rejects_case_whose_fail_to_pass_is_already_green(self) -> None:
        (self.source / "calc.py").write_text(FIXED, encoding="utf-8")

        result = self.verify(unified_patch(FIXED, REGRESSED))

        self.assertEqual("baseline_invalid", result.status)

    def test_reports_patch_apply_failure(self) -> None:
        result = self.verify("diff --git a/missing.py b/missing.py\n--- a/missing.py\n+++ b/missing.py\n@@ -1 +1 @@\n-x\n+y\n")

        self.assertEqual("patch_apply_failed", result.status)

    def test_reports_fail_to_pass_failure_after_irrelevant_patch(self) -> None:
        result = self.verify(unified_patch(BUGGY, IRRELEVANT))

        self.assertEqual("fail_to_pass_failed", result.status)
        self.assertEqual("failed", result.fail_to_pass)

    def test_reports_pass_to_pass_regression(self) -> None:
        result = self.verify(unified_patch(BUGGY, REGRESSED))

        self.assertEqual("pass_to_pass_failed", result.status)
        self.assertEqual("passed", result.fail_to_pass)
        self.assertEqual("failed", result.pass_to_pass)

    def test_applies_patch_when_run_directory_is_relative(self) -> None:
        previous = Path.cwd()
        os.chdir(self.root)
        try:
            result = verify_case(
                self.case,
                AgentArtifact(patch=unified_patch(BUGGY, FIXED), adapter="test"),
                Path("relative-run"),
                repository_root=self.root,
            )
        finally:
            os.chdir(previous)

        self.assertEqual("passed", result.status)


if __name__ == "__main__":
    unittest.main()
