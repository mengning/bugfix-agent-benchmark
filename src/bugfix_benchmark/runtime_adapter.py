from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import AgentArtifact, BenchmarkCase


class DevStarRuntimeAdapter:
    """Dispatch a case to the current online DevStar Agent instance."""

    name = "devstar-runtime"

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        workspace: Path,
        timeout_seconds: float = 900.0,
        poll_seconds: float = 2.0,
    ) -> None:
        if not base_url.strip() or not token.strip():
            raise ValueError("DevStar platform URL and instance token are required")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.workspace = workspace.resolve()
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds

    def run(self, case: BenchmarkCase) -> AgentArtifact:
        if not self.workspace.is_dir() or not (self.workspace / ".git").exists():
            raise RuntimeError(f"prepared case workspace is not a Git repository: {self.workspace}")
        payload = case.evaluation_payload()
        # Local fixtures use a symbolic baseline. The runner prepared the exact
        # workspace already; the Agent should not attempt to resolve the marker.
        if case.source_path:
            payload["base_commit"] = ""
        response = self._request("POST", "/-/agent-services/instances/dispatch", {
            "target_self": True,
            "command": "/evaluate-case",
            "metadata": {
                "evaluation": payload,
                "workspace": {"mode": "benchmark_workspace", "path": str(self.workspace)},
            },
        })
        events = response.get("events") if isinstance(response, dict) else None
        if not isinstance(events, list) or len(events) != 1:
            raise RuntimeError("DevStar dispatch did not return exactly one event")
        event_id = int(events[0].get("event_id") or 0)
        if event_id <= 0:
            raise RuntimeError("DevStar dispatch returned an invalid event id")

        deadline = time.monotonic() + self.timeout_seconds
        while True:
            event = self._request("GET", f"/-/agent-services/events/{event_id}/result")
            status = str(event.get("status") or "").lower()
            if status == "success":
                result = event.get("result")
                if isinstance(result, str):
                    result = json.loads(result)
                artifact = result.get("artifact") if isinstance(result, dict) else None
                if not isinstance(artifact, dict):
                    raise RuntimeError("DevStar Agent result has no artifact")
                if str(artifact.get("case_id") or "") != case.case_id:
                    raise RuntimeError("DevStar Agent artifact case_id does not match dispatched case")
                patch = artifact.get("patch")
                if not isinstance(patch, str) or not patch.strip():
                    raise RuntimeError("DevStar Agent returned no patch")
                return AgentArtifact(patch=patch, adapter=self.name, metadata={"event_id": event_id})
            if status == "failed":
                raise RuntimeError(f"DevStar Agent event failed: {event.get('error') or 'unknown error'}")
            if status not in {"queued", "running"}:
                raise RuntimeError(f"unexpected DevStar Agent event status: {status or '<empty>'}")
            if time.monotonic() >= deadline:
                raise RuntimeError(f"DevStar Agent event {event_id} timed out")
            time.sleep(min(self.poll_seconds, max(0, deadline - time.monotonic())))

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"DevStar {method} {path} returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"DevStar {method} {path} failed: {exc.reason}") from exc


def runtime_adapter_from_environment(workspace: Path, *, timeout_seconds: float = 900.0) -> DevStarRuntimeAdapter:
    base_url = os.getenv("DEVSTAR_PLATFORM_URL") or os.getenv("DEVSTAR_BASE_URL") or ""
    token = os.getenv("DEVSTAR_TOKEN") or ""
    return DevStarRuntimeAdapter(
        base_url=base_url, token=token, workspace=workspace, timeout_seconds=timeout_seconds
    )
