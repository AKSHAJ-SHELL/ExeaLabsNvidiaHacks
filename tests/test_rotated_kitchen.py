"""The sim must not assume every counter is on the north wall facing +y (issue #42). `rotated_kitchen` puts runs
on the west (facing +x), south (facing -y) and east (facing -x) walls: the base parks in front of each fixture,
the walkers get a floor strip that exists, and the scripted expert still succeeds."""

import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")

from arrival.scan.bundle import load_room  # noqa: E402
from arrival.sim.collect import SimEnv, _front, run_episode  # noqa: E402
from arrival.sim.people import KEEP_OUT  # noqa: E402
from arrival.sim.policy import ScriptedExpert  # noqa: E402
from arrival.sim.tasks import SIM_FAMILIES, make_tasks  # noqa: E402
from arrival.twin.compile import _rect_distance, compile_twin  # noqa: E402

SCANS = "tests/fixtures/scans"
RUNS = ("counter_w", "counter_s", "counter_e")


@pytest.fixture(scope="module")
def twin():
    return compile_twin(load_room("rotated_kitchen", SCANS))


def _tasks(twin, families, n, people=0):
    tasks = make_tasks(twin, list(families), n, seed=5, people=people, log=lambda *_: None)
    for t in tasks:  # collect() fills these before an episode runs
        if t["family"] in ("open_drawer", "close_drawer", "put_in_drawer"):
            t["handle"], t["joint"] = f'{t["fixture"]}_drawer0_handle', f'{t["fixture"]}_drawer0'
        elif t["family"] in ("open_door", "close_door"):
            t["joint"] = f'{t["fixture"]}_door'
    return tasks


def _footprint_clearance(twin, xy):
    return min(_rect_distance(list(xy), f) for f in twin["fixtures"])


def test_every_fixture_type_is_built(twin):
    env = SimEnv(twin, _tasks(twin, ["open_drawer"], 1)[0], res=32)
    bodies = {env.model.body(i).name for i in range(env.model.nbody)}
    assert {"fridge_w", "counter_w", "stove_s", "counter_s", "counter_e"} <= bodies
    assert any(env.model.geom(i).name.startswith("sink_w") for i in range(env.model.ngeom))  # the basin is cut in


def test_base_parks_in_front_of_fixtures_on_every_wall(twin):
    tasks = _tasks(twin, SIM_FAMILIES, 14)
    assert {t.get("fixture") or t["source"] for t in tasks} >= set(RUNS)
    for t in tasks:
        env = SimEnv(twin, t, res=32)
        base = env.data.body("robot_base")
        xy = base.xpos[:2]
        anchor = env.anchor
        assert _footprint_clearance(twin, xy) >= 0.25, (t["task_id"], xy)
        assert 0.4 < xy[0] < 4.1 and 0.4 < xy[1] < 3.1, (t["task_id"], xy)
        heading = base.xmat.reshape(3, 3)[:, 0][:2]
        assert np.dot(heading, _front(anchor)[:2]) < -0.99, t["task_id"]  # faces the fixture's front
        assert _rect_distance(list(xy), anchor) < 0.8, t["task_id"]  # and stands at it, not across the room


def test_sink_tasks_only_from_the_sink_run(twin):
    tasks = _tasks(twin, ["counter_to_sink"], 8)
    assert {t["source"] for t in tasks} == {"counter_w"} and "mug_2" not in {t["object_id"] for t in tasks}
    assert not _tasks(twin, ["counter_to_counter"], 4)  # the runs are on different walls, none continues another


@pytest.mark.parametrize("fixture", RUNS)
def test_walkers_get_a_strip_in_front_of_each_run(twin, fixture):
    t = next(t for t in _tasks(twin, ["open_drawer"], 6, people=2) if t["fixture"] == fixture)
    env = SimEnv(twin, t, res=32)
    assert env.people_note is None
    floor, (bx, by), front, note = env._free_floor(env.anchor, env.data.body("robot_base").xpos)
    assert note is None and floor[2] - floor[0] >= 1.0 and floor[3] - floor[1] >= 0.6
    for path in env.walkers.paths:
        for p in path:
            w = env.walkers.M.T @ p
            assert 0.0 < w[0] < 4.5 and 0.0 < w[1] < 3.5, (fixture, w)
            assert _footprint_clearance(twin, w) >= KEEP_OUT - 1e-9, (fixture, w)
        assert abs(path[4][1] - (front + 0.35)) < 1e-9 and abs(path[4][0] - bx) >= 0.8  # the counter stop, beside the base
        assert path[2][1] == path[3][1] and path[2][1] > by + 0.4  # the lane behind the base
    env.step(np.array(list(env.data.ctrl[:7]) + [0.04]))
    assert all(0.0 < x < 4.5 and 0.0 < y < 3.5 for x, y in env.people_xy)


@pytest.mark.parametrize("family,fixture,obj", [("counter_to_sink", "counter_w", "mug_1"), ("open_drawer", "counter_e", None),
                                                ("open_door", "counter_s", None), ("put_in_drawer", "counter_w", "mug_1")])
def test_expert_succeeds_with_people_on_a_rotated_run(twin, family, fixture, obj):
    t = next(t for t in _tasks(twin, [family], 8, people=2)
             if (t.get("fixture") or t["source"]) == fixture and (obj is None or t["object_id"] == obj))
    env = SimEnv(twin, t, res=32)
    ep = run_episode(env, ScriptedExpert(), t)
    assert ep["success"] and not ep["safety"]["human_contact"], (t["task_id"], ep["detail"])
    assert ep["ik_error"] < 0.02
