import copy

import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")

from arrival.scan.bundle import load_room  # noqa: E402
from arrival.sim import robot  # noqa: E402
from arrival.sim.collect import SimEnv  # noqa: E402
from arrival.sim.people import HEIGHT, Walkers, person_spec  # noqa: E402
from arrival.sim.scene import build_mjcf  # noqa: E402
from arrival.twin.compile import compile_twin  # noqa: E402

TASK = {"family": "counter_to_sink", "object_id": "mug_1", "source": "counter_a", "target": "sink_1",
        "target_x": 1.6, "start": [1.0, 0.35, 0.97], "lighting": "neutral", "people": 2, "seed": 3}
HOLD = np.array(list(robot.HOME) + [robot.FINGER_OPEN])


@pytest.fixture(scope="module")
def twin():
    return compile_twin(load_room("hero_kitchen", "scans"))


def test_people_are_seeded_and_varied():
    assert person_spec(5, 2) == person_spec(5, 2)
    specs = [person_spec(5, i) for i in range(12)]
    heights = [s["height"] for s in specs]
    assert all(HEIGHT[0] <= h <= HEIGHT[1] for h in heights) and max(heights) - min(heights) > 0.1
    assert len({s["shirt"] for s in specs}) > 2 and len({s["skin"] for s in specs}) > 1
    assert person_spec(6, 2) != person_spec(5, 2)
    floor = (0.4, 1.65, 3.6, 2.7)
    a, b = Walkers(3, floor, seed=7), Walkers(3, floor, seed=7)
    assert all(np.array_equal(p, q) for p, q in zip(a.paths, b.paths))


def _thigh_x(env, i):
    return float(env.model.geom_pos[env.model.geom(f"person_{i}_thigh_r").id][0])


def test_limbs_swing_while_walking_and_hang_when_standing(twin):
    env = SimEnv(twin, TASK, res=32)
    m = env.model
    assert m.geom(f"person_0_torso").size[0] > m.geom(f"person_0_thigh_r").size[0]  # torso stays the widest geom
    xs = []
    for _ in range(12):
        env.step(HOLD)
        xs.append(_thigh_x(env, 0))
    assert max(abs(x) for x in xs) > 0.05 and env.walkers.amp[0] > 0.5
    r, l = m.geom_pos[m.geom("person_0_thigh_r").id][0], m.geom_pos[m.geom("person_0_thigh_l").id][0]
    assert r * l < 0  # legs alternate
    ua = m.geom_pos[m.geom("person_0_uarm_r").id][0]
    assert ua * r < 0  # the arm swings against the leg on its side
    env.walkers.speed = 0.0
    for _ in range(30):
        env.step(HOLD)
    assert env.walkers.amp[0] == 0.0 and abs(_thigh_x(env, 0)) < 1e-9
    assert env.data.mocap_pos[0][2] == 0.0


def _inside(twin, xy, z):
    for f in twin["fixtures"]:
        yaw = f.get("yaw", 0.0)
        dx, dy = xy[0] - f["position"][0], xy[1] - f["position"][1]
        lx = np.cos(yaw) * dx + np.sin(yaw) * dy
        ly = -np.sin(yaw) * dx + np.cos(yaw) * dy
        if abs(lx) < f["size"][0] / 2 and abs(ly) < f["size"][1] / 2 and z < f["position"][2] + f["size"][2] / 2:
            return f["id"]
    return None


def test_people_never_clip_through_fixtures(twin):
    t = copy.deepcopy(twin)
    island = {**copy.deepcopy(t["fixtures"][2]), "id": "island_1", "position": [2.0, 2.0, 0.46], "size": [0.6, 0.5, 0.92]}
    t["fixtures"].append(island)
    m = mujoco.MjModel.from_xml_string(build_mjcf(t, (1.3, 1.0, 0.75), n_people=3, people_seed=11))
    d = mujoco.MjData(m)
    walkers = Walkers(3, (0.4, 1.65, 3.6, 2.7), seed=11, fixtures=t["fixtures"])
    geoms = [g for g in range(m.ngeom) if m.geom(g).name.startswith("person_")]
    near_island = False
    for _ in range(600):  # 30 s of walking
        xy = walkers.step(m, d, 0.05)
        mujoco.mj_kinematics(m, d)
        for g in geoms:
            c, half = d.geom_xpos[g], m.geom_size[g][1]
            axis = d.geom_xmat[g].reshape(3, 3)[:, 2] * (half if m.geom_type[g] == mujoco.mjtGeom.mjGEOM_CAPSULE else 0)
            for p in (c - axis, c, c + axis):
                hit = _inside(t, p[:2], p[2])
                assert hit is None, f"{m.geom(g).name} inside {hit} at {np.round(p, 3)}"
        for x, y in xy:
            assert 0.0 < x < 4.0 and 0.0 < y < 3.0
            near_island = near_island or np.hypot(x - 2.0, y - 2.0) < 1.0
    assert near_island  # the paths do go round the island, not just away from it
    assert all(len({tuple(np.round(p, 3)) for p in path}) >= 4 for path in walkers.paths)  # via corners repeat


