#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bugfix_benchmark.swebench import official_cases, read_instance_ids, select_records, write_jsonl


CASE_FIELDS = (
    "instance_id", "repo", "base_commit", "problem_statement", "FAIL_TO_PASS", "PASS_TO_PASS"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download selected cases from the official SWE-bench dataset."
    )
    parser.add_argument("--dataset", default="SWE-bench/SWE-bench_Lite")
    parser.add_argument("--split", default="test")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--all", action="store_true", help="download the complete official split")
    selection.add_argument(
        "--instances-file",
        type=Path,
        help="download only IDs in this file (defaults to sample-10.txt)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".benchmark/datasets/swe-bench-lite.jsonl"),
    )
    parser.add_argument("--ids-output", type=Path, help="write selected instance IDs for grading")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        from datasets import load_dataset
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "The datasets package is required. Install it with: "
            "python3 -m pip install 'datasets>=2.14'"
        ) from exc

    dataset = load_dataset(args.dataset, split=args.split)
    records = [dict(item) for item in dataset]
    if not args.all:
        instance_ids = read_instance_ids(
            args.instances_file or Path("datasets/swe-bench-lite/sample-10.txt")
        )
        records = select_records(records, instance_ids)
    cases = official_cases(records)
    public_records = [
        {field: record[field] for field in CASE_FIELDS if field in record}
        for record in records
    ]
    write_jsonl(public_records, args.output)
    if args.ids_output:
        args.ids_output.parent.mkdir(parents=True, exist_ok=True)
        args.ids_output.write_text(
            "".join(f"{case.case_id}\n" for case in cases), encoding="utf-8"
        )
    print(f"wrote {len(cases)} official cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
