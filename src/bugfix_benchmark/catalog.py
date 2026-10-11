from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .models import BenchmarkCase


def load_cases(manifest: Path) -> List[BenchmarkCase]:
    if not manifest.is_file():
        raise FileNotFoundError(f"benchmark manifest not found: {manifest}")
    if manifest.suffix.lower() == ".jsonl":
        records = []
        for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{manifest}:{number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{manifest}:{number}: each JSONL line must be an object")
            records.append(value)
    else:
        value = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise ValueError(f"{manifest}: JSON manifest must be an array of objects")
        records = value
    cases = [BenchmarkCase.from_record(record) for record in records]
    seen = set()
    for case in cases:
        if case.case_id in seen:
            raise ValueError(f"duplicate case_id: {case.case_id}")
        seen.add(case.case_id)
    return cases
