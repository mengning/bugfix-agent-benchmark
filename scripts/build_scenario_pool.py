#!/usr/bin/env python3
"""Build a scenario-oriented research pool without storing gold patches.

The external seeds are human-selected; this script verifies their upstream IDs
and target-test metadata. It does not certify test alignment or replay cases.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
LIVE_DATASET = "SWE-bench-Live/MultiLang"
MULTI_DATASET = "ByteDance-Seed/Multi-SWE-bench"
SCHEMA_VERSION = "scenario-pool-v1"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def fetch_json(url: str) -> dict:
    return json.loads(fetch_bytes(url))


def fetch_jsonl(url: str) -> list[dict]:
    return [json.loads(line) for line in fetch_bytes(url).splitlines() if line.strip()]


def fetch_bytes(url: str) -> bytes:
    result = subprocess.run(
        ["curl", "--fail", "--location", "--silent", "--show-error", "--retry", "6",
         "--retry-all-errors", "--retry-delay", "2", "--max-time", "60", url],
        check=True, capture_output=True,
    )
    return result.stdout


def changed_files(patch: str | None) -> int | None:
    if patch is None:
        return None
    return len(set(re.findall(r"^diff --git a/(.+?) b/", patch, re.MULTILINE)))


def span_label(files: int | None, issue_chars: int | None) -> str:
    if files is None:
        return "unknown"
    if files >= 4 and (issue_chars or 0) >= 500:
        return "long_task_proxy"
    if files >= 2:
        return "multi_file_proxy"
    return "single_file_reference"


def lite_family(obstacle: str) -> str:
    """Broad, explicitly provisional grouping of earlier paper-review labels."""
    label = obstacle.lower()
    if any(word in label for word in ("security", "password", "sensitive")):
        return "security_contract"
    if any(word in label for word in ("compatibility", "version", "platform", "deprecated", "stdlib", "signature")):
        return "compatibility"
    if any(word in label for word in ("state", "cache", "lifecycle", "transition", "propagation", "lazy", "refit")):
        return "state_propagation"
    if any(word in label for word in ("validation", "constraint", "exception", "error", "unsupported")):
        return "validation"
    if any(word in label for word in ("empty", "missing", "none", "numeric", "subtype", "boundary", "collision")):
        return "boundary"
    if any(word in label for word in ("serialization", "roundtrip", "dtype", "query", "format", "text", "dimension", "key", "prefix")):
        return "data_semantics"
    return "integration_semantics"


def lite_context(repo: str) -> str:
    name = repo.split("/")[-1]
    if name in {"django", "flask"}:
        return "web_framework"
    if name in {"pytest", "pylint", "sphinx", "sympy"}:
        return "developer_tool"
    if name in {"astropy", "matplotlib", "seaborn", "xarray", "scikit-learn"}:
        return "scientific_library"
    return "library"


def lite_rows(inventory: list[dict], official: dict[str, dict]) -> list[dict]:
    rows = []
    for item in inventory:
        if not item.get("selected"):
            continue
        source = official.get(item["instance_id"], {})
        files = changed_files(source.get("patch"))
        statement = source.get("problem_statement", "")
        rows.append({
            "schema_version": SCHEMA_VERSION,
            "source": "SWE-bench/SWE-bench_Lite",
            "case_id": item["instance_id"],
            "repository": item["repo"],
            "base_commit": item["base_commit"],
            "title": item["title"],
            "mechanism_family": lite_family(item["repair_obstacle"]),
            "defect_mechanism": item["repair_obstacle"],
            "operational_context": lite_context(item["repo"]),
            "reference_changed_files": files,
            "task_span": span_label(files, len(statement) if statement else None),
            "target_test_count": item["verification_evidence"]["fail_to_pass_count"],
            "selection_purpose": item.get("review", {}).get("capability_hypothesis", item["repair_obstacle"]),
            "review_stage": "paper_reviewed_not_replayed",
            "classification_basis": "existing_case_review_plus_provisional_family_rule",
            "problem_input_status": "official_issue_record",
            "evidence_url": f"https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite",
        })
    return rows


def external_rows(seeds: list[dict]) -> list[dict]:
    cache: dict[str, dict[str, dict]] = {}
    rows = []
    for seed in seeds:
        locator = seed["locator"]
        if locator not in cache:
            kind, key = locator.split(":", 1)
            if kind == "live":
                url = ("https://datasets-server.huggingface.co/rows?dataset="
                       "SWE-bench-Live%2FMultiLang&config=default&split="
                       f"{key}&offset=0&length=30")
                result = fetch_json(url)
                records = [entry["row"] for entry in result["rows"]]
            elif kind == "multi":
                url = f"https://huggingface.co/datasets/{MULTI_DATASET}/resolve/main/{key}"
                records = fetch_jsonl(url)
            elif kind == "pro":
                url = ("https://datasets-server.huggingface.co/rows?dataset="
                       "ScaleAI%2FSWE-bench_Pro&config=default&split=test&offset="
                       f"{key}&length=20")
                result = fetch_json(url)
                records = [entry["row"] for entry in result["rows"]]
            else:
                raise ValueError(f"unknown source locator: {locator}")
            cache[locator] = {record["instance_id"]: record for record in records if record.get("instance_id")}
        record = cache[locator].get(seed["case_id"])
        if record is None:
            raise ValueError(f"upstream case missing: {locator} {seed['case_id']}")
        kind = locator.split(":", 1)[0]
        if kind == "live":
            tests = record.get("FAIL_TO_PASS") or []
            title = record["problem_statement"].splitlines()[0].strip()
            patch = record.get("patch")
            base = record.get("base_commit")
            issue_chars = len(record["problem_statement"])
            evidence_url = f"https://huggingface.co/datasets/{LIVE_DATASET}"
            input_status = "official_problem_statement_not_audited"
            source = LIVE_DATASET
        elif kind == "pro":
            raw_tests = record.get("fail_to_pass") or "[]"
            tests = json.loads(raw_tests) if isinstance(raw_tests, str) else raw_tests
            title = next((line.strip(" #*\t") for line in record["problem_statement"].splitlines()
                          if len(line.strip(" #*\t")) >= 12), "")
            patch = record.get("patch")
            base = record.get("base_commit")
            issue_chars = len(record["problem_statement"])
            evidence_url = "https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro"
            input_status = "curated_statement_original_issue_link_pending"
            source = "ScaleAI/SWE-bench_Pro"
        else:
            tests = [name for name, result in (record.get("f2p_tests") or {}).items()
                     if result.get("test") == "FAIL" and result.get("fix") == "PASS"]
            # Multi-SWE-bench's title is often the *repair PR* title, not the
            # original Issue. Withhold it until an independent Issue is linked.
            title = None
            patch = record.get("fix_patch")
            base_record = record.get("base")
            base = base_record.get("sha") if isinstance(base_record, dict) else base_record
            issue_chars = len(record.get("body") or "")
            evidence_url = f"https://huggingface.co/datasets/{MULTI_DATASET}/blob/main/{locator.split(':', 1)[1]}"
            input_status = "linked_prefixed_issue_required_pr_body_not_accepted"
            source = MULTI_DATASET
        if not tests:
            raise ValueError(f"no upstream fail-to-pass target: {seed['case_id']}")
        files = changed_files(patch)
        rows.append({
            "schema_version": SCHEMA_VERSION,
            "source": source,
            "case_id": seed["case_id"],
            "repository": (f"{record.get('org')}/{record.get('repo')}" if kind == "multi"
                           else record.get("repo")),
            "base_commit": base,
            "title": title,
            "mechanism_family": seed["mechanism"],
            "defect_mechanism": seed["mechanism"],
            "operational_context": seed["context"],
            "reference_changed_files": files,
            "task_span": span_label(files, issue_chars),
            "target_test_count": len(tests),
            "selection_purpose": seed["selection_purpose"],
            "review_stage": "metadata_screened_not_replayed",
            "classification_basis": "title_plus_upstream_target_metadata_needs_case_review",
            "problem_input_status": input_status,
            "target_alignment_warning": (
                "broad_target_set_requires_test_audit" if len(tests) > 100 else None
            ),
            "evidence_url": evidence_url,
        })
    return rows


PRIOR_FAMILIES = {
    "astropy__astropy-12907": ("data_semantics", "scientific_library"),
    "django__django-12700": ("security_contract", "web_framework"),
    "Lang-1": ("boundary", "library"),
    "black-1": ("recovery", "developer_tool"),
    "Bower-1": ("integration_semantics", "developer_tool"),
    "cpp_peglib-1": ("memory_safety", "library"),
    "rayon-rs__rayon-986": ("state_transition", "library"),
    "grpc__grpc-go-3361": ("recovery", "service"),
    "vuejs__core-11761": ("state_propagation", "frontend"),
    "tornado-1": ("compatibility", "web_framework"),
    "fmtlib__fmt-4490": ("compatibility", "library"),
    "KhronosGroup__glslang-4006": ("data_semantics", "compiler"),
    "apple__pkl-1165": ("data_semantics", "library"),
    "wiremock__wiremock-3130": ("configuration", "service"),
    "libsdl-org__SDL-11761": ("compatibility", "toolchain"),
    "etcd-10492": ("concurrency", "service"),
    "etcd-4876": ("concurrency", "service"),
}


def add_prior(rows: list[dict], prior: list[dict]) -> None:
    by_id = {row["case_id"]: row for row in rows}
    for item in prior:
        case_id = item["case_id"]
        family, context = PRIOR_FAMILIES[case_id]
        if case_id in by_id:
            row = by_id[case_id]
            row["prior_case_review_status"] = item["status"]
            row["prior_oracle_evidence"] = item["oracle_evidence"]
            if item["status"] == "hold":
                row["review_stage"] = "hold_input_or_oracle"
            continue
        row = {
            "schema_version": SCHEMA_VERSION,
            "source": (MULTI_DATASET if item["source"] == "Multi-SWE-bench" else item["source"]),
            "case_id": case_id,
            "repository": item["repository"],
            "base_commit": None,
            "title": item["selection_purpose"],
            "mechanism_family": family,
            "defect_mechanism": family,
            "operational_context": context,
            "reference_changed_files": None,
            "task_span": "unknown",
            "target_test_count": None,
            "selection_purpose": item["selection_purpose"],
            "review_stage": "hold_input_or_oracle" if item["status"] == "hold" else "case_reviewed_not_replayed",
            "classification_basis": "prior_case_review",
            "problem_input_status": "requires_source_specific_audit",
            "evidence_url": item["evidence_urls"][0],
            "prior_oracle_evidence": item["oracle_evidence"],
        }
        rows.append(row)
        by_id[case_id] = row


def load_seeds(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def build(inventory: list[dict], official: dict[str, dict], seeds: list[dict], prior: list[dict]) -> list[dict]:
    rows = lite_rows(inventory, official) + external_rows(seeds)
    add_prior(rows, prior)
    ids = [row["case_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case IDs after source merge")
    return sorted(rows, key=lambda row: (row["mechanism_family"], row["source"], row["case_id"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-lite", type=Path, default=ROOT / ".benchmark/datasets/swe-bench-lite-all.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "datasets/cross-source/scenario-pool-v1.jsonl")
    args = parser.parse_args()
    official = {row["instance_id"]: row for row in read_jsonl(args.official_lite)} if args.official_lite.exists() else {}
    rows = build(
        read_jsonl(ROOT / "datasets/swe-bench-lite/case-inventory-v2.jsonl"),
        official,
        load_seeds(ROOT / "datasets/cross-source/scenario-seeds-v1.tsv"),
        read_jsonl(ROOT / "datasets/cross-source/case-candidates.jsonl"),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(f"scenario_pool={len(rows)} paper_reviewed={sum(row['review_stage'] == 'paper_reviewed_not_replayed' for row in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
