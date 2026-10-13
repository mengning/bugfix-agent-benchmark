from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from scripts.run_agent_benchmark import build_parser, run


class BatchCliTests(unittest.TestCase):
    def test_runs_agent_command_for_selected_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture"
            fixture.mkdir()
            (fixture / "value.txt").write_text("before\n", encoding="utf-8")
            manifest = root / "manifest.jsonl"
            manifest.write_text(
                json.dumps(
                    {
                        "case_id": "case-1",
                        "repository": "smoke/case-1",
                        "source_path": "fixture",
                        "base_commit": "fixture",
                        "problem_statement": "Change value.",
                        "fail_to_pass": ["test ! -f value.ok"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            args = build_parser().parse_args(
                [
                    "--manifest",
                    str(manifest),
                    "--repository-root",
                    str(root),
                    "--agent-command",
                    (
                        "python3 -c \"import os; "
                        "open(os.path.join(os.environ['BENCHMARK_WORKSPACE'], 'value.ok'), 'w').close(); "
                        "open(os.environ['BENCHMARK_ARTIFACT_FILE'], 'w').write('{\\\\\\\"patch\\\\\\\": \\\\\\\"diff --git a/value.txt b/value.txt\\\\\\\\n--- a/value.txt\\\\\\\\n+++ b/value.txt\\\\\\\\n@@ -1 +1 @@\\\\\\\\n-before\\\\\\\\n+after\\\\\\\\n\\\\\\\"}')\""
                    ),
                    "--results-dir",
                    str(root / "results"),
                    "--run-id",
                    "batch",
                ]
            )

            score = run(args)

            self.assertEqual(1, score["total"])
            self.assertEqual(0, score["passed"])
            self.assertEqual("baseline_invalid", score["cases"][0]["status"])


if __name__ == "__main__":
    unittest.main()
