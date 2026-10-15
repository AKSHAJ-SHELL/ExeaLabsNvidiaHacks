"""ScanBundle -> twin dict (twin.json) + RoboCasa-subset layout (layout.yaml)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import yaml

from arrival.catalog.fixtures import default_config_name, fixture_type
from arrival.catalog.objects import catalog_id

COUNTER_DEPTH = 0.65
COUNTER_HEIGHT = 0.92
SYNTH_RADIUS = 0.3


def _rect_distance(xy: list[float], fixture: dict) -> float:
    """Horizontal distance from a point to a fixture's footprint rectangle (axis-aligned)."""
    (px, py), (cx, cy, _), (sx, sy, _) = xy[:2], fixture["position"], fixture["size"]
    dx = max(abs(px - cx) - sx / 2, 0.0)
    dy = max(abs(py - cy) - sy / 2, 0.0)
    return math.hypot(dx, dy)


def _synth_counters(fixtures: list[dict]) -> list[dict]:
    counters = [f for f in fixtures if f["type"] == "counter"]
    out = []
    for f in fixtures:
        if f["source_category"] not in ("sink", "stove"):
            continue
        if any(_rect_distance(f["position"], c) <= SYNTH_RADIUS for c in counters + out):
            continue
        out.append({
            "id": f"counter_synth_{f['id']}",
            "type": "counter",
            "size": [max(f["size"][0] + 0.4, 1.2), COUNTER_DEPTH, COUNTER_HEIGHT],
            "position": [f["position"][0], f["position"][1], COUNTER_HEIGHT / 2],
            "yaw": 0.0,
            "source_category": "synthesized",
        })
    return out


def compile_twin(bundle: dict) -> dict:
    fixtures = []
    for f in bundle.get("fixtures", []):
        fx = {
            "id": f["id"],
            "type": fixture_type(f["category"]),
            "size": [float(v) for v in f["size"]],
            "position": [float(v) for v in f["position"]],
            "yaw": float(f.get("yaw", 0.0)),
            "source_category": f["category"],
        }
        cfg = default_config_name(f["category"])
        if cfg and fx["type"] == "counter":
            fx["default_config_name"] = cfg
        fixtures.append(fx)
    fixtures += _synth_counters(fixtures)
    objects = [
        {
            "id": o["id"],
            "catalog_id": catalog_id(o["label"]),
            "label": o["label"],
            "size": [float(v) for v in o["size"]],
            "position": [float(v) for v in o["position"]],
            "yaw": float(o.get("yaw", 0.0)),
        }
        for o in bundle.get("objects", [])
    ]
    return {
        "room_id": bundle["room_id"],
        "geometry_source": bundle["geometry_source"],
        "blocks_claims": list(bundle.get("blocks_claims", [])),
        "frame": "z_up",
        "units": "meters",
        "walls": [dict(w) for w in bundle.get("walls", [])],
        "fixtures": fixtures,
        "objects": objects,
    }


def layout_dict(twin: dict) -> dict:
    walls, xs, ys = [], [], []
    for w in twin.get("walls", []):
        (x0, y0), (x1, y1) = w["start"], w["end"]
        xs += [x0, x1]
        ys += [y0, y1]
        length = math.hypot(x1 - x0, y1 - y0)
        along_x = abs(x1 - x0) >= abs(y1 - y0)
        size = [length, w["thickness"], w["height"]] if along_x else [w["thickness"], length, w["height"]]
        walls.append({"name": w["id"], "type": "wall", "size": _r(size),
                      "pos": _r([(x0 + x1) / 2, (y0 + y1) / 2, w["height"] / 2])})
    room: dict = {"walls": walls}
    if xs:
        room["floor"] = [{"name": "floor", "type": "floor",
                          "size": _r([max(xs) - min(xs), max(ys) - min(ys), 0.02]),
                          "pos": _r([(max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, 0.0])}]
    bottom_row = []
    for f in twin["fixtures"]:
        entry = {"name": f["id"], "type": f["type"], "size": _r(f["size"]), "pos": _r(f["position"])}
        if f.get("yaw"):
            entry["z_rot"] = round(f["yaw"], 6)
        if f.get("default_config_name"):
            entry["default_config_name"] = f["default_config_name"]
        bottom_row.append(entry)
    return {
        "room": room,
        "main_group": {"group_origin": [0, 0], "group_pos": [0.0, 0.0], "group_z_rot": 0.0,
                       "bottom_row": bottom_row},
    }


def _r(v: list[float]) -> list[float]:
    return [round(float(x), 6) for x in v]


def write_twin(twin: dict, twin_dir: str | Path) -> tuple[Path, Path]:
    twin_dir = Path(twin_dir)
    twin_dir.mkdir(parents=True, exist_ok=True)
    twin_path, layout_path = twin_dir / "twin.json", twin_dir / "layout.yaml"
    twin_path.write_text(json.dumps(twin, indent=2))
    layout_path.write_text(yaml.safe_dump(layout_dict(twin), sort_keys=False, default_flow_style=None))
    return twin_path, layout_path
