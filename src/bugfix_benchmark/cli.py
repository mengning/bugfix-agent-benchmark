from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import List, Optional

from .adapters import PatchDirectoryAdapter
from .runner import BenchmarkRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bugfix-benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="run and independently score benchmark cases")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--repository-root", type=Path, default=Path.cwd())
    run.add_argument("--results-dir", type=Path, default=Path("results"))
    run.add_argument("--run-id")
    run.add_argument("--case", action="append", default=[], dest="cases")
    run.add_argument("--max-cases", type=int)
    run.add_argument("--command-timeout", type=float, default=600.0)
    run.add_argument("--adapter", choices=("patch-dir",), required=True)
    run.add_argument("--patch-dir", type=Path)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.patch_dir is None:
        parser.error("--patch-dir is required for adapter=patch-dir")
    adapter = PatchDirectoryAdapter(args.patch_dir)
    score = BenchmarkRunner(args.repository_root).run(
        args.manifest,
        adapter,
        args.results_dir,
        run_id=args.run_id,
        case_ids=args.cases,
        max_cases=args.max_cases,
        command_timeout=args.command_timeout,
    )
    print(
        f"run={score['run_id']} passed={score['passed']}/{score['total']} "
        f"pass_rate={score['pass_rate']:.1%}"
    )
    for case in score["cases"]:
        print(f"{case['case_id']}: {case['status']}")
    return 0 if score["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
