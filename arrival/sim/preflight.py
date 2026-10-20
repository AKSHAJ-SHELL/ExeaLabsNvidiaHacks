"""Where the base stands for a task, and a cheap geometric pre-flight on that spot, before any MuJoCo model is built.

`base_pose` is the one place the stand rule lives (SimEnv uses it too), written in the fixture's own frame so it holds
on any wall. `check_task` then rejects a task whose stand spot is outside the room, too close to a wall or a fixture,
or whose pick, place or stroke points lie beyond the arm's horizontal reach. It is geometry only: the reach test is
the horizontal envelope REACH, not an IK solve, so a task that passes can still miss in physics (that is counted as a
dropped attempt, not a skip), but a layout the base cannot stand in never costs sim time or a traceback.
"""

from __future__ import annotations

import math

import numpy as np

from arrival.sim.scene import drawer_x, front_stand
from arrival.twin.compile import is_counter_host, to_local, to_world

REACH = 0.745  # farthest horizontal point the hand holds a mug from, measured: put_in_drawer on the rotated
# kitchen's east run succeeded with the mug 0.742 m from the base and missed at 0.75, 0.76 and 0.77 m
BASE_CLEAR = 0.15  # the base column is 0.12 m in radius
WALL_CLEAR = 0.15  # base centre to the wall's face
STROKE = 0.15  # wipe_counter strokes run this far either side of the sponge, along the counter
DRAWER_OPEN_PUT = 0.14  # start state for put_in_drawer: wide enough for a mug on the exposed tray, and the base
# can then park straight in front without the pulled-out front reaching its column
FRIDGE_BASE_ALONG = 0.1  # base centre past the door's free edge, along the front
FRIDGE_BASE_OUT = 0.75  # base centre out from the fridge front: nearer, the handle's arc folds the elbow onto its stop
FRIDGE_BASE_YAW = 0.0  # degrees the base turns toward the hinge from facing the front
FLAP_MARGIN = 0.06  # open_oven / open_dishwasher: base column edge to where the open door's top edge lands
FAUCET_STANDOFF = 0.34  # base column to counter front for turn_on_faucet (0.28 elsewhere): the lever is at the back
# of the counter above shoulder height, and a horizontal hand reaches it with less joint strain from further out
ARM_STANDOFF_TRIM = {"procedural": 0.0, "menagerie": 0.02}  # the real hand's closed fingertips reach 8 mm past the eef,
# the procedural fingers 23 mm: the faucet push stands 2 cm closer with it (0.34 misses the lever, 0.32 turns it to 1.10 rad)
DISHWASHER_SIDE = 0.55  # load/unload_dishwasher: the base parks this far beside the dishwasher centre, clear of its door
RACK_FRONT = 0.15  # the rack spot an object is set into (or taken from) lies this far out from the dishwasher front
FLAP_DOOR_BELOW = {"open_oven": 0.24, "open_dishwasher": 0.18}  # fixture height minus the door's height, per family
PICK_PLACE = ("counter_to_sink", "counter_to_counter")
MOBILE_STEP = 0.3  # a mobile base parks this far along the source run toward the target, as counter_to_sink parks
# between the object and the sink; it then drives to `drive_spot` once the object is held


def front(f: dict) -> np.ndarray:
    """Unit normal out of a fixture's front face (local +y), in the world."""
    y = f.get("yaw", 0.0)
    return np.array([-np.sin(y), np.cos(y), 0.0])


def corners(f: dict) -> list[tuple[float, float]]:
    hx, hy = f["size"][0] / 2, f["size"][1] / 2
    return [to_world((dx, dy), f) for dx in (-hx, hx) for dy in (-hy, hy)]


def top(f: dict) -> float:
    return f["position"][2] + f["size"][2] / 2


def park(c: dict, along: float, out: float) -> tuple[float, float, float]:
    """Base centre `along` the fixture's run (its local x) and `out` beyond its front face."""
    yaw, d = c.get("yaw", 0.0), c["size"][1] / 2 + out
    return (c["position"][0] + np.cos(yaw) * along - np.sin(yaw) * d,
            c["position"][1] + np.sin(yaw) * along + np.cos(yaw) * d, 0.75)