def test_feet_stay_out_of_the_counter_at_the_stop(twin):
    """With the robot base given, the loop stops 0.35 m from the counter front: the swinging toe reaches further
    than that at full stride, so the walker has to arrive with the swing faded."""
    base, floor = (2.6, 1.0, 0.75), (0.4, 1.65, 3.6, 2.7)
    for seed in (2, 5, 7, 16, 18):
        m = mujoco.MjModel.from_xml_string(build_mjcf(twin, base, n_people=2, people_seed=seed))
        d = mujoco.MjData(m)
        walkers = Walkers(2, floor, seed=seed, base_xy=base[:2], front_y=0.75, fixtures=twin["fixtures"])
        feet = [g for g in range(m.ngeom) if "_foot_" in m.geom(g).name]
        (cx, _, _), (sx, _, _) = next(f for f in twin["fixtures"] if f["id"] == "counter_a")["position"],             next(f for f in twin["fixtures"] if f["id"] == "counter_a")["size"]
        stopped = set()
        for _ in range(400):
            walkers.step(m, d, 0.05)
            mujoco.mj_kinematics(m, d)
            for g in feet:
                c, half = d.geom_xpos[g], m.geom_size[g][1]
                axis = d.geom_xmat[g].reshape(3, 3)[:, 2] * half
                for p in (c - axis, c + axis):
                    assert _inside(twin, p[:2], p[2]) is None, (seed, m.geom(g).name, np.round(p, 3))
            for i in range(2):  # a pause starting in front of counter_a; the fridge visit's pauses sit left of it or deeper
                x, y = walkers.pos[i]
                if (walkers.wait[i] > 0 and abs(walkers.wait[i] - walkers.total[i]) < 1e-9
                        and abs(x - cx) < sx / 2 and y < 1.2):
                    stopped.add(i)
        assert stopped == {0, 1}, (seed, stopped)


def _door_geoms(m):
    return [g for g in range(m.ngeom) if m.geom_bodyid[g] == m.body("fridge_1_door").id]


def test_person_opens_and_closes_the_fridge(twin):
    base = (2.6, 1.0, 0.75)
    m = mujoco.MjModel.from_xml_string(build_mjcf(twin, base, n_people=2, people_seed=3))
    d = mujoco.MjData(m)
    walkers = Walkers(2, (0.4, 1.65, 3.6, 2.7), seed=3, base_xy=base[:2], front_y=0.75, fixtures=twin["fixtures"],
                      fridge_visit=True)
    assert walkers.visit is not None
    who = walkers.visit["person"]
    door, qadr = _door_geoms(m), int(m.joint("fridge_1_door").qposadr[0])
    people = [g for g in range(m.ngeom) if m.geom(g).name.startswith("person_")]
    hand = m.geom(f"person_{who}_farm_r").id
    site = m.site("fridge_1_door_handle").id
    qs, held, on_bar = [], False, False
    for _ in range(240):  # 12 s: open, look, close, walk away
        walkers.step(m, d, 0.05)
        mujoco.mj_kinematics(m, d)
        q = float(d.qpos[qadr])
        qs.append(q)
        held = held or (q > 0.05 and bool(walkers.driven_geoms))
        if 0.05 < q < 0.2 and len(qs) < 60:  # pulling: the hand is on the bar, 9 cm out from the panel
            tip = d.geom_xpos[hand] + d.geom_xmat[hand].reshape(3, 3)[:, 2] * m.geom_size[hand][1]
            on_bar = on_bar or np.linalg.norm(tip - d.site_xpos[site]) < 0.12
        for g in people:
            dist = min(mujoco.mj_geomDistance(m, d, g, h, 1.0, None) for h in door)
            assert dist >= (-0.01 if g == hand else 0.0), (m.geom(g).name, round(q, 3), round(dist, 4))
            c, half = d.geom_xpos[g], m.geom_size[g][1]
            axis = d.geom_xmat[g].reshape(3, 3)[:, 2] * (half if m.geom_type[g] == mujoco.mjtGeom.mjGEOM_CAPSULE else 0)
            for p in (c - axis, c, c + axis):
                assert _inside(twin, p[:2], p[2]) is None, (m.geom(g).name, np.round(p, 3))
    assert max(qs) > 1.0 and abs(max(qs) - walkers.visit["q_open"]) < 1e-6  # opened to the planned angle (57 deg plus)
    assert qs[-1] == 0.0 and not walkers.driven_geoms  # and shut again
    assert max(abs(b - a) for a, b in zip(qs, qs[1:])) < 0.12  # a swing, not a jump
    assert held and on_bar


