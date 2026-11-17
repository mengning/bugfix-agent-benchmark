#!/usr/bin/env python3
"""Generate Agent patches for official SWE-bench cases without locally grading test IDs."""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bugfix_benchmark.agent_runner import CommandAgentAdapter, command_from_string
from bugfix_benchmark.runtime_adapter import runtime_adapter_from_environment
from bugfix_benchmark.naming import _new_run_id, _safe_name
from bugfix_benchmark.swebench import official_cases, read_instance_ids, select_records, build_predictions, write_jsonl
from bugfix_benchmark.workspace import prepare_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Bugfix Agent patches for SWE-bench cases.")
    parser.add_argument("--dataset-file", type=Path, required=True)
    parser.add_argument("--instances-file", type=Path, help="optional official instance selection")
    parser.add_argument("--adapter", choices=("command", "devstar-runtime"), default="command")
    parser.add_argument("--agent-command", help="required for the command adapter")
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--run-id")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--agent-timeout", type=float, default=900.0)
    parser.add_argument("--keep-workspaces", action="store_true")
    parser.add_argument("--resume", action="store_true", help="resume an existing run")
    parser.add_argument("--retry-failed", action="store_true", help="retry failed DevStar events only after confirming they have stopped")
    parser.add_argument("--model-name", default="bugfix-agent", help="model_name_or_path in the official predictions file")
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



def isolate_workspace_history(workspace: Path) -> None:
    """Keep the checked-out tree but remove upstream history before Agent access."""
    shutil.rmtree(workspace / ".git")
    for command in (
        ["git", "init", "--quiet"],
        ["git", "config", "core.autocrlf", "false"],
        ["git", "add", "--all", "--force"],
        ["git", "-c", "user.name=benchmark", "-c", "user.email=benchmark@example.invalid",
         "commit", "--quiet", "--allow-empty", "-m", "benchmark baseline"],
    ):
        result = subprocess.run(command, cwd=workspace, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode:
            raise RuntimeError("cannot prepare isolated benchmark history")


def run(args: argparse.Namespace) -> dict[str, object]:
    if args.retry_failed and not args.resume:
        raise ValueError("--retry-failed requires --resume")
    if args.adapter == "command" and not args.agent_command:
        raise ValueError("--agent-command is required for adapter=command")
    if args.adapter == "devstar-runtime" and args.agent_command:
        raise ValueError("--agent-command cannot be used with adapter=devstar-runtime")
    dataset_sha256 = hashlib.sha256(args.dataset_file.read_bytes()).hexdigest()
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
    run_dir.mkdir(parents=True, exist_ok=args.resume)
    patches_dir.mkdir(exist_ok=args.resume)
    cases_dir.mkdir(exist_ok=args.resume)
    command = command_from_string(args.agent_command) if args.adapter == "command" else []
    results = []
    instance_ids = tuple(case.case_id for case in cases)
    instances_path = run_dir / "instances.txt"
    if args.resume and instances_path.is_file() and read_instance_ids(instances_path) != instance_ids:
        raise ValueError("resume instance selection differs from the existing run")
    previous_summary = run_dir / "run.json"
    if args.resume and previous_summary.is_file():
        previous = json.loads(previous_summary.read_text(encoding="utf-8"))
        if (previous.get("model_name") != args.model_name
                or previous.get("dataset_sha256") != dataset_sha256
                or previous.get("adapter") != args.adapter):
            raise ValueError("resume model, dataset contents or adapter differs from the existing run")
    instances_path.write_text("".join(f"{case_id}\n" for case_id in instance_ids), encoding="utf-8")
    skipped_existing = 0

    def save_progress() -> dict[str, object]:
        completed_ids = [case_id for case_id in instance_ids if (patches_dir / f"{_safe_name(case_id)}.patch").is_file()]
        predictions = build_predictions(completed_ids, patches_dir, args.model_name, allow_empty=True)
        prediction_path = run_dir / "predictions.jsonl"
        temporary_predictions = run_dir / "predictions.jsonl.tmp"
        write_jsonl(predictions, temporary_predictions)
        temporary_predictions.replace(prediction_path)
        generated = sum(result["status"] == "patch_generated" for result in results)
        summary = {
            "run_id": run_id, "dataset_file": str(args.dataset_file), "dataset_sha256": dataset_sha256,
            "adapter": args.adapter, "model_name": args.model_name, "total": len(cases),
            "patches_generated": generated, "agent_failed": sum(result["status"] == "agent_failed" for result in results),
            "skipped_existing": skipped_existing, "cases": results,
        }
        temporary_summary = run_dir / "run.json.tmp"
        temporary_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary_summary.replace(run_dir / "run.json")
        return summary

    for case in cases:
        case_dir = cases_dir / _safe_name(case.case_id)
        case_dir.mkdir(exist_ok=args.resume)
        workspace = case_dir / "workspace"
        patch_path = patches_dir / f"{_safe_name(case.case_id)}.patch"
        result_path = case_dir / "result.json"
        if args.resume and result_path.is_file() and patch_path.is_file():
            previous = json.loads(result_path.read_text(encoding="utf-8"))
            if previous.get("status") == "patch_generated" and patch_path.stat().st_size:
                results.append(previous)
                skipped_existing += 1
                save_progress()
                continue
            if (args.adapter == "devstar-runtime" and not args.retry_failed
                    and previous.get("status") == "agent_failed"):
                results.append(previous)
                save_progress()
                continue
        if args.resume and args.adapter == "devstar-runtime" and workspace.exists() and not args.retry_failed:
            # An interrupted dispatcher may have left a still-running remote event.
            # Never replace its workspace without an explicit retry decision.
            if not patch_path.exists():
                patch_path.write_text("", encoding="utf-8")
            result = {"case_id": case.case_id, "status": "agent_failed",
                      "error": "workspace retained; confirm the DevStar event has stopped before --retry-failed"}
            results.append(result)
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            save_progress()
            continue
        succeeded = False
        try:
            prepare_workspace(case, workspace, ROOT)
            isolate_workspace_history(workspace)
            # The source is the recorded base tree, but its local commit is a new snapshot.
            agent_case = replace(case, base_commit="")
            if args.adapter == "devstar-runtime":
                adapter = runtime_adapter_from_environment(workspace, timeout_seconds=args.agent_timeout)
            else:
                adapter = CommandAgentAdapter(
                    command=command, case_file=case_dir / "case.json", workspace=workspace,
                    artifact_file=case_dir / "artifact.json", timeout_seconds=args.agent_timeout,
                )
            artifact = adapter.run(agent_case)
            patch_path.write_text(artifact.patch, encoding="utf-8")
            result = {"case_id": case.case_id, "status": "patch_generated", "artifact": artifact.metadata}
            succeeded = True
        except Exception as exc:
            patch_path.write_text("", encoding="utf-8")
            result = {"case_id": case.case_id, "status": "agent_failed", "error": str(exc)}
        finally:
            if not args.keep_workspaces and (args.adapter != "devstar-runtime" or succeeded) and workspace.is_dir():
                shutil.rmtree(workspace)
        results.append(result)
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        save_progress()

    return save_progress()


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
