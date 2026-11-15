"""Auditable surface screening of the official SWE-bench Lite test split."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Set, Tuple


REPRODUCTION = re.compile(r"reproduc|steps to|example|actual|expected", re.IGNORECASE)
SYMPTOM = re.compile(r"bug|error|fail|incorrect|wrong|crash", re.IGNORECASE)
REQUEST_TITLE = re.compile(
    r"^(?:Add|Allow|Please|Improve|Support|Feature|Expose|Make|Return|Update|Refactor)\b",
    re.IGNORECASE,
)


def build_inventory(
    records: Iterable[Dict[str, Any]], reviewed_ids: Set[str], held_ids: Set[str],
    case_reviews: Dict[str, Dict[str, Any]] | None = None,
    reviewed_annotations: Dict[str, Dict[str, Any]] | None = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Keep all cases visible; screen a runnable pool without claiming semantic review."""
    inventory: List[Dict[str, Any]] = []
    selected: List[str] = []
    seen = set()
    case_reviews = case_reviews or {}
    reviewed_annotations = reviewed_annotations or {}
    for record in records:
        case_id = str(record.get("instance_id") or "").strip()
        repo = str(record.get("repo") or "").strip()
        commit = str(record.get("base_commit") or "").strip()
        statement = str(record.get("problem_statement") or "").strip()
        if not all((case_id, repo, commit, statement)):
            raise ValueError("official record lacks instance_id, repo, base_commit, or issue")
        if case_id in seen:
            raise ValueError(f"duplicate official instance_id: {case_id}")
        seen.add(case_id)
        failing = record.get("FAIL_TO_PASS")
        passing = record.get("PASS_TO_PASS")
        if not isinstance(failing, list) or not isinstance(passing, list):
            raise ValueError(f"{case_id}: official test evidence must be lists")

        title = statement.splitlines()[0].strip()
        review = case_reviews.get(case_id)
        prior = reviewed_annotations.get(case_id)
        if review is not None:
            required = (
                "repository_context", "repair_obstacle", "issue_information",
                "capability_hypothesis", "inference_limit", "target_test", "test_alignment",
            )
            if review.get("instance_id") != case_id or review.get("decision") not in ("include", "hold"):
                raise ValueError(f"{case_id}: invalid case review identity or decision")
            if any(not isinstance(review.get(field), str) or not review[field].strip() for field in required):
                raise ValueError(f"{case_id}: incomplete case review")
            if review["target_test"] not in failing:
                raise ValueError(f"{case_id}: target_test absent from official FAIL_TO_PASS")
            if review["decision"] == "include" and not passing:
                raise ValueError(f"{case_id}: reviewed inclusion requires regression tests")
        has_reproduction = bool(REPRODUCTION.search(statement))
        has_symptom = bool(SYMPTOM.search(statement))
        request_wording = bool(REQUEST_TITLE.search(title))
        if review is not None and review["decision"] == "hold":
            reason = "manual_test_alignment_hold"
        elif review is not None and review["decision"] == "include":
            reason = "manual_case_review"
        elif case_id in held_ids:
            reason = "manual_test_alignment_hold"
        elif not failing:
            reason = "missing_target_tests"
        elif not passing:
            reason = "missing_regression_tests"
        elif case_id in reviewed_ids:
            reason = "manual_paper_screen"
        elif request_wording:
            reason = "feature_request_wording"
        elif not has_reproduction:
            reason = "missing_reproduction_signal"
        elif not has_symptom:
            reason = "missing_symptom_signal"
        else:
            reason = "surface_evidence"
        included = reason in ("manual_case_review", "manual_paper_screen", "surface_evidence")
        if included:
            selected.append(case_id)
        inventory.append({
            "instance_id": case_id,
            "dataset": "SWE-bench/SWE-bench_Lite",
            "split": "test",
            "repo": repo,
            "base_commit": commit,
            "title": title,
            "repository_context": (review or prior or {}).get("repository_context", repo),
            "repair_obstacle": (review or prior or {}).get("repair_obstacle"),
            "issue_information": (review or prior or {}).get("issue_information") if review or prior else {
                "reproduction_signal": has_reproduction,
                "symptom_signal": has_symptom,
                "request_wording": request_wording,
            },
            "verification_evidence": {
                "fail_to_pass_count": len(failing),
                "pass_to_pass_count": len(passing),
            },
            "screening_reason": reason,
            "selected": included,
            "review_status": (
                "case_reviewed" if reason == "manual_case_review"
                else "review_hold" if review is not None and review["decision"] == "hold"
                else "paper_screened" if reason == "manual_paper_screen"
                else "needs_case_review" if included else "not_selected"
            ),
            "review": ({
                "target_test": review["target_test"],
                "test_alignment": review["test_alignment"],
                "capability_hypothesis": review["capability_hypothesis"],
                "inference_limit": review["inference_limit"],
            } if review else {
                "capability_hypothesis": prior["capability_hypothesis"],
                "inference_limit": prior["inference_limit"],
            } if prior else None),
        })
    missing_reviewed = reviewed_ids - seen
    if missing_reviewed:
        raise ValueError(f"reviewed IDs absent from official split: {sorted(missing_reviewed)}")
    missing_case_reviews = set(case_reviews) - seen
    if missing_case_reviews:
        raise ValueError(f"case reviews absent from official split: {sorted(missing_case_reviews)}")
    return inventory, selected
