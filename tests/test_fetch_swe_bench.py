from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts import fetch_swe_bench


class FetchSweBenchTests(unittest.TestCase):
    def test_all_writes_full_official_selection_without_gold_patches(self) -> None:
        records = [
            {
                "instance_id": "owner__repo-1",
                "repo": "owner/repo",
                "base_commit": "abc123",
                "problem_statement": "Fix the bug",
                "FAIL_TO_PASS": '["test_bug"]',
                "PASS_TO_PASS": "[]",
                "patch": "gold solution must not be exposed",
                "test_patch": "hidden tests must not be exposed",
            },
            {
                "instance_id": "owner__repo-2",
                "repo": "owner/repo",
                "base_commit": "def456",
                "problem_statement": "Fix another bug",
                "FAIL_TO_PASS": '["test_other"]',
                "PASS_TO_PASS": "[]",
                "patch": "second gold patch",
            },
        ]
        fake_datasets = types.ModuleType("datasets")
        fake_datasets.load_dataset = lambda name, split: records
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "cases.jsonl"
            ids_output = Path(directory) / "instances.txt"
            argv = [
                "fetch_swe_bench.py", "--all", "--output", str(output),
                "--ids-output", str(ids_output),
            ]
            with patch.dict(sys.modules, {"datasets": fake_datasets}), patch.object(sys, "argv", argv):
                self.assertEqual(0, fetch_swe_bench.main())

            saved = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(["owner__repo-1", "owner__repo-2"], [item["instance_id"] for item in saved])
            self.assertNotIn("patch", saved[0])
            self.assertNotIn("test_patch", saved[0])
            self.assertEqual("owner__repo-1\nowner__repo-2\n", ids_output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
