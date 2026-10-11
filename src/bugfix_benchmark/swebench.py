from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


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


def build_predictions(
    instance_ids: Sequence[str], patch_directory: Path, model_name: str
) -> List[Dict[str, str]]:
    if not model_name.strip():
        raise SweBenchError("model name must not be empty")
    predictions = []
    for instance_id in instance_ids:
        patch_path = patch_directory / f"{instance_id}.patch"
        if not patch_path.is_file():
            raise SweBenchError(f"missing patch for {instance_id}: {patch_path}")
        patch = patch_path.read_text(encoding="utf-8")
        if not patch.strip():
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
) -> List[str]:
    if max_workers <= 0:
        raise SweBenchError("max_workers must be positive")
    return [
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
