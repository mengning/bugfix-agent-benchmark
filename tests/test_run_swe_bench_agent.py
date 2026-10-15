from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.run_swe_bench_agent import build_parser, run


class RunSweBenchAgentTests(unittest.TestCase):
    def test_generates_patch_for_official_case_without_running_local_test_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            subprocess.run(["git", "init", "--quiet", str(source)], check=True)
            (source / "value.txt").write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "value.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(source), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--quiet", "-m", "baseline"],
                check=True,
            )
            commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
            dataset = root / "cases.jsonl"
            dataset.write_text(
                json.dumps({
                    "instance_id": "owner__repo-1",
                    "repo": "owner/repo",
                    "source_url": str(source),
                    "base_commit": commit,
                    "problem_statement": "Change the value",
                    "FAIL_TO_PASS": '["not a shell command"]',
                    "PASS_TO_PASS": "[]",
                }) + "\n",
                encoding="utf-8",
            )
            agent = root / "agent.py"
            agent.write_text(
                "import json, os, pathlib, subprocess\n"
                "workspace = pathlib.Path(os.environ['BENCHMARK_WORKSPACE'])\n"
                "(workspace / 'value.txt').write_text('after\\n')\n"
                "patch = subprocess.check_output(['git', 'diff'], cwd=workspace, text=True)\n"
                "pathlib.Path(os.environ['BENCHMARK_ARTIFACT_FILE']).write_text(json.dumps({'patch': patch}))\n",
                encoding="utf-8",
            )
            args = build_parser().parse_args([
                "--dataset-file", str(dataset),
                "--agent-command", f"{sys.executable} {agent}",
                "--results-dir", str(root / "results"),
                "--run-id", "official-run",
            ])

            result = run(args)
            run_dir = root / "results" / "official-run"

            self.assertEqual(1, result["patches_generated"])
            self.assertIn("+after", (run_dir / "patches" / "owner__repo-1.patch").read_text(encoding="utf-8"))
            self.assertEqual("owner__repo-1\n", (run_dir / "instances.txt").read_text(encoding="utf-8"))
            self.assertFalse((run_dir / "score.json").exists())

    def test_agent_failure_keeps_empty_patch_for_official_denominator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "cases.jsonl"
            dataset.write_text(
                json.dumps({
                    "instance_id": "owner__repo-1", "repo": "owner/repo",
                    "source_url": str(root / "missing"), "base_commit": "abc123",
                    "problem_statement": "Fix the bug", "FAIL_TO_PASS": "[]", "PASS_TO_PASS": "[]",
                }) + "\n",
                encoding="utf-8",
            )
            args = build_parser().parse_args([
                "--dataset-file", str(dataset),
                "--agent-command", "python3 -c pass",
                "--results-dir", str(root / "results"),
                "--run-id", "failed-run",
            ])

            result = run(args)

            self.assertEqual(1, result["agent_failed"])
            self.assertEqual("", (root / "results" / "failed-run" / "patches" / "owner__repo-1.patch").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
