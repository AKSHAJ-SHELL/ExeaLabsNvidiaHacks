"""Robot-human distance per control step (PPL-2 safety metric), plus arm-fixture contacts (POL-4).

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
        # Arm-fixture contacts: the arm links (not the hand or fingers, which are meant to touch handles and
        # objects) against anything but the robot itself, people and free objects (bodies with a free joint).
        links = {model.body(f"link{i}").id for i in range(1, 8)}
        free = {model.jnt_bodyid[j] for j in range(model.njnt) if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_FREE}
        self.link_geoms = {g for g in range(model.ngeom) if model.geom_bodyid[g] in links}
        self.robot_geoms = {g for g in range(model.ngeom) if model.geom_bodyid[g] in body_ids}
        self.free_geoms = {g for g in range(model.ngeom) if model.geom_bodyid[g] in free}
        self.reset()

    def reset(self) -> None:
        self.n = 0
        self.min_d = float("inf")
        self.min_step = None
        self.contact = False
        self.arm_steps = 0
        self.arm_depth = 0.0
        self.arm_worst = None

    def _arm_contacts(self, model, data) -> None:
        hit = False
        for i in range(data.ncon):
            c = data.contact[i]
            for a, b in ((c.geom1, c.geom2), (c.geom2, c.geom1)):
                if a in self.link_geoms and b not in self.robot_geoms | self.person_geoms | self.free_geoms:
                    hit = True
                    if -c.dist > self.arm_depth:
                        self.arm_depth = -c.dist
                        self.arm_worst = (model.body(model.geom_bodyid[a]).name,
                                          model.geom(b).name or model.body(model.geom_bodyid[b]).name)
        self.arm_steps += hit

    def update(self, model, data) -> None:
        self._arm_contacts(model, data)
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
        arm = {"arm_contact_steps": self.arm_steps, "arm_contact_max_depth_m": round(self.arm_depth, 4),
               "arm_contact_worst": list(self.arm_worst) if self.arm_worst else None}
        if not self.people:
            return {"min_human_distance_m": None, "min_distance_step": None, "human_contact": False, "people": 0,
                    **arm}
        return {"min_human_distance_m": round(self.min_d, 4), "min_distance_step": self.min_step,
                "human_contact": bool(self.contact), "people": len(self.people), **arm}
