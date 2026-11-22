from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "configs/swe-bench-lite.json"


def read_config(parser: argparse.ArgumentParser, path: Path | None) -> dict[str, Any]:
    """Overlay a user configuration on the repository defaults."""
    path = path or DEFAULT_CONFIG
    try:
        defaults = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        settings = json.loads(path.read_text(encoding="utf-8")) if path != DEFAULT_CONFIG else defaults
        if not isinstance(settings, dict):
            raise ValueError("expected a JSON object")
        config = defaults.copy()
        for name, values in settings.items():
            if name not in defaults or type(values) is not type(defaults[name]):
                raise ValueError(f"invalid setting: {name}")
            if not isinstance(values, dict):
                config[name] = values
                continue
            for key, value in values.items():
                if key not in defaults[name] or type(value) is not type(defaults[name][key]):
                    raise ValueError(f"invalid setting: {name}.{key}")
            config[name] = {**defaults[name], **values}
        for target, source in config["agent"]["env_map"].items():
            if not target.isidentifier() or not isinstance(source, str) or not source.isidentifier():
                raise ValueError("agent.env_map must map environment variable names to names")
    except (OSError, ValueError) as exc:
        parser.error(f"invalid benchmark config {path}: {exc}")
    return config
