"""SIM-5: a real non-kitchen RoomPlan scan (tests/fixtures/roomplan/amal.json, a table and two chairs) becomes a
room the arm can work in: the table is a table, furniture is solid, and move_on_table episodes pass physics."""

from pathlib import Path

import pytest

mujoco = pytest.importorskip("mujoco")

from arrival.scan import roomplan  # noqa: E402
from arrival.sim.collect import SimEnv, run_episode  # noqa: E402
from arrival.sim.policy import ScriptedExpert  # noqa: E402
from arrival.sim.scene import build_mjcf, is_table, part_names  # noqa: E402
from arrival.sim.tasks import SIM_FAMILIES, make_tasks  # noqa: E402
from arrival.twin.compile import compile_twin, place_default_objects  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "roomplan"


def _room(name: str) -> dict:
    twin = compile_twin(roomplan.load(FIXTURES / f"{name}.json", name))
    place_default_objects(twin, seed=0)
    return twin


@pytest.fixture(scope="module")
def office():
    return _room("amal")


def test_table_is_built_as_a_table(office):
    table = next(f for f in office["fixtures"] if is_table(f))
    m = mujoco.MjModel.from_xml_string(build_mjcf(office, (2.0, 0.6, 0.75)))
    names = {m.geom(i).name for i in range(m.ngeom)}
    assert f'{table["id"]}_top' in names and all(f'{table["id"]}_leg{k}' in names for k in range(4))
    joints = {m.joint(i).name for i in range(m.njnt)}
    assert not any(j.startswith(table["id"]) for j in joints)  # no drawers or doors under a dining table
    assert not any(p["fixture"] == table["id"] for p in part_names(office))


def test_furniture_is_solid(office):
    chairs = [f for f in office["fixtures"] if f["source_category"] == "chair"]
    m = mujoco.MjModel.from_xml_string(build_mjcf(office, (2.0, 0.6, 0.75)))
    for c in chairs:
        g = m.geom(f'{c["id"]}_box')
        assert m.geom_contype[g.id] and m.geom_conaffinity[g.id]


def test_office_tasks_are_table_tasks_only(office):
    fams = {t["family"] for t in make_tasks(office, list(SIM_FAMILIES), 40, log=lambda *_: None)}
    assert fams == {"move_on_table"}  # no drawer, door or sink tasks invented for an office


def test_move_on_table_passes_physics(office):
    task = make_tasks(office, ["move_on_table"], 1, seed=0, log=lambda *_: None)[0]
    env = SimEnv(office, task, res=32)
    ep = run_episode(env, ScriptedExpert(), task)
    assert ep["success"], ep["detail"]
    assert ep["detail"]["target_error_m"] < 0.02 and ep["ik_error"] < 0.02


def test_people_are_skipped_when_the_room_has_no_free_strip(office):
    task = make_tasks(office, ["move_on_table"], 1, seed=0, people=2, log=lambda *_: None)[0]
    env = SimEnv(office, task, res=32)
    assert env.walkers is None and task["people"] == 0 and "people_skipped" in task


def test_desk_behind_a_chair_gets_no_task():
    # shopyseek: the desk's only free long side is where its chair stands, so a fixed base has nowhere to stand
    assert make_tasks(_room("shopyseek"), ["move_on_table"], 4, log=lambda *_: None) == []
