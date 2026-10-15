#!/usr/bin/env python3
"""Generate Agent patches for official SWE-bench cases without locally grading test IDs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bugfix_benchmark.agent_runner import CommandAgentAdapter, command_from_string
from bugfix_benchmark.runner import _new_run_id, _safe_name
from bugfix_benchmark.swebench import official_cases, read_instance_ids, select_records
from bugfix_benchmark.workspace import prepare_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Bugfix Agent patches for SWE-bench cases.")
    parser.add_argument("--dataset-file", type=Path, required=True)
    parser.add_argument("--instances-file", type=Path, help="optional official instance selection")
    parser.add_argument("--agent-command", required=True)
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--run-id")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--agent-timeout", type=float, default=900.0)
    parser.add_argument("--keep-workspaces", action="store_true")
    return parser


def _load_records(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        raise FileNotFoundError(f"official dataset file not found: {path}")
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{number}: expected a JSON object")
        records.append(value)
    return records


def run(args: argparse.Namespace) -> dict[str, object]:
    records = _load_records(args.dataset_file)
    if args.instances_file:
        records = select_records(records, read_instance_ids(args.instances_file))
    cases = official_cases(records)
    if args.max_cases is not None:
        if args.max_cases <= 0:
            raise ValueError("max-cases must be positive")
        cases = cases[: args.max_cases]

    run_id = args.run_id or _new_run_id()
    run_dir = (args.results_dir / run_id).resolve()
    patches_dir = run_dir / "patches"
    cases_dir = run_dir / "cases"
    run_dir.mkdir(parents=True, exist_ok=False)
    patches_dir.mkdir()
    cases_dir.mkdir()
    command = command_from_string(args.agent_command)
    results = []

    for case in cases:
        case_dir = cases_dir / _safe_name(case.case_id)
        case_dir.mkdir()
        workspace = case_dir / "workspace"
        patch_path = patches_dir / f"{_safe_name(case.case_id)}.patch"
        try:
            prepare_workspace(case, workspace, ROOT)
            artifact = CommandAgentAdapter(
                command=command,
                case_file=case_dir / "case.json",
                workspace=workspace,
                artifact_file=case_dir / "artifact.json",
                timeout_seconds=args.agent_timeout,
            ).run(case)
            patch_path.write_text(artifact.patch, encoding="utf-8")
            result = {"case_id": case.case_id, "status": "patch_generated", "artifact": artifact.metadata}
        except Exception as exc:
            patch_path.write_text("", encoding="utf-8")
            result = {"case_id": case.case_id, "status": "agent_failed", "error": str(exc)}
        finally:
            if not args.keep_workspaces and workspace.is_dir():
                shutil.rmtree(workspace)
        results.append(result)
        (case_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    (run_dir / "instances.txt").write_text(
        "".join(f"{case.case_id}\n" for case in cases), encoding="utf-8"
    )
    generated = sum(result["status"] == "patch_generated" for result in results)
    summary: dict[str, object] = {
        "run_id": run_id,
        "dataset_file": str(args.dataset_file),
        "total": len(cases),
        "patches_generated": generated,
        "agent_failed": len(cases) - generated,
        "cases": results,
    }
    (run_dir / "run.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    args = build_parser().parse_args()
    result = run(args)
    print(
        f"run={result['run_id']} patches={result['patches_generated']}/{result['total']} "
        f"agent_failed={result['agent_failed']}"
    )
    return 0 if result["agent_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
