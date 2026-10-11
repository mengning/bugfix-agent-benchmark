from __future__ import annotations

from pathlib import Path

from .models import AgentArtifact, BenchmarkCase


class PatchDirectoryAdapter:
    name = "patch-dir"

    def __init__(self, patch_directory: Path) -> None:
        self.patch_directory = patch_directory

    def run(self, case: BenchmarkCase) -> AgentArtifact:
        path = self.patch_directory / f"{case.case_id}.patch"
        patch = path.read_text(encoding="utf-8") if path.is_file() else ""
        return AgentArtifact(patch=patch, adapter=self.name, metadata={"patch_path": str(path)})
