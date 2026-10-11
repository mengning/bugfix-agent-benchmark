from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from bugfix_benchmark.cli import build_parser, main


class CliTests(unittest.TestCase):
    def test_public_cli_exposes_only_patch_directory_adapter(self) -> None:
        parser = build_parser()
        run_parser = next(
            action.choices["run"]
            for action in parser._actions
            if getattr(action, "choices", None) and "run" in action.choices
        )
        adapter_action = next(
            action for action in run_parser._actions if action.dest == "adapter"
        )

        self.assertEqual(("patch-dir",), adapter_action.choices)

    def test_returns_nonzero_when_patch_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fixture"
            source.mkdir()
            (source / "test_failure.py").write_text(
                "import unittest\nclass Failure(unittest.TestCase):\n    def test_fails(self): self.fail('red')\n",
                encoding="utf-8",
            )
            manifest = root / "manifest.jsonl"
            manifest.write_text(
                json.dumps(
                    {
                        "case_id": "missing-patch",
                        "repository": "fixture",
                        "source_path": "fixture",
                        "base_commit": "fixture",
                        "problem_statement": "Fix it.",
                        "fail_to_pass": ["python3 -m unittest test_failure"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            patches = root / "patches"
            patches.mkdir()

            exit_code = main(
                [
                    "run",
                    "--manifest",
                    str(manifest),
                    "--repository-root",
                    str(root),
                    "--adapter",
                    "patch-dir",
                    "--patch-dir",
                    str(patches),
                    "--results-dir",
                    str(root / "results"),
                    "--run-id",
                    "cli-test",
                ]
            )

            self.assertEqual(1, exit_code)
            score = json.loads((root / "results/cli-test/score.json").read_text(encoding="utf-8"))
            self.assertEqual("no_patch", score["cases"][0]["status"])


if __name__ == "__main__":
    unittest.main()
