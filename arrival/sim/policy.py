"""Policies for the sim: act(obs) -> action (7 arm joint targets + 1 gripper opening target, meters).

ScriptedExpert  IK waypoint controller (the data generator).
VLMPlanner      instruction + scene objects -> plan JSON via Nemotron (Token Factory) or a rule-based fallback.
VLAClient       HTTP client for a GR00T N1.x policy server (GR00T_POLICY_URL); not bundled.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path

import numpy as np

from arrival.sim import ik
from arrival.sim.robot import FINGER_OPEN, HOME


class Policy:
    def reset(self, env, task: dict) -> None:  # noqa: D401
        pass

    def act(self, obs: dict) -> np.ndarray:
        raise NotImplementedError


FRIDGE_HOOK_ALONG = 0.015  # eef past the bar axis toward the free edge, so the hand clears the edge
FRIDGE_HOOK_OUT = 0.035  # eef out from the bar axis, so the open inner pad clears the panel on the way in
FRIDGE_HOOK = np.radians(40)  # door angle the hooked pull covers: the arm follows the bar exactly up to here
FRIDGE_TURN = 0.3  # share of the door's turn the hand follows while hooked; more folds the elbow onto its stop
DOOR_TURN = 0.0  # share of the door's turn the hand follows while pulling: the bar is vertical, so the pads can
# stay put and it turns between them; following it all the way spends joint 7's range on the swing and pins it at its stop
FRIDGE_FLIP = np.diag([-1.0, -1.0, 1.0])  # half a turn about the approach axis
FRIDGE_CLEAR = 0.04  # closed fingers slide this far out along the panel, off the bar's free side
FRIDGE_FAR = 0.90  # metres from the hinge where the hand rounds the free edge (the edge is at 0.745)
FRIDGE_BACK = 0.08  # how far inside the panel the hand rounds the edge and lines up before the push
FRIDGE_PUSH_AT = 0.62  # metres from the hinge where the closed fingertips push the inside face
FRIDGE_PUSH_GAP = 0.025  # eef behind the inside face: the closed fingertips reach 2.3 cm past the eef
FRIDGE_PUSH_END = np.radians(80)  # door angle the push is planned to
FRIDGE_PUSH_ROLL = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])  # fingers stacked vertically
# for the push, so the hand is narrow along the panel and its far finger stays off the edge
FRIDGE_PULL_STEPS = 10  # control steps per quarter of the hooked pull and per sixth of the push


class ScriptedExpert(Policy):
    """Plans eef waypoints for the task, solves IK per waypoint (biased toward HOME), then plays joint targets
    with min-jerk timing; waypoints flagged `via` are passed through without stopping."""

    def __init__(self, seg_steps: int = 20, hold_steps: int = 8):
        self.seg_steps, self.hold_steps = seg_steps, hold_steps

    @staticmethod
    def _grip_yaw(env, yaw: float) -> float:
        """Parallel jaws are symmetric under a half turn: use yaw + pi when yaw is >120 deg from the hand's
        current heading, so the wrist never spins half a turn for an equivalent grasp."""
        x = env.data.site("eef").xmat.reshape(3, 3)[:, 0]
        return yaw + np.pi if np.cos(yaw - np.arctan2(x[1], x[0])) < -0.5 else yaw

    def _waypoints(self, env, task: dict) -> list[tuple]:
        """(pos, R, gripper, steps[, via]) list."""
        fam, o, c = task["family"], FINGER_OPEN, 0.0
        if fam in ("counter_to_sink", "counter_to_counter"):
            p = env.body_pos(task["object_id"])
            gz = p[2] + min(0.01, env.obj_half_h(task["object_id"]) * 0.2)
            tgt = env.place_point(task)
            g = env.grasp(task["object_id"])
            yaw = 0.0
            if g is not None:  # rim or handle grasp: same xy offset at the set-down, eef kept at its height over the body
                p = p + np.array([g["off"][0], g["off"][1], 0.0])
                tgt = tgt + np.array([g["off"][0], g["off"][1], g["z"] - env.body_pos(task["object_id"])[2]])
                gz, yaw = g["z"], g["yaw"]
            R = ik.down(self._grip_yaw(env, yaw))
            s = self.seg_steps
            lift = [((p[0], p[1], gz + 0.22), R, c, s)]
            if g is not None:  # a wide object tips in the pads as it leaves the counter: lift it in short steps
                lift = [((p[0], p[1], gz + dz), R, c, s, dz < 0.22) for dz in (0.03, 0.08, 0.15, 0.22)]
            return [((p[0], p[1], gz + 0.18), R, o, s), ((p[0], p[1], gz + 0.02), R, o, s),
                    ((p[0], p[1], gz), R, o, s // 2), ((p[0], p[1], gz), R, c, self.hold_steps)] + lift + [
                    ((tgt[0], tgt[1], gz + 0.22), R, c, 2 * s),
                    ((tgt[0], tgt[1], tgt[2]), R, c, s), ((tgt[0], tgt[1], tgt[2]), R, o, self.hold_steps),
                    ((tgt[0], tgt[1], tgt[2] + 0.2), R, o, s)]
        if fam == "open_drawer":
            h, axis = env.site_pos(task["handle"]), env.pull_axis(task)
            R = ik.down(self._grip_yaw(env, np.arctan2(axis[1], axis[0])))  # fingers close across the pull axis
            h = h + np.array([0, 0, 0.0])
            pre = h + np.array([0, 0, 0.12])
            s = self.seg_steps
            return [(pre, R, o, s), (h + 0.005 * axis, R, o, s), (h + 0.005 * axis, R, c, self.hold_steps)] + [
                (h + (0.005 + 0.32 * k / 6) * axis, R, c, s // 2, k < 6) for k in range(1, 7)] + [
                (h + 0.325 * axis, R, o, self.hold_steps), (h + 0.325 * axis + np.array([0, 0, 0.15]), R, o, s)]
        if fam == "put_in_drawer":
            # hand parallel to the counter front (yaw 90) so its long side stays clear of the overhang; the drop into
            # the drawer is a chain of short via-point steps, because one long joint-space move bows back over the
            # counter top and the fingers lose the mug on the slab
            p = env.body_pos(task["object_id"])
            gz = p[2] + min(0.01, env.obj_half_h(task["object_id"]) * 0.2)
            tgt = env.drawer_place_point(task)
            R = ik.down(self._grip_yaw(env, np.pi / 2))
            s = self.seg_steps
            lift = gz + 0.15
            n_steps = int(np.ceil((lift - tgt[2]) / 0.1))
            zs = np.linspace(lift, tgt[2], n_steps + 1)[1:]
            descent = [((tgt[0], tgt[1], z), R, c, s // 2, k < n_steps - 1) for k, z in enumerate(zs)]
            return [((p[0], p[1], gz + 0.18), R, o, s), ((p[0], p[1], gz + 0.02), R, o, s),
                    ((p[0], p[1], gz), R, o, s // 2), ((p[0], p[1], gz), R, c, self.hold_steps),
                    ((p[0], p[1], lift), R, c, s), ((tgt[0], tgt[1], lift), R, c, 2 * s)] + descent + [
                    ((tgt[0], tgt[1], tgt[2]), R, o, self.hold_steps), ((tgt[0], tgt[1], tgt[2] + 0.15), R, o, s)]
        if fam == "wipe_counter":
            # pinch the sponge across its short side, press it to the top and make two strokes along the counter
            p = env.body_pos(task["object_id"])
            top = env.place_point_top(task)
            hh = env.obj_half_h(task["object_id"])
            R = ik.down(self._grip_yaw(env, 0.0))
            s = self.seg_steps
            press = top + hh - 0.004
            strokes = [(p[0] + dx, p[1], press) for dx in (0.15, -0.15, 0.15, -0.15)]
            return [((p[0], p[1], p[2] + 0.15), R, o, s), ((p[0], p[1], p[2]), R, o, s),
                    ((p[0], p[1], p[2]), R, c, self.hold_steps), ((p[0], p[1], press), R, c, s // 2)] + [
                    (w, R, c, s, k < 3) for k, w in enumerate(strokes)] + [
                    ((p[0], p[1], press), R, c, s), ((p[0], p[1], press), R, o, self.hold_steps),
                    ((p[0], p[1], press + 0.15), R, o, s)]
        if fam == "close_drawer":
            # push the handle bar from outside with the closed fingers until the front meets the carcass
            h, axis = env.site_pos(task["handle"]), env.pull_axis(task)
            R = ik.down(self._grip_yaw(env, np.arctan2(axis[1], axis[0])))
            touch = h + 0.025 * axis  # closed finger block (6 mm half) against the bar (12 mm radius)
            s = self.seg_steps
            shut = touch - float(self.open_at) * axis
            return [(touch + 0.12 * axis + np.array([0, 0, 0.1]), R, c, s), (touch + 0.03 * axis, R, c, s)] + [
                (touch + (0.03 - (0.03 + float(self.open_at)) * k / 4) * axis, R, c, s // 2, k < 4) for k in range(1, 5)] + [
                (shut + 0.1 * axis, R, o, s)]
        if fam == "close_door":
            # push the handle bar back along its arc from the outside, hand nearly vertical as in open_door
            hinge, h, _ = env.door_geometry(task)
            r = np.linalg.norm((h - hinge)[:2])
            a_open = np.arctan2(*(h - hinge)[[1, 0]])
            s, up = self.seg_steps, np.array([0, 0, 1.0])
            grasp = np.array([0, 0, 0.04])

            def pt(a):
                return hinge + np.array([r * np.cos(a), r * np.sin(a), h[2] - hinge[2]]) + grasp

            def nrm(a):
                return -np.array([-np.sin(a), np.cos(a), 0.0])

            along = np.array([-nrm(a_open)[1], nrm(a_open)[0], 0.0])
            if np.dot(along, env.data.site("eef").xmat.reshape(3, 3)[:, 1]) < 0:
                along = -along

            def ori(a):
                rot = a - a_open
                ax = np.array([np.cos(rot) * along[0] - np.sin(rot) * along[1],
                               np.sin(rot) * along[0] + np.cos(rot) * along[1]])
                return ik.tilted(nrm(a)[:2], ax, np.radians(10))

            sweep = float(self.open_at) + np.radians(3)  # a little past closed so the latch gap closes
            out = [(pt(a_open) + 0.03 * nrm(a_open) + 0.15 * up, ori(a_open), c, s),
                   (pt(a_open) + 0.03 * nrm(a_open), ori(a_open), c, s)]
            for k in range(1, 9):
                a = a_open + sweep * k / 8
                out.append((pt(a) + 0.03 * nrm(a), ori(a), c, s // 2, k < 8))
            out.append((out[-1][0] + 0.15 * up, out[-1][1], o, s))
            return out
        if fam == "open_door":
            # The bar handle sits 2-3 cm below the counter-top overhang, so the hand comes down nearly vertical
            # (15 deg tilt keeps the hand body clear of the slab) with the fingers closing along the panel.
            # Segments interpolate in joint space, so the hand first goes out in front of the counter and high,
            # then straight down in front, then in to the bar; a direct move from HOME sweeps through the slab.
            hinge, h, _ = env.door_geometry(task)
            r = np.linalg.norm((h - hinge)[:2])
            a0 = np.arctan2(*(h - hinge)[[1, 0]])
            s, up = self.seg_steps, np.array([0, 0, 1.0])
            # Hold the bar near its top (the grasp fails from 0.115 up): a higher wrist reaches further along the arc,
            # and with the tilt it keeps the elbow (link4) above the swinging panel, which is solid to its full drawn
            # height (MAN-2).
            grasp = np.array([0, 0, 0.09])

            def pt(a):
                return hinge + np.array([r * np.cos(a), r * np.sin(a), h[2] - hinge[2]]) + grasp

            def nrm(a):  # outward normal of the panel at door angle a (swings outward, clockwise from above)
                return -np.array([-np.sin(a), np.cos(a), 0.0])

            along = np.array([-nrm(a0)[1], nrm(a0)[0], 0.0])
            if np.dot(along, env.data.site("eef").xmat.reshape(3, 3)[:, 1]) < 0:
                along = -along  # equivalent parallel-jaw grasp that does not spin the wrist half a turn

            def ori(a):
                rot = DOOR_TURN * (a - a0)
                ax = np.array([np.cos(rot) * along[0] - np.sin(rot) * along[1],
                               np.sin(rot) * along[0] + np.cos(rot) * along[1]])
                return ik.tilted(nrm(a)[:2], ax, np.radians(15))

            n0, g = nrm(a0), pt(a0)
            out = [(g + 0.2 * n0 + 0.35 * up, ori(a0), o, s), (g + 0.2 * n0, ori(a0), o, s),
                   (g + 0.005 * n0, ori(a0), o, s), (g + 0.005 * n0, ori(a0), c, self.hold_steps)]
            for k in range(1, 9):  # one smooth via-point pull: stop-and-go pulses let the bar slide off the pads
                a = a0 - np.radians(80) * k / 8
                out.append((pt(a) + 0.005 * nrm(a), ori(a), c, s // 2, k < 8))
            out.append((out[-1][0], out[-1][1], o, self.hold_steps))
            out.append((out[-1][0] + 0.15 * up, out[-1][1], o, s))
            return out
        if fam == "open_fridge":
            # The door is hinged at the fixture's left and swings out into the room. From this base the arm can
            # follow the bar's arc only to about 40 deg, so the plan has two parts: the fingers close round the
            # vertical bar from beyond the free edge and pull to 40 deg, then slide off the bar's free side, round
            # the free edge to the inside face and push the door on with the closed fingertips.
            hinge, h, _ = env.door_geometry(task)
            r = np.linalg.norm((h - hinge)[:2])
            a0 = np.arctan2(*(h - hinge)[[1, 0]])
            s, up = self.seg_steps, np.array([0, 0, 1.0])

            def along(a):  # from the hinge toward the free edge at door angle a
                return np.array([np.cos(a), np.sin(a), 0.0])

            def nrm(a):  # outward normal of the panel (the door swings counter-clockwise from above)
                return np.array([-np.sin(a), np.cos(a), 0.0])

            def pt(a):
                return hinge + (r + FRIDGE_HOOK_ALONG) * along(a) + FRIDGE_HOOK_OUT * nrm(a) + (h[2] - hinge[2]) * up

            def ori(a):  # the other parallel-jaw heading: the first one starts joint 7 on its +2.90 stop
                return ik.facing(-along(a0 + FRIDGE_TURN * (a - a0))[:2]) @ FRIDGE_FLIP

            def push(q):  # eef with the closed fingertips on the inside face at door angle q
                return hinge + FRIDGE_PUSH_AT * along(q) - FRIDGE_PUSH_GAP * nrm(q) + (h[2] - hinge[2]) * up

            def pori(q):
                return ik.facing(nrm(q)[:2]) @ FRIDGE_PUSH_ROLL

            d0, g = along(a0), pt(a0)
            out = [(g + 0.25 * d0 + 0.15 * up, ori(a0), o, s), (g + 0.25 * d0, ori(a0), o, s),
                   (g + 0.08 * d0, ori(a0), o, s, True), (g, ori(a0), o, s), (g, ori(a0), c, self.hold_steps)]
            for k in range(1, 5):
                a = a0 + FRIDGE_HOOK * k / 4
                out.append((pt(a), ori(a), c, FRIDGE_PULL_STEPS, k < 4))
            a, q1 = a0 + FRIDGE_HOOK, FRIDGE_HOOK
            far = hinge + FRIDGE_FAR * along(q1) + (h[2] - hinge[2]) * up  # clear of the free edge
            out += [(pt(a) + FRIDGE_CLEAR * along(a), ori(a), c, s, True),
                    (far - FRIDGE_BACK * nrm(q1), pori(q1), c, s, True),
                    (push(q1) - FRIDGE_BACK * nrm(q1), pori(q1), c, s)]
            for k in range(7):
                q = q1 - np.radians(3) + (FRIDGE_PUSH_END - q1 + np.radians(3)) * k / 6
                out.append((push(q), pori(q), c, FRIDGE_PULL_STEPS, k < 6))
            q = FRIDGE_PUSH_END
            out += [(push(q) - 0.12 * nrm(q), pori(q), c, s), (push(q) - 0.12 * nrm(q) + 0.1 * up, pori(q), c, s)]
            return out
        raise ValueError(f"unknown family {fam}")

    def reset(self, env, task: dict) -> None:
        if task["family"] in ("close_drawer", "close_door"):
            self.open_at = float(env.data.joint(task["joint"]).qpos[0])  # how far the part starts open
        wps = self._waypoints(env, task)
        # Parallel jaws make a half turn about the approach axis the same grasp. Plan both and keep the one whose
        # wrist stays furthest from the joint 7 stops: a fixed world yaw costs joint 7 the whole base swing, which
        # with one of the two headings pins it at the +2.90 rad stop for the second half of the move.
        flip = np.diag([-1.0, -1.0, 1.0])
        plans = [self._plan(env, wps)]
        if task["family"] not in ("open_door", "close_door"):
            # flipped, the cabinet-door grasp lands on the other wrist branch (joint 5 negative): link5 or the elbow
            # then meets the solid panel (#47) and the bar slips out of the pads at 26 to 36 deg
            plans.append(self._plan(env, [(p, R @ flip, *rest) for p, R, *rest in wps]))
        best_err = min(err for _, err, _ in plans)
        self.plan, self.ik_error, _ = min((pl for pl in plans if pl[1] <= best_err + 0.005), key=lambda pl: pl[2])
        self.t = 0

    @staticmethod
    def _plan(env, waypoints) -> tuple[list[np.ndarray], float, float]:
        """Joint-space plan for the waypoints: (targets per step, worst IK position error, peak |joint 7|)."""
        q = np.array(HOME)
        plan: list[np.ndarray] = []
        prev = np.concatenate([q, [FINGER_OPEN]])
        ik_error, q7 = 0.0, abs(q[6])
        chain: list[tuple[np.ndarray, int]] = []
        for pos, R, g, steps, *via in waypoints:
            q, err = ik.solve(env.model, env.data, pos, R, q, env.qadr, env.dofadr)
            ik_error, q7 = max(ik_error, err), max(q7, abs(float(q[6])))
            nxt = np.concatenate([q, [g]])
            chain.append((nxt, steps))
            if via and via[0]:
                continue
            total = sum(n for _, n in chain)
            knots = np.cumsum([0] + [n for _, n in chain]) / total
            pts = np.array([prev] + [p for p, _ in chain])
            for k in range(1, total + 1):
                t = min(1.0, k / max(1, total - 2))
                s = t ** 3 * (10 - 15 * t + 6 * t * t)
                plan.append(np.array([np.interp(s, knots, pts[:, j]) for j in range(pts.shape[1])]))
            prev, chain = nxt, []
        return plan, ik_error, q7

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
    closing = any(w in s for w in ("close", "shut", "push"))
    if "fridge" in s:
        return {"family": "open_fridge", "object": None, "target": None}
    if "wipe" in s or "scrub" in s or "clean" in s:
        return {"family": "wipe_counter", "object": obj, "target": None}
    if "drawer" in s:
        if closing:
            return {"family": "close_drawer", "object": None, "target": None}
        if obj and any(w in s for w in ("put", "place", "move")):
            return {"family": "put_in_drawer", "object": obj, "target": None}
        return {"family": "open_drawer", "object": None, "target": None}
    if "door" in s:
        return {"family": "close_door" if closing else "open_door", "object": None, "target": None}
    if "sink" in s:
        return {"family": "counter_to_sink", "object": obj, "target": next((f for f in fixtures if "sink" in f), None)}
    return {"family": "counter_to_counter", "object": obj, "target": None}


class VLMPlanner:
    """Turns an instruction + scene inventory into a plan JSON with Nemotron; falls back to rule_plan.
    Maintains a response cache so tests and repeated runs execute offline without network."""

    def __init__(self, log=print, cache_path: Path | str | None = None):
        self.log = log
        self.source = None
        self.cache_path = Path(cache_path) if cache_path else Path(__file__).resolve().parents[1] / "models" / "nemotron_cache.json"
        self._cache = self._load_cache()
        self._offline = False  # set by the first network failure so later tasks skip the 60 s timeout

    def _cache_key(self, instruction: str, objects: list[str], fixtures: list[str],
                   research_context: str | None = None) -> str:
        base = f"{instruction.strip().lower()}::{sorted(objects)}::{sorted(fixtures)}"
        if research_context:
            return f"{base}::tavily={hashlib.sha1(research_context.encode()).hexdigest()[:12]}"  # hash() is salted per process
        return base

    def _load_cache(self) -> dict:
        if self.cache_path and self.cache_path.is_file():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception as e:
                self.log(f"[sim] VLMPlanner: cache load failed ({e!r}); starting with empty cache")
                return {}
        return {}

    def _save_cache(self) -> None:
        if not self.cache_path:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache, indent=2) + "\n", encoding="utf-8")
        except Exception as e:
            self.log(f"[sim] VLMPlanner: warning, could not write cache to {self.cache_path}: {e}")

    @staticmethod
    def _parse_plan(txt: str, objects: list[str], fixtures: list[str]) -> dict:
        """First JSON object in the reply, checked against the known families, objects and fixtures."""
        from arrival.sim.tasks import SIM_FAMILIES

        plan, _ = json.JSONDecoder().raw_decode(txt[txt.index("{"):])
        if not isinstance(plan, dict) or plan.get("family") not in SIM_FAMILIES:
            raise ValueError(f"plan has no known family: {plan!r}")
        if plan.get("object") is not None and plan["object"] not in objects:
            raise ValueError(f"plan object {plan['object']!r} is not in the scene")
        if plan.get("target") is not None and plan["target"] not in fixtures:
            raise ValueError(f"plan target {plan['target']!r} is not in the scene")
        return {"family": plan["family"], "object": plan.get("object"), "target": plan.get("target")}

    def plan(self, instruction: str, objects: list[str], fixtures: list[str],
             research_context: str | None = None) -> dict:
        from arrival.models.token_factory import TokenFactoryNotConfigured, complete

        key = self._cache_key(instruction, objects, fixtures, research_context)
        if key in self._cache:
            self.source = "cache"
            return dict(self._cache[key])
        if self._offline:
            self.source = "rule_based"
            return rule_plan(instruction, objects, fixtures)

        try:
            user_payload = {"instruction": instruction, "objects": objects, "fixtures": fixtures}
            if research_context:
                user_payload["research_context"] = research_context
            txt = complete([{"role": "system", "content": "Return only JSON: {\"family\": one of counter_to_sink|"
                             "counter_to_counter|open_drawer|open_door|close_drawer|close_door|put_in_drawer|wipe_counter|open_fridge, \"object\": id|null, \"target\": id|null}"},
                            {"role": "user", "content": json.dumps(user_payload)}], role="super")
            plan = self._parse_plan(txt, objects, fixtures)
            self.source = "token_factory"
            self._cache[key] = plan
            self._save_cache()
        except TokenFactoryNotConfigured as e:
            self.log(f"[sim] VLMPlanner: Token Factory not configured ({e}); using rule-based parser")
            plan, self.source = rule_plan(instruction, objects, fixtures), "rule_based"
        except Exception as e:  # network / parse errors also fall back, loudly
            if isinstance(e, OSError):  # URLError and timeouts: the endpoint is down, do not retry it per task
                self._offline = True
                self.log("[sim] VLMPlanner: endpoint unreachable; rule-based parser for the rest of this run")
            self.log(f"[sim] VLMPlanner: model call failed ({e!r}); using rule-based parser")
            plan, self.source = rule_plan(instruction, objects, fixtures), "rule_based"
        return plan


class VLANotConfigured(RuntimeError):
    pass


class VLAClient(Policy):
    """Client for a GR00T N1.x policy server (e.g. gr00t inference service behind an HTTP shim).

    POST {GR00T_POLICY_URL}/act  JSON:
      {"video.ego_view": <base64 PNG HxWx3 uint8>, "video.wrist": <base64 PNG>, "state.single_arm": [7],
       "state.gripper": [1], "annotation.human.task_description": "<instruction>"}
    Response: {"action.single_arm": [[7], ...], "action.gripper": [[1], ...]}  (absolute joint targets, chunk)
    Matches meta/modality.json of datasets written by `arrival sim`; the wire helpers live in
    arrival.policy_server.protocol, which also checks the response (ProtocolError, a ValueError).
    """

    def __init__(self, url: str | None = None, timeout: float = 10.0):
        from arrival import config as settings

        self.url = url or settings.get("GR00T_POLICY_URL")
        if not self.url:
            raise VLANotConfigured("GR00T_POLICY_URL is not set; start a GR00T policy server and export its URL.")
        self.timeout = timeout
        self.queue: list[np.ndarray] = []

    def reset(self, env, task: dict) -> None:
        self.instruction = task["instruction"]
        self.queue = []

    def act(self, obs: dict) -> np.ndarray:
        if not self.queue:
            from arrival.policy_server.protocol import decode_response, encode_request

            body = json.dumps(encode_request(obs, self.instruction)).encode()
            req = urllib.request.Request(self.url.rstrip("/") + "/act", data=body, method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                self.queue = list(decode_response(json.load(r)))
        return np.asarray(self.queue.pop(0), dtype=float)
