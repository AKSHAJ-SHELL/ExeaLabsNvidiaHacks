"""Apple RoomPlan CapturedRoom JSON (subset, ARKit Y-up) -> ScanBundle (Z-up)."""

from __future__ import annotations

import json
import math
from pathlib import Path

from arrival.scan.bundle import validate


def _center(m: list[float]) -> list[float]:
    return [float(m[12]), float(-m[14]), float(m[13])]


def _yaw(m: list[float]) -> float:
    # Local +X axis is the first column (indexes 0, 1, 2). Map Y-up -> Z-up the same way as positions.
    ax, ay = m[0], -m[2]
    yaw = math.atan2(ay, ax)
    return 0.0 if abs(yaw) < 1e-12 else yaw


def _size(dim: list[float]) -> list[float]:
    return [float(dim[0]), float(dim[2]), float(dim[1])]


def _wall(w: dict) -> dict:
    m, dim = w["transform"], w["dimensions"]
    cx, cy, _ = _center(m)
    yaw = _yaw(m)
    sx, sy, _ = _size(dim)
    # Long horizontal edge, rotated by yaw.
    if sx >= sy:
        half, ux, uy = sx / 2, math.cos(yaw), math.sin(yaw)
    else:
        half, ux, uy = sy / 2, -math.sin(yaw), math.cos(yaw)
    return {
        "id": w.get("identifier", "wall"),
        "start": [cx - ux * half, cy - uy * half],
        "end": [cx + ux * half, cy + uy * half],
        "height": float(dim[1]),
        "thickness": float(min(dim[0], dim[2])),
    }


def _object(o: dict, i: int) -> dict:
    m = o["transform"]
    return {
        "id": o.get("identifier", f"object_{i}"),
        "category": o.get("category", "unknown"),
        "size": _size(o["dimensions"]),
        "position": _center(m),
        "yaw": _yaw(m),
    }


def to_bundle(roomplan: dict, room_id: str) -> dict:
    """Normalize a CapturedRoom dict. RoomPlan objects become fixtures; counters are not invented here."""
    bundle = {
        "schema_version": "1",
        "room_id": room_id,
        "units": "meters",
        "frame": "z_up",
        "geometry_source": "roomplan",
        "blocks_claims": [],
        "walls": [_wall(w) for w in roomplan.get("walls", [])],
        "fixtures": [_object(o, i) for i, o in enumerate(roomplan.get("objects", []))],
        "objects": [],
    }
    return validate(bundle)


def load(path: str | Path, room_id: str) -> dict:
    with open(path) as f:
        return to_bundle(json.load(f), room_id)
