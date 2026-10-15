"""Policies for the sim: act(obs) -> action (7 arm joint targets + 1 gripper opening target, meters).

ScriptedExpert  IK waypoint controller (the data generator).
VLMPlanner      instruction + scene objects -> plan JSON via Nemotron (Token Factory) or a rule-based fallback.
VLAClient       HTTP client for a GR00T N1.x policy server (GR00T_POLICY_URL); not bundled.
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.request

import numpy as np

from arrival.sim import ik
from arrival.sim.robot import FINGER_OPEN, HOME


class Policy:
    def reset(self, env, task: dict) -> None:  # noqa: D401
        pass

    def act(self, obs: dict) -> np.ndarray:
        raise NotImplementedError


class ScriptedExpert(Policy):
    """Plans eef waypoints for the task, solves IK per waypoint, then interpolates joint targets."""

    def __init__(self, seg_steps: int = 20, hold_steps: int = 8):
        self.seg_steps, self.hold_steps = seg_steps, hold_steps

    def _waypoints(self, env, task: dict) -> list[tuple]:
        """(pos, R, gripper, steps) list."""
        fam, o, c = task["family"], FINGER_OPEN, 0.0
        if fam in ("counter_to_sink", "counter_to_counter"):
            p = env.body_pos(task["object_id"])
            gz = p[2] + min(0.01, env.obj_half_h(task["object_id"]) * 0.2)
            tgt = env.place_point(task)
            R = ik.down(0.0)
            s = self.seg_steps
            return [((p[0], p[1], gz + 0.18), R, o, s), ((p[0], p[1], gz + 0.02), R, o, s),
                    ((p[0], p[1], gz), R, o, s // 2), ((p[0], p[1], gz), R, c, self.hold_steps),
                    ((p[0], p[1], gz + 0.22), R, c, s), ((tgt[0], tgt[1], gz + 0.22), R, c, 2 * s),
                    ((tgt[0], tgt[1], tgt[2]), R, c, s), ((tgt[0], tgt[1], tgt[2]), R, o, self.hold_steps),
                    ((tgt[0], tgt[1], tgt[2] + 0.2), R, o, s)]
        if fam == "open_drawer":
            h, axis = env.site_pos(task["handle"]), env.pull_axis(task)
            R = ik.down(np.arctan2(axis[1], axis[0]))  # fingers close across the pull axis
            h = h + np.array([0, 0, 0.0])
            pre = h + np.array([0, 0, 0.12])
            s = self.seg_steps
            return [(pre, R, o, s), (h + 0.005 * axis, R, o, s), (h + 0.005 * axis, R, c, self.hold_steps)] + [
                (h + (0.005 + 0.32 * k / 6) * axis, R, c, s // 2) for k in range(1, 7)] + [
                (h + 0.325 * axis, R, o, self.hold_steps), (h + 0.325 * axis + np.array([0, 0, 0.15]), R, o, s)]
        if fam == "open_door":
            hinge, h, R0 = env.door_geometry(task)
            r = np.linalg.norm((h - hinge)[:2])
            a0 = np.arctan2(*(h - hinge)[[1, 0]])
            out = []
            s = self.seg_steps
            normal = -np.array([-np.sin(a0), np.cos(a0), 0.0])  # outward from the closed panel
            out += [(h + 0.1 * normal, ik.facing(-normal[:2]), o, s), (h + 0.005 * normal, ik.facing(-normal[:2]), o, s),
                    (h + 0.005 * normal, ik.facing(-normal[:2]), c, self.hold_steps)]
            for k in range(1, 9):
                a = a0 - np.radians(85) * k / 8  # right-hinged cabinet door swings outward (clockwise from above)
                pt = hinge + np.array([r * np.cos(a), r * np.sin(a), h[2] - hinge[2]])
                n = -np.array([-np.sin(a), np.cos(a), 0.0])
                out.append((pt + 0.005 * n, ik.facing(-n[:2]), c, s // 2))
            out.append((out[-1][0], out[-1][1], o, self.hold_steps))
            return out
        raise ValueError(f"unknown family {fam}")

    def reset(self, env, task: dict) -> None:
        q = np.array(HOME)
        self.plan: list[np.ndarray] = []
        prev = np.concatenate([q, [FINGER_OPEN]])
        self.ik_error = 0.0
        for pos, R, g, steps in self._waypoints(env, task):
            q, err = ik.solve(env.model, env.data, pos, R, q, env.qadr, env.dofadr)
            self.ik_error = max(self.ik_error, err)
            nxt = np.concatenate([q, [g]])
            for k in range(1, steps + 1):
                self.plan.append(prev + (nxt - prev) * min(1.0, k / max(1, steps - 2)))
            prev = nxt
        self.t = 0

    def done(self) -> bool:
        return self.t >= len(self.plan)

    def act(self, obs: dict) -> np.ndarray:
        a = self.plan[min(self.t, len(self.plan) - 1)]
        self.t += 1
        return a


# ---------- language planning ----------

def rule_plan(instruction: str, objects: list[str], fixtures: list[str]) -> dict:
    """Deterministic parser: family + object + target from keywords."""
    s = instruction.lower()
    obj = next((o for o in objects if o.split("_")[0] in s), None)
    if "drawer" in s:
        return {"family": "open_drawer", "object": None, "target": None}
    if "door" in s:
        return {"family": "open_door", "object": None, "target": None}
    if "sink" in s:
        return {"family": "counter_to_sink", "object": obj, "target": next((f for f in fixtures if "sink" in f), None)}
    return {"family": "counter_to_counter", "object": obj, "target": None}


class VLMPlanner:
    """Turns an instruction + scene inventory into a plan JSON with Nemotron; falls back to rule_plan."""

    def __init__(self, log=print):
        self.log = log
        self.source = None

    def plan(self, instruction: str, objects: list[str], fixtures: list[str]) -> dict:
        from arrival.models.token_factory import TokenFactoryNotConfigured, complete

        try:
            txt = complete([{"role": "system", "content": "Return only JSON: {\"family\": one of counter_to_sink|"
                             "counter_to_counter|open_drawer|open_door, \"object\": id|null, \"target\": id|null}"},
                            {"role": "user", "content": json.dumps({"instruction": instruction, "objects": objects,
                                                                    "fixtures": fixtures})}], role="super")
            plan = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
            self.source = "token_factory"
        except TokenFactoryNotConfigured as e:
            self.log(f"[sim] VLMPlanner: Token Factory not configured ({e}); using rule-based parser")
            plan, self.source = rule_plan(instruction, objects, fixtures), "rule_based"
        except Exception as e:  # network / parse errors also fall back, loudly
            self.log(f"[sim] VLMPlanner: model call failed ({e!r}); using rule-based parser")
            plan, self.source = rule_plan(instruction, objects, fixtures), "rule_based"
        return plan


class VLANotConfigured(RuntimeError):
    pass


class VLAClient(Policy):
    """Client for a GR00T N1.x policy server (e.g. gr00t inference service behind an HTTP shim).

    POST {GR00T_POLICY_URL}/act  JSON:
      {"video.ego_view": <base64 PNG HxWx3 uint8>, "state.single_arm": [7], "state.gripper": [1],
       "annotation.human.task_description": "<instruction>"}
    Response: {"action.single_arm": [[7], ...], "action.gripper": [[1], ...]}  (absolute joint targets, chunk)
    Matches meta/modality.json of datasets written by `arrival sim`.
    """

    def __init__(self, url: str | None = None, timeout: float = 10.0):
        self.url = url or os.environ.get("GR00T_POLICY_URL")
        if not self.url:
            raise VLANotConfigured("GR00T_POLICY_URL is not set; start a GR00T policy server and export its URL.")
        self.timeout = timeout
        self.queue: list[np.ndarray] = []

    def reset(self, env, task: dict) -> None:
        self.instruction = task["instruction"]
        self.queue = []

    def act(self, obs: dict) -> np.ndarray:
        if not self.queue:
            import io

            from PIL import Image

            buf = io.BytesIO()
            Image.fromarray(obs["ego_view"]).save(buf, format="PNG")
            body = json.dumps({"video.ego_view": base64.b64encode(buf.getvalue()).decode(),
                               "state.single_arm": obs["state"][:7].tolist(), "state.gripper": obs["state"][7:8].tolist(),
                               "annotation.human.task_description": self.instruction}).encode()
            req = urllib.request.Request(self.url.rstrip("/") + "/act", data=body, method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                out = json.load(r)
            self.queue = [np.concatenate([a, g]) for a, g in zip(out["action.single_arm"], out["action.gripper"])]
        return np.asarray(self.queue.pop(0), dtype=float)
