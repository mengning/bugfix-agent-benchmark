#!/usr/bin/env python3
"""Freeze all official Lite IDs and build an auditable screened case pool."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bugfix_benchmark.selection_inventory import build_inventory
from bugfix_benchmark.swebench import read_instance_ids, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-file", type=Path, required=True)
    parser.add_argument(
        "--reviewed-selection", type=Path,
        default=Path("datasets/swe-bench-lite/diagnostic-v1.jsonl"),
    )
    parser.add_argument(
        "--holds-file", type=Path,
        default=Path("datasets/swe-bench-lite/test-alignment-holds.txt"),
    )
    parser.add_argument(
        "--case-reviews", type=Path,
        default=Path("datasets/swe-bench-lite/case-reviews-v2.jsonl"),
    )
    parser.add_argument(
        "--full-output", type=Path,
        default=Path("datasets/swe-bench-lite/full-300.txt"),
    )
    parser.add_argument(
        "--screened-output", type=Path,
        default=Path("datasets/swe-bench-lite/screened-v2.txt"),
    )
    parser.add_argument(
        "--reviewed-output", type=Path,
        default=Path("datasets/swe-bench-lite/reviewed-v2.txt"),
    )
    parser.add_argument(
        "--inventory-output", type=Path,
        default=Path("datasets/swe-bench-lite/case-inventory-v2.jsonl"),
    )
    args = parser.parse_args()

    records = [
        json.loads(line)
        for line in args.dataset_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    reviewed_annotations = {}
    for line in args.reviewed_selection.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            reviewed_annotations[row["instance_id"]] = row
    reviewed_ids = set(reviewed_annotations)
    held_ids = set(read_instance_ids(args.holds_file)) if args.holds_file.is_file() else set()
    case_reviews = {}
    if args.case_reviews.is_file():
        for number, line in enumerate(args.case_reviews.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            review = json.loads(line)
            case_id = review.get("instance_id")
            if case_id in case_reviews:
                raise ValueError(f"{args.case_reviews}:{number}: duplicate review ID {case_id}")
            case_reviews[case_id] = review
    inventory, selected = build_inventory(
        records, reviewed_ids, held_ids, case_reviews, reviewed_annotations
    )
    for path, ids in (
        (args.full_output, [row["instance_id"] for row in inventory]),
        (args.screened_output, selected),
        (args.reviewed_output, [
            row["instance_id"] for row in inventory
            if row["review_status"] in ("paper_screened", "case_reviewed")
        ]),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{case_id}\n" for case_id in ids), encoding="utf-8")
    write_jsonl(inventory, args.inventory_output)
    print(f"official_full={len(inventory)} screened={len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