def test_fridge_visit_is_seeded_and_optional(twin):
    floor, fx = (0.4, 1.65, 3.6, 2.7), twin["fixtures"]
    a = Walkers(2, floor, seed=3, base_xy=(2.6, 1.0), front_y=0.75, fixtures=fx)
    b = Walkers(2, floor, seed=3, base_xy=(2.6, 1.0), front_y=0.75, fixtures=fx)
    assert (a.visit is None) == (b.visit is None)
    if a.visit:
        assert a.visit["person"] == b.visit["person"] and a.visit["q_open"] == b.visit["q_open"]
    none = Walkers(2, floor, seed=3, base_xy=(2.6, 1.0), front_y=0.75, fixtures=fx, fridge_visit=False)
    assert none.visit is None
    visits = sum(Walkers(2, floor, seed=s, base_xy=(2.6, 1.0), front_y=0.75, fixtures=fx).visit is not None
                 for s in range(20))
    assert 5 <= visits <= 18  # P_VISIT is 0.6 and the plan can decline
    near = Walkers(2, floor, seed=3, base_xy=(1.2, 1.0), front_y=0.75, fixtures=fx, fridge_visit=True)
    assert near.visit is None  # the base is inside the door's swing plus CLEAR: nobody opens it


def test_episode_with_a_fridge_visit_still_succeeds(twin):
    from arrival.sim.collect import run_episode
    from arrival.sim.policy import ScriptedExpert

    for seed in range(12):
        task = {"family": "open_drawer", "fixture": "counter_b", "handle": "counter_b_drawer0_handle",
                "joint": "counter_b_drawer0", "lighting": "neutral", "people": 2, "seed": seed}
        env = SimEnv(twin, task, res=32)
        if env.walkers.visit is not None:
            break
    else:
        pytest.fail("no seed in 0..11 plans a fridge visit for counter_b")
    ep = run_episode(env, ScriptedExpert(), task)
    assert ep["fridge_visit"] and env.walkers.door_max > 1.0
    assert ep["success"], ep["detail"]
    assert not ep["safety"]["human_contact"] and not ep["safety"]["door_contact"]
    assert "door_contact" in ep["safety"]


def test_yaw_does_not_spike_on_the_frame_a_walker_arrives_at_a_pause(twin):
    m = mujoco.MjModel.from_xml_string(build_mjcf(twin, (2.6, 1.0, 0.75), n_people=2, people_seed=3))
    d = mujoco.MjData(m)
    walkers = Walkers(2, (0.4, 1.65, 3.6, 2.7), seed=3, base_xy=(2.6, 1.0), front_y=0.75,
                      fixtures=twin["fixtures"], fridge_visit=True)
    for _ in range(240):
        walkers.step(m, d, 0.05)
        for i in range(2):
            if walkers.wait[i] > 0:  # stopped, including the frame it arrives: already facing the stop yaw
                assert walkers.yaw[i] == walkers._pause_yaw(i), i


def test_summary_is_strict_json_before_the_first_update(twin):
    import json

    from arrival.sim.safety import SafetyMonitor

    m = mujoco.MjModel.from_xml_string(build_mjcf(twin, (2.6, 1.0, 0.75), n_people=2, people_seed=3))
    s = SafetyMonitor(m).summary()
    assert s["min_human_distance_m"] is None and s["people"] == 2
    json.dumps(s, allow_nan=False)