def place_point(twin: dict, task: dict) -> np.ndarray:
    """Where a counter_to_sink / counter_to_counter / move_on_table task sets the object down (eef target, world)."""
    fx = {f["id"]: f for f in twin["fixtures"]}
    tgt = fx[task["target"]]
    hh = next(o for o in twin["objects"] if o["id"] == task["object_id"])["size"][2] / 2
    if "target_xy" in task:  # move_on_table: a spot on the same table
        return np.array([task["target_xy"][0], task["target_xy"][1], top(tgt) + hh + 0.012])
    tops = max(top(f) for f in twin["fixtures"] if is_counter_host(f)) if tgt["type"] == "sink" else top(tgt)
    if tgt["type"] == "sink":
        return np.array([tgt["position"][0], tgt["position"][1], tops + hh + 0.05])
    return np.array([task["target_x"], task.get("target_y", tgt["position"][1]), tops + hh + 0.012])


def mobile_drive(task: dict, mobile: bool) -> bool:
    """True when the base drives during this task: only counter_to_counter does, and only on a mobile base."""
    return mobile and task["family"] == "counter_to_counter"


def drive_spot(twin: dict, task: dict) -> tuple[float, float, float]:
    """Where a mobile base stands to set the object down: in front of the place point, the same 0.28 m out from the
    target counter's front that the parked pose keeps from the source's. World xy and the stand height."""
    tgt = next(f for f in twin["fixtures"] if f["id"] == task["target"])
    return park(tgt, to_local(place_point(twin, task)[:2], tgt)[0], 0.28)


def faucet_counter(twin: dict, sink: dict) -> dict:
    """The counter run the sink is set into (its frame holds the sink's centre); the lever is pushed from in front of it."""
    for c in twin["fixtures"]:
        if is_counter_host(c):
            lx, ly = to_local(sink["position"][:2], c)
            if abs(lx) < c["size"][0] / 2 and abs(ly) < c["size"][1] / 2:
                return c
    raise StopIteration(f"no counter run holds {sink['id']}")


def rack_spot(d: dict) -> tuple[float, float]:
    """World xy in the middle of the part of a dishwasher's upper rack that is out past its front."""
    n = front(d)
    out = d["size"][1] / 2 + RACK_FRONT
    return float(d["position"][0] + n[0] * out), float(d["position"][1] + n[1] * out)


