"""A real iPhone RoomPlan scan of a kitchen (tests/fixtures/roomplan/kitchen_real_01.json, geometry only: the
coreModel blob and every frame were left out). It was the first real kitchen through the pipeline, and it showed
that RoomPlan objects face their local +Z: before the fix every cabinet, appliance and fridge faced its wall, the
robot's stand spots fell outside the room and the job ended 'unsupported layout'."""
from pathlib import Path

import numpy as np
import pytest

from arrival.scan import roomplan
from arrival.twin.compile import compile_twin

FIXTURE = Path(__file__).parent / "fixtures" / "roomplan" / "kitchen_real_01.json"


@pytest.fixture(scope="module")
def twin():
    return compile_twin(roomplan.load(FIXTURE, "kitchen_real_01"))


def _bounds(twin):
    pts = np.array([p for w in twin["walls"] for p in (w["start"], w["end"])])
    return pts.min(axis=0), pts.max(axis=0)


def test_every_fixture_faces_into_the_room(twin):
    from arrival.sim.preflight import front

    lo, hi = _bounds(twin)
    fixtures = [f for f in twin["fixtures"] if f["type"] != "sink"]
    assert len(fixtures) >= 5
    for f in fixtures:
        c = np.array(f["position"][:2])
        ahead = c + front(f)[:2] * (f["size"][1] / 2 + 0.5)  # half a metre in front of the face
        behind = c - front(f)[:2] * (f["size"][1] / 2 + 0.5)
        assert np.all(ahead > lo) and np.all(ahead < hi), (f["id"], f["type"], ahead.round(2))
        assert not (np.all(behind > lo) and np.all(behind < hi)), (f["id"], "its back is in the room too")


def test_tasks_get_stand_spots_inside_the_room(twin):
    pytest.importorskip("mujoco")
    from arrival.sim.tasks import make_tasks

    log, pre = [], {}
    tasks = make_tasks(twin, ["open_drawer", "open_door", "close_drawer", "close_door"], 8, seed=0,
                       log=log.append, preflight=pre)
    assert tasks, log
    assert not any("outside the room" in str(r) for r in pre.get("reasons", [])), pre.get("reasons")
