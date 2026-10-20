# CAP-2a: RGB-D scan-frame format

Issue #58 (CAP-2), format, loader and fixture only. The format is in `docs/04-contracts.md`, section "RGB-D scan frames". Code: `arrival/scan/rgbd.py`. Tests: `pytest tests/test_rgbd.py -p no:cacheprovider`.

- `load_manifest(dir)` validates strictly and raises `ManifestError` with a `code` per rule.
- `unproject(depth, K, T)` gives Nx3 room-frame points; `project(points, K, T)` returns pixels and depth. A pixel unprojects and projects back within 1e-6.
- `write_synthetic_bundle(dir, depth_unit="m"|"mm")` writes two cameras seeing the floor (z = 0) and a wall (x = 3); both cameras' floor points lie within 1 mm of z = 0.

Blocked, needs a device: the Swift recorder that writes a bundle from ARKit and LiDAR. Nothing downstream (twin fitting, EVAL) reads these bundles yet.
