"""Four-photo input slot. Geometry is NOT measured: copies the hero kitchen and blocks claims."""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

from arrival.scan.bundle import load_room, validate


def bundle_from_photos(paths: list, room_id: str, scans_dir: str | Path = "scans",
                       template_room: str = "hero_kitchen") -> dict:
    paths = [Path(p) for p in paths]
    if len(paths) != 4:
        raise ValueError(f"bundle_from_photos needs exactly 4 photos, got {len(paths)}")
    for p in paths:
        if not p.is_file():
            raise ValueError(f"photo not found: {p}")
    scans_dir = Path(scans_dir)
    template = load_room(template_room, scans_dir)
    photo_dir = scans_dir / room_id / "photos"
    photo_dir.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(paths):
        shutil.copy2(p, photo_dir / f"photo_{i}{p.suffix.lower()}")
    bundle = copy.deepcopy(template)
    bundle["room_id"] = room_id
    bundle["geometry_source"] = "four_photo_unmeasured"
    bundle["blocks_claims"] = ["geometry", "realism"]
    return validate(bundle)