def test_driven_door_contact_is_not_an_arm_contact(twin):
    from types import SimpleNamespace

    from arrival.sim.safety import SafetyMonitor

    m = mujoco.MjModel.from_xml_string(build_mjcf(twin, (2.6, 1.0, 0.75), n_people=1, people_seed=3))
    mon = SafetyMonitor(m)
    door = next(g for g in range(m.ngeom) if m.geom_bodyid[g] == m.body("fridge_1_door").id)
    link = next(iter(mon.link_geoms))
    data = SimpleNamespace(ncon=1, contact=[SimpleNamespace(geom1=link, geom2=door, dist=-0.01)])
    mon._arm_contacts(m, data)
    assert mon.arm_steps == 1
    mon.reset()
    mon._arm_contacts(m, data, {door})
    assert mon.arm_steps == 0


# ---- L27: people pass ----

def _open_door_task(twin, tid="sim_open_door_0025"):
    """A hero open_door task in which a walker heading for their counter stop meets the door pull's elbow: 5 cm of
    contact before L27."""
    from arrival.sim.tasks import finish_task, make_tasks

    fams = ["counter_to_sink", "open_door", "open_fridge", "wipe_counter", "put_in_drawer", "open_drawer"]
    task = next(t for t in make_tasks(twin, fams, 30, seed=0, people=2, log=lambda *_: None) if t["task_id"] == tid)
    finish_task(task)
    return task


def test_a_walker_gives_way_to_the_arm_and_the_contact_is_gone(twin, monkeypatch):
    from arrival.sim.collect import run_episode
    from arrival.sim.policy import ScriptedExpert

    task = _open_door_task(twin)
    env = SimEnv(twin, task, res=32)
    ep = run_episode(env, ScriptedExpert(), task)
    assert ep["success"] and not ep["safety"]["human_contact"] and ep["safety"]["min_human_distance_m"] > 0.03
    assert env.walkers.stats["slowed_s"] > 0
    monkeypatch.setattr(Walkers, "_give_way", lambda *a: 1.0)  # the same episode with walkers that never give way
    env = SimEnv(twin, task, res=32)
    ep = run_episode(env, ScriptedExpert(), task)
    assert ep["success"] and ep["safety"]["human_contact"]


NEAR_EXTRA = 0.30  # after WAIT_MAX without PROGRESS every step walks away at 0.04 m; the spot the clock started from can
# be PROGRESS along the way out, so 2 * PROGRESS takes 6 steps


def _held_up(twin, seed, block_at, seconds=60.0):
    """One walker on the hero loop against a fake arm: `block_at(t, w)` gives the arm's point (or None), and the room
    is the distance to it less 0.5 m. Returns the longest stretch standing exactly still and the longest stretch
    within PROGRESS of one spot (planned pauses excluded from both), the smallest room, the room the moment the arm
    first appeared, and the walker."""
    from arrival.sim.people import PROGRESS

    base = (2.6, 1.0, 0.75)
    m = mujoco.MjModel.from_xml_string(build_mjcf(twin, base, n_people=1, people_seed=seed))
    d = mujoco.MjData(m)
    w = Walkers(1, (0.4, 1.65, 3.6, 2.7), seed=seed, base_xy=base[:2], front_y=0.75, fixtures=twin["fixtures"],
                fridge_visit=False)
    st = {"b": None}
    w.arm_clearance = lambda data, i, p, amp=None: np.inf if st["b"] is None else float(np.linalg.norm(p - st["b"])) - 0.5
    still = near = longest = near_long = 0.0
    anchor, room, first, t = w.pos[0].copy(), np.inf, None, 0.0
    while t < seconds:
        before = w.pos[0].copy()
        w.step(m, d, 0.05)
        t += 0.05
        st["b"] = block_at(t, w, st["b"])
        p = w.pos[0]
        room = min(room, w.arm_clearance(d, 0, p))
        if first is None and st["b"] is not None:
            first = w.arm_clearance(d, 0, p)
        still = still + 0.05 if np.array_equal(before, p) and w.wait[0] <= 0 else 0.0
        if np.linalg.norm(p - anchor) > PROGRESS or w.wait[0] > 0:
            anchor, near = p.copy(), 0.0
        else:
            near += 0.05
        longest, near_long = max(longest, still), max(near_long, near)
    return longest, near_long, room, first, w


