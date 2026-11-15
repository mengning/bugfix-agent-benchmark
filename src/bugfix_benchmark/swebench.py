from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .models import BenchmarkCase


class SweBenchError(RuntimeError):
    pass


def read_instance_ids(path: Path) -> Tuple[str, ...]:
    if not path.is_file():
        raise SweBenchError(f"instance list not found: {path}")
    instance_ids = tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not instance_ids:
        raise SweBenchError(f"instance list is empty: {path}")
    seen = set()
    for instance_id in instance_ids:
        if instance_id in seen:
            raise SweBenchError(f"duplicate instance_id: {instance_id}")
        seen.add(instance_id)
    return instance_ids


def select_records(
    records: Iterable[Dict[str, Any]], instance_ids: Sequence[str]
) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for record in records:
        instance_id = str(record.get("instance_id") or "").strip()
        if instance_id:
            by_id[instance_id] = dict(record)
    missing = [instance_id for instance_id in instance_ids if instance_id not in by_id]
    if missing:
        raise SweBenchError(f"instance_id not found in dataset: {', '.join(missing)}")
    return [by_id[instance_id] for instance_id in instance_ids]


def official_cases(records: Iterable[Dict[str, Any]]) -> List[BenchmarkCase]:
    """Prepare official cases for Agent invocation, not local test execution."""
    cases = []
    seen = set()
    for record in records:
        instance_id = str(record.get("instance_id") or "").strip()
        repository = str(record.get("repo") or "").strip()
        base_commit = str(record.get("base_commit") or "").strip()
        problem_statement = str(record.get("problem_statement") or "").strip()
        if not all((instance_id, repository, base_commit, problem_statement)):
            raise SweBenchError("official case requires instance_id, repo, base_commit, and problem_statement")
        if instance_id in seen:
            raise SweBenchError(f"duplicate instance_id: {instance_id}")
        seen.add(instance_id)
        cases.append(
            BenchmarkCase(
                case_id=instance_id,
                repository=repository,
                base_commit=base_commit,
                problem_statement=problem_statement,
                fail_to_pass=(),
                pass_to_pass=(),
                source_url=str(record.get("source_url") or f"https://github.com/{repository.removesuffix('.git')}.git"),
                metadata={"dataset": "SWE-bench/SWE-bench_Lite"},
            )
        )
    if not cases:
        raise SweBenchError("official dataset contains no cases")
    return cases


def build_predictions(
    instance_ids: Sequence[str], patch_directory: Path, model_name: str, *, allow_empty: bool = False
) -> List[Dict[str, str]]:
    if not model_name.strip():
        raise SweBenchError("model name must not be empty")
    predictions = []
    for instance_id in instance_ids:
        patch_path = patch_directory / f"{instance_id}.patch"
        if not patch_path.is_file():
            raise SweBenchError(f"missing patch for {instance_id}: {patch_path}")
        patch = patch_path.read_text(encoding="utf-8")
        if not patch.strip() and not allow_empty:
            raise SweBenchError(f"empty patch for {instance_id}: {patch_path}")
        predictions.append(
            {
                "instance_id": instance_id,
                "model_name_or_path": model_name.strip(),
                "model_patch": patch,
            }
        )
    return predictions


def write_jsonl(records: Iterable[Dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record, ensure_ascii=False) for record in records]
    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def build_harness_command(
    *,
    python_executable: str,
    dataset_name: str,
    predictions_path: Path,
    run_id: str,
    max_workers: int,
    instance_ids: Sequence[str] = (),
) -> List[str]:
    if max_workers <= 0:
        raise SweBenchError("max_workers must be positive")
    command = [
        python_executable,
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        dataset_name,
        "--predictions_path",
        str(predictions_path),
        "--max_workers",
        str(max_workers),
        "--run_id",
        run_id,
    ]
    if instance_ids:
        command.extend(["--instance_ids", *instance_ids])
    return command


def score_from_harness_report(
    report: Dict[str, Any], instance_ids: Sequence[str], run_id: str
) -> Dict[str, Any]:
    if int(report.get("total_instances", -1)) != len(instance_ids):
        raise SweBenchError("harness report total does not match selected instance count")
    statuses = {
        "resolved_ids": "resolved",
        "unresolved_ids": "unresolved",
        "empty_patch_ids": "empty_patch",
        "error_ids": "error",
        "incomplete_ids": "incomplete",
    }
    by_id = {}
    for field, status in statuses.items():
        for instance_id in report.get(field, []):
            by_id[str(instance_id)] = status
    cases = [
        {
            "case_id": instance_id,
            "status": by_id.get(instance_id, "incomplete"),
            "passed": by_id.get(instance_id) == "resolved",
        }
        for instance_id in instance_ids
    ]
    passed = sum(case["passed"] for case in cases)
    return {
        "run_id": run_id,
        "scorer": "official_swebench_harness",
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "pass_rate": passed / len(cases) if cases else 0.0,
        "cases": cases,
    }
