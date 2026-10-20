"""EVAL-1a: how far the twin's render is from a real RGB-D frame taken at the same camera pose.

Pure arrays in, numbers out: nothing here reads a scan or a capture file (CAP-2a will supply frames). Camera
convention is OpenCV: x right, y down, z forward, `cam_to_room` a 4x4 that maps camera coordinates to the twin's
z-up room frame, K a 3x3 pinhole matrix in pixels of the frame's own size. Depth is metres along the optical axis.

Metrics, all on pixels outside the robot mask:
  depth_l1_m          mean |depth_ref - depth_sim| over pixels where the reference depth is valid and the twin hit
                      something (n_depth of them)
  rgb_mae             mean absolute error of RGB scaled to [0, 1], over every non-robot pixel (n_rgb)
  rgb_one_minus_ssim  1 - mean SSIM (7x7 uniform window, luma, data range 1) over the same pixels
  rgb_psnr_db         PSNR from the RGB mean squared error; None when the images are identical
The twin renders the fixed room only: the robot and people are hidden, so a reference frame that shows them needs
a robot_mask (and the walkers get no mask here, so score frames without people).
"""

from __future__ import annotations

import math

import numpy as np

from arrival.sim.scene import build_mjcf

SSIM_WIN = 7
BASE = (0.0, 0.0, 0.75)  # the robot is hidden, so where it stands only has to be a valid pose
HIDDEN_GROUP = 4  # geom group of the hidden bodies; the scene option below switches it off
_CV_TO_MJ = np.diag([1.0, -1.0, -1.0])  # MuJoCo cameras look down -z with y up


def look_at(eye, target, up=(0.0, 0.0, 1.0)) -> np.ndarray:
    """cam_to_room (OpenCV axes) for a camera at eye looking at target."""
    eye, target, up = (np.asarray(v, float) for v in (eye, target, up))
    z = target - eye
    z /= np.linalg.norm(z)
    if abs(float(z @ up)) > 1 - 1e-6:  # looking straight along up: any horizontal axis will do
        up = np.array([0.0, 1.0, 0.0])
    x = np.cross(z, up)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    T = np.eye(4)
    T[:3, :3] = np.stack([x, y, z], axis=1)
    T[:3, 3] = eye
    return T


def perturb_pose(cam_to_room: np.ndarray, shift_m: float, yaw_deg: float) -> np.ndarray:
    """cam_to_room moved shift_m along the camera's own x axis and turned yaw_deg about its own y axis."""
    a = math.radians(yaw_deg)
    R = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    T = np.array(cam_to_room, float)
    T[:3, 3] += T[:3, 0] * shift_m
    T[:3, :3] = T[:3, :3] @ R
    return T


def _hidden_bodies(model) -> list[int]:
    import mujoco

    out = []
    for b in range(model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, b) or ""
        if name == "robot_base" or name.startswith("person_"):
            out.append(b)
    return out


def render_twin(twin: dict, K, cam_to_room, size: tuple[int, int], base_pos=BASE) -> tuple[np.ndarray, np.ndarray]:
    """(rgb uint8 HxWx3, depth float32 HxW in metres) of the twin from the pose, robot and people excluded.
    size is (height, width); base_pos only says where the hidden robot stands. Depth is 0 where the camera sees no surface (sky above the open room). The
    principal point must sit within 2% of the image centre and fx within 2% of fy: the MuJoCo camera is symmetric."""
    import mujoco

    h, w = size
    K = np.asarray(K, float)
    T = np.asarray(cam_to_room, float)
    if K.shape != (3, 3) or T.shape != (4, 4):
        raise ValueError("K must be 3x3 and cam_to_room 4x4")
    if abs(K[0, 2] - w / 2) > 0.02 * w or abs(K[1, 2] - h / 2) > 0.02 * h or abs(K[0, 0] - K[1, 1]) > 0.02 * K[1, 1]:
        raise ValueError("render_twin needs a centred principal point and square pixels")
    model = mujoco.MjModel.from_xml_string(build_mjcf(twin, tuple(base_pos), n_people=0))
    model.vis.global_.offwidth = max(model.vis.global_.offwidth, w)
    model.vis.global_.offheight = max(model.vis.global_.offheight, h)
    hidden = set(_hidden_bodies(model))
    for g in range(model.ngeom):
        b = int(model.geom_bodyid[g])
        while b > 0 and b not in hidden:
            b = int(model.body_parentid[b])
        if b in hidden:
            model.geom_group[g] = HIDDEN_GROUP
    cam = model.camera("overview")
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, (T[:3, :3] @ _CV_TO_MJ).ravel())
    model.cam_pos[cam.id] = T[:3, 3]
    model.cam_quat[cam.id] = quat
    model.cam_fovy[cam.id] = math.degrees(2 * math.atan(h / 2 / K[1, 1]))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    opt = mujoco.MjvOption()
    opt.geomgroup[HIDDEN_GROUP] = 0
    r = mujoco.Renderer(model, h, w)
    try:
        r.update_scene(data, "overview", scene_option=opt)
        rgb = r.render().copy()
        r.enable_depth_rendering()
        r.update_scene(data, "overview", scene_option=opt)
        depth = r.render().astype(np.float32)
    finally:
        r.close()
    far = float(model.stat.extent * model.vis.map.zfar)
    depth[~(depth < far * 0.99)] = 0.0
    return rgb, depth


