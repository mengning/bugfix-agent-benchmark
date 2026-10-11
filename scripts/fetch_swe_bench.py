#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bugfix_benchmark.swebench import read_instance_ids, select_records, write_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download selected cases from the official SWE-bench dataset."
    )
    parser.add_argument("--dataset", default="SWE-bench/SWE-bench_Lite")
    parser.add_argument("--split", default="test")
    parser.add_argument(
        "--instances-file",
        type=Path,
        default=Path("datasets/swe-bench-lite/sample-10.txt"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".benchmark/datasets/swe-bench-lite.jsonl"),
    )
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

    instance_ids = read_instance_ids(args.instances_file)
    dataset = load_dataset(args.dataset, split=args.split)
    records = select_records((dict(item) for item in dataset), instance_ids)
    write_jsonl(records, args.output)
    print(f"wrote {len(records)} official cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