def base_pose(twin: dict, task: dict, obj_xy=None, mobile: bool = False, arm: str = "procedural"
              ) -> tuple[tuple[float, float, float], float, dict]:
    """(base position, base yaw in degrees, anchor fixture): in front of the fixture the task works at, facing it,
    on any wall. `obj_xy` is the object's xy at the start (the task's `start` when omitted). `mobile` moves the
    counter_to_counter stand spot MOBILE_STEP toward the target instead of midway: the base drives the rest.
    `arm` trims the stand spots that push with the closed fingertips (ARM_STANDOFF_TRIM)."""
    fx = {f["id"]: f for f in twin["fixtures"]}
    fam, fixtures = task["family"], twin["fixtures"]
    if obj_xy is None and "object_id" in task:
        obj_xy = task["start"][:2]
    yaw_off = 0.0
    if mobile_drive(task, mobile):
        src = fx[task["source"]]
        ox, tx = to_local(obj_xy[:2], src)[0], to_local(place_point(twin, task)[:2], src)[0]
        base = park(src, ox + MOBILE_STEP * float(np.sign(tx - ox)), 0.28)
    elif fam == "move_on_table":
        # at the table edge nearer the object (task["side"] is +1 or -1 along the table's local y), halfway between
        # where the object starts and where it goes, facing in
        src = fx[task["source"]]
        ox, tx = to_local(obj_xy[:2], src)[0], to_local(task["target_xy"], src)[0]
        base = to_world(((ox + tx) / 2, task["side"] * (src["size"][1] / 2 + 0.28)), src) + (0.75,)
        n = task["side"] * front(src)
        return base, float(np.degrees(np.arctan2(-n[1], -n[0]))), src
    elif fam in PICK_PLACE:
        src = fx[task["source"]]
        mid = (np.array(obj_xy[:2]) + place_point(twin, task)[:2]) / 2
        base = park(src, to_local(mid, src)[0], 0.28)
    elif fam == "wipe_counter":
        src = fx[task["source"]]
        base = park(src, to_local(obj_xy[:2], src)[0], 0.28)
    elif fam == "put_in_drawer":
        # straight in front, between the mug and the drawer, just beyond the pulled-out front and its handle;
        # parking beside the drawer instead puts the elbow into whatever appliance flanks the counter
        src = fx[task["fixture"]]
        along = (drawer_x(src, fixtures) + to_local(obj_xy[:2], src)[0]) / 2
        base = park(src, along, DRAWER_OPEN_PUT + 0.07 + 0.14)  # front + handle bar + base column + margin
    elif fam in FLAP_DOOR_BELOW:
        # straight in front of the bar, just far enough out that the door swings all the way down to flat without
        # its top edge reaching the base column; parking beside the swing instead puts the wrist under the arm for a
        # horizontal grasp
        src = fx[task["fixture"]]
        base = park(src, 0.0, src["size"][2] - FLAP_DOOR_BELOW[fam] + 0.12 + FLAP_MARGIN)
    elif fam == "turn_on_faucet":
        # in front of the counter run at the sink, closer than for counter_to_sink: the lever is at the back of the
        # counter, at the edge of what a horizontal hand reaches from the usual parking spot
        sink = fx[task["fixture"]]
        src = faucet_counter(twin, sink)
        base = park(src, to_local(sink["position"][:2], src)[0], FAUCET_STANDOFF - ARM_STANDOFF_TRIM[arm])
    elif fam in ("load_dishwasher", "unload_dishwasher"):
        # beside the dishwasher, in front of the counter, so the flat door and the rolled-out rack stay clear of the
        # base column and both the rack and the counter spot are within reach
        src = fx[task["fixture"]]
        base = park(src, math.copysign(DISHWASHER_SIDE, to_local(obj_xy[:2], src)[0]), 0.28)
    elif fam == "open_fridge":
        # beside the door's free edge and out of its swing (the hinge is on the fixture's left edge), facing the
        # front like the cabinet door tasks
        src = fx[task["fixture"]]
        base = park(src, src["size"][0] / 2 + FRIDGE_BASE_ALONG, FRIDGE_BASE_OUT)
        yaw_off = -FRIDGE_BASE_YAW
    else:
        src = fx[task["fixture"]]
        base = park(src, *front_stand(src, fam, fixtures))
    n = front(src)
    return base, float(np.degrees(np.arctan2(-n[1], -n[0])) + yaw_off), src


def _segment_distance(p, a, b) -> float:
    a, b, p = np.asarray(a, float), np.asarray(b, float), np.asarray(p, float)
    ab = b - a
    t = float(np.clip((p - a) @ ab / max(float(ab @ ab), 1e-12), 0.0, 1.0))
    return float(np.linalg.norm(a + t * ab - p))


def _footprint_distance(xy, f: dict) -> float:
    lx, ly = to_local(xy, f)
    return math.hypot(max(abs(lx) - f["size"][0] / 2, 0.0), max(abs(ly) - f["size"][1] / 2, 0.0))


