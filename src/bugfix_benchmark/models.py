from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Tuple


def _commands(record: Dict[str, Any], lower: str, upper: str) -> Tuple[str, ...]:
    value = record.get(lower)
    if value is None:
        value = record.get(upper, ())
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{lower} must be a list of runnable commands")
    return tuple(str(item).strip() for item in value if str(item).strip())


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    repository: str
    base_commit: str
    problem_statement: str
    fail_to_pass: Tuple[str, ...]
    pass_to_pass: Tuple[str, ...] = ()
    source_url: str = ""
    source_path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> "BenchmarkCase":
        case_id = str(record.get("case_id") or record.get("instance_id") or "").strip()
        repository = str(record.get("repository") or record.get("repo") or "").strip()
        base_commit = str(record.get("base_commit") or "").strip()
        problem_statement = str(record.get("problem_statement") or record.get("issue") or "").strip()
        source_path = str(record.get("source_path") or "").strip()
        source_url = str(record.get("source_url") or record.get("clone_url") or "").strip()
        if not source_url and repository and not source_path and "/" in repository:
            source_url = f"https://github.com/{repository.removesuffix('.git')}.git"
        fail_to_pass = _commands(record, "fail_to_pass", "FAIL_TO_PASS")
        pass_to_pass = _commands(record, "pass_to_pass", "PASS_TO_PASS")
        if not case_id:
            raise ValueError("case_id or instance_id is required")
        if not repository:
            raise ValueError(f"{case_id}: repository is required")
        if not base_commit:
            raise ValueError(f"{case_id}: base_commit is required")
        if not problem_statement:
            raise ValueError(f"{case_id}: problem_statement is required")
        if not source_url and not source_path:
            raise ValueError(f"{case_id}: source_url or source_path is required")
        if not fail_to_pass:
            raise ValueError(f"{case_id}: fail_to_pass must contain at least one runnable command")
        known = {
            "case_id", "instance_id", "repository", "repo", "base_commit",
            "problem_statement", "issue", "source_path", "source_url",
            "clone_url", "fail_to_pass", "FAIL_TO_PASS", "pass_to_pass",
            "PASS_TO_PASS",
        }
        return cls(
            case_id=case_id,
            repository=repository,
            base_commit=base_commit,
            problem_statement=problem_statement,
            fail_to_pass=fail_to_pass,
            pass_to_pass=pass_to_pass,
            source_url=source_url,
            source_path=source_path,
            metadata={key: value for key, value in record.items() if key not in known},
        )

@dataclass(frozen=True)
class AgentArtifact:
    patch: str
    adapter: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseResult:
    case_id: str
    status: str
    fail_to_pass: str = "not_run"
    pass_to_pass: str = "not_run"
    failure_reason: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def as_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["passed"] = self.passed
        return result
