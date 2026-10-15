"""Distance oracle. Drops attempts whose object did not reach the target."""

from __future__ import annotations

import math

TOLERANCE = 0.05


def judge(attempt: dict) -> bool:
    frames, target = attempt["frames"], attempt["target"]
    obj = frames[-1]["object_position"]
    dist = math.dist(obj, target)  # 3D: the object must be lowered onto the target, not left hovering
    closed = max(f["gripper"] for f in frames) > 0.5
    return dist <= TOLERANCE and closed


def keep(attempts):
    for a in attempts:
        if a["success"]:
            yield a