def _ssim_map(a: np.ndarray, b: np.ndarray, win: int = SSIM_WIN) -> np.ndarray:
    """Per-pixel SSIM of two HxW float images in [0, 1], uniform window, edges padded by replication."""
    from numpy.lib.stride_tricks import sliding_window_view

    def mean(x):
        p = np.pad(x, win // 2, mode="edge")
        return sliding_window_view(p, (win, win)).mean(axis=(-1, -2))

    c1, c2 = 0.01 ** 2, 0.03 ** 2
    ma, mb = mean(a), mean(b)
    va, vb, cab = mean(a * a) - ma * ma, mean(b * b) - mb * mb, mean(a * b) - ma * mb
    return ((2 * ma * mb + c1) * (2 * cab + c2)) / ((ma * ma + mb * mb + c1) * (va + vb + c2))


def score(rgb_ref, depth_ref, rgb_sim, depth_sim, valid_depth_mask, robot_mask=None) -> dict:
    """Errors between a reference frame and the twin render (see the module doc for each key)."""
    rgb_ref, rgb_sim = np.asarray(rgb_ref), np.asarray(rgb_sim)
    depth_ref, depth_sim = np.asarray(depth_ref, float), np.asarray(depth_sim, float)
    if rgb_ref.shape != rgb_sim.shape or depth_ref.shape != depth_sim.shape or rgb_ref.shape[:2] != depth_ref.shape:
        raise ValueError("reference and simulated frames must have the same shape")
    keep = np.ones(depth_ref.shape, bool) if robot_mask is None else ~np.asarray(robot_mask, bool)
    d_ok = keep & np.asarray(valid_depth_mask, bool) & np.isfinite(depth_ref) & (depth_ref > 0)
    sim_hit = depth_sim > 0
    d_use = d_ok & sim_hit
    n_px = depth_ref.size
    a, b = rgb_ref.astype(float) / 255.0, rgb_sim.astype(float) / 255.0
    n_rgb, n_depth = int(keep.sum()), int(d_use.sum())
    out = {"depth_l1_m": float(np.abs(depth_ref - depth_sim)[d_use].mean()) if n_depth else None,
           "n_depth": n_depth, "n_rgb": n_rgb,
           "depth_mask_coverage": round(n_depth / n_px, 4), "rgb_mask_coverage": round(n_rgb / n_px, 4),
           "depth_sim_no_hit": int((d_ok & ~sim_hit).sum()),
           "rgb_mae": None, "rgb_one_minus_ssim": None, "rgb_psnr_db": None}
    if n_rgb:
        out["rgb_mae"] = float(np.abs(a - b)[keep].mean())
        mse = float(((a - b) ** 2)[keep].mean())
        out["rgb_psnr_db"] = None if mse == 0 else float(10 * math.log10(1.0 / mse))
        luma = np.array([0.299, 0.587, 0.114])
        out["rgb_one_minus_ssim"] = float(1.0 - _ssim_map(a @ luma, b @ luma)[keep].mean())
    return out


def side_by_side_png(path, rgb_ref, rgb_sim, depth_ref=None, depth_sim=None) -> None:
    """reference | twin (| depth reference | depth twin, grey, scaled to the reference's range) as one PNG."""
    from PIL import Image

    tiles = [np.asarray(rgb_ref), np.asarray(rgb_sim)]
    if depth_ref is not None and depth_sim is not None:
        hi = max(float(np.max(depth_ref)), 1e-6)
        for d in (depth_ref, depth_sim):
            g = (np.clip(np.asarray(d, float) / hi, 0, 1) * 255).astype(np.uint8)
            tiles.append(np.repeat(g[..., None], 3, axis=2))
    Image.fromarray(np.concatenate(tiles, axis=1)).save(path)


def evaluate_frames(twin: dict, frames: list[dict], heldout_ids: list[str]) -> dict:
    """Score frames against the twin. Each frame is {id, rgb, depth, valid_depth_mask, K, cam_to_room[, robot_mask]}.
    Raises ValueError for any frame id not in heldout_ids, so a training frame cannot count. A twin whose
    blocks_claims holds 'realism' (a four-photo bundle) gets {"realism": None, "reason": ...} instead of numbers."""
    allowed = set(heldout_ids)
    bad = [str(f.get("id")) for f in frames if f.get("id") not in allowed]
    if bad:
        raise ValueError(f"frames not in the held-out manifest: {', '.join(bad)}")
    if "realism" in twin.get("blocks_claims", []):
        return {"realism": None, "reason": f"bundle {twin.get('room_id')!r} blocks the realism claim "
                                          f"(geometry_source {twin.get('geometry_source')!r}); no metrics reported"}
    per = []
    for f in frames:
        rgb = np.asarray(f["rgb"])
        rgb_sim, depth_sim = render_twin(twin, f["K"], f["cam_to_room"], rgb.shape[:2])
        s = score(rgb, f["depth"], rgb_sim, depth_sim, f["valid_depth_mask"], f.get("robot_mask"))
        per.append({"id": f["id"], **s})

    def pooled(key, weight):  # pixel-weighted mean over the frames that have the metric
        rows = [(p[key], p[weight]) for p in per if p[key] is not None]
        n = sum(w for _, w in rows)
        return sum(v * w for v, w in rows) / n if n else None

    return {"realism": {"frames": len(per), "heldout_only": True,
                        "depth_l1_m": pooled("depth_l1_m", "n_depth"),
                        "rgb_mae": pooled("rgb_mae", "n_rgb"),
                        "rgb_one_minus_ssim": pooled("rgb_one_minus_ssim", "n_rgb"),
                        "n_depth": sum(p["n_depth"] for p in per), "n_rgb": sum(p["n_rgb"] for p in per),
                        "per_frame": per}}
