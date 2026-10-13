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
    if case.source_path:
        source = Path(case.source_path)
        if not source.is_absolute():
            source = repository_root / source
        if not source.is_dir():
            raise WorkspaceError(f"local source_path does not exist: {source}")
        shutil.copytree(source, destination, ignore=_ignore_generated)
        _run(["git", "init", "--quiet"], destination, "cannot initialize local fixture workspace")
        _run(["git", "add", "--all"], destination, "cannot stage local fixture baseline")
        return destination
    if not case.source_url:
        raise WorkspaceError(f"{case.case_id}: source_url or source_path is required")
    _run(
        ["git", "clone", "--quiet", "--no-checkout", case.source_url, str(destination)],
        repository_root,
        f"cannot clone {case.source_url}",
    )
    _run(
        ["git", "checkout", "--quiet", "--detach", case.base_commit],
        destination,
        f"cannot checkout base_commit {case.base_commit}",
    )
    return destination


def _ignore_generated(_directory: str, names: list[str]) -> set[str]:
    ignored = {".git", "__pycache__", ".pytest_cache", ".venv"}
    return {name for name in names if name in ignored or name.endswith(".pyc")}


def _run(command: list[str], cwd: Path, message: str) -> None:
    completed = subprocess.run(
        command, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if completed.returncode != 0:
        detail = completed.stdout.strip()
        raise WorkspaceError(f"{message}: {detail}" if detail else message)
