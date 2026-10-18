import json

import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")

from arrival.scan.bundle import load_room  # noqa: E402
from arrival.sim import ik, robot  # noqa: E402
from arrival.sim.collect import SimEnv, collect  # noqa: E402
from arrival.sim.policy import VLAClient, VLANotConfigured, VLMPlanner  # noqa: E402
from arrival.sim.scene import build_mjcf  # noqa: E402
from arrival.twin.compile import compile_twin  # noqa: E402


@pytest.fixture(scope="module")
def twin():
    return compile_twin(load_room("hero_kitchen", "scans"))


def test_scene_has_moving_parts_and_people(twin):
    m = mujoco.MjModel.from_xml_string(build_mjcf(twin, (1.3, 1.0, 0.75), n_people=2))
    names = {m.joint(i).name for i in range(m.njnt)}
    assert {"counter_a_drawer0", "counter_a_door", "fridge_1_door", "mug_1"} <= names
    assert m.joint("counter_a_drawer0").type == mujoco.mjtJoint.mjJNT_SLIDE
    assert m.joint("fridge_1_door").type == mujoco.mjtJoint.mjJNT_HINGE
    assert m.nmocap == 2
    assert {m.camera(i).name for i in range(m.ncam)} >= {"ego_view", "wrist", "overview"}


def test_ik_reaches_counter_point(twin):
    task = {"family": "counter_to_sink", "object_id": "mug_1", "source": "counter_a", "target": "sink_1",
            "target_x": 1.6, "start": [1.0, 0.35, 0.97], "lighting": "neutral", "people": 0}
    env = SimEnv(twin, task, res=32)
    target = np.array([1.0, 0.35, 1.0])
    q, err = ik.solve(env.model, env.data, target, ik.down(0.0), np.array(robot.HOME), env.qadr, env.dofadr)
    assert err < 0.02
    d = mujoco.MjData(env.model)
    d.qpos[env.qadr] = q
    mujoco.mj_kinematics(env.model, d)
    assert np.linalg.norm(d.site("eef").xpos - target) < 0.02


def test_collect_writes_valid_dataset(twin, tmp_path):
    from arrival.export.validate import validate

    res = collect(twin, ["counter_to_sink"], 2, tmp_path, people=1, res=64, log=lambda *_: None)
    r = res["report_data"]
    assert r["attempts"] == 2 and r["successes"] >= 1
    info = json.loads((res["dataset"] / "meta" / "info.json").read_text())
    assert info["arrival_generator"] == "mujoco_scripted_ik" and info["arrival_physically_valid"] is True
    emb = json.loads((res["dataset"] / "meta" / "embodiment.json").read_text())
    assert emb["joints_are_placeholder"] is False
    import pyarrow.parquet as pq

    t = pq.read_table(res["dataset"] / "data" / "chunk-000" / "episode_000000.parquet")
    s = np.array(t.column("observation.state").to_pylist())
    assert s.shape[1] == 8 and np.ptp(s[:, :7], axis=0).max() > 0.3  # real joint motion
    assert list((res["dataset"] / "videos" / "chunk-000" / "observation.images.wrist").glob("*.mp4"))
    errors = validate(res["dataset"])
    assert not errors, errors


@pytest.mark.parametrize("fixture", ["counter_a", "counter_b"])
def test_scripted_expert_opens_cabinet_door(twin, fixture):
    from arrival.sim.collect import run_episode
    from arrival.sim.policy import ScriptedExpert

    task = {"family": "open_door", "fixture": fixture, "joint": f"{fixture}_door", "lighting": "neutral", "people": 0,
            "seed": 0}
    env = SimEnv(twin, task, res=32)
    ep = run_episode(env, ScriptedExpert(), task)
    assert ep["success"], ep["detail"]
    assert ep["detail"]["qpos"] > np.radians(65)  # success threshold is 60 deg; keep a margin
    assert ep["ik_error"] < 0.02


@pytest.mark.parametrize("family,fixture", [("close_drawer", "counter_a"), ("close_drawer", "counter_b"),
                                            ("close_door", "counter_a"), ("close_door", "counter_b")])
def test_scripted_expert_closes_open_parts(twin, family, fixture):
    from arrival.sim.collect import DOOR_OPEN, DRAWER_OPEN, run_episode
    from arrival.sim.policy import ScriptedExpert

    joint = f"{fixture}_door" if family == "close_door" else f"{fixture}_drawer0"
    task = {"family": family, "fixture": fixture, "joint": joint, "handle": f"{fixture}_drawer0_handle",
            "lighting": "neutral", "people": 0, "seed": 0}
    env = SimEnv(twin, task, res=32)
    start = float(env.data.joint(joint).qpos[0])
    assert start == pytest.approx(DOOR_OPEN if family == "close_door" else DRAWER_OPEN)  # it really starts open
    ep = run_episode(env, ScriptedExpert(), task)
    assert ep["success"], ep["detail"]
    assert ep["ik_error"] < 0.03


def test_scripted_expert_puts_mug_in_drawer_and_wipes(twin):
    from arrival.sim.collect import run_episode
    from arrival.sim.policy import ScriptedExpert
    from arrival.sim.tasks import make_tasks

    for family in ("put_in_drawer", "wipe_counter"):
        task = make_tasks(twin, [family], 1, seed=0)[0]
        if family == "put_in_drawer":
            task["handle"], task["joint"] = f'{task["fixture"]}_drawer0_handle', f'{task["fixture"]}_drawer0'
        env = SimEnv(twin, task, res=32)
        ep = run_episode(env, ScriptedExpert(), task)
        assert ep["success"], (family, ep["detail"])
    assert ep["detail"]["wiped_m"] >= 0.4  # the sponge travelled pressed to the counter, not carried above it


