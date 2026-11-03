#!/usr/bin/env python3
"""Validate the curated selection and summarize an official SWE-bench score."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bugfix_benchmark.diagnostic import breakdown_score, load_selection, validate_upstream


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--selection", type=Path,
        default=Path("datasets/swe-bench-lite/diagnostic-v1.jsonl"),
    )
    parser.add_argument(
        "--instances-file", type=Path,
        default=Path("datasets/swe-bench-lite/diagnostic-v1.txt"),
    )
    parser.add_argument("--dataset-file", type=Path, required=True)
    parser.add_argument("--score-file", type=Path, help="score.json from the official SWE-bench harness")
    args = parser.parse_args()

    cases = load_selection(args.selection, args.instances_file)
    records = [
        json.loads(line)
        for line in args.dataset_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    validate_upstream(cases, records)
    if args.score_file:
        score = json.loads(args.score_file.read_text(encoding="utf-8"))
        result = breakdown_score(cases, score)
        result["scorer"] = "official_swebench_harness"
    else:
        result = {"status": "selection_validated", "total": len(cases), "score": None}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