def reach_points(twin: dict, task: dict, obj_xy=None, mobile: bool = False) -> list[tuple[str, np.ndarray]]:
    """The horizontal points the hand must reach for the task: the object, where it goes, the wipe strokes.
    Drawer, door and fridge tasks have none here: their stand spot is derived from the part's own geometry.
    On a mobile base the place point is measured from the drive spot, not from the parked pose (see `check_task`)."""
    fam = task["family"]
    if obj_xy is None and "object_id" in task:
        obj_xy = task["start"][:2]
    if mobile_drive(task, mobile):
        return [("the object", np.array(obj_xy[:2]))]
    if fam in PICK_PLACE or fam == "move_on_table":
        return [("the object", np.array(obj_xy[:2])), ("the place point", place_point(twin, task)[:2])]
    if fam == "put_in_drawer":
        src = next(f for f in twin["fixtures"] if f["id"] == task["fixture"])
        tray = np.array(to_world((drawer_x(src, twin["fixtures"]), src["size"][1] / 2 + DRAWER_OPEN_PUT / 2), src))
        return [("the object", np.array(obj_xy[:2])), ("the drawer tray", tray)]
    if fam in ("load_dishwasher", "unload_dishwasher"):
        d = next(f for f in twin["fixtures"] if f["id"] == task["fixture"])
        return [("the object", np.array(obj_xy[:2])), ("the rack", np.array(rack_spot(d)))]
    if fam == "wipe_counter":
        src = next(f for f in twin["fixtures"] if f["id"] == task["source"])
        u = np.array([math.cos(src.get("yaw", 0.0)), math.sin(src.get("yaw", 0.0))])
        p = np.array(obj_xy[:2])
        return [("the object", p), ("the stroke end", p + STROKE * u), ("the stroke end", p - STROKE * u)]
    return []


def _stand_problem(twin: dict, b, anchor: dict, what: str = "base stand spot") -> str | None:
    walls = twin.get("walls") or []
    if walls:
        xs = [p[0] for w in walls for p in (w["start"], w["end"])]
        ys = [p[1] for w in walls for p in (w["start"], w["end"])]
        if not (min(xs) < b[0] < max(xs) and min(ys) < b[1] < max(ys)):
            return f"{what} ({b[0]:.2f}, {b[1]:.2f}) at {anchor['id']} is outside the room"
        for w in walls:
            d = _segment_distance(b, w["start"], w["end"]) - w.get("thickness", 0.0) / 2
            if d < WALL_CLEAR:
                return f"{what} at {anchor['id']} is {max(d, 0.0):.2f} m from {w.get('id', 'a wall')}, needs {WALL_CLEAR:.2f} m"
    for f in twin["fixtures"]:
        d = _footprint_distance(b, f)
        if d < BASE_CLEAR:
            return f"{what} at {anchor['id']} is {d:.2f} m from {f['id']}, needs {BASE_CLEAR:.2f} m"
    return None


def check_task(twin: dict, task: dict, obj_xy=None, mobile: bool = False) -> str | None:
    """None when the base can stand where the task needs it and reach what it needs; otherwise one sentence saying
    why not. `task` is a pool entry (fixture, or object_id, source and start) or a finished task. On a mobile base
    a counter_to_counter task is checked at both stand spots and along the straight drive between them."""
    try:
        base, _, anchor = base_pose(twin, task, obj_xy, mobile)
    except (KeyError, StopIteration, IndexError, TypeError, ValueError) as e:  # a task naming a fixture the twin lacks
        return f"no stand spot: the task does not match the twin ({type(e).__name__}: {e})"
    b = np.array(base[:2])
    why = _stand_problem(twin, b, anchor)
    if why:
        return why
    if mobile_drive(task, mobile):
        end = np.array(drive_spot(twin, task)[:2])
        for k in range(1, 9):  # the drive is one straight line: its whole length must be clear, not just its ends
            why = _stand_problem(twin, b + (end - b) * k / 8, anchor, "base drive path")
            if why:
                return why
        d = float(np.linalg.norm(place_point(twin, task)[:2] - end))
        if d > REACH:
            return f"the place point is {d:.2f} m from the drive spot at {anchor['id']}, beyond the {REACH:.3f} m reach"
    for what, p in reach_points(twin, task, obj_xy, mobile):
        d = float(np.linalg.norm(np.asarray(p) - b))
        if d > REACH:
            return f"{what} is {d:.2f} m from the base at {anchor['id']}, beyond the {REACH:.3f} m reach"
    return None
