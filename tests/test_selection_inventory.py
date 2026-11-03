from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bugfix_benchmark.selection_inventory import build_inventory


ROOT = Path(__file__).resolve().parents[1]


def record(case_id: str, title: str, body: str, *, green: int = 1) -> dict:
    return {
        "instance_id": case_id, "repo": "owner/repo", "base_commit": "a" * 40,
        "problem_statement": title + "\n" + body,
        "FAIL_TO_PASS": ["target"], "PASS_TO_PASS": ["regression"] * green,
    }


class SelectionInventoryTests(unittest.TestCase):
    def test_review_overrides_surface_rule_only_with_matching_upstream_test(self) -> None:
        rows = [
            record("accepted-1", "Wrong response", "Reproduction example: response fails."),
            record("held-1", "Wrong response", "Reproduction example: response fails."),
        ]
        reviews = {
            "accepted-1": {
                "instance_id": "accepted-1", "decision": "include",
                "repair_obstacle": "state_transition", "repository_context": "service state",
                "issue_information": "reproduction without fix", "capability_hypothesis": "state tracking",
                "inference_limit": "one transition only", "target_test": "target",
                "test_alignment": "target covers the described response",
            },
            "held-1": {
                "instance_id": "held-1", "decision": "hold",
                "repair_obstacle": "parsing", "repository_context": "parser",
                "issue_information": "reproduction", "capability_hypothesis": "parsing",
                "inference_limit": "target test too broad", "target_test": "target",
                "test_alignment": "target name alone cannot identify the reported behavior",
            },
        }
        inventory, selected = build_inventory(rows, set(), set(), reviews)
        self.assertEqual(["accepted-1"], selected)
        self.assertEqual("case_reviewed", inventory[0]["review_status"])
        self.assertEqual("state_transition", inventory[0]["repair_obstacle"])
        self.assertEqual("manual_test_alignment_hold", inventory[1]["screening_reason"])
        with self.assertRaisesRegex(ValueError, "target_test"):
            build_inventory(rows, set(), set(), {"accepted-1": {**reviews["accepted-1"], "target_test": "other"}})
        without_regression = [record("accepted-1", "Wrong response", "Reproduction example: response fails.", green=0)]
        with self.assertRaisesRegex(ValueError, "regression"):
            build_inventory(without_regression, set(), set(), {"accepted-1": reviews["accepted-1"]})

    def test_published_inventory_agrees_with_both_runnable_lists(self) -> None:
        base = ROOT / "datasets/swe-bench-lite"
        inventory = [
            json.loads(line)
            for line in (base / "case-inventory-v2.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        full = (base / "full-300.txt").read_text(encoding="utf-8").splitlines()
        screened = (base / "screened-v2.txt").read_text(encoding="utf-8").splitlines()
        reviewed = (base / "reviewed-v2.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(300, len(full))
        self.assertEqual(84, len(screened))
        self.assertEqual(full, [row["instance_id"] for row in inventory])
        self.assertEqual(screened, [row["instance_id"] for row in inventory if row["selected"]])
        self.assertEqual(84, len(reviewed))
        self.assertEqual(screened, reviewed)
        self.assertEqual(reviewed, [
            row["instance_id"] for row in inventory
            if row["review_status"] in ("paper_screened", "case_reviewed")
        ])
        self.assertEqual(7, sum(row["review_status"] == "paper_screened" for row in inventory))
        self.assertEqual(len(full), len(set(full)))
        self.assertNotIn("psf__requests-1963", screened)
        self.assertTrue(all("gold_patch" not in row and "test_patch" not in row for row in inventory))

    def test_screening_excludes_feature_requests_and_weak_test_evidence(self) -> None:
        rows = [
            record("bug-1", "Wrong response", "Reproduction example: response fails."),
            record("feature-1", "Add support for headers", "Example reports an error."),
            record("weak-1", "Wrong output", "Expected output fails.", green=0),
            record("reviewed-1", "Boundary case", "No keyword here."),
            record("excluded-1", "Wrong redirect", "Reproduction example fails."),
        ]
        inventory, selected = build_inventory(rows, {"reviewed-1"}, {"excluded-1"})
        self.assertEqual(["bug-1", "reviewed-1"], selected)
        self.assertEqual("needs_case_review", inventory[0]["review_status"])
        self.assertEqual("paper_screened", inventory[3]["review_status"])
        self.assertEqual("feature_request_wording", inventory[1]["screening_reason"])
        self.assertEqual("missing_regression_tests", inventory[2]["screening_reason"])
        self.assertEqual("manual_test_alignment_hold", inventory[4]["screening_reason"])
        self.assertNotIn("problem_statement", inventory[0])

    def test_rejects_duplicate_official_ids(self) -> None:
        same = record("same", "Wrong output", "Expected output fails.")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_inventory([same, same], set(), set())

    def test_cli_materializes_reproducible_full_and_screened_lists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.jsonl"
            source.write_text("\n".join(json.dumps(row) for row in [
                record("bug-1", "Wrong response", "Reproduction example: response fails."),
                record("feature-1", "Add support for headers", "Example reports an error."),
            ]) + "\n", encoding="utf-8")
            selection = root / "reviewed.jsonl"
            selection.write_text("", encoding="utf-8")
            reviews = root / "reviews.jsonl"
            reviews.write_text("", encoding="utf-8")
            completed = subprocess.run([
                sys.executable, str(ROOT / "scripts/build_swe_lite_selection.py"),
                "--dataset-file", str(source), "--reviewed-selection", str(selection),
                "--case-reviews", str(reviews),
                "--full-output", str(root / "full.txt"),
                "--screened-output", str(root / "screened.txt"),
                "--reviewed-output", str(root / "reviewed.txt"),
                "--inventory-output", str(root / "inventory.jsonl"),
            ], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("bug-1\nfeature-1\n", (root / "full.txt").read_text(encoding="utf-8"))
            self.assertEqual("bug-1\n", (root / "screened.txt").read_text(encoding="utf-8"))
            self.assertEqual("", (root / "reviewed.txt").read_text(encoding="utf-8"))
            self.assertEqual(2, len((root / "inventory.jsonl").read_text(encoding="utf-8").splitlines()))

    def test_default_review_file_is_applied_to_published_inventory(self) -> None:
        base = ROOT / "datasets/swe-bench-lite"
        inventory = {
            row["instance_id"]: row for row in (
                json.loads(line) for line in (base / "case-inventory-v2.jsonl").read_text(encoding="utf-8").splitlines()
            )
        }
        self.assertEqual("case_reviewed", inventory["astropy__astropy-14995"]["review_status"])
        self.assertEqual("optional_state_propagation", inventory["astropy__astropy-14995"]["repair_obstacle"])
        self.assertEqual("structural_semantics", inventory["astropy__astropy-12907"]["repair_obstacle"])
        self.assertTrue(inventory["astropy__astropy-12907"]["review"]["capability_hypothesis"])
        self.assertEqual("review_hold", inventory["sympy__sympy-21612"]["review_status"])
        self.assertFalse(inventory["sympy__sympy-21612"]["selected"])
        self.assertEqual(77, sum(row["review_status"] == "case_reviewed" for row in inventory.values()))
        self.assertEqual(33, sum(row["review_status"] == "review_hold" for row in inventory.values()))
        self.assertEqual(0, sum(row["review_status"] == "needs_case_review" for row in inventory.values()))


if __name__ == "__main__":
    unittest.main()
