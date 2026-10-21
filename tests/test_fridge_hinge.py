"""Right-hinged fridge: the twin field `hinge: "right"` mirrors the door in the MJCF, the expert's pull and push,
the stand spot and the walker's visit. Without the field nothing changes."""
import copy
import hashlib

import pytest

mujoco = pytest.importorskip("mujoco")

from arrival.scan.bundle import load_room  # noqa: E402
from arrival.sim.collect import collect  # noqa: E402
from arrival.sim.scene import build_mjcf, part_names  # noqa: E402
from arrival.twin.compile import compile_twin  # noqa: E402

QUIET = lambda *a, **k: None  # noqa: E731
WIDTH = 4.0  # the hero kitchen's room width: mirroring it in x puts the fridge at the east wall


@pytest.fixture(scope="module")
def hero():
    return compile_twin(load_room("hero_kitchen", "scans"))


@pytest.fixture(scope="module")
def mirrored(hero):
    """The hero kitchen reflected in x with a right-hinged fridge: the free edge faces the room, as the left-hinged
    fridge's does in the original. (The original fridge's right-hinged free edge would be in the room corner.)"""
    t = copy.deepcopy(hero)
    for w in t["walls"]:
        w["start"][0], w["end"][0] = WIDTH - w["start"][0], WIDTH - w["end"][0]
    for o in t["fixtures"] + t["objects"]:
        o["position"][0] = WIDTH - o["position"][0]
        if o["id"] == "fridge_1":
            o["hinge"] = "right"
    return t


def test_left_hinge_mjcf_is_unchanged(hero):
    xml = build_mjcf(hero, (2.6, 1.0, 0.75), n_people=2, people_seed=3)
    # measured on the code before the hinge field existed
    assert hashlib.sha256(xml.encode()).hexdigest()[:16] == "c21c9615b58d63ec"
    explicit = copy.deepcopy(hero)
    next(f for f in explicit["fixtures"] if f["id"] == "fridge_1")["hinge"] = "left"
    assert build_mjcf(explicit, (2.6, 1.0, 0.75), n_people=2, people_seed=3) == xml


def test_right_hinge_mirrors_the_door(hero, mirrored):
    right = mujoco.MjModel.from_xml_string(build_mjcf(mirrored, (2.6, 1.0, 0.75)))
    left = mujoco.MjModel.from_xml_string(build_mjcf(hero, (2.6, 1.0, 0.75)))
    for m, sign in ((left, 1.0), (right, -1.0)):
        assert m.joint("fridge_1_door").axis[2] == sign
    cx = 4.0 - 0.375  # the mirrored fridge's centre
    assert right.body("fridge_1_door").pos[0] == pytest.approx(0.375)  # hinge on the fixture's right edge
    assert left.body("fridge_1_door").pos[0] == pytest.approx(-0.375)
    hr = right.site("fridge_1_door_handle").pos[0]
    hl = left.site("fridge_1_door_handle").pos[0]
    assert hr == pytest.approx(-hl) and cx > 3.0
    assert any(p["joint"] == "fridge_1_door" for p in part_names(mirrored))


def _summary(twin, families, episodes, people, seed, tmp_path):
    return collect(twin, families, episodes, tmp_path, people=people, res=32, seed=seed, log=QUIET)["report_data"]


@pytest.mark.parametrize("people,seed", [(0, 0), (2, 3), (2, 5)])
def test_expert_opens_a_right_hinged_fridge(mirrored, tmp_path, people, seed):
    r = _summary(mirrored, ["open_fridge"], 2, people, seed, tmp_path)
    assert (r["attempts"], r["successes"], r["skipped_unreachable"]) == (2, 2, 0)
    assert r["human_contacts"] == 0 and r["door_contacts"] == 0


@pytest.mark.parametrize("seed", [3, 5])
def test_walkers_open_a_right_hinged_fridge_without_contact(mirrored, tmp_path, seed):
    # open_fridge parks the robot beside the free edge, where the walker's stand point is, so that family plans no
    # visit; these families park it at the counter and the visit is planned (the logged fridge_visit stat)
    r = _summary(mirrored, ["open_drawer", "open_door", "wipe_counter"], 6, 2, seed, tmp_path)
    assert r["fridge_visits"] >= 1
    assert r["attempts"] == r["successes"] == 6
    assert r["human_contacts"] == 0 and r["door_contacts"] == 0
