from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, Optional, Sequence
import uuid

from .catalog import load_cases
from .models import CaseResult
from .verifier import verify_case


class BenchmarkRunner:
    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve()

    def run(
        self,
        manifest: Path,
        adapter: Any,
        results_root: Path,
        *,
        run_id: Optional[str] = None,
        case_ids: Sequence[str] = (),
        max_cases: Optional[int] = None,
        command_timeout: float = 600.0,
    ) -> Dict[str, Any]:
        cases = load_cases(manifest)
        if case_ids:
            selected = set(case_ids)
            cases = [case for case in cases if case.case_id in selected]
            missing = selected.difference(case.case_id for case in cases)
            if missing:
                raise ValueError(f"unknown case_id(s): {', '.join(sorted(missing))}")
        if max_cases is not None:
            if max_cases <= 0:
                raise ValueError("max_cases must be positive")
            cases = cases[:max_cases]
        if not cases:
            raise ValueError("no benchmark cases selected")

        actual_run_id = run_id or _new_run_id()
        run_dir = results_root / actual_run_id
        patches_dir = run_dir / "patches"
        cases_dir = run_dir / "cases"
        patches_dir.mkdir(parents=True, exist_ok=False)
        cases_dir.mkdir(parents=True, exist_ok=True)
        results = []
        for case in cases:
            case_name = _safe_name(case.case_id)
            case_dir = cases_dir / case_name
            case_dir.mkdir(parents=True, exist_ok=True)
            try:
                artifact = adapter.run(case)
                (patches_dir / f"{case_name}.patch").write_text(artifact.patch, encoding="utf-8")
                result = verify_case(
                    case,
                    artifact,
                    case_dir,
                    repository_root=self.repository_root,
                    command_timeout=command_timeout,
                )
                result.evidence["adapter"] = artifact.adapter
            except Exception as exc:  # adapter and transport failures are case results
                result = CaseResult(
                    case_id=case.case_id,
                    status="agent_failed",
                    failure_reason=str(exc),
                )
                (patches_dir / f"{case_name}.patch").write_text("", encoding="utf-8")
            value = result.as_dict()
            results.append(value)
            (case_dir / "result.json").write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

        passed = sum(1 for result in results if result["passed"])
        score: Dict[str, Any] = {
            "run_id": actual_run_id,
            "manifest": str(manifest),
            "adapter": getattr(adapter, "name", adapter.__class__.__name__),
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "pass_rate": passed / len(results),
            "cases": results,
        }
        (run_dir / "score.json").write_text(
            json.dumps(score, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return score


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{stamp}-{uuid.uuid4().hex[:8]}"


def _safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    if not name:
        raise ValueError(f"case_id has no safe filename representation: {value!r}")
    return name