def test_a_person_held_up_by_the_arm_never_waits_more_than_wait_max(twin):
    """The arm stands in the lane for good. The walker stops at it, and after WAIT_MAX without PROGRESS walks away;
    whatever happens next, they never stand still longer than WAIT_MAX, never stay within PROGRESS of one spot longer
    than WAIT_MAX plus NEAR_EXTRA, and never walk into it."""
    from arrival.sim.people import WAIT_MAX

    w0 = Walkers(1, (0.4, 1.65, 3.6, 2.7), seed=3, base_xy=(2.6, 1.0), front_y=0.75, fixtures=twin["fixtures"],
                 fridge_visit=False)
    lane = (w0.paths[0][2] + w0.paths[0][3]) / 2
    longest, near, room, _, w = _held_up(twin, 3, lambda t, w, b: lane, 30.0)
    assert w.stats["stops"] >= 1 and w.stats["walk_aways"] >= 1
    assert longest <= WAIT_MAX + 1e-6 and near <= WAIT_MAX + NEAR_EXTRA + 1e-6 and room > 0.0, (longest, near, room)


def test_a_person_blocked_where_they_step_back_to_keeps_walking(twin):
    """The arm follows the walker: after they first walk away it sits 0.03 m inside the stop line ahead of the
    waypoint they went back to. Before, they stood there for good (20.9 s and counting)."""
    from arrival.sim.people import WAIT_MAX

    w0 = Walkers(1, (0.4, 1.65, 3.6, 2.7), seed=3, base_xy=(2.6, 1.0), front_y=0.75, fixtures=twin["fixtures"],
                 fridge_visit=False)
    lane = (w0.paths[0][2] + w0.paths[0][3]) / 2
    moved = {}

    def block(t, w, b):
        if w.backing[0] and not moved:
            path = w.paths[0]
            wp, nxt = path[w.idx[0] % len(path)], path[(w.idx[0] + w.dir[0]) % len(path)]
            moved["b"] = wp + (nxt - wp) / np.linalg.norm(nxt - wp) * 0.53
        return moved.get("b", lane)

    longest, near, room, _, w = _held_up(twin, 3, block, 40.0)
    assert moved and w.stats["walk_aways"] >= 2
    assert longest <= WAIT_MAX + 1e-6 and near <= WAIT_MAX + NEAR_EXTRA + 1e-6 and room > 0.0, (longest, near, room)


@pytest.mark.parametrize("seed, k, off", [(9, 3, 0.52), (10, 3, 0.52), (10, 5, 0.46), (11, 1, 0.70)])
def test_an_arm_that_appears_beside_the_waypoint_the_walker_stands_on(twin, seed, k, off):
    """The arm shows up, and stays, just as the walker reaches waypoint k on their second lap, `off` m along the leg
    they are about to walk: 0.02 m inside the stop line for 0.52, and 0.04 m into them for 0.46. Before, they cycled between stopping, stepping back
    to the waypoint they stood on and turning round, still for 40 to 55 s in a minute."""
    from arrival.sim.people import WAIT_MAX

    def block(t, w, b):
        path = w.paths[0]
        if b is None and t > 3 and np.linalg.norm(w.pos[0] - path[k]) < 0.05:
            u = path[(k + 1) % len(path)] - path[k]
            return path[k] + u / np.linalg.norm(u) * off
        return b

    longest, near, room, first, w = _held_up(twin, seed, block, 60.0)
    assert longest <= WAIT_MAX + 1e-6 and near <= WAIT_MAX + NEAR_EXTRA + 1e-6, (longest, near, w.stats)
    assert room >= min(first, 0.0) - 1e-9, (room, first)  # below zero only where the arm was put on them


def test_a_person_cornered_by_the_arm_and_the_floor_edge_still_moves(twin):
    """A still arm 0.028 m from a walker standing in the corner of the area they may walk away into: every full
    walk-away goal is cut short by the edge or leads through the arm. Before, they stood there for good (30 of 30 s);
    now they take the heading that gains most room, however short."""
    from arrival.sim.people import WAIT_MAX

    base = (2.6, 1.0, 0.75)
    m = mujoco.MjModel.from_xml_string(build_mjcf(twin, base, n_people=1, people_seed=0))
    d = mujoco.MjData(m)
    w = Walkers(1, (0.4, 1.65, 3.6, 2.7), seed=0, base_xy=base[:2], front_y=0.75, fixtures=twin["fixtures"],
                fridge_visit=False)
    arm = np.array([3.398, 2.471])
    w.arm_clearance = lambda data, i, p, amp=None: float(np.linalg.norm(p - arm)) - 0.5
    w.pos[0] = np.array([3.773, 2.842])
    w.anchor[0], w.idx[0] = w.pos[0].copy(), 2
    start = w.arm_clearance(d, 0, w.pos[0])
    still = longest = 0.0
    room = start
    for _ in range(600):  # 30 s
        before = w.pos[0].copy()
        w.step(m, d, 0.05)
        still = still + 0.05 if np.array_equal(before, w.pos[0]) and w.wait[0] <= 0 else 0.0
        longest, room = max(longest, still), min(room, w.arm_clearance(d, 0, w.pos[0]))
    assert longest <= WAIT_MAX + 1e-6 and w.stats["walk_aways"] >= 1, (longest, w.stats)
    assert room >= min(start, 0.0) - 1e-9


