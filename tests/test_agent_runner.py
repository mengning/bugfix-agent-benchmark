from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from bugfix_benchmark.agent_runner import CommandAgentAdapter
from bugfix_benchmark.models import BenchmarkCase


PATCH = "diff --git a/calc.py b/calc.py\n--- a/calc.py\n+++ b/calc.py\n"


def make_case(source_path: str = "fixture") -> BenchmarkCase:
    return BenchmarkCase.from_record(
        {
            "case_id": "case-1",
            "repository": "smoke/case-1",
            "source_path": source_path,
            "base_commit": "fixture",
            "problem_statement": "Fix the bug.",
            "fail_to_pass": ["python3 -m unittest"],
        }
    )


class CommandAgentAdapterTests(unittest.TestCase):
    def test_runs_command_with_case_workspace_and_artifact_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = make_case()
            case_file = root / "case.json"
            artifact_file = root / "artifact.json"
            workspace = root / "workspace"
            workspace.mkdir()
            case_file.write_text(json.dumps(case.evaluation_payload()), encoding="utf-8")

            adapter = CommandAgentAdapter(
                command=[
                    "python3",
                    "-c",
                    (
                        "import json, os; "
                        "assert os.path.isdir(os.environ['BENCHMARK_WORKSPACE']); "
                        "json.dump({'patch': %r}, open(os.environ['BENCHMARK_ARTIFACT_FILE'], 'w'))"
                    )
                    % PATCH,
                ],
                case_file=case_file,
                workspace=workspace,
                artifact_file=artifact_file,
            )

            artifact = adapter.run(case)

        self.assertEqual(PATCH, artifact.patch)
        self.assertEqual("command", artifact.adapter)
        self.assertEqual(str(workspace), artifact.metadata["workspace"])

    def test_rejects_artifact_without_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact_file = root / "artifact.json"
            workspace = root / "workspace"
            workspace.mkdir()
            adapter = CommandAgentAdapter(
                command=[
                    "python3",
                    "-c",
                    "open(__import__('os').environ['BENCHMARK_ARTIFACT_FILE'], 'w').write('{}')",
                ],
                case_file=root / "case.json",
                workspace=workspace,
                artifact_file=artifact_file,
            )
            with self.assertRaisesRegex(RuntimeError, "patch"):
                adapter.run(make_case())
