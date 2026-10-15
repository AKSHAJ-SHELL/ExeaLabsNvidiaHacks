import copy
import json
import struct
import zlib

import pytest

from arrival.scan import bundle, roomplan
from arrival.scan.four_photo import bundle_from_photos

from conftest import SCANS


def test_sink_coordinate_conversion():
    b = roomplan.load(SCANS / "hero_kitchen" / "roomplan.json", "hero_kitchen")
    sink = next(f for f in b["fixtures"] if f["id"] == "sink_1")
    assert sink["category"] == "sink"
    assert sink["position"] == pytest.approx([1.6, 0.40, 0.85], abs=1e-6)
    assert sink["size"] == pytest.approx([0.6, 0.5, 0.25], abs=1e-6)
    assert sink["yaw"] == 0.0
    assert b["geometry_source"] == "roomplan"


def test_roomplan_walls_project_to_floor():
    b = roomplan.load(SCANS / "hero_kitchen" / "roomplan.json", "hero_kitchen")
    north = next(w for w in b["walls"] if w["id"] == "wall_north")
    assert sorted([north["start"][0], north["end"][0]]) == pytest.approx([0.0, 4.0])
    assert north["start"][1] == pytest.approx(0.0) and north["end"][1] == pytest.approx(0.0)
    assert north["height"] == pytest.approx(2.4)
    assert north["thickness"] == pytest.approx(0.02)
    east = next(w for w in b["walls"] if w["id"] == "wall_east")
    assert sorted([east["start"][1], east["end"][1]]) == pytest.approx([0.0, 3.0])


def test_yaw_from_rotation():
    # 90 degrees about ARKit +Y: local +X maps to ARKit -Z, i.e. Z-up +Y -> yaw +pi/2.
    m = [0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1]
    rp = {"walls": [], "objects": [{"identifier": "t", "category": "table", "dimensions": [1, 1, 1], "transform": m}]}
    b = roomplan.to_bundle(rp, "r")
    assert b["fixtures"][0]["yaw"] == pytest.approx(1.5707963, abs=1e-6)


def test_hero_scan_loads(hero_bundle):
    assert hero_bundle["room_id"] == "hero_kitchen"
    assert hero_bundle["geometry_source"] == "authored_sample"
    assert {f["id"] for f in hero_bundle["fixtures"]} == {"counter_a", "sink_1", "counter_b", "fridge_1", "stove_1"}


@pytest.mark.parametrize("key,value", [("frame", "y_up"), ("units", "feet"), ("schema_version", "2")])
def test_rejects_bad_bundle(tmp_path, hero_bundle, key, value):
    bad = copy.deepcopy(hero_bundle)
    bad[key] = value
    p = tmp_path / "scan.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        bundle.load(p)


def _tiny_png(path):
    raw = b"\x00\xff\x00\x00"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return path


def test_four_photo_slot(tmp_path):
    scans = tmp_path / "scans"
    (scans / "hero_kitchen").mkdir(parents=True)
    (scans / "hero_kitchen" / "scan.json").write_text((SCANS / "hero_kitchen" / "scan.json").read_text())
    photos = [_tiny_png(tmp_path / f"p{i}.png") for i in range(4)]
    b = bundle_from_photos(photos, "my_room", scans_dir=scans)
    assert b["geometry_source"] == "four_photo_unmeasured"
    assert b["blocks_claims"] == ["geometry", "realism"]
    assert {"counter_a", "sink_1", "counter_b", "fridge_1", "stove_1"} <= {f["id"] for f in b["fixtures"]}
    assert len(list((scans / "my_room" / "photos").iterdir())) == 4
    with pytest.raises(ValueError):
        bundle_from_photos(photos[:3], "my_room", scans_dir=scans)
