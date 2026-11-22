#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bugfix_benchmark.defaults import read_config
from bugfix_benchmark.swebench import (
    SweBenchError,
    build_harness_command,
    build_predictions,
    read_instance_ids,
    score_from_harness_report,
    write_jsonl,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Grade Agent patches with the official SWE-bench harness."
    )
    parser.add_argument("--config", type=Path, help="benchmark JSON configuration")
    parser.add_argument("--instances-file", type=Path)
    parser.add_argument("--patch-dir", type=Path)
    parser.add_argument("--model-name")
    parser.add_argument("--dataset")
    parser.add_argument("--run-id")
    parser.add_argument("--max-workers", type=int)
    parser.add_argument(
        "--allow-empty", action=argparse.BooleanOptionalAction,
        help="submit empty Agent patches so the official report counts those cases",
    )
    parser.add_argument("--python", default=sys.executable, dest="python_executable")
    parser.add_argument(
        "--predictions-path",
        type=Path,
    )
    parser.add_argument("--report-path", type=Path, help="official harness summary JSON path")
    parser.add_argument("--score-path", type=Path, help="output normalized score.json path")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write predictions and print the official harness command without running it",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    export_dataset = None
    if args.config or args.patch_dir is None:
        config = read_config(parser, args.config)
        run = config["run"]
        grading = config["grading"]
        args.run_id = args.run_id or run["run_id"]
        run_dir = Path(run["results_dir"]) / args.run_id
        args.instances_file = args.instances_file or run_dir / "instances.txt"
        args.patch_dir = args.patch_dir or run_dir / "patches"
        args.model_name = args.model_name or run["model_name"]
        args.max_workers = grading["max_workers"] if args.max_workers is None else args.max_workers
        args.allow_empty = grading["allow_empty"] if args.allow_empty is None else args.allow_empty
        args.predictions_path = args.predictions_path or run_dir / "grading-predictions.jsonl"
        if args.dataset is None:
            dataset = config["dataset"]
            args.dataset = dataset["scoring_dataset_file"]
            export_dataset = [
                sys.executable, str(ROOT / "scripts/fetch_swe_bench.py"),
                "--dataset", dataset["name"], "--split", dataset["split"],
                "--revision", dataset["revision"], "--instances-file", str(args.instances_file),
                "--output", dataset["scoring_input_file"], "--scoring-output", args.dataset,
            ]
    else:
        if not args.model_name:
            parser.error("--model-name is required when using --patch-dir without --config")
        args.run_id = args.run_id or "bugfix-benchmark"
        run_dir = Path("results") / args.run_id
        args.instances_file = args.instances_file or Path("datasets/swe-bench-lite/sample-10.txt")
        args.dataset = args.dataset or "SWE-bench/SWE-bench_Lite"
        args.max_workers = 4 if args.max_workers is None else args.max_workers
        args.predictions_path = args.predictions_path or Path(".benchmark/predictions.jsonl")
    try:
        instance_ids = read_instance_ids(args.instances_file)
        predictions = build_predictions(
            instance_ids, args.patch_dir, args.model_name, allow_empty=bool(args.allow_empty)
        )
        command = build_harness_command(
            python_executable=args.python_executable,
            dataset_name=args.dataset,
            predictions_path=args.predictions_path,
            run_id=args.run_id,
            max_workers=args.max_workers,
            instance_ids=instance_ids,
        )
    except SweBenchError as exc:
        parser.error(str(exc))
    write_jsonl(predictions, args.predictions_path)
    print(f"wrote {len(predictions)} predictions to {args.predictions_path}")
    print(shlex.join(command))
    if args.dry_run:
        return 0
    if export_dataset:
        exit_code = subprocess.run(export_dataset, check=False).returncode
        if exit_code:
            return exit_code
    exit_code = subprocess.run(command, check=False).returncode
    if exit_code:
        return exit_code
    report_path = args.report_path or Path(f"{args.model_name.replace('/', '__')}.{args.run_id}.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError(f"official harness report must be an object: {report_path}")
    score = score_from_harness_report(report, instance_ids, args.run_id)
    score["dataset"] = args.dataset
    score["model_name"] = args.model_name
    score_path = args.score_path or run_dir / "score.json"
    score_path.parent.mkdir(parents=True, exist_ok=True)
    score_path.write_text(
        json.dumps(score, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"official score: {score['passed']}/{score['total']} -> {score_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
