"""Robot-human distance per control step (PPL-2 safety metric).

People are mocap bodies with non-colliding geoms, so MuJoCo never reports a robot-person contact pair.
The metric is geometric instead: horizontal clearance between every robot collision geom (capsule axis
or box/cylinder centre, minus its radius) and a vertical cylinder around each person (radius = the widest
person geom, the torso). Contact is clearance <= 0 or, should person geoms ever collide, a contact pair.
Height is ignored: the arm works between 0.5 m and 1.6 m, where the person cylinder always is.
"""

from __future__ import annotations

import numpy as np

ROBOT_BODIES = ("robot_base",) + tuple(f"link{i}" for i in range(1, 8)) + ("hand", "finger_l", "finger_r")


def _seg_point_dist(a: np.ndarray, b: np.ndarray, p: np.ndarray) -> float:
    ab = b - a
    n = float(ab @ ab)
    t = 0.0 if n < 1e-12 else float(np.clip((p - a) @ ab / n, 0.0, 1.0))
    return float(np.linalg.norm(a + t * ab - p))


class SafetyMonitor:
    def __init__(self, model):
        import mujoco

        body_ids = {model.body(n).id for n in ROBOT_BODIES}
        self.geoms = [g for g in range(model.ngeom)
                      if model.geom_bodyid[g] in body_ids and (model.geom_contype[g] or model.geom_conaffinity[g])]
        self.capsule = {g: model.geom_type[g] == mujoco.mjtGeom.mjGEOM_CAPSULE for g in self.geoms}
        self.radius = {g: float(np.hypot(model.geom_size[g][0], model.geom_size[g][1]))
                       if model.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX else float(model.geom_size[g][0])
                       for g in self.geoms}
        self.half = {g: float(model.geom_size[g][1]) for g in self.geoms}
        self.people = []
        self.person_geoms = set()
        for b in range(model.nbody):
            if model.body(b).name.startswith("person_"):
                gs = [g for g in range(model.ngeom) if model.geom_bodyid[g] == b]
                self.people.append((b, max(float(model.geom_size[g][0]) for g in gs)))
                self.person_geoms.update(gs)
        self.reset()

    def reset(self) -> None:
        self.n = 0
        self.min_d = float("inf")
        self.min_step = None
        self.contact = False

    def update(self, model, data) -> None:
        if not self.people:
            return
        d = float("inf")
        for b, r in self.people:
            p = data.xpos[b][:2]
            for g in self.geoms:
                c = data.geom_xpos[g]
                if self.capsule[g]:
                    axis = data.geom_xmat[g].reshape(3, 3)[:, 2] * self.half[g]
                    dist = _seg_point_dist((c - axis)[:2], (c + axis)[:2], p)
                else:
                    dist = float(np.linalg.norm(c[:2] - p))
                d = min(d, dist - self.radius[g] - r)
        for i in range(data.ncon):
            g1, g2 = data.contact[i].geom1, data.contact[i].geom2
            if (g1 in self.person_geoms and g2 in self.geoms) or (g2 in self.person_geoms and g1 in self.geoms):
                d = min(d, 0.0)
        if d < self.min_d:
            self.min_d, self.min_step = d, self.n
        self.contact = self.contact or d <= 0.0
        self.n += 1

    def summary(self) -> dict:
        if not self.people:
            return {"min_human_distance_m": None, "min_distance_step": None, "human_contact": False, "people": 0}
        return {"min_human_distance_m": round(self.min_d, 4), "min_distance_step": self.min_step,
                "human_contact": bool(self.contact), "people": len(self.people)}
