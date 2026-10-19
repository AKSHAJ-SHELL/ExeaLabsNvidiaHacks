"""Sim task families: counter_to_sink, counter_to_counter (when reachable), open_drawer, open_door."""

from __future__ import annotations

import math
import random

from arrival.catalog.objects import PICKABLE
from arrival.tasks.propose import LIGHTING, POSE_OFFSETS, WORDINGS, top_z
from arrival.sim.scene import stand_is_clear
from arrival.twin.compile import is_counter_host, to_local, to_world

SIM_FAMILIES = ("counter_to_sink", "counter_to_counter", "open_drawer", "open_door", "close_drawer", "close_door",
                "put_in_drawer", "wipe_counter")
REACH = 0.78  # max horizontal eef reach from the arm base used when placing the base
BASE_CLEAR = 0.15  # the base column is 0.12 m in radius
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
}


def _fx(twin: dict, fid: str) -> dict:
    return next(f for f in twin["fixtures"] if f["id"] == fid)


def _holder(o: dict, counters: list[dict]) -> dict | None:
    """The counter whose top the object stands on, judged in the counter's own frame (any wall, any yaw)."""
    for c in counters:
        lx, ly = to_local(o["position"], c)
        if abs(lx) < c["size"][0] / 2 and abs(ly) < c["size"][1] / 2:
            return c
    return None


def make_tasks(twin: dict, families: list[str], n: int, seed: int = 0, people: int = 0, holdout: bool = False,
               split: str = "train", use_generated_instructions: bool = False,
               log=print) -> list[dict]:
    """n task variations cycling through the requested families; unreachable families are skipped and logged.
    holdout=False draws the training set: wording HOLDOUT_WORDING (families with 4 templates) and HOLDOUT_OFFSET
    are excluded. holdout=True draws only those; families with 3 templates keep all 3 either way.
    use_generated_instructions draws from the Nemotron cache (or the template fallback) for `split` instead."""
    rng = random.Random(seed)
    counters = [f for f in twin["fixtures"] if is_counter_host(f)]
    sinks = [f for f in twin["fixtures"] if f["type"] == "sink"]
    pools: dict[str, list[dict]] = {}
    for fam in families:
        pool = []
        if fam in ("counter_to_sink", "counter_to_counter"):
            for o in twin["objects"]:
                # bowl is held by its rim (MAN-4); plate, pan and spatula stay out of the pick pool
                if o["catalog_id"] not in PICKABLE + ("bowl",):
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
            pool = [{"fixture": c["id"], "name": c["id"].replace("_", " ")} for c in counters
                    if stand_is_clear(c, fam, twin["fixtures"], BASE_CLEAR)]
        if not pool:
            log(f"[sim] family {fam}: no reachable variation in this room for a fixed-base arm; skipped")
            continue
        pools[fam] = pool
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
            w = rng.randrange(len(options))
            instr = options[w]
        else:
            words = SIM_WORDINGS[fam]
            w = rng.choice([k for k in range(len(words)) if len(words) <= HOLDOUT_WORDING or (k == HOLDOUT_WORDING) == holdout])
            instr = words[w].format(name=name)
        t = {"family": fam, "lighting": light, "wording_index": w, "people": people, "seed": seed * 1000 + i,
             "holdout": holdout, "instruction": instr, "split": split, **v}
        if "start" in v:
            off = rng.choice([o for o in POSE_OFFSETS if (list(o) == HOLDOUT_OFFSET) == holdout])
            src = _fx(twin, v["source"])
            co, si = math.cos(src.get("yaw", 0.0)), math.sin(src.get("yaw", 0.0))  # offsets run along the counter
            t["start"] = [v["start"][0] + co * off[0] - si * off[1] * 0.5, v["start"][1] + si * off[0] + co * off[1] * 0.5,
                          top_z(src) + 0.06]
        t["task_id"] = f"sim_{fam}_{i:04d}"
        tasks.append(t)
    return tasks