@pytest.mark.parametrize("seed, start, arm", [(4, (0.2124, 2.8786), (0.699, 2.824)),
                                              (0, (0.2104, 1.33), (0.656, 1.534))])
@pytest.mark.parametrize("idx, way", [(0, 1), (0, -1), (1, 1), (2, -1)])
def test_the_gaining_step_is_found_between_headings_and_short_of_fixtures(twin, seed, start, arm, idx, way):
    """Walkers in a corner of their area beside a still arm. The only steps that gain room lie between 16 even
    headings (seed 4), or stop short of a fixture further along the heading (seed 0). Before, they stood for good."""
    from arrival.sim.people import WAIT_MAX

    base = (2.6, 1.0, 0.75)
    m = mujoco.MjModel.from_xml_string(build_mjcf(twin, base, n_people=1, people_seed=seed))
    d = mujoco.MjData(m)
    w = Walkers(1, (0.4, 1.65, 3.6, 2.7), seed=seed, base_xy=base[:2], front_y=0.75, fixtures=twin["fixtures"],
                fridge_visit=False)
    arm = np.array(arm)
    w.arm_clearance = lambda data, i, p, amp=None: float(np.linalg.norm(p - arm)) - 0.5
    w.pos[0] = np.array(start)
    w.anchor[0], w.idx[0], w.dir[0] = w.pos[0].copy(), idx, way
    first = w.arm_clearance(d, 0, w.pos[0])
    still = longest = 0.0
    room = first
    for _ in range(400):  # 20 s
        before = w.pos[0].copy()
        w.step(m, d, 0.05)
        still = still + 0.05 if np.array_equal(before, w.pos[0]) and w.wait[0] <= 0 else 0.0
        longest, room = max(longest, still), min(room, w.arm_clearance(d, 0, w.pos[0]))
    assert longest <= WAIT_MAX + 1e-6 and np.linalg.norm(w.pos[0] - np.array(start)) > 0.2, (longest, w.stats)
    assert room >= min(first, 0.0) - 1e-9


def test_give_way_bands_follow_the_persons_height():
    from types import SimpleNamespace

    from arrival.sim.people import body_bands

    short = next(person_spec(s, 0) for s in range(200) if person_spec(s, 0)["height"] < 1.62)
    tall = next(person_spec(s, 0) for s in range(200) if person_spec(s, 0)["height"] > 1.84)
    for s in (short, tall):
        bands = body_bands(s)
        assert bands[-1][1] == s["height"] and all(a[1] == b[0] for a, b in zip(bands, bands[1:]))
        assert bands[0][2][-1] > bands[0][2][0]  # the foot reaches further at full stride than standing
    assert body_bands(tall)[0][2][-1] > body_bands(short)[0][2][-1]
    w = Walkers(1, (0.4, 1.65, 3.6, 2.7), seed=0)
    w._arm, w._column = ([0], {0: True}, {0: 0.04}, {0: 0.1}), 0  # one horizontal capsule at 1.75 m, 0.6 m away,
    data = SimpleNamespace(geom_xpos=np.array([[1.6, 2.0, 1.75]]), xpos=np.array([[2.4, 2.0, 0.0]]),  # 0.8 m out
                           geom_xmat=np.array([[0.0, 0.0, 1.0, 0.0, 1.0, 0.0, -1.0, 0.0, 0.0]]))  # from the column
    room = {}
    for name, s in (("short", short), ("tall", tall)):
        w.specs[0], w.bands[0] = s, body_bands(s)
        room[name] = w.arm_clearance(data, 0, np.array([1.0, 2.0]))
    assert room["short"] == float("inf")  # over the short person's head
    assert 0.0 < room["tall"] < 0.6


