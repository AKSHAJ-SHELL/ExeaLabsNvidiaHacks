# EVAL-1a: realism metrics

`arrival/eval/realism.py` scores how far the twin's render is from a real RGB-D frame at the same camera pose. It takes arrays only; CAP-2a will supply real frames later, and no real frame has been scored yet (issue #65 stays open for that).

Conventions: OpenCV camera axes (x right, y down, z forward), `cam_to_room` a 4x4 into the twin's z-up frame, K in pixels of the frame's size, depth in metres along the optical axis. The MuJoCo camera is symmetric, so `render_twin` refuses a principal point more than 2% off centre or fx and fy more than 2% apart. Robot and people are hidden by moving their geoms into a group the scene option switches off. Depth is 0 where the camera sees no surface (open ceiling); those pixels are excluded and counted in `depth_sim_no_hit`.

Functions: `render_twin(twin, K, cam_to_room, (h, w))`, `score(rgb_ref, depth_ref, rgb_sim, depth_sim, valid_depth_mask, robot_mask=None)`, `evaluate_frames(twin, frames, heldout_ids)`, plus `look_at`, `perturb_pose` and `side_by_side_png`.

Metrics (robot pixels excluded from all):
- `depth_l1_m`: mean absolute depth error in metres over pixels with valid reference depth and a twin hit (`n_depth`).
- `rgb_mae`: mean absolute RGB error in [0, 1] over all non-robot pixels (`n_rgb`).
- `rgb_one_minus_ssim`: 1 - mean SSIM (7x7 uniform window, luma). `rgb_psnr_db` is also given (None when identical).
- `depth_mask_coverage`, `rgb_mask_coverage`: counted pixels over all pixels.

`evaluate_frames` raises `ValueError` for any frame id not in `heldout_ids` (checked before anything is rendered), so a training frame cannot count. If the twin's `blocks_claims` contains `realism` (four-photo bundles) it returns `{"realism": None, "reason": ...}`. Otherwise it returns pixel-weighted means and a per-frame list.

Sanity numbers (hero kitchen, 64x80): the twin against its own render gives depth 0 m and RGB 0; the same view moved 0.15 m and turned 5 degrees gives depth L1 0.18 m, RGB MAE 0.075, 1-SSIM 0.51.

Not done: lens distortion, off-centre principal points, people in reference frames (no person mask), and any threshold for what counts as realistic.

Test: `python -m pytest tests/test_realism.py -p no:cacheprovider`.
