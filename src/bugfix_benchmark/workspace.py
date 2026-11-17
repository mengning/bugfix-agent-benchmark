from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from .models import BenchmarkCase


class WorkspaceError(RuntimeError):
    pass


def prepare_workspace(case: BenchmarkCase, destination: Path, repository_root: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not case.source_url:
        raise WorkspaceError(f"{case.case_id}: source_url is required")
    _run(
        ["git", "clone", "--quiet", "--no-checkout", case.source_url, str(destination)],
        repository_root,
        "cannot clone source repository",
    )
    _run(
        ["git", "checkout", "--quiet", "--detach", case.base_commit],
        destination,
        f"cannot checkout base_commit {case.base_commit}",
    )
    return destination


def _run(command: list[str], cwd: Path, message: str) -> None:
    completed = subprocess.run(
        command, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if completed.returncode != 0:
        raise WorkspaceError(f"{message} (exit code {completed.returncode}; output omitted)")
