from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Dict, Iterable, List

from .models import AgentArtifact, BenchmarkCase, CaseResult
from .workspace import WorkspaceError, prepare_workspace


@dataclass(frozen=True)
class CommandResult:
    command: str
    exit_code: int
    log_path: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    def as_dict(self) -> Dict[str, object]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "log_path": self.log_path,
        }


def verify_case(
    case: BenchmarkCase,
    artifact: AgentArtifact,
    run_dir: Path,
    *,
    repository_root: Path,
    command_timeout: float = 600.0,
) -> CaseResult:
    if not artifact.patch.strip():
        return CaseResult(case_id=case.case_id, status="no_patch", failure_reason="Agent returned no patch")
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    workspace = run_dir / "workspace"
    patch_path = run_dir / "agent.patch"
    patch_path.write_text(artifact.patch, encoding="utf-8")
    try:
        prepare_workspace(case, workspace, repository_root)
    except WorkspaceError as exc:
        return CaseResult(case_id=case.case_id, status="workspace_failed", failure_reason=str(exc))

    baseline = _run_commands(
        case.fail_to_pass, workspace, logs_dir, "baseline-fail-to-pass", command_timeout
    )
    baseline_pass = _run_commands(
        case.pass_to_pass, workspace, logs_dir, "baseline-pass-to-pass", command_timeout
    )
    if any(result.passed for result in baseline):
        return CaseResult(
            case_id=case.case_id,
            status="baseline_invalid",
            fail_to_pass="already_passing",
            failure_reason="at least one FAIL_TO_PASS command already passed on the base workspace",
            evidence=_evidence(patch_path, baseline=baseline, baseline_pass=baseline_pass),
        )
    if not all(result.passed for result in baseline_pass):
        return CaseResult(
            case_id=case.case_id,
            status="baseline_invalid",
            pass_to_pass="already_failing",
            failure_reason="at least one PASS_TO_PASS command failed on the base workspace",
            evidence=_evidence(patch_path, baseline=baseline, baseline_pass=baseline_pass),
        )

    rejected_path = _rejected_patch_path(artifact.patch, workspace, case.protected_paths)
    if rejected_path is not None:
        return CaseResult(
            case_id=case.case_id,
            status="patch_rejected",
            failure_reason=f"patch modifies generated or protected path: {rejected_path}",
            evidence=_evidence(patch_path, baseline=baseline, baseline_pass=baseline_pass),
        )

    applied = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(patch_path)],
        cwd=str(workspace),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    apply_log = logs_dir / "patch-apply.log"
    apply_log.write_text(
        f"$ git apply {patch_path.name}\nexit_code={applied.returncode}\n{applied.stdout}",
        encoding="utf-8",
    )
    if applied.returncode != 0:
        return CaseResult(
            case_id=case.case_id,
            status="patch_apply_failed",
            failure_reason=applied.stdout.strip() or "git apply rejected the patch",
            evidence=_evidence(patch_path, baseline=baseline, baseline_pass=baseline_pass, apply_log=apply_log),
        )

    fail_results = _run_commands(
        case.fail_to_pass, workspace, logs_dir, "patched-fail-to-pass", command_timeout
    )
    if not all(result.passed for result in fail_results):
        return CaseResult(
            case_id=case.case_id,
            status="fail_to_pass_failed",
            fail_to_pass="failed",
            failure_reason="one or more FAIL_TO_PASS commands still fail after applying the patch",
            evidence=_evidence(
                patch_path, baseline=baseline, baseline_pass=baseline_pass,
                fail_to_pass=fail_results, apply_log=apply_log
            ),
        )

    pass_results = _run_commands(
        case.pass_to_pass, workspace, logs_dir, "patched-pass-to-pass", command_timeout
    )
    if not all(result.passed for result in pass_results):
        return CaseResult(
            case_id=case.case_id,
            status="pass_to_pass_failed",
            fail_to_pass="passed",
            pass_to_pass="failed",
            failure_reason="one or more PASS_TO_PASS commands regressed after applying the patch",
            evidence=_evidence(
                patch_path,
                baseline=baseline,
                baseline_pass=baseline_pass,
                fail_to_pass=fail_results,
                pass_to_pass=pass_results,
                apply_log=apply_log,
            ),
        )

    return CaseResult(
        case_id=case.case_id,
        status="passed",
        fail_to_pass="passed",
        pass_to_pass="passed" if case.pass_to_pass else "not_applicable",
        evidence=_evidence(
            patch_path,
            baseline=baseline,
            baseline_pass=baseline_pass,
            fail_to_pass=fail_results,
            pass_to_pass=pass_results,
            apply_log=apply_log,
        ),
    )


def _rejected_patch_path(patch: str, workspace: Path, protected_paths: Iterable[str]) -> str | None:
    listed = subprocess.run(
        ["git", "apply", "--numstat", "-z"],
        cwd=str(workspace),
        input=patch.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if listed.returncode != 0:
        return None  # git apply below reports malformed patches as patch_apply_failed
    protected = tuple(path.rstrip("/") for path in protected_paths)
    generated = {".git", ".benchmark", "results", "logs", "__pycache__", ".pytest_cache", ".venv"}
    for record in listed.stdout.split(b"\0"):
        if not record:
            continue
        fields = record.split(b"\t", 2)
        if len(fields) != 3 or not fields[2]:
            return "<unsupported patch path>"
        path = fields[2].decode("utf-8", errors="replace")
        parts = Path(path).parts
        if any(part in generated for part in parts) or path.endswith((".log", ".pyc")):
            return path
        if any(path == item or path.startswith(item + "/") for item in protected):
            return path
    return None


def _run_commands(
    commands: Iterable[str],
    workspace: Path,
    logs_dir: Path,
    prefix: str,
    timeout: float,
) -> List[CommandResult]:
    results = []
    for index, command in enumerate(commands, 1):
        log_path = logs_dir / f"{prefix}-{index}.log"
        try:
            completed = subprocess.run(
                command,
                cwd=str(workspace),
                shell=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
            output = completed.stdout
            exit_code = completed.returncode
        except subprocess.TimeoutExpired as exc:
            output = str(exc.stdout or "") + f"\ncommand timed out after {timeout:g}s\n"
            exit_code = 124
        log_path.write_text(
            f"$ {command}\nexit_code={exit_code}\n{output}", encoding="utf-8"
        )
        results.append(
            CommandResult(
                command=command,
                exit_code=exit_code,
                log_path=str(log_path.relative_to(logs_dir.parent)),
            )
        )
    return results


def _evidence(
    patch_path: Path,
    *,
    baseline: Iterable[CommandResult] = (),
    baseline_pass: Iterable[CommandResult] = (),
    fail_to_pass: Iterable[CommandResult] = (),
    pass_to_pass: Iterable[CommandResult] = (),
    apply_log: Path = None,
) -> Dict[str, object]:
    value: Dict[str, object] = {
        "patch_path": patch_path.name,
        "patch_bytes": patch_path.stat().st_size,
        "baseline_fail_to_pass": [item.as_dict() for item in baseline],
        "baseline_pass_to_pass": [item.as_dict() for item in baseline_pass],
        "fail_to_pass": [item.as_dict() for item in fail_to_pass],
        "pass_to_pass": [item.as_dict() for item in pass_to_pass],
    }
    if apply_log is not None:
        value["patch_apply_log"] = str(apply_log.relative_to(patch_path.parent))
    return value
