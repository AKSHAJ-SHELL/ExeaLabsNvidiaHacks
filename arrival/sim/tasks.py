"""Sim task families: counter_to_sink, counter_to_counter (when reachable), open_drawer, open_door, the close and
put-away families, wipe_counter and open_fridge."""

from __future__ import annotations

import math
import random

from arrival.catalog.objects import GRASPABLE
from arrival.tasks.propose import LIGHTING, POSE_OFFSETS, WORDINGS, top_z
from arrival.sim.preflight import check_task
from arrival.twin.compile import is_counter_host, to_local, to_world

REACH = 0.78  # max horizontal eef reach from the arm base used when placing the base
SIM_FAMILIES = ("counter_to_sink", "counter_to_counter", "open_drawer", "open_door", "close_drawer", "close_door",
                "put_in_drawer", "wipe_counter", "open_fridge")
HOLDOUT_WORDING = 3  # docs/07-eval.md: template 4 and the (0, +0.08) offset are for evaluation only
HOLDOUT_OFFSET = [0.0, 0.08]
SIM_WORDINGS = {
    **WORDINGS,
    "open_drawer": ["Open the top drawer.", "Pull the top drawer of the {name} open.",
                    "Slide open the drawer under the counter."],
    "open_door": ["Open the cabinet door.", "Swing the {name} cabinet door open.", "Pull the cabinet door open."],
    "close_drawer": ["Close the drawer.", "Push the open drawer of the {name} shut.", "Slide the drawer closed."],
    "close_door": ["Close the cabinet door.", "Push the {name} cabinet door shut.", "Swing the open door closed."],
    "put_in_drawer": ["Put the {name} in the open drawer.", "Place the {name} into the drawer.",
                      "Move the {name} from the counter into the drawer."],
    "wipe_counter": ["Wipe the counter with the {name}.", "Clean the counter top with the {name}.",
                     "Scrub the counter using the {name}."],
    "open_fridge": ["Open the fridge.", "Pull the {name} door open.", "Swing the fridge door open."],
}


def finish_task(t: dict) -> dict:
    """Add the handle/joint names the scripted policy and the success check read; shared by collect and eval."""
    if t["family"] in ("open_drawer", "close_drawer", "put_in_drawer"):
        t["handle"], t["joint"] = f'{t["fixture"]}_drawer0_handle', f'{t["fixture"]}_drawer0'
    elif t["family"] in ("open_door", "close_door", "open_fridge"):
        t["joint"] = f'{t["fixture"]}_door'
    return t


def _fx(twin: dict, fid: str) -> dict:
    return next(f for f in twin["fixtures"] if f["id"] == fid)


def _holder(o: dict, counters: list[dict]) -> dict | None:
    """The counter whose top the object stands on, judged in the counter's own frame (any wall, any yaw)."""
    for c in counters:
        lx, ly = to_local(o["position"], c)
        if abs(lx) < c["size"][0] / 2 and abs(ly) < c["size"][1] / 2:
            return c
    return None


def _offset_start(src: dict, start, off) -> list[float]:
    """`start` moved by a POSE_OFFSETS entry, which runs along the source counter (its local x, and y at half)."""
    co, si = math.cos(src.get("yaw", 0.0)), math.sin(src.get("yaw", 0.0))
    return [start[0] + co * off[0] - si * off[1] * 0.5, start[1] + si * off[0] + co * off[1] * 0.5]


def _start_variants(twin: dict, v: dict) -> list:
    """The object's xy for every offset make_tasks may apply (train and held-out); [None] for tasks without one."""
    if "start" not in v:
        return [None]
    src = _fx(twin, v["source"])
    return [_offset_start(src, v["start"], off) for off in POSE_OFFSETS]


