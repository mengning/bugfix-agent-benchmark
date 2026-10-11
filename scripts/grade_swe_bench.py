#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bugfix_benchmark.swebench import (
    build_harness_command,
    build_predictions,
    read_instance_ids,
    write_jsonl,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Grade Agent patches with the official SWE-bench harness."
    )
    parser.add_argument(
        "--instances-file",
        type=Path,
        default=Path("datasets/swe-bench-lite/sample-10.txt"),
    )
    parser.add_argument("--patch-dir", type=Path, required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--dataset", default="SWE-bench/SWE-bench_Lite")
    parser.add_argument("--run-id", default="bugfix-benchmark")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--python", default=sys.executable, dest="python_executable")
    parser.add_argument(
        "--predictions-path",
        type=Path,
        default=Path(".benchmark/predictions.jsonl"),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write predictions and print the official harness command without running it",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    instance_ids = read_instance_ids(args.instances_file)
    predictions = build_predictions(instance_ids, args.patch_dir, args.model_name)
    write_jsonl(predictions, args.predictions_path)
    command = build_harness_command(
        python_executable=args.python_executable,
        dataset_name=args.dataset,
        predictions_path=args.predictions_path,
        run_id=args.run_id,
        max_workers=args.max_workers,
    )
    print(f"wrote {len(predictions)} predictions to {args.predictions_path}")
    print(shlex.join(command))
    if args.dry_run:
        return 0
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
