from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bugfix_benchmark.swebench import (
    SweBenchError,
    build_harness_command,
    build_predictions,
    official_cases,
    score_from_harness_report,
    read_instance_ids,
    select_records,
)


class SweBenchDatasetTests(unittest.TestCase):
    def test_reads_comments_and_rejects_duplicate_instance_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "instances.txt"
            path.write_text("# sample\nowner__repo-1\n\nowner__repo-2\n", encoding="utf-8")
            self.assertEqual(("owner__repo-1", "owner__repo-2"), read_instance_ids(path))

            path.write_text("owner__repo-1\nowner__repo-1\n", encoding="utf-8")
            with self.assertRaisesRegex(SweBenchError, "duplicate instance_id"):
                read_instance_ids(path)

    def test_selects_official_records_in_requested_order(self) -> None:
        records = [
            {"instance_id": "owner__repo-2", "repo": "owner/repo"},
            {"instance_id": "owner__repo-1", "repo": "owner/repo"},
        ]

        selected = select_records(records, ("owner__repo-1", "owner__repo-2"))

        self.assertEqual(
            ["owner__repo-1", "owner__repo-2"],
            [item["instance_id"] for item in selected],
        )

    def test_rejects_instance_id_missing_from_official_dataset(self) -> None:
        with self.assertRaisesRegex(SweBenchError, "not found in dataset"):
            select_records([], ("owner__missing-1",))

    def test_official_cases_preserve_full_split_without_local_test_commands(self) -> None:
        records = [
            {
                "instance_id": "owner__repo-1",
                "repo": "owner/repo",
                "base_commit": "abc123",
                "problem_statement": "Fix the bug",
                "FAIL_TO_PASS": '["tests/test_bug.py::test_case"]',
                "PASS_TO_PASS": "[]",
            },
            {
                "instance_id": "owner__repo-2",
                "repo": "owner/repo",
                "base_commit": "def456",
                "problem_statement": "Fix another bug",
                "FAIL_TO_PASS": '["tests/test_other.py::test_case"]',
                "PASS_TO_PASS": "[]",
            },
        ]

        cases = official_cases(records)

        self.assertEqual(["owner__repo-1", "owner__repo-2"], [case.case_id for case in cases])
        self.assertEqual((), cases[0].fail_to_pass)
        self.assertEqual("https://github.com/owner/repo.git", cases[0].source_url)
        self.assertEqual("abc123", cases[0].base_commit)


class SweBenchPredictionTests(unittest.TestCase):
    def test_builds_official_predictions_from_patch_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            patches = Path(directory)
            (patches / "owner__repo-1.patch").write_text(
                "diff --git a/a b/a\n", encoding="utf-8"
            )

            predictions = build_predictions(("owner__repo-1",), patches, "example-agent")

        self.assertEqual(
            [
                {
                    "instance_id": "owner__repo-1",
                    "model_name_or_path": "example-agent",
                    "model_patch": "diff --git a/a b/a\n",
                }
            ],
            predictions,
        )

    def test_rejects_missing_agent_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(SweBenchError, "missing patch"):
                build_predictions(("owner__repo-1",), Path(directory), "example-agent")

    def test_empty_agent_patch_is_submitted_as_unresolved_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            patch_path = Path(directory) / "owner__repo-1.patch"
            patch_path.write_text("", encoding="utf-8")

            predictions = build_predictions(
                ("owner__repo-1",), Path(directory), "example-agent", allow_empty=True
            )

        self.assertEqual("", predictions[0]["model_patch"])

    def test_builds_portable_official_harness_command(self) -> None:
        command = build_harness_command(
            python_executable="python3",
            dataset_name="SWE-bench/SWE-bench_Lite",
            predictions_path=Path("predictions.jsonl"),
            run_id="public-run",
            max_workers=4,
        )

        self.assertEqual("python3", command[0])
        self.assertIn("swebench.harness.run_evaluation", command)
        self.assertIn("predictions.jsonl", command)
        self.assertNotIn("/private/tmp", " ".join(command))

    def test_harness_command_limits_denominator_to_selected_instances(self) -> None:
        command = build_harness_command(
            python_executable="python3",
            dataset_name="SWE-bench/SWE-bench_Lite",
            predictions_path=Path("predictions.jsonl"),
            run_id="sample-run",
            max_workers=2,
            instance_ids=("owner__repo-1", "owner__repo-2"),
        )

        self.assertEqual(
            ["--instance_ids", "owner__repo-1", "owner__repo-2"],
            command[-3:],
        )

    def test_harness_report_yields_score_without_counting_empty_patch_as_pass(self) -> None:
        score = score_from_harness_report(
            {
                "total_instances": 2,
                "resolved_ids": ["owner__repo-1"],
                "unresolved_ids": [],
                "empty_patch_ids": ["owner__repo-2"],
                "error_ids": [],
                "incomplete_ids": [],
            },
            ("owner__repo-1", "owner__repo-2"),
            "sample-run",
        )

        self.assertEqual(2, score["total"])
        self.assertEqual(1, score["passed"])
        self.assertEqual(0.5, score["pass_rate"])
        self.assertEqual("empty_patch", score["cases"][1]["status"])


if __name__ == "__main__":
    unittest.main()