def test_a_person_at_the_counter_works_its_top(twin):
    base, floor = (2.6, 1.0, 0.75), (0.4, 1.65, 3.6, 2.7)
    m = mujoco.MjModel.from_xml_string(build_mjcf(twin, base, n_people=2, people_seed=5))
    d = mujoco.MjData(m)
    w = Walkers(2, floor, seed=5, base_xy=base[:2], front_y=0.75, fixtures=twin["fixtures"], fridge_visit=False)
    assert all("use" in faces for faces in w.faces)
    tall = {"fixtures": [{**f, "size": [*f["size"][:2], 9.0]} for f in twin["fixtures"]]}  # footprint test only
    tops = {f["id"]: f["position"][2] + f["size"][2] / 2 for f in twin["fixtures"]}
    xs = {0: [], 1: []}
    for _ in range(400):
        w.step(m, d, 0.05)
        mujoco.mj_kinematics(m, d)
        for i in range(2):
            if w.wait[i] > 0 and w.faces[i][w.at[i]] == "use" and w.reach[i] and w.reach[i][0] > 0.99:
                g = m.geom(f"person_{i}_farm_r").id
                tip = d.geom_xpos[g] + d.geom_xmat[g].reshape(3, 3)[:, 2] * m.geom_size[g][1]
                under = _inside(tall, tip[:2], 0.0)
                assert under is not None and tip[2] > tops[under], np.round(tip, 3)  # over a counter top, on it
                xs[i].append(float(tip[0]))
        for g in range(m.ngeom):
            if m.geom(g).name.startswith("person_"):
                c, half = d.geom_xpos[g], m.geom_size[g][1]
                axis = d.geom_xmat[g].reshape(3, 3)[:, 2] * (half if m.geom_type[g] == mujoco.mjtGeom.mjGEOM_CAPSULE else 0)
                for p in (c - axis, c, c + axis):
                    assert _inside(twin, p[:2], p[2]) is None, (m.geom(g).name, np.round(p, 3))
    assert all(xs[i] and max(xs[i]) - min(xs[i]) > 0.08 for i in xs)  # the hand works along the counter


@pytest.mark.parametrize("people", [1, 2])
def test_the_arm_opens_the_fridge_with_people_walking(twin, people):
    from arrival.sim.collect import run_episode
    from arrival.sim.policy import ScriptedExpert
    from arrival.sim.tasks import finish_task, make_tasks

    for task in make_tasks(twin, ["open_fridge"], 2, seed=0, people=people, log=lambda *_: None):
        finish_task(task)
        env = SimEnv(twin, task, res=32)
        ep = run_episode(env, ScriptedExpert(), task)
        assert ep["success"], ep["detail"]
        assert ep["safety"]["people"] == people and not ep["safety"]["human_contact"]


def _mirrored(twin, width=4.0):
    """The hero kitchen reflected in x = 2 with its fridge hinged on the left (seen from the front): the mirror image
    of the usual right-hinged one, so every number of its plans has a reflected counterpart to compare with."""
    t = copy.deepcopy(twin)
    t["room_id"] += "_mirrored"
    for w in t["walls"]:
        w["start"], w["end"] = [width - w["end"][0], w["end"][1]], [width - w["start"][0], w["start"][1]]
    for f in t["fixtures"] + t["objects"]:
        f["position"][0] = width - f["position"][0]
        f["yaw"] = -f.get("yaw", 0.0)
    next(f for f in t["fixtures"] if f["type"].startswith("fridge"))["hinge"] = "left"
    return t


def test_left_hinged_fridge_is_the_mirror_of_the_right(twin):
    from arrival.sim.scene import fridge_door_frame

    bundle = load_room("hero_kitchen", "scans")
    next(f for f in bundle["fixtures"] if f["category"] == "refrigerator")["hinge"] = "left"
    assert next(f for f in compile_twin(bundle)["fixtures"] if f["id"] == "fridge_1")["hinge"] == "left"
    assert "hinge" not in next(f for f in twin["fixtures"] if f["id"] == "fridge_1")
    from arrival.scan.bundle import ScanBundleError, validate

    next(f for f in bundle["fixtures"] if f["category"] == "refrigerator")["hinge"] = "rigth"
    with pytest.raises(ScanBundleError, match="hinge"):
        validate(bundle)

    right = _mirrored(twin)
    fl, fr = (next(f for f in t["fixtures"] if f["id"] == "fridge_1") for t in (twin, right))
    a, b = fridge_door_frame(fl), fridge_door_frame(fr)
    assert a["sign"] == 1.0 and b["sign"] == -1.0 and b["hinge"] == (-a["hinge"][0], a["hinge"][1])
    assert b["handle"] == (-a["handle"][0], *a["handle"][1:])
    handles = []
    for t, base in ((twin, (2.6, 1.0, 0.75)), (right, (1.4, 1.0, 0.75))):
        m = mujoco.MjModel.from_xml_string(build_mjcf(t, base))
        dd = mujoco.MjData(m)
        dd.qpos[int(m.joint("fridge_1_door").qposadr[0])] = 0.7
        mujoco.mj_kinematics(m, dd)
        handles.append(dd.site("fridge_1_door_handle").xpos.copy())
    (lx, ly, lz), right_handle = handles
    assert ly > 0.9 and np.allclose([4.0 - lx, ly, lz], right_handle, atol=1e-6)  # out into the room, mirrored


