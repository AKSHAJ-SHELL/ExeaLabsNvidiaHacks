"""Scripted retarget generator. NOT physics and NOT MimicGen: seed cartesian trajectories
translated to new start poses, with the target point recomputed from the fixtures."""

from __future__ import annotations

from arrival.tasks.propose import shuffled, top_z

FPS = 20
SEG = 16
N_FRAMES = 5 * SEG
HOVER = 0.18
GRASP = 0.02
LIFT = 0.20
RISE = 0.15


def is_miss(attempt_index: int) -> bool:
    """Attempt indexes 9, 19, 29, ... are scripted misses (gripper never closes)."""
    return attempt_index % 10 == 9


def target_point(task: dict, twin: dict) -> list[float]:
    fixtures = {f["id"]: f for f in twin["fixtures"]}
    target = fixtures[task["target_fixture_id"]]
    if task["family"] == "counter_to_sink":
        return [target["position"][0], target["position"][1], top_z(target) + 0.02]
    return [target["position"][0], target["position"][1], top_z(target) + task["object_size"][2] / 2]


def _lerp(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(len(a))]


def seed_trajectory(start: list[float], target: list[float], miss: bool = False) -> list[dict]:
    """80 frames, piecewise linear in cartesian space, 16 frames per segment."""
    sx, sy, sz = start
    hover, low = [sx, sy, sz + HOVER], [sx, sy, sz + GRASP]
    lifted_eef, lifted_obj = [sx, sy, sz + LIFT], [sx, sy, sz + LIFT]
    carried = [target[0], target[1], sz + LIFT]
    risen = [target[0], target[1], sz + LIFT + RISE]
    frames = []
    for i in range(N_FRAMES):
        seg, k = divmod(i, SEG)
        t = k / (SEG - 1)
        if seg == 0:
            eef, grip, obj = _lerp(hover, low, t), 0.0, list(start)
        elif seg == 1:
            eef, grip, obj = list(low), t, list(start)
        elif seg == 2:
            eef, grip, obj = _lerp(low, lifted_eef, t), 1.0, _lerp(list(start), lifted_obj, t)
        elif seg == 3:
            eef, grip, obj = _lerp(lifted_eef, carried, t), 1.0, _lerp(lifted_obj, carried, t)
        else:
            eef = _lerp(carried, risen, t)
            grip = max(0.0, 1.0 - k / 7) if k < 8 else 0.0
            obj = list(target)
        if miss:
            grip, obj = 0.0, list(start)
        frames.append({
            "t": round(i / FPS, 6),
            "joint": [0.0] * 7,
            "gripper": round(grip, 6),
            "eef": [round(v, 6) for v in eef],
            "object_position": [round(v, 6) for v in obj],
        })
    return frames


def retarget(seed_frames: list[dict], seed_start: list[float], task: dict, target: list[float],
             miss: bool = False) -> list[dict]:
    """Translate the seed's approach (hover/grasp/lift) by start delta; recompute carry/release to target."""
    d = [task["start_position"][i] - seed_start[i] for i in range(3)]
    if not any(abs(v) > 1e-12 for v in d) and not miss:
        return [dict(f) for f in seed_frames]
    start = [seed_start[i] + d[i] for i in range(3)]
    fresh = seed_trajectory(start, target, miss=miss)
    # Approach segments are a pure translation of the seed: copy them translated to keep the seed's shape.
    if not miss:
        for i in range(3 * SEG):
            f = seed_frames[i]
            fresh[i]["eef"] = [round(f["eef"][j] + d[j], 6) for j in range(3)]
            fresh[i]["object_position"] = [round(f["object_position"][j] + d[j], 6) for j in range(3)]
    return fresh


def seed_key(task: dict) -> tuple:
    return (task["family"], task["object_id"])


def build_seeds(tasks: list[dict], twin: dict) -> dict:
    """Seeds: scanned pose (pose_index 0), neutral lighting, wording template 1."""
    seeds = {}
    # Prefer the scanned pose; if the counter inset rejected it, fall back to the lowest surviving pose.
    for t in sorted(tasks, key=lambda t: t["pose_index"]):
        if t["lighting"] == "neutral" and t["wording_index"] == 1 and seed_key(t) not in seeds:
            seeds[seed_key(t)] = (list(t["start_position"]), seed_trajectory(t["start_position"], target_point(t, twin)))
    return seeds


def make_attempt(attempt_index: int, task: dict, twin: dict, seeds: dict) -> dict:
    from arrival.generate.oracle import judge

    miss = is_miss(attempt_index)
    target = target_point(task, twin)
    seed_start, seed_frames = seeds[seed_key(task)]
    frames = retarget(seed_frames, seed_start, task, target, miss=miss)
    attempt = {"attempt_index": attempt_index, "task": task, "fps": FPS, "frames": frames, "target": target}
    attempt["success"] = judge(attempt)
    return attempt


def generate(tasks: list[dict], twin: dict, episodes: int, seed: int = 0):
    """Yield attempts until `episodes` successes or `2 * episodes` attempts."""
    order = shuffled(tasks, seed)
    if not order:
        raise ValueError("no tasks to generate from")
    seeds = build_seeds(tasks, twin)
    successes = 0
    i = 0
    while successes < episodes and i < 2 * episodes:
        att = make_attempt(i, order[i % len(order)], twin, seeds)
        successes += att["success"]
        yield att
        i += 1


def count_attempts(episodes: int) -> dict:
    """Attempt/success/drop counts for N successes under the miss pattern, without generating frames."""
    successes = attempts = 0
    while successes < episodes and attempts < 2 * episodes:
        successes += not is_miss(attempts)
        attempts += 1
    return {"attempts": attempts, "successes": successes, "dropped": attempts - successes}
