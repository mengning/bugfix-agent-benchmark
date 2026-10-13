from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Dict, List, Sequence

from .models import AgentArtifact, BenchmarkCase


class CommandAgentAdapter:
    """Run one Agent command against one prepared case workspace."""

    name = "command"

    def __init__(
        self,
        *,
        command: Sequence[str],
        case_file: Path,
        workspace: Path,
        artifact_file: Path,
        timeout_seconds: float = 900.0,
    ) -> None:
        if not command:
            raise ValueError("Agent command must not be empty")
        self.command = tuple(command)
        self.case_file = case_file
        self.workspace = workspace
        self.artifact_file = artifact_file
        self.timeout_seconds = max(1.0, timeout_seconds)

    def run(self, case: BenchmarkCase) -> AgentArtifact:
        if not self.workspace.is_dir():
            raise RuntimeError(f"Agent workspace does not exist: {self.workspace}")
        self.case_file.parent.mkdir(parents=True, exist_ok=True)
        self.artifact_file.parent.mkdir(parents=True, exist_ok=True)
        self.case_file.write_text(
            json.dumps(case.evaluation_payload(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if self.artifact_file.exists():
            self.artifact_file.unlink()
        env = os.environ.copy()
        env.update(
            {
                "BENCHMARK_CASE_FILE": str(self.case_file),
                "BENCHMARK_WORKSPACE": str(self.workspace),
                "BENCHMARK_ARTIFACT_FILE": str(self.artifact_file),
                "BENCHMARK_CASE_ID": case.case_id,
            }
        )
        try:
            completed = subprocess.run(
                list(self.command),
                cwd=str(self.workspace),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            output = str(exc.stdout or "")
            raise RuntimeError(
                f"Agent command timed out after {self.timeout_seconds:g}s: {output}"
            ) from exc
        if completed.returncode != 0:
            raise RuntimeError(
                f"Agent command exited with code {completed.returncode}: "
                f"{completed.stdout.strip()}"
            )
        if not self.artifact_file.is_file():
            raise RuntimeError(
                f"Agent did not write artifact file: {self.artifact_file}"
            )
        try:
            payload = json.loads(self.artifact_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Agent artifact is not valid JSON: {exc}") from exc
        patch = str(payload.get("patch") or "").strip()
        if not patch:
            patch_path = str(payload.get("patch_path") or "").strip()
            if patch_path:
                patch = Path(patch_path).read_text(encoding="utf-8").strip()
        if not patch:
            raise RuntimeError("Agent artifact must contain a non-empty patch or patch_path")
        return AgentArtifact(
            patch=patch + "\n",
            adapter=self.name,
            metadata={
                "case_file": str(self.case_file),
                "artifact_file": str(self.artifact_file),
                "workspace": str(self.workspace),
                "agent_stdout": completed.stdout[-4000:],
            },
        )


def command_from_string(value: str) -> List[str]:
    import shlex

    command = shlex.split(value)
    if not command:
        raise ValueError("Agent command must not be empty")
    return command
