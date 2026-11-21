from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicScriptTests(unittest.TestCase):
    def test_configured_cli_exports_selected_inputs_and_scores_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            config.write_text(json.dumps({
                "dataset": {"instances_file": "selected.txt"},
                "run": {"results_dir": "runs", "run_id": "trial", "model_name": "custom"},
            }), encoding="utf-8")
            (root / "selected.txt").write_text("owner__repo-1\n", encoding="utf-8")
            (root / "datasets.py").write_text(
                "def load_dataset(name, *, split, revision):\n"
                "    assert split == 'test' and len(revision) == 40\n"
                "    return [{'instance_id': 'owner__repo-1', 'repo': 'owner/repo', "
                "'base_commit': 'abc', 'problem_statement': 'Fix the bug', 'patch': 'gold'}]\n",
                encoding="utf-8",
            )
            env = {**os.environ, "PYTHONPATH": str(root)}
            public_input = root / "agent.jsonl"
            fetch = subprocess.run(
                [sys.executable, str(ROOT / "scripts/fetch_swe_bench.py"), "--config", str(config),
                 "--output", str(public_input)],
                cwd=root, env=env, capture_output=True, text=True,
            )
            self.assertEqual(0, fetch.returncode, fetch.stderr)
            self.assertNotIn("patch", json.loads(public_input.read_text(encoding="utf-8")))
            patch_dir = root / "runs/trial/patches"
            patch_dir.mkdir(parents=True)
            (patch_dir.parent / "instances.txt").write_text("owner__repo-1\n", encoding="utf-8")
            (patch_dir / "owner__repo-1.patch").write_text("", encoding="utf-8")
            grade = subprocess.run(
                [sys.executable, str(ROOT / "scripts/grade_swe_bench.py"), "--config", str(config),
                 "--max-workers", "2", "--dry-run"],
                cwd=root, env=env, capture_output=True, text=True,
            )
            self.assertEqual(0, grade.returncode, grade.stderr)
            self.assertIn("--max_workers 2 --run_id trial", grade.stdout)
            row = json.loads((patch_dir.parent / "grading-predictions.jsonl").read_text(encoding="utf-8"))
            self.assertEqual("custom", row["model_name_or_path"])
            self.assertEqual("", row["model_patch"])

    def test_fetch_script_exposes_portable_cli(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/fetch_swe_bench.py"), "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        self.assertEqual(0, completed.returncode, completed.stdout)
        self.assertIn("--instances-file", completed.stdout)
        self.assertNotIn("/Users/", completed.stdout)

    def test_grade_script_exposes_portable_cli(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/grade_swe_bench.py"), "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        self.assertEqual(0, completed.returncode, completed.stdout)
        self.assertIn("--patch-dir", completed.stdout)
        self.assertIn("--dry-run", completed.stdout)
        self.assertNotIn("/private/tmp", completed.stdout)

    def test_batch_script_exposes_agent_command_cli(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/run_swe_bench_agent.py"), "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        self.assertEqual(0, completed.returncode, completed.stdout)
        self.assertIn("--agent-command", completed.stdout)
        self.assertIn("--dataset-file", completed.stdout)


if __name__ == "__main__":
    unittest.main()
