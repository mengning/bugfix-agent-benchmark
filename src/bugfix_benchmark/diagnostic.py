"""Selection integrity and score breakdown for the SWE-bench Lite diagnostic set."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Dict, List

from .swebench import read_instance_ids


REQUIRED_TEXT = (
    "instance_id", "repo", "base_commit", "role", "repository_context",
    "repair_obstacle", "issue_information", "capability_hypothesis", "inference_limit",
)
ROLES = {"core", "information_control"}


def load_selection(manifest: Path, ids_file: Path) -> List[Dict[str, Any]]:
    """Load reviewed annotations and require the runner's ID list to match exactly."""
    cases: List[Dict[str, Any]] = []
    seen = set()
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        if not isinstance(case, dict):
            raise ValueError(f"{manifest}:{number}: expected an object")
        case_id = case.get("instance_id")
        if case_id in seen:
            raise ValueError(f"duplicate instance_id: {case_id}")
        seen.add(case_id)
        for field in REQUIRED_TEXT:
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise ValueError(f"{manifest}:{number}: missing {field}")
        if case["role"] not in ROLES:
            raise ValueError(f"{manifest}:{number}: unknown role {case['role']}")
        if not re.fullmatch(r"[0-9a-f]{40}", case["base_commit"]):
            raise ValueError(f"{manifest}:{number}: invalid base_commit")
        evidence = case.get("verification_evidence")
        if not isinstance(evidence, dict) or any(
            not isinstance(evidence.get(field), int) or evidence[field] < 0
            for field in ("fail_to_pass_count", "pass_to_pass_count")
        ):
            raise ValueError(f"{manifest}:{number}: invalid verification_evidence")
        if evidence["fail_to_pass_count"] == 0:
            raise ValueError(f"{manifest}:{number}: no FAIL_TO_PASS tests")
        cases.append(case)
    ids = read_instance_ids(ids_file)
    if tuple(case["instance_id"] for case in cases) != ids:
        raise ValueError("selection IDs do not match the runner instance list")
    return cases


def validate_upstream(cases: List[Dict[str, Any]], records: List[Dict[str, Any]]) -> None:
    """Check the pinned source and visible test evidence against official records."""
    by_id = {record["instance_id"]: record for record in records}
    for case in cases:
        case_id = case["instance_id"]
        if case_id not in by_id:
            raise ValueError(f"missing upstream instance_id: {case_id}")
        record = by_id[case_id]
        for field in ("repo", "base_commit"):
            if case[field] != record.get(field):
                raise ValueError(f"{case_id}: upstream {field} differs")
        if not str(record.get("problem_statement") or "").strip():
            raise ValueError(f"{case_id}: upstream problem_statement is empty")
        for field, count_field in (
            ("FAIL_TO_PASS", "fail_to_pass_count"),
            ("PASS_TO_PASS", "pass_to_pass_count"),
        ):
            if len(record.get(field) or []) != case["verification_evidence"][count_field]:
                raise ValueError(f"{case_id}: upstream {field} count differs")


def breakdown_score(cases: List[Dict[str, Any]], score: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize only official harness results; never treat patches as successes."""
    if score.get("scorer") != "official_swebench_harness":
        raise ValueError("an official SWE-bench harness score is required")
    rows = score.get("cases")
    if not isinstance(rows, list):
        raise ValueError("missing score cases")
    by_id = {row["case_id"]: row for row in rows}
    expected = {case["instance_id"] for case in cases}
    if len(by_id) != len(rows) or set(by_id) != expected:
        raise ValueError("score has missing, duplicate, or extra case IDs")
    result: Dict[str, Any] = {"total": len(cases), "resolved": 0, "by_role": {}, "by_obstacle": {}}
    for case in cases:
        row = by_id[case["instance_id"]]
        resolved = row.get("status") == "resolved"
        if row.get("passed") is not resolved:
            raise ValueError(f"{case['instance_id']}: inconsistent official score row")
        result["resolved"] += int(resolved)
        for group, label in (("by_role", case["role"]), ("by_obstacle", case["repair_obstacle"])):
            bucket = result[group].setdefault(label, {"total": 0, "resolved": 0})
            bucket["total"] += 1
            bucket["resolved"] += int(resolved)
    return result
