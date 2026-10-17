"""Apple RoomPlan CapturedRoom JSON (subset, ARKit Y-up) -> ScanBundle (Z-up, floor at z=0, room aligned)."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from arrival.catalog.fixtures import default_size
from arrival.scan.bundle import validate

SNAP_TOL = math.radians(5.0)
MIN_WALL_THICKNESS = 0.1
SURFACES = ("walls", "doors", "windows", "openings", "floors")
PORTALS = (("doors", "door"), ("windows", "window"), ("openings", "opening"))


def _enum(value, default: str = "unknown") -> str:
    """Apple encodes Swift enums as {"case": {}}; older/simplified exports use a plain string."""
    if isinstance(value, dict):
        value = next(iter(value), default)
    return str(value) if value else default


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _center(m: list[float]) -> list[float]:
    return [float(m[12]), float(-m[14]), float(m[13])]


def _apply(m: list[float], p: list[float]) -> list[float]:
    """Column-major 4x4 applied to a local point, then ARKit Y-up -> Z-up."""
    x, y, z = p
    wx = m[0] * x + m[4] * y + m[8] * z + m[12]
    wy = m[1] * x + m[5] * y + m[9] * z + m[13]
    wz = m[2] * x + m[6] * y + m[10] * z + m[14]
    return [float(wx), float(-wz), float(wy)]


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
    category = _snake(_enum(o.get("category")))
    dim = o.get("dimensions") or []
    size = _size(dim) if len(dim) == 3 and min(dim) > 0 else default_size(category)
    return {
        "id": o.get("identifier", f"object_{i}"),
        "category": category,
        "size": size,
        "position": _center(m),
        "yaw": _yaw(m),
    }


def _portal(s: dict, i: int, kind: str, wall_ids: set[str]) -> dict:
    """A door, window or opening: a Surface whose parentIdentifier is the wall it sits in."""
    m, cat = s["transform"], s.get("category")
    parent = s.get("parentIdentifier")
    entry = {
        "id": s.get("identifier", f"{kind}_{i}"),
        "wall_id": parent if parent in wall_ids else None,
        "size": _size(s["dimensions"]),
        "position": _center(m),
        "yaw": _yaw(m),
    }
    if kind == "door":
        entry["is_open"] = bool(isinstance(cat, dict) and (cat.get("door") or {}).get("isOpen"))
    return entry


def _floor(f: dict, i: int, z0: float) -> dict | None:
    """polygonCorners are local plane coordinates (x, y, ~0); the floor transform puts them in the room."""
    corners = f.get("polygonCorners") or []
    if len(corners) < 3 or not f.get("transform"):
        return None
    pts = [_apply(f["transform"], c)[:2] for c in corners]
    return {"id": f.get("identifier", f"floor_{i}"), "z": round(float(f["transform"][13]) - z0, 9), "corners": pts}


def _floor_height(roomplan: dict) -> float:
    """ARKit Y of the floor: floors[] transforms if present, else the lowest wall bottom, else 0."""
    floors = [f["transform"][13] for f in roomplan.get("floors", []) if f.get("transform")]
    if floors:
        return float(min(floors))
    bottoms = [w["transform"][13] - w["dimensions"][1] / 2 for w in roomplan.get("walls", [])]
    return float(min(bottoms)) if bottoms else 0.0


def _story_of(item: dict) -> int:
    return int(item.get("story") or 0)


def _flatten(roomplan: dict) -> dict:
    """A CapturedStructure export carries rooms[]; merge their surfaces and objects, each tagged with its story."""
    rooms = roomplan.get("rooms")
    if not rooms:
        return roomplan
    flat: dict = {k: [] for k in SURFACES + ("objects",)}
    for room in rooms:
        for k in flat:
            flat[k] += [{**item, "story": item.get("story", room.get("story", 0))} for item in room.get(k, [])]
    return flat


def _select_story(roomplan: dict, story: int | None) -> tuple[dict, int, int]:
    """Keep one story. Default: the one with the most objects (lowest index on a tie)."""
    keys = SURFACES + ("objects",)
    items = [i for k in keys for i in roomplan.get(k, [])]
    stories = sorted({_story_of(i) for i in items}) or [0]
    if story is None:
        counts = {s: sum(1 for o in roomplan.get("objects", []) if _story_of(o) == s) for s in stories}
        story = max(stories, key=lambda s: (counts[s], -s))
    elif story not in stories:
        raise ValueError(f"story {story} not in export (has {stories})")
    picked = {k: [i for i in roomplan.get(k, []) if _story_of(i) == story] for k in keys}
    return picked, story, len(stories)


def _snap(yaw: float) -> float:
    q = round(yaw / (math.pi / 2)) * (math.pi / 2)
    yaw = q if abs(yaw - q) <= SNAP_TOL else yaw
    yaw = math.atan2(math.sin(yaw), math.cos(yaw))
    return 0.0 if abs(yaw) < 1e-9 else round(yaw, 9)


def _align(walls: list[dict], posed: list[dict], polygons: list[list[list[float]]]) -> None:
    """Rotate about z so the longest wall runs along +X, then translate the walls' min corner to (0, 0).
    `posed` entries carry position and yaw; `polygons` are bare [x, y] lists."""
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
    for f in posed:
        f["position"][:2] = rot(*f["position"][:2])
        f["yaw"] = _snap(f["yaw"] - theta)
    for poly in polygons:
        poly[:] = [rot(*p) for p in poly]
    mx = min(min(w["start"][0], w["end"][0]) for w in walls)
    my = min(min(w["start"][1], w["end"][1]) for w in walls)
    for w in walls:
        w["start"] = [round(w["start"][0] - mx, 9), round(w["start"][1] - my, 9)]
        w["end"] = [round(w["end"][0] - mx, 9), round(w["end"][1] - my, 9)]
    for f in posed:
        f["position"] = [round(f["position"][0] - mx, 9), round(f["position"][1] - my, 9), f["position"][2]]
    for poly in polygons:
        poly[:] = [[round(p[0] - mx, 9), round(p[1] - my, 9)] for p in poly]


def _kept(o: dict) -> bool:
    return _enum(o.get("confidence"), "high") != "low"


def to_bundle(roomplan: dict, room_id: str, story: int | None = None) -> dict:
    """Normalize a CapturedRoom (or CapturedStructure) dict. RoomPlan objects become fixtures; counters are not
    invented here. Low-confidence objects are dropped; z is measured from the selected story's floor."""
    roomplan, story, story_count = _select_story(_flatten(roomplan), story)
    z0 = _floor_height(roomplan)
    walls = [_wall(w, z0) for w in roomplan.get("walls", [])]
    wall_ids = {w["id"] for w in walls}
    fixtures = [_object(o, i) for i, o in enumerate(roomplan.get("objects", [])) if _kept(o)]
    portals = {key: [_portal(s, i, kind, wall_ids) for i, s in enumerate(roomplan.get(key, []))]
               for key, kind in PORTALS}
    floors = [fl for fl in (_floor(f, i, z0) for i, f in enumerate(roomplan.get("floors", []))) if fl]
    posed = fixtures + [p for ps in portals.values() for p in ps]
    for p in posed:
        p["position"][2] = round(p["position"][2] - z0, 9)
    _align(walls, posed, [f["corners"] for f in floors])
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
        "doors": portals["doors"],
        "windows": portals["windows"],
        "openings": portals["openings"],
        "floors": floors,
        "story": story,
        "story_count": story_count,
    }
    return validate(bundle)


def load(path: str | Path, room_id: str, story: int | None = None) -> dict:
    with open(path) as f:
        return to_bundle(json.load(f), room_id, story)
