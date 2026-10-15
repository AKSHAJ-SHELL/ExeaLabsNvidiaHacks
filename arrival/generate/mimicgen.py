"""MimicGen probe. Tonight's generator is scripted_retarget; this only checks whether RoboCasa imports.
The real command lives in docs/09-later.md."""

from __future__ import annotations

import importlib.util


def probe() -> dict:
    if importlib.util.find_spec("robocasa") is None:
        return {"available": False, "skipped": True, "reason": "robocasa not installed"}
    return {"available": True, "skipped": True, "reason": "MimicGen wiring not implemented (see docs/09-later.md)"}
