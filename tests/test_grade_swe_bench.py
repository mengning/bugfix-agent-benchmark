from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts import grade_swe_bench


class GradeSweBenchTests(unittest.TestCase):
    def test_official_report_becomes_score_with_empty_agent_patch_counted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ids = root / "instances.txt"
            ids.write_text("owner__repo-1\nowner__repo-2\n", encoding="utf-8")
            patches = root / "patches"
            patches.mkdir()
            (patches / "owner__repo-1.patch").write_text("diff --git a/a b/a\n", encoding="utf-8")
            (patches / "owner__repo-2.patch").write_text("", encoding="utf-8")
            report = root / "results.json"
            report.write_text(json.dumps({
                "total_instances": 2,
                "resolved_ids": ["owner__repo-1"],
                "unresolved_ids": [],
                "empty_patch_ids": ["owner__repo-2"],
                "error_ids": [],
                "incomplete_ids": [],
            }), encoding="utf-8")
            predictions = root / "predictions.jsonl"
            score = root / "score.json"
            argv = [
                "grade_swe_bench.py", "--instances-file", str(ids),
                "--patch-dir", str(patches), "--model-name", "example-agent",
                "--run-id", "sample-run", "--allow-empty",
                "--predictions-path", str(predictions), "--report-path", str(report),
                "--score-path", str(score),
            ]
            with patch.object(sys, "argv", argv), patch.object(
                grade_swe_bench.subprocess, "run",
                return_value=types.SimpleNamespace(returncode=0),
            ):
                self.assertEqual(0, grade_swe_bench.main())

            rows = [json.loads(line) for line in predictions.read_text(encoding="utf-8").splitlines()]
            self.assertEqual("", rows[1]["model_patch"])
            result = json.loads(score.read_text(encoding="utf-8"))
            self.assertEqual(2, result["total"])
            self.assertEqual(1, result["passed"])
            self.assertEqual("empty_patch", result["cases"][1]["status"])


if __name__ == "__main__":
    unittest.main()
