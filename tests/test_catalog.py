from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from bugfix_benchmark.catalog import load_cases


class CatalogTests(unittest.TestCase):
    def test_loads_jsonl_and_normalizes_swe_bench_aliases(self) -> None:
        record = {
            "instance_id": "owner__repo-1",
            "repo": "owner/repo",
            "source_url": "https://example.invalid/owner/repo.git",
            "base_commit": "abc123",
            "problem_statement": "Fix the regression.",
            "FAIL_TO_PASS": ["python -m unittest test_fix"],
            "PASS_TO_PASS": ["python -m unittest test_existing"],
        }
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.jsonl"
            manifest.write_text(json.dumps(record) + "\n", encoding="utf-8")

            cases = load_cases(manifest)

        self.assertEqual(1, len(cases))
        self.assertEqual("owner__repo-1", cases[0].case_id)
        self.assertEqual("owner/repo", cases[0].repository)
        self.assertEqual(("python -m unittest test_fix",), cases[0].fail_to_pass)
        self.assertEqual(("python -m unittest test_existing",), cases[0].pass_to_pass)

    def test_loads_json_array(self) -> None:
        record = {
            "case_id": "local-average",
            "repository": "python-oracle",
            "source_path": "python-oracle",
            "base_commit": "fixture",
            "problem_statement": "Keep fractional averages.",
            "fail_to_pass": ["python -m unittest test_calc.CalcTests.test_average"],
        }
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps([record]), encoding="utf-8")

            cases = load_cases(manifest)

        self.assertEqual("python-oracle", cases[0].source_path)

    def test_rejects_case_without_runnable_fail_to_pass_commands(self) -> None:
        record = {
            "case_id": "broken",
            "repository": "owner/repo",
            "source_url": "https://example.invalid/owner/repo.git",
            "base_commit": "abc123",
            "problem_statement": "Fix it.",
            "fail_to_pass": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.jsonl"
            manifest.write_text(json.dumps(record) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "fail_to_pass"):
                load_cases(manifest)


if __name__ == "__main__":
    unittest.main()
