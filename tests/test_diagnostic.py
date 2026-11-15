from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bugfix_benchmark.diagnostic import breakdown_score, load_selection, validate_upstream


ROOT = Path(__file__).resolve().parents[1]
SELECTION = ROOT / "datasets/swe-bench-lite/diagnostic-v1.jsonl"
IDS = ROOT / "datasets/swe-bench-lite/diagnostic-v1.txt"


class DiagnosticSelectionTests(unittest.TestCase):
    def test_public_selection_matches_ids_and_contains_four_dimensions(self) -> None:
        cases = load_selection(SELECTION, IDS)
        self.assertEqual(7, len(cases))
        self.assertEqual(5, sum(case["role"] == "core" for case in cases))
        self.assertEqual(2, sum(case["role"] == "information_control" for case in cases))
        for case in cases:
            with self.subTest(case=case["instance_id"]):
                self.assertTrue(case["repository_context"])
                self.assertTrue(case["repair_obstacle"])
                self.assertTrue(case["issue_information"])
                self.assertTrue(case["verification_evidence"])
                self.assertTrue(case["capability_hypothesis"])
                self.assertTrue(case["inference_limit"])

    def test_rejects_duplicate_or_mismatched_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selection = root / "selection.jsonl"
            first = SELECTION.read_text(encoding="utf-8").splitlines()[0]
            selection.write_text(first + "\n" + first + "\n", encoding="utf-8")
            ids = root / "ids.txt"
            ids.write_text("a\nb\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_selection(selection, ids)

    def test_checks_pinned_upstream_record_and_test_evidence(self) -> None:
        cases = [{
            "instance_id": "a", "repo": "owner/repo", "base_commit": "a" * 40,
            "verification_evidence": {"fail_to_pass_count": 1, "pass_to_pass_count": 2},
        }]
        upstream = [{
            "instance_id": "a", "repo": "owner/repo", "base_commit": "a" * 40,
            "problem_statement": "An issue", "FAIL_TO_PASS": ["red"],
            "PASS_TO_PASS": ["green1", "green2"],
        }]
        validate_upstream(cases, upstream)
        upstream[0]["FAIL_TO_PASS"] = []
        with self.assertRaisesRegex(ValueError, "FAIL_TO_PASS"):
            validate_upstream(cases, upstream)

    def test_reports_only_official_scores_and_separates_roles(self) -> None:
        cases = [
            {"instance_id": "a", "role": "core", "repair_obstacle": "structural_semantics"},
            {"instance_id": "b", "role": "information_control", "repair_obstacle": "state_transition"},
        ]
        score = {"scorer": "official_swebench_harness", "cases": [
            {"case_id": "a", "status": "resolved", "passed": True},
            {"case_id": "b", "status": "unresolved", "passed": False},
        ]}
        result = breakdown_score(cases, score)
        self.assertEqual({"total": 1, "resolved": 1}, result["by_role"]["core"])
        self.assertEqual({"total": 1, "resolved": 0}, result["by_role"]["information_control"])
        with self.assertRaisesRegex(ValueError, "official"):
            breakdown_score(cases, {"scorer": "patch_generation", "cases": score["cases"]})
        with self.assertRaisesRegex(ValueError, "missing"):
            breakdown_score(cases, {"scorer": "official_swebench_harness", "cases": score["cases"][:1]})

    def test_public_selection_matches_cached_official_records(self) -> None:
        cached = ROOT / ".benchmark/datasets/swe-bench-lite-all.jsonl"
        if not cached.is_file():
            self.skipTest("official dataset cache is not present")
        records = [json.loads(line) for line in cached.read_text(encoding="utf-8").splitlines()]
        validate_upstream(load_selection(SELECTION, IDS), records)

    def test_report_cli_prints_official_breakdown(self) -> None:
        cases = load_selection(SELECTION, IDS)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "official.jsonl"
            records = [{
                "instance_id": case["instance_id"], "repo": case["repo"],
                "base_commit": case["base_commit"], "problem_statement": "Issue",
                "FAIL_TO_PASS": ["red"] * case["verification_evidence"]["fail_to_pass_count"],
                "PASS_TO_PASS": ["green"] * case["verification_evidence"]["pass_to_pass_count"],
            } for case in cases]
            dataset.write_text("\n".join(json.dumps(row) for row in records) + "\n", encoding="utf-8")
            score_file = root / "score.json"
            score_file.write_text(json.dumps({
                "scorer": "official_swebench_harness",
                "cases": [{"case_id": case["instance_id"], "status": "unresolved", "passed": False} for case in cases],
            }), encoding="utf-8")
            completed = subprocess.run([
                sys.executable, str(ROOT / "scripts/report_diagnostic.py"),
                "--dataset-file", str(dataset), "--score-file", str(score_file),
            ], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual(7, json.loads(completed.stdout)["total"])


if __name__ == "__main__":
    unittest.main()
