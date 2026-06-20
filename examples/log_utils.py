"""Shared JSONL log writer for cadpya examples."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cadpya.engine.root_coordinator import LogEntry


def write_jsonl(log: list[LogEntry], path: str | Path) -> None:
    """Write simulation log entries to a JSONL file.

    Each LogEntry is serialized as one JSON object per line.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for entry in log:
            d = asdict(entry)
            if d.get("merged_into") is None:
                del d["merged_into"]
            f.write(json.dumps(d) + "\n")
    print(f"Wrote {len(log)} entries to {out}")
