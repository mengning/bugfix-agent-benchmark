#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bugfix_benchmark.agent_runner import CommandAgentAdapter, command_from_string
from bugfix_benchmark.catalog import load_cases
from bugfix_benchmark.runner import BenchmarkRunner, _new_run_id, _safe_name
from bugfix_benchmark.verifier import verify_case
from bugfix_benchmark.workspace import prepare_workspace
from bugfix_benchmark.models import CaseResult
import json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local Agent command for every benchmark case and score patches."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--agent-command", required=True)
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--run-id")
    parser.add_argument("--case", action="append", default=[], dest="cases")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--agent-timeout", type=float, default=900.0)
    parser.add_argument("--command-timeout", type=float, default=600.0)
    return parser


def run(args: argparse.Namespace) -> dict[str, object]:
    repository_root = args.repository_root.resolve()
    cases = load_cases(args.manifest)
    if args.cases:
        selected = set(args.cases)
        cases = [case for case in cases if case.case_id in selected]
        missing = selected.difference(case.case_id for case in cases)
        if missing:
            raise ValueError(f"unknown case_id(s): {', '.join(sorted(missing))}")
    if args.max_cases is not None:
        if args.max_cases <= 0:
            raise ValueError("max_cases must be positive")
        cases = cases[: args.max_cases]
    if not cases:
        raise ValueError("no benchmark cases selected")

    run_id = args.run_id or _new_run_id()
    run_dir = args.results_dir / run_id
    patches_dir = run_dir / "patches"
    cases_dir = run_dir / "cases"
    patches_dir.mkdir(parents=True, exist_ok=False)
    cases_dir.mkdir(parents=True, exist_ok=True)
    command = command_from_string(args.agent_command)
    results: list[dict[str, object]] = []
    for case in cases:
        case_name = _safe_name(case.case_id)
        case_dir = cases_dir / case_name
        case_dir.mkdir(parents=True, exist_ok=True)
        workspace = case_dir / "workspace"
        case_file = case_dir / "case.json"
        artifact_file = case_dir / "artifact.json"
        try:
            prepare_workspace(case, workspace, repository_root)
            artifact = CommandAgentAdapter(
                command=command,
                case_file=case_file,
                workspace=workspace,
                artifact_file=artifact_file,
                timeout_seconds=args.agent_timeout,
            ).run(case)
            patch_path = patches_dir / f"{case_name}.patch"
            patch_path.write_text(artifact.patch, encoding="utf-8")
            result = verify_case(
                case,
                artifact,
                case_dir,
                repository_root=repository_root,
                command_timeout=args.command_timeout,
            )
            result.evidence["adapter"] = artifact.adapter
        except Exception as exc:
            patch_path = patches_dir / f"{case_name}.patch"
            patch_path.write_text("", encoding="utf-8")
            result = CaseResult(
                case_id=case.case_id,
                status="agent_failed",
                failure_reason=str(exc),
            )
        value = result.as_dict()
        results.append(value)
        (case_dir / "result.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    passed = sum(1 for result in results if result["passed"])
    score: dict[str, object] = {
        "run_id": run_id,
        "manifest": str(args.manifest),
        "adapter": "command",
        "agent_command": command,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": passed / len(results),
        "cases": results,
    }
    (run_dir / "score.json").write_text(
        json.dumps(score, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return score


def main() -> int:
    args = build_parser().parse_args()
    score = run(args)
    print(
        f"run={score['run_id']} passed={score['passed']}/{score['total']} "
        f"pass_rate={score['pass_rate']:.1%}"
    )
    for case in score["cases"]:
        print(f"{case['case_id']}: {case['status']}")
    return 0 if score["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