def test_cabinet_fronts_collide_where_they_are_drawn(twin):
    """Each counter's hidden door/drawer collision box spans the same height as its visible front, so the arm
    cannot pass through the top of a front it can see (the door panel used to stop 22 cm below the counter top)."""
    from arrival.sim.scene import KICK, REVEAL, TOP_T

    m = mujoco.MjModel.from_xml_string(build_mjcf(twin, (1.3, 1.6, 0.75)))
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    for c in (f for f in twin["fixtures"] if f["type"] == "counter"):
        zf = c["size"][2] - TOP_T
        for name, lo, hi in ((f'{c["id"]}_door_panel', KICK + REVEAL, zf - REVEAL),
                             (f'{c["id"]}_drawer0_front', 0.600, zf - REVEAL)):
            g = m.geom(name).id
            z, hz = d.geom_xpos[g][2], m.geom_size[g][2]
            assert z - hz == pytest.approx(lo, abs=1e-3) and z + hz == pytest.approx(hi, abs=1e-3), name


ARM_BODIES = [f"link{i}" for i in range(1, 8)] + ["hand", "finger_l", "finger_r"]


def _arm_overlaps(env, task, every: int = 2) -> dict:
    """Run the scripted expert; worst penetration (m) of any arm geom into the scene, checked with
    mj_geomDistance every `every` steps. Drawn-only geoms tolerate 1 cm (anything deeper is the arm visibly
    passing through), colliding geoms 2 cm (soft contact while pushing or gripping). The floor, people,
    free objects and the arm's own pedestal are skipped."""
    from arrival.sim.policy import ScriptedExpert

    m, d = env.model, env.data
    arm_b = {m.body(n).id for n in ARM_BODIES}
    free = tuple(o["id"] for o in env.twin["objects"])
    arm = [g for g in range(m.ngeom) if m.geom_bodyid[g] in arm_b]
    others = [g for g in range(m.ngeom) if m.geom_bodyid[g] not in arm_b | {m.body("robot_base").id}
              and m.geom_type[g] != mujoco.mjtGeom.mjGEOM_PLANE
              and not m.body(m.geom_bodyid[g]).name.startswith(("person",) + free)]
    tol = {g: 0.02 if (m.geom_contype[g] or m.geom_conaffinity[g]) else 0.01 for g in others}
    policy = ScriptedExpert()
    policy.reset(env, task)
    ft, worst, step = np.zeros(6), {}, 0
    while not policy.done() and step < 600:
        env.step(policy.act(None))
        step += 1
        if step % every:
            continue
        for ga in arm:
            for gb in others:
                dist = mujoco.mj_geomDistance(m, d, ga, gb, tol[gb], ft)
                if dist < -tol[gb]:
                    key = (m.body(m.geom_bodyid[ga]).name, m.geom(gb).name or f"{m.body(m.geom_bodyid[gb]).name}#{gb}")
                    worst[key] = min(worst.get(key, 0.0), dist)
    return worst


@pytest.mark.parametrize("family,fixture", [("open_door", "counter_a"), ("open_door", "counter_b"),
                                            ("open_drawer", "counter_a"), ("open_drawer", "counter_b"),
                                            ("close_door", "counter_a"), ("close_door", "counter_b"),
                                            ("close_drawer", "counter_a"), ("put_in_drawer", None),
                                            ("counter_to_sink", None), ("wipe_counter", None)])
def test_arm_never_passes_through_the_scene(twin, family, fixture):
    from arrival.sim.tasks import make_tasks

    if fixture:
        task = {"family": family, "fixture": fixture, "lighting": "neutral", "people": 0, "seed": 0}
    else:
        task = make_tasks(twin, [family], 1, seed=0, log=lambda *_: None)[0]
        fixture = task.get("fixture")
    if family in ("open_drawer", "close_drawer", "put_in_drawer"):
        task["handle"], task["joint"] = f"{fixture}_drawer0_handle", f"{fixture}_drawer0"
    elif family in ("open_door", "close_door"):
        task["joint"] = f"{fixture}_door"
    env = SimEnv(twin, task, res=32)
    worst = _arm_overlaps(env, task)
    assert env.success(task)[0], env.success(task)[1]
    assert not worst, {k: f"{-v * 100:.1f} cm" for k, v in worst.items()}


def test_bowl_is_hollow_and_goes_to_sink(twin):
    from arrival.sim.collect import run_episode
    from arrival.sim.policy import ScriptedExpert
    from arrival.sim.tasks import make_tasks

    task = next(t for t in make_tasks(twin, ["counter_to_sink"], 40, seed=1) if t["object_id"] == "bowl_1")
    env = SimEnv(twin, task, res=32)
    walls = [env.model.geom(i).name for i in range(env.model.ngeom) if env.model.geom(i).name.startswith("bowl_1_wall")]
    assert len(walls) == 8
    ep = run_episode(env, ScriptedExpert(), task)
    assert ep["success"], ep["detail"]


def test_vla_requires_server(monkeypatch):
    monkeypatch.delenv("GR00T_POLICY_URL", raising=False)
    with pytest.raises(VLANotConfigured):
        VLAClient()


def test_vlm_planner_falls_back(monkeypatch):
    monkeypatch.delenv("TOKEN_FACTORY_API_KEY", raising=False)
    p = VLMPlanner(log=lambda *_: None)
    plan = p.plan("Put the mug in the sink.", ["mug_1", "bowl_1"], ["sink_1", "counter_a"])
    assert p.source == "rule_based"
    assert plan == {"family": "counter_to_sink", "object": "mug_1", "target": "sink_1"}
