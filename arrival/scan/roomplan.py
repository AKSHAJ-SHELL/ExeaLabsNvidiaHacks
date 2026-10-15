"""Apple RoomPlan CapturedRoom JSON (subset, ARKit Y-up) -> ScanBundle (Z-up, floor at z=0, room aligned)."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from arrival.scan.bundle import validate

SNAP_TOL = math.radians(5.0)
MIN_WALL_THICKNESS = 0.1


def _enum(value, default: str = "unknown") -> str:
    """Apple encodes Swift enums as {"case": {}}; older/simplified exports use a plain string."""
    if isinstance(value, dict):
        value = next(iter(value), default)
    return str(value) if value else default


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _center(m: list[float]) -> list[float]:
    return [float(m[12]), float(-m[14]), float(m[13])]


def _yaw(m: list[float]) -> float:
    # Local +X axis is the first column (indexes 0, 1, 2). Map Y-up -> Z-up the same way as positions.
    ax, ay = m[0], -m[2]
    yaw = math.atan2(ay, ax)
    return 0.0 if abs(yaw) < 1e-12 else yaw


def _size(dim: list[float]) -> list[float]:
    return [float(dim[0]), float(dim[2]), float(dim[1])]


def _wall(w: dict, z0: float) -> dict:
    m, dim = w["transform"], w["dimensions"]
    cx, cy, _ = _center(m)
    yaw = _yaw(m)
    sx, sy, _ = _size(dim)
    # Long horizontal edge, rotated by yaw.
    if sx >= sy:
        half, ux, uy = sx / 2, math.cos(yaw), math.sin(yaw)
    else:
        half, ux, uy = sy / 2, -math.sin(yaw), math.cos(yaw)
    thickness = float(min(dim[0], dim[2]))
    return {
        "id": w.get("identifier", "wall"),
        "start": [cx - ux * half, cy - uy * half],
        "end": [cx + ux * half, cy + uy * half],
        "height": float(dim[1]),
        "thickness": thickness if thickness > 0 else MIN_WALL_THICKNESS,
    }


def _object(o: dict, i: int) -> dict:
    m = o["transform"]
    return {
        "id": o.get("identifier", f"object_{i}"),
        "category": _snake(_enum(o.get("category"))),
        "size": _size(o["dimensions"]),
        "position": _center(m),
        "yaw": _yaw(m),
    }


def _floor_height(roomplan: dict) -> float:
    """ARKit Y of the floor: floors[] transforms if present, else the lowest wall bottom, else 0."""
    floors = [f["transform"][13] for f in roomplan.get("floors", []) if f.get("transform")]
    if floors:
        return float(min(floors))
    bottoms = [w["transform"][13] - w["dimensions"][1] / 2 for w in roomplan.get("walls", [])]
    return float(min(bottoms)) if bottoms else 0.0


def _snap(yaw: float) -> float:
    q = round(yaw / (math.pi / 2)) * (math.pi / 2)
    yaw = q if abs(yaw - q) <= SNAP_TOL else yaw
    yaw = math.atan2(math.sin(yaw), math.cos(yaw))
    return 0.0 if abs(yaw) < 1e-9 else round(yaw, 9)


def _align(walls: list[dict], fixtures: list[dict]) -> None:
    """Rotate about z so the longest wall runs along +X, then translate the walls' min corner to (0, 0)."""
    if not walls:
        return
    w = max(walls, key=lambda w: math.dist(w["start"], w["end"]))
    theta = math.atan2(w["end"][1] - w["start"][1], w["end"][0] - w["start"][0])
    theta = (theta + math.pi / 2) % math.pi - math.pi / 2  # direction mod pi, in [-pi/2, pi/2)
    c, s = math.cos(-theta), math.sin(-theta)

    def rot(x: float, y: float) -> list[float]:
        return [c * x - s * y, s * x + c * y]

    for w in walls:
        w["start"], w["end"] = rot(*w["start"]), rot(*w["end"])
    for f in fixtures:
        f["position"][:2] = rot(*f["position"][:2])
        f["yaw"] = _snap(f["yaw"] - theta)
    mx = min(min(w["start"][0], w["end"][0]) for w in walls)
    my = min(min(w["start"][1], w["end"][1]) for w in walls)
    for w in walls:
        w["start"] = [round(w["start"][0] - mx, 9), round(w["start"][1] - my, 9)]
        w["end"] = [round(w["end"][0] - mx, 9), round(w["end"][1] - my, 9)]
    for f in fixtures:
        f["position"] = [round(f["position"][0] - mx, 9), round(f["position"][1] - my, 9), f["position"][2]]


def _kept(o: dict) -> bool:
    return _enum(o.get("confidence"), "high") != "low"


def to_bundle(roomplan: dict, room_id: str) -> dict:
    """Normalize a CapturedRoom dict. RoomPlan objects become fixtures; counters are not invented here.
    Low-confidence objects are dropped; z is measured from the floor."""
    z0 = _floor_height(roomplan)
    walls = [_wall(w, z0) for w in roomplan.get("walls", [])]
    fixtures = [_object(o, i) for i, o in enumerate(roomplan.get("objects", [])) if _kept(o)]
    for f in fixtures:
        f["position"][2] = round(f["position"][2] - z0, 9)
    _align(walls, fixtures)
    bundle = {
        "schema_version": "1",
        "room_id": room_id,
        "units": "meters",
        "frame": "z_up",
        "geometry_source": "roomplan",
        "blocks_claims": [],
        "walls": walls,
        "fixtures": fixtures,
        "objects": [],
    }
    return validate(bundle)


def load(path: str | Path, room_id: str) -> dict:
    with open(path) as f:
        return to_bundle(json.load(f), room_id)
