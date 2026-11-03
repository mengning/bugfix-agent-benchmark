from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("scenario_pool", ROOT / "scripts/build_scenario_pool.py")
assert SPEC and SPEC.loader
scenario_pool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scenario_pool)


class ScenarioPoolTests(unittest.TestCase):
    def test_span_proxy_is_not_claimed_from_one_file_or_short_issue(self) -> None:
        self.assertEqual(2, scenario_pool.changed_files(
            "diff --git a/a.py b/a.py\n" "diff --git a/b.py b/b.py\n"
            "diff --git a/a.py b/a.py\n"
        ))
        self.assertEqual("unknown", scenario_pool.span_label(None, 1000))
        self.assertEqual("multi_file_proxy", scenario_pool.span_label(8, 200))
        self.assertEqual("long_task_proxy", scenario_pool.span_label(4, 500))

    def test_published_pool_has_unique_source_backed_cases_and_no_gold(self) -> None:
        path = ROOT / "datasets/cross-source/scenario-pool-v1.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertGreaterEqual(len(rows), 150)
        self.assertEqual(len(rows), len({row["case_id"] for row in rows}))
        self.assertGreaterEqual(len({row["source"] for row in rows}), 8)
        self.assertTrue(all(row["selection_purpose"] and row["evidence_url"] for row in rows))
        self.assertTrue(all(row["review_stage"] != "runnable" for row in rows))
        self.assertTrue(all("/" in row["repository"] for row in rows))
        forbidden = {"patch", "fix_patch", "test_patch", "FAIL_TO_PASS", "PASS_TO_PASS"}
        self.assertTrue(all(not forbidden.intersection(row) for row in rows))

    def test_existing_hold_is_not_promoted_by_metadata_seed(self) -> None:
        rows = [json.loads(line) for line in (
            ROOT / "datasets/cross-source/scenario-pool-v1.jsonl"
        ).read_text(encoding="utf-8").splitlines()]
        by_id = {row["case_id"]: row for row in rows}
        self.assertEqual("hold_input_or_oracle", by_id["apple__pkl-1165"]["review_stage"])
        self.assertEqual("hold_input_or_oracle", by_id["libsdl-org__SDL-11761"]["review_stage"])


if __name__ == "__main__":
    unittest.main()
