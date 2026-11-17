#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bugfix_benchmark.swebench import official_cases, read_instance_ids, select_records, write_jsonl


CASE_FIELDS = (
    "instance_id", "repo", "base_commit", "problem_statement"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download selected cases from the official SWE-bench dataset."
    )
    parser.add_argument("--dataset", default="SWE-bench/SWE-bench_Lite")
    parser.add_argument("--split", default="test")
    parser.add_argument("--revision", help="immutable Hugging Face dataset revision")
    parser.add_argument("--source-json", type=Path, help="load a full local dataset snapshot instead of Hugging Face")
    parser.add_argument("--expected-sha256", help="verify the local snapshot's SHA-256 before loading")
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
    parser.add_argument(
        "--scoring-output", type=Path,
        help="write full records for the official scorer; keep this file outside Agent access",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    outputs = [path.resolve() for path in (args.output, args.ids_output, args.scoring_output) if path]
    if len(outputs) != len(set(outputs)):
        raise ValueError("Agent input, instance IDs and scoring output must use different files")
    if args.source_json and args.source_json.resolve() in outputs:
        raise ValueError("dataset snapshot must not be overwritten")
    if args.source_json and args.revision:
        raise ValueError("--source-json and --revision cannot be combined")
    if args.expected_sha256 and not args.source_json:
        raise ValueError("--expected-sha256 requires --source-json")
    if args.scoring_output:
        if args.scoring_output.suffix != ".json":
            raise ValueError("scoring output must be a .json file")
    if args.source_json:
        source = args.source_json.read_bytes()
        if args.expected_sha256 and hashlib.sha256(source).hexdigest().lower() != args.expected_sha256.lower():
            raise ValueError("dataset snapshot SHA-256 does not match")
        records = json.loads(source)
        if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
            raise ValueError("dataset snapshot must be a JSON array of records")
    else:
        try:
            from datasets import load_dataset
        except ModuleNotFoundError as exc:
            raise SystemExit(
                "The datasets package is required. Install it with: "
                "python3 -m pip install 'datasets>=2.14'"
            ) from exc
        options = {"split": args.split}
        if args.revision:
            options["revision"] = args.revision
        dataset = load_dataset(args.dataset, **options)
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
    if args.scoring_output:
        args.scoring_output.parent.mkdir(parents=True, exist_ok=True)
        args.scoring_output.write_text(json.dumps(records, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.ids_output:
        args.ids_output.parent.mkdir(parents=True, exist_ok=True)
        args.ids_output.write_text(
            "".join(f"{case.case_id}\n" for case in cases), encoding="utf-8"
        )
    print(f"wrote {len(cases)} official cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
