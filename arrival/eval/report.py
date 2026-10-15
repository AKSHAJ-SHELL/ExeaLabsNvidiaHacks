"""Speed and cost report. Dollars are unmeasured except the local CPU run ($0)."""

from __future__ import annotations

import json
from pathlib import Path


def build_report(room_id: str, attempts: int, successes: int, seconds: float, families: list[str],
                 generator: str = "scripted_retarget", physically_valid: bool = False) -> dict:
    return {
        "room_id": room_id,
        "generator": generator,
        "physically_valid": physically_valid,
        "attempts": attempts,
        "successes": successes,
        "dropped": attempts - successes,
        "seconds": round(seconds, 3),
        "demos_per_hour": round(successes / seconds * 3600, 1) if seconds > 0 else 0.0,
        "tasks": families,
        "dollars": {
            "local_cpu": {"usd": 0, "measured": True},
            "token_factory": {"usd": None, "measured": False},
            "serverless_jobs": {"usd": None, "measured": False},
            "cosmos": {"usd": None, "measured": False},
            "object_storage": {"usd": None, "measured": False},
            "endpoint": {"usd": None, "measured": False},
        },
        "teleop_baseline": None,
        "usefulness": None,
        "realism": None,
    }


def write_report(report: dict, reports_dir: str | Path) -> Path:
    path = Path(reports_dir) / f"{report['room_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return path
