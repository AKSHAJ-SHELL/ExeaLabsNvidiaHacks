"""Sim task families: counter_to_sink, counter_to_counter (when reachable), open_drawer, open_door."""

from __future__ import annotations

import random

from arrival.catalog.objects import PICKABLE
from arrival.tasks.propose import LIGHTING, POSE_OFFSETS, WORDINGS, top_z

SIM_FAMILIES = ("counter_to_sink", "counter_to_counter", "open_drawer", "open_door")
REACH = 0.78  # max horizontal eef reach from the arm base used when placing the base
SIM_WORDINGS = {
    **WORDINGS,
    "open_drawer": ["Open the top drawer.", "Pull the top drawer of the {name} open.",
                    "Slide open the drawer under the counter."],
    "open_door": ["Open the cabinet door.", "Swing the {name} cabinet door open.", "Pull the cabinet door open."],
}


def _fx(twin: dict, fid: str) -> dict:
    return next(f for f in twin["fixtures"] if f["id"] == fid)


def make_tasks(twin: dict, families: list[str], n: int, seed: int = 0, people: int = 0,
               log=print) -> list[dict]:
    """n task variations cycling through the requested families; unreachable families are skipped and logged."""
    rng = random.Random(seed)
    counters = [f for f in twin["fixtures"] if f["type"] == "counter"]
    sinks = [f for f in twin["fixtures"] if f["type"] == "sink"]
    pools: dict[str, list[dict]] = {}
    for fam in families:
        pool = []
        if fam in ("counter_to_sink", "counter_to_counter"):
            for o in twin["objects"]:
                if o["catalog_id"] not in PICKABLE:  # bowl, plate and pan are wider than the gripper opening
                    continue
                src = next((c for c in counters if abs(o["position"][0] - c["position"][0]) < c["size"][0] / 2), None)
                if src is None:
                    continue
                if fam == "counter_to_sink":
                    tgts = [s for s in sinks if abs(s["position"][0] - o["position"][0]) < 2 * REACH - 0.3]
                    tgt_xy = [(s, s["position"][0]) for s in tgts]
                else:
                    tgt_xy = []
                    for c in counters:
                        if c is src:
                            continue
                        edge = c["position"][0] - (c["size"][0] / 2 - 0.12) * (1 if c["position"][0] > o["position"][0] else -1)
                        if abs(edge - o["position"][0]) < 1.0:  # base sits between source and target
                            tgt_xy.append((c, edge))
                for tgt, tx in tgt_xy:
                    pool.append({"object_id": o["id"], "object_label": o["label"], "source": src["id"],
                                 "target": tgt["id"], "target_x": tx, "start": list(o["position"])})
        elif fam in ("open_drawer", "open_door"):
            pool = [{"fixture": c["id"], "name": c["id"].replace("_", " ")} for c in counters]
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
        w = rng.randrange(len(SIM_WORDINGS[fam]))
        name = v.get("object_label") or v.get("name")
        t = {"family": fam, "lighting": light, "wording_index": w, "people": people, "seed": seed * 1000 + i,
             "instruction": SIM_WORDINGS[fam][w].format(name=name), **v}
        if "start" in v:
            off = rng.choice(POSE_OFFSETS)
            t["start"] = [v["start"][0] + off[0], v["start"][1] + off[1] * 0.5,
                          top_z(_fx(twin, v["source"])) + 0.06]
        t["task_id"] = f"sim_{fam}_{i:04d}"
        tasks.append(t)
    return tasks
