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
