from __future__ import annotations

import json
import hashlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts import fetch_swe_bench


class FetchSweBenchTests(unittest.TestCase):
    def test_local_snapshot_is_verified_and_agent_input_excludes_answers(self) -> None:
        records = [{"instance_id": "owner__repo-1", "repo": "owner/repo", "base_commit": "abc123",
                    "problem_statement": "Fix the bug", "patch": "reference patch",
                    "test_patch": "reference tests", "FAIL_TO_PASS": ["hidden"]}]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.json"
            source.write_text(json.dumps(records), encoding="utf-8")
            public = Path(directory) / "agent.jsonl"
            checksum = hashlib.sha256(source.read_bytes()).hexdigest()
            argv = ["fetch_swe_bench.py", "--all", "--source-json", str(source),
                    "--expected-sha256", checksum, "--output", str(public)]
            with patch.object(sys, "argv", argv):
                self.assertEqual(0, fetch_swe_bench.main())
            saved = json.loads(public.read_text())
            self.assertNotIn("patch", saved)
            self.assertNotIn("test_patch", saved)
            self.assertNotIn("FAIL_TO_PASS", saved)
            public.unlink()
            argv[argv.index(checksum)] = "0" * 64
            with patch.object(sys, "argv", argv), self.assertRaisesRegex(ValueError, "SHA-256"):
                fetch_swe_bench.main()
            self.assertFalse(public.exists())

    def test_revision_and_separate_full_scoring_snapshot(self) -> None:
        records = [{"instance_id": "owner__repo-1", "repo": "owner/repo", "base_commit": "abc123",
                    "problem_statement": "Fix the bug", "patch": "reference patch",
                    "test_patch": "reference tests"}]
        calls = []
        fake_datasets = types.ModuleType("datasets")
        def load_dataset(name, **kwargs):
            calls.append((name, kwargs))
            return records
        fake_datasets.load_dataset = load_dataset
        with tempfile.TemporaryDirectory() as directory:
            public = Path(directory) / "agent.jsonl"
            scoring = Path(directory) / "scoring.json"
            argv = ["fetch_swe_bench.py", "--all", "--revision", "deadbeef",
                    "--output", str(public), "--scoring-output", str(scoring)]
            with patch.dict(sys.modules, {"datasets": fake_datasets}), patch.object(sys, "argv", argv):
                self.assertEqual(0, fetch_swe_bench.main())
            self.assertEqual("deadbeef", calls[0][1]["revision"])
            self.assertNotIn("patch", json.loads(public.read_text()))
            self.assertEqual("reference patch", json.loads(scoring.read_text())[0]["patch"])

    def test_scoring_snapshot_cannot_overwrite_agent_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            same = str(Path(directory) / "cases.json")
            argv = ["fetch_swe_bench.py", "--output", same, "--scoring-output", same]
            with patch.object(sys, "argv", argv), self.assertRaises(ValueError):
                fetch_swe_bench.main()

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
            self.assertNotIn("FAIL_TO_PASS", saved[0])
            self.assertNotIn("PASS_TO_PASS", saved[0])
            self.assertEqual("owner__repo-1\nowner__repo-2\n", ids_output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
