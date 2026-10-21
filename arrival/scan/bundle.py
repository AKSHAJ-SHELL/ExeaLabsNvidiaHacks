"""Load and validate a ScanBundle (scans/<room_id>/scan.json)."""

from __future__ import annotations

import json
from pathlib import Path

GEOMETRY_SOURCES = ("authored_sample", "roomplan", "four_photo_unmeasured")
OPTIONAL_LISTS = ("doors", "windows", "openings", "floors")


class ScanBundleError(ValueError):
    pass


def validate(bundle: dict) -> dict:
    if bundle.get("schema_version") != "1":
        raise ScanBundleError(f"schema_version must be '1', got {bundle.get('schema_version')!r}")
    if bundle.get("units") != "meters":
        raise ScanBundleError(f"units must be 'meters', got {bundle.get('units')!r}")
    if bundle.get("frame") != "z_up":
        raise ScanBundleError(f"frame must be 'z_up', got {bundle.get('frame')!r}")
    if bundle.get("geometry_source") not in GEOMETRY_SOURCES:
        raise ScanBundleError(f"geometry_source must be one of {GEOMETRY_SOURCES}")
    if not isinstance(bundle.get("blocks_claims", []), list):
        raise ScanBundleError("blocks_claims must be a list")
    if not bundle.get("room_id"):
        raise ScanBundleError("room_id is required")
    for key in ("walls", "fixtures", "objects") + OPTIONAL_LISTS:
        if not isinstance(bundle.get(key, []), list):
            raise ScanBundleError(f"{key} must be a list")
    for key in ("fixtures", "objects", "doors", "windows", "openings"):
        for item in bundle.get(key, []):
            if len(item.get("size", [])) != 3 or len(item.get("position", [])) != 3:
                raise ScanBundleError(f"{item.get('id')}: size and position must have 3 values")
    for item in bundle.get("fixtures", []):
        if item.get("hinge", "right") not in ("left", "right"):
            raise ScanBundleError(f"{item.get('id')}: hinge must be 'left' or 'right', got {item['hinge']!r}")
    for fl in bundle.get("floors", []):
        if len(fl.get("corners", [])) < 3 or any(len(c) != 2 for c in fl["corners"]):
            raise ScanBundleError(f"{fl.get('id')}: floor corners must be 3 or more [x, y] points")
    for key in ("story", "story_count"):
        if key in bundle and not isinstance(bundle[key], int):
            raise ScanBundleError(f"{key} must be an integer")
    bundle.setdefault("blocks_claims", [])
    return bundle


def load(path: str | Path) -> dict:
    with open(path) as f:
        return validate(json.load(f))


def load_room(room_id: str, scans_dir: str | Path = "scans") -> dict:
    return load(Path(scans_dir) / room_id / "scan.json")
