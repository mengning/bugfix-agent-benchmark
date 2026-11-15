from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from bugfix_benchmark.models import AgentArtifact

from scripts.run_swe_bench_agent import build_parser, isolate_workspace_history, run


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

            predictions = [json.loads(line) for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual("owner__repo-1", predictions[0]["instance_id"])
            self.assertIn("+after", predictions[0]["model_patch"])

            args.resume = True
            agent.write_text("raise RuntimeError('must not run again')\n", encoding="utf-8")
            resumed = run(args)
            self.assertEqual(1, resumed["patches_generated"])
            self.assertEqual(1, resumed["skipped_existing"])

    def test_devstar_runtime_generates_and_resumes_without_local_model_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "cases.jsonl"
            dataset.write_text(json.dumps({"instance_id": "owner__repo-1", "repo": "owner/repo",
                "base_commit": "abc", "problem_statement": "Fix it",
                "FAIL_TO_PASS": '["hidden test"]', "PASS_TO_PASS": "[]"}) + "\n")
            args = build_parser().parse_args(["--dataset-file", str(dataset), "--adapter", "devstar-runtime",
                "--results-dir", str(root / "results"), "--run-id", "runtime"])
            class FakeAdapter:
                def run(self, case):
                    assert not case.fail_to_pass
                    return AgentArtifact(patch="diff --git a/a b/a\n", adapter="devstar-runtime", metadata={"event_id": 42})
            def prepare(case, workspace, _):
                workspace.mkdir()
            with patch("scripts.run_swe_bench_agent.prepare_workspace", side_effect=prepare), \
                 patch("scripts.run_swe_bench_agent.isolate_workspace_history"), \
                 patch("scripts.run_swe_bench_agent.runtime_adapter_from_environment", return_value=FakeAdapter()):
                result = run(args)
                self.assertEqual(1, result["patches_generated"])
                self.assertEqual(42, result["cases"][0]["artifact"]["event_id"])
                args.resume = True
                self.assertEqual(1, run(args)["skipped_existing"])
                dataset.write_text(dataset.read_text() + "\n")
                with self.assertRaisesRegex(ValueError, "dataset contents"):
                    run(args)

    def test_failed_devstar_workspace_is_retained_and_not_retried_implicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "cases.jsonl"
            dataset.write_text(json.dumps({"instance_id": "owner__repo-1", "repo": "owner/repo",
                "base_commit": "abc", "problem_statement": "Fix it"}) + "\n")
            args = build_parser().parse_args(["--dataset-file", str(dataset), "--adapter", "devstar-runtime",
                "--results-dir", str(root / "results"), "--run-id", "runtime"])
            class FailedAdapter:
                def run(self, case):
                    raise RuntimeError("event may still be running")
            def prepare(case, workspace, _):
                workspace.mkdir()
            with patch("scripts.run_swe_bench_agent.prepare_workspace", side_effect=prepare) as prepared, \
                 patch("scripts.run_swe_bench_agent.isolate_workspace_history"), \
                 patch("scripts.run_swe_bench_agent.runtime_adapter_from_environment", return_value=FailedAdapter()):
                self.assertEqual(1, run(args)["agent_failed"])
                self.assertTrue((root / "results/runtime/cases/owner__repo-1/workspace").exists())
                args.resume = True
                self.assertEqual(1, run(args)["agent_failed"])
                self.assertEqual(1, prepared.call_count)

    def test_interrupted_runtime_with_workspace_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "cases.jsonl"
            dataset.write_text(json.dumps({"instance_id": "owner__repo-1", "repo": "owner/repo",
                "base_commit": "abc", "problem_statement": "Fix it"}) + "\n")
            args = build_parser().parse_args(["--dataset-file", str(dataset), "--adapter", "devstar-runtime",
                "--results-dir", str(root / "results"), "--run-id", "runtime"])
            class FailedAdapter:
                def run(self, case):
                    raise RuntimeError("event may still run")
            def prepare(case, workspace, _):
                workspace.mkdir()
            with patch("scripts.run_swe_bench_agent.prepare_workspace", side_effect=prepare) as prepared, \
                 patch("scripts.run_swe_bench_agent.isolate_workspace_history"), \
                 patch("scripts.run_swe_bench_agent.runtime_adapter_from_environment", return_value=FailedAdapter()):
                run(args)
                case_dir = root / "results/runtime/cases/owner__repo-1"
                (case_dir / "result.json").unlink()
                args.resume = True
                result = run(args)
                self.assertEqual(1, result["agent_failed"])
                self.assertIn("workspace retained", result["cases"][0]["error"])
                self.assertEqual(1, prepared.call_count)

    def test_history_is_removed_and_baseline_tree_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            (root / "value.txt").write_text("base\n")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--quiet", "-m", "base"], check=True)
            (root / "value.txt").write_text("gold answer\n")
            subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--quiet", "-am", "secret fix"], check=True)
            subprocess.run(["git", "-C", str(root), "checkout", "--quiet", "--detach", "HEAD~1"], check=True)
            isolate_workspace_history(root)
            history = subprocess.check_output(["git", "-C", str(root), "log", "--all", "--format=%s"], text=True)
            self.assertEqual("benchmark baseline\n", history)
            self.assertEqual("base\n", (root / "value.txt").read_text())

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

    def test_resume_retries_failed_case_and_replaces_empty_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            subprocess.run(["git", "init", "--quiet", str(source)], check=True)
            (source / "value.txt").write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "value.txt"], check=True)
            subprocess.run(["git", "-C", str(source), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--quiet", "-m", "baseline"], check=True)
            commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
            dataset = root / "cases.jsonl"
            dataset.write_text(json.dumps({"instance_id": "owner__repo-1", "repo": "owner/repo", "source_url": str(source), "base_commit": commit, "problem_statement": "Fix", "FAIL_TO_PASS": "[]", "PASS_TO_PASS": "[]"}) + "\n", encoding="utf-8")
            agent = root / "agent.py"
            agent.write_text("raise RuntimeError('fail first')\n", encoding="utf-8")
            args = build_parser().parse_args(["--dataset-file", str(dataset), "--agent-command", f"{sys.executable} {agent}", "--results-dir", str(root / "results"), "--run-id", "retry-run"])
            self.assertEqual(1, run(args)["agent_failed"])
            agent.write_text("import json, os, pathlib\npathlib.Path(os.environ['BENCHMARK_ARTIFACT_FILE']).write_text(json.dumps({'patch':'diff --git a/value.txt b/value.txt\\n--- a/value.txt\\n+++ b/value.txt\\n@@ -1 +1 @@\\n-before\\n+after\\n'}))\n", encoding="utf-8")
            args.resume = True
            self.assertEqual(1, run(args)["patches_generated"])
            predictions = [json.loads(line) for line in (root / "results" / "retry-run" / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(1, len(predictions))
            self.assertIn("+after", predictions[0]["model_patch"])


if __name__ == "__main__":
    unittest.main()
