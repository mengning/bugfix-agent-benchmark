from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{stamp}-{uuid.uuid4().hex[:8]}"


def _safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    if not name:
        raise ValueError(f"case_id has no safe filename representation: {value!r}")
    return name
