"""Damped least-squares IK on the eef site (position + gripper-down orientation)."""

from __future__ import annotations

import mujoco
import numpy as np


def solve(model, data, target_pos, R_t, q0, qadr: list[int], dofadr: list[int],
          iters: int = 200, damping: float = 0.05, tol: float = 2e-3) -> tuple[np.ndarray, float]:
    """Returns (q, position error). Works on a scratch MjData; R_t is the target eef rotation matrix."""
    d = mujoco.MjData(model)
    d.qpos[:] = data.qpos
    d.qpos[qadr] = q0
    sid = model.site("eef").id
    R_t = np.asarray(R_t, dtype=float)
    jp, jr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
    lo, hi = model.jnt_range[[model.dof_jntid[i] for i in dofadr]].T
    err = 1.0
    for _ in range(iters):
        mujoco.mj_kinematics(model, d)
        mujoco.mj_comPos(model, d)
        R = d.site_xmat[sid].reshape(3, 3)
        ep = np.asarray(target_pos) - d.site_xpos[sid]
        er = 0.5 * (np.cross(R[:, 0], R_t[:, 0]) + np.cross(R[:, 1], R_t[:, 1]) + np.cross(R[:, 2], R_t[:, 2]))
        err = float(np.linalg.norm(ep))
        if err < tol and np.linalg.norm(er) < 0.02:
            break
        mujoco.mj_jacSite(model, d, jp, jr, sid)
        J = np.vstack([jp[:, dofadr], jr[:, dofadr]])
        e = np.concatenate([ep, 0.5 * er])
        dq = J.T @ np.linalg.solve(J @ J.T + damping ** 2 * np.eye(6), e)
        d.qpos[qadr] = np.clip(d.qpos[qadr] + dq, lo, hi)
    return d.qpos[qadr].copy(), err


def down(yaw: float = 0.0) -> np.ndarray:
    """Gripper pointing straight down, fingers closing along (sin yaw, -cos yaw)."""
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array([[c, s, 0], [s, -c, 0], [0, 0, -1.0]])


def facing(direction_xy) -> np.ndarray:
    """Gripper pointing horizontally along direction_xy, fingers closing horizontally (vertical bar handles)."""
    z = np.array([direction_xy[0], direction_xy[1], 0.0])
    z /= np.linalg.norm(z)
    y = np.cross(z, [0, 0, 1.0])
    return np.column_stack([np.cross(y, z), y, z])
