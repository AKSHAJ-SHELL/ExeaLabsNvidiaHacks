"""CAP-2a: RGB-D manifest loader, unprojection and the synthetic two-camera bundle (offline, tiny)."""

import json

import numpy as np
import pytest

from arrival.scan import rgbd


def _edit(root, fn):
    p = root / rgbd.MANIFEST_NAME
    m = json.loads(p.read_text())
    fn(m)
    p.write_text(json.dumps(m))


def test_unproject_known_pixel_roundtrips():
    K = np.array([[100.0, 0, 32], [0, 100.0, 24], [0, 0, 1]])
    T = rgbd.look_at((1.0, 2.0, 1.5), (3.0, 2.0, 1.5))  # looks along +x, so camera -z is room +x
    depth = np.zeros((48, 64), np.float32)
    depth[14, 52] = 2.0  # 20 px right of centre, 10 px above
    pts = rgbd.unproject(depth, K, T)
    assert pts.shape == (1, 3)
    # right of the image is room -y when looking along +x with Z up; above centre is +z
    expected = [1.0 + 2.0, 2.0 - 20 / 100 * 2.0, 1.5 + 10 / 100 * 2.0]
    assert np.allclose(pts[0], expected, atol=1e-6)
    uv, d = rgbd.project(pts, K, T)
    assert np.allclose(uv[0], [52, 14], atol=1e-6) and abs(d[0] - 2.0) < 1e-6


@pytest.mark.parametrize("unit", ["m", "mm"])
def test_synthetic_bundle_points_land_on_floor_plane(tmp_path, unit):
    m = rgbd.load_manifest(rgbd.write_synthetic_bundle(tmp_path, depth_unit=unit))
    assert [f.split for f in m.frames] == ["train", "heldout"]
    for f in m.frames:
        pts = rgbd.unproject(rgbd.load_depth(m, f), rgbd.depth_intrinsics(m, f), f.camera_to_room)
        on_wall = np.abs(pts[:, 0] - 3.0) < 1e-3
        floor = pts[~on_wall]
        assert on_wall.any() and len(floor) > 100  # each camera sees wall and floor
        assert np.abs(floor[:, 2]).max() < 1e-3  # 1 mm, also covers the mm PNG quantisation


@pytest.mark.parametrize("mutate,code", [
    (lambda m: m.update(depth_unit="mm"), "depth_unit"),  # files are .npy
    (lambda m: m["frames"][1].update(timestamp=0.5), "non_monotonic_timestamps"),
    (lambda m: m["frames"][0].update(camera_to_room=[2, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]),
     "non_orthonormal_rotation"),
    (lambda m: m["frames"][0].update(rgb="rgb/nope.png"), "missing_file"),
    (lambda m: m.update(splits={"train": ["f000"], "heldout": ["f000", "f001"]}), "frame_in_both_splits"),
    (lambda m: m["axes"].update(camera="opencv"), "axis_convention"),
    (lambda m: m["frames"][0].update(camera_to_room=[float("nan")] * 16), "nonfinite_transform"),
])
def test_malformed_manifest_rejected_with_distinct_code(tmp_path, mutate, code):
    root = rgbd.write_synthetic_bundle(tmp_path)
    _edit(root, mutate)
    with pytest.raises(rgbd.ManifestError) as e:
        rgbd.load_manifest(root)
    assert e.value.code == code and str(e.value).startswith(code + ":")
