from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from bugfix_benchmark.swebench import (
    SweBenchError,
    build_harness_command,
    build_predictions,
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


if __name__ == "__main__":
    unittest.main()