def make_tasks(twin: dict, families: list[str], n: int, seed: int = 0, people: int = 0, holdout: bool = False,
               split: str = "train", use_generated_instructions: bool = False,
               log=print, preflight: dict | None = None) -> list[dict]:
    """n task variations cycling through the requested families. Every candidate variation first passes the
    geometric pre-flight (`arrival.sim.preflight.check_task`: stand spot inside the room and clear of walls and
    fixtures, pick and place points within the arm's horizontal reach); a rejected one is logged with its reason and
    never becomes a task, and a family left with none is skipped. When `preflight` is a dict it is filled with
    {"rejected": count, "families": [skipped families], "reasons": [{"family", "reason"}, ...]}.
    holdout=False draws the training set: wording HOLDOUT_WORDING (families with 4 templates) and HOLDOUT_OFFSET
    are excluded. holdout=True draws only those; families with 3 templates keep all 3 either way.
    use_generated_instructions draws from the Nemotron cache (or the template fallback) for `split` instead."""
    rng = random.Random(seed)
    counters = [f for f in twin["fixtures"] if is_counter_host(f)]
    sinks = [f for f in twin["fixtures"] if f["type"] == "sink"]
    pools: dict[str, list[dict]] = {}
    pre = preflight if preflight is not None else {}
    pre.update({"rejected": 0, "families": [], "reasons": []})
    for fam in families:
        pool = []
        if fam in ("counter_to_sink", "counter_to_counter"):
            for o in twin["objects"]:
                if o["catalog_id"] not in GRASPABLE:  # the spatula stays out of the pick pool
                    continue
                src = _holder(o, counters)
                if src is None:
                    continue
                ox = to_local(o["position"], src)[0]  # local x: distance along the source run, whatever wall it is on
                if fam == "counter_to_sink":  # a sink set into the same run, within reach along it
                    tgts = [s for s in sinks if abs(to_local(s["position"], src)[0] - ox) < 2 * REACH - 0.3
                            and abs(to_local(s["position"], src)[1]) < src["size"][1] / 2]
                    tgt_xy = [(s, s["position"][0], s["position"][1]) for s in tgts]
                else:
                    tgt_xy = []
                    for c in counters:
                        if c is src or math.cos(c.get("yaw", 0.0) - src.get("yaw", 0.0)) < 0.9:
                            continue  # the target must continue the source run
                        side = 1 if to_local(c["position"], src)[0] > ox else -1
                        tx, ty = to_world((-side * (c["size"][0] / 2 - 0.12), 0.0), c)  # the target's near end
                        if abs(to_local((tx, ty), src)[0] - ox) < 1.0:  # base sits between source and target
                            tgt_xy.append((c, tx, ty))
                for tgt, tx, ty in tgt_xy:
                    pool.append({"object_id": o["id"], "object_label": o["label"], "source": src["id"],
                                 "target": tgt["id"], "target_x": tx, "target_y": ty, "start": list(o["position"])})
        elif fam == "put_in_drawer":
            from arrival.sim.scene import drawer_x
            for o in twin["objects"]:
                if o["catalog_id"] != "mug":
                    continue
                src = _holder(o, counters)
                if src is None or abs(to_local(o["position"], src)[0] - drawer_x(src, twin["fixtures"])) > 0.6:
                    continue  # the base parks beside the open drawer, so the mug must be within reach of that spot
                pool.append({"object_id": o["id"], "object_label": o["label"], "source": src["id"], "fixture": src["id"],
                             "start": list(o["position"])})
        elif fam == "wipe_counter":
            for o in twin["objects"]:
                if o["catalog_id"] != "sponge":
                    continue
                src = _holder(o, counters)
                if src is not None:
                    pool.append({"object_id": o["id"], "object_label": o["label"], "source": src["id"],
                                 "fixture": src["id"], "start": list(o["position"])})
        elif fam in ("open_drawer", "open_door", "close_drawer", "close_door"):
            pool = [{"fixture": c["id"], "name": c["id"].replace("_", " ")} for c in counters]
        elif fam == "open_fridge":
            pool = [{"fixture": f["id"], "name": "fridge"} for f in twin["fixtures"]
                    if f["type"].startswith("fridge")]
        kept = []
        for v in pool:
            why = None
            for xy in _start_variants(twin, v):  # every start pose the offsets can give must be reachable
                why = why or check_task(twin, {"family": fam, **v}, xy)
            if why is None:
                kept.append(v)
            else:
                pre["rejected"] += 1
                pre["reasons"].append({"family": fam, "reason": why})
                log(f"[sim] family {fam}: variation {v.get('object_id') or v['fixture']} rejected by pre-flight: {why}")
        if not kept:
            log(f"[sim] family {fam}: no reachable variation in this room for a fixed-base arm; skipped")
            pre["families"].append(fam)
            continue
        pools[fam] = kept
    tasks = []
    fams = list(pools)
    for i in range(n if fams else 0):
        fam = fams[i % len(fams)]
        v = dict(rng.choice(pools[fam]))
        light = rng.choice(LIGHTING)
        name = v.get("object_label") or v.get("name")
        if use_generated_instructions:
            from arrival.tasks.instructions import generate_instructions
            gen = generate_instructions(fam, object_name=v.get("object_label"), fixture_name=v.get("name"))
            options = gen.get(split, gen.get("train", SIM_WORDINGS[fam]))
            instr = options[rng.randrange(len(options))]
            w = -1  # the generated lists have their own indexing: no template index, and no holdout wording
        else:
            words = SIM_WORDINGS[fam]
            w = rng.choice([k for k in range(len(words)) if len(words) <= HOLDOUT_WORDING or (k == HOLDOUT_WORDING) == holdout])
            instr = words[w].format(name=name)
        t = {"family": fam, "lighting": light, "wording_index": w, "people": people, "seed": seed * 1000 + i,
             "holdout": holdout, "instruction": instr, "split": split, **v}
        if "start" in v:
            off = rng.choice([o for o in POSE_OFFSETS if (list(o) == HOLDOUT_OFFSET) == holdout])
            src = _fx(twin, v["source"])
            t["start"] = [*_offset_start(src, v["start"], off), top_z(src) + 0.06]  # offsets run along the counter
        t["task_id"] = f"sim_{fam}_{i:04d}"
        tasks.append(t)
    return tasks
