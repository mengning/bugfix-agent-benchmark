from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    repository: str
    base_commit: str
    problem_statement: str
    fail_to_pass: Tuple[str, ...] = ()
    pass_to_pass: Tuple[str, ...] = ()
    protected_paths: Tuple[str, ...] = ()
    source_url: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def evaluation_payload(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "repository": self.repository,
            "source_url": self.source_url,
            "source_path": "",
            "base_commit": self.base_commit,
            "problem_statement": self.problem_statement,
            "fail_to_pass": list(self.fail_to_pass),
            "pass_to_pass": list(self.pass_to_pass),
            "protected_paths": list(self.protected_paths),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class AgentArtifact:
    patch: str
    adapter: str
    metadata: Dict[str, Any] = field(default_factory=dict)