def test_a_person_opens_a_left_hinged_fridge_with_the_left_hand(twin):
    right = _mirrored(twin)
    base = (1.4, 1.0, 0.75)
    m = mujoco.MjModel.from_xml_string(build_mjcf(right, base, n_people=2, people_seed=3))
    d = mujoco.MjData(m)
    w = Walkers(2, (0.4, 1.65, 3.6, 2.7), seed=3, base_xy=base[:2], front_y=0.75, fixtures=right["fixtures"],
                fridge_visit=True)
    left = Walkers(2, (0.4, 1.65, 3.6, 2.7), seed=3, base_xy=(2.6, 1.0), front_y=0.75, fixtures=twin["fixtures"],
                   fridge_visit=True)
    assert w.visit is not None and w.visit["hand"] == "l" and left.visit["hand"] == "r"
    assert np.allclose([4.0 - left.visit["s1"][0], left.visit["s1"][1]], w.visit["s1"])
    who, qadr = w.visit["person"], int(m.joint("fridge_1_door").qposadr[0])
    door, hand = _door_geoms(m), m.geom(f"person_{who}_farm_l").id
    people = [g for g in range(m.ngeom) if m.geom(g).name.startswith("person_")]
    qs = []
    for _ in range(240):
        w.step(m, d, 0.05)
        mujoco.mj_kinematics(m, d)
        qs.append(float(d.qpos[qadr]))
        for g in people:
            dist = min(mujoco.mj_geomDistance(m, d, g, h, 1.0, None) for h in door)
            assert dist >= (-0.01 if g == hand else 0.0), (m.geom(g).name, round(qs[-1], 3), round(dist, 4))
    assert abs(max(qs) - w.visit["q_open"]) < 1e-6 and qs[-1] == 0.0


@pytest.mark.parametrize("people", [0, 1])
def test_the_arm_opens_a_left_hinged_fridge(twin, people):
    from arrival.sim.collect import run_episode
    from arrival.sim.policy import ScriptedExpert
    from arrival.sim.tasks import finish_task, make_tasks

    right = _mirrored(twin)
    tasks = make_tasks(right, ["open_fridge"], 2, seed=0, people=people, log=lambda *_: None)
    assert len(tasks) == 2
    for task in tasks:
        finish_task(task)
        env = SimEnv(right, task, res=32)
        assert env.base0[0] < 3.625 - 0.375  # on the free edge's side, left of the fridge
        ep = run_episode(env, ScriptedExpert(), task)
        assert ep["success"], ep["detail"]
        assert 65.0 < np.degrees(ep["detail"]["qpos"]) < 90.0  # 66.8 measured, threshold 60: keep the margin in view
        assert not ep["safety"]["human_contact"]


def test_the_push_follows_a_fridge_on_a_side_wall():
    """u_kitchen_42's fridge faces +x (yaw pi/2). The push used to be planned at world angles, which only match a
    fridge facing +y: the hand knocked the door back to 4 deg and link7 went 6 cm into the panel flinging it to 112."""
    from arrival.sim.collect import run_episode
    from arrival.sim.policy import ScriptedExpert
    from arrival.sim.tasks import finish_task, make_tasks

    twin = compile_twin(load_room("u_kitchen_42", "tests/fixtures/scans"))
    task = make_tasks(twin, ["open_fridge"], 1, seed=0, people=0, log=lambda *_: None)[0]
    finish_task(task)
    ep = run_episode(SimEnv(twin, task, res=32), ScriptedExpert(), task)
    assert ep["success"] and 75.0 < np.degrees(ep["detail"]["qpos"]) < 85.0, ep["detail"]  # the planned 80 deg
    assert ep["safety"]["arm_contact_steps"] == 0, ep["safety"]["arm_contact_worst"]
