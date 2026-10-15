from arrival.tasks.propose import LIGHTING, propose


def test_families_and_sources(hero_twin):
    tasks = propose(hero_twin)["tasks"]
    assert {t["family"] for t in tasks} == {"counter_to_sink", "counter_to_counter"}
    assert {t["object_id"] for t in tasks} == {"mug_1", "bowl_1"}
    assert "sponge_1" not in {t["object_id"] for t in tasks}
    assert {t["lighting"] for t in tasks} <= set(LIGHTING)
    for t in tasks:
        assert "people" not in t and "cosmos" not in t
        assert t["source_fixture_id"] == "counter_a"
    sink = [t for t in tasks if t["family"] == "counter_to_sink"]
    assert {t["target_fixture_id"] for t in sink} == {"sink_1"}
    assert {t["mimicgen_template"] for t in sink} == {"PnPCounterToSink"}
    c2c = [t for t in tasks if t["family"] == "counter_to_counter"]
    assert {t["target_fixture_id"] for t in c2c} == {"counter_b"}
    assert {t["mimicgen_template"] for t in c2c} == {None}


def test_four_wordings_for_mug_sink(hero_twin):
    tasks = propose(hero_twin)["tasks"]
    mug = [t for t in tasks if t["family"] == "counter_to_sink" and t["object_id"] == "mug_1"
           and t["pose_index"] == 0 and t["lighting"] == "neutral"]
    assert [t["instruction"] for t in mug] == [
        "Pick up the mug from the counter and place it in the sink.",
        "Put the mug in the sink.",
        "Move the mug off the counter into the sink.",
        "Take the mug and drop it in the sink.",
    ]
    assert mug[0]["start_position"] == [1.0, 0.35, 0.97]


def test_counter_to_counter_wording(hero_twin):
    tasks = propose(hero_twin)["tasks"]
    w = {t["instruction"] for t in tasks if t["family"] == "counter_to_counter" and t["object_id"] == "bowl_1"}
    assert "Put the bowl onto the other counter." in w
    assert len(w) == 4


def test_start_poses(hero_twin):
    tasks = propose(hero_twin)["tasks"]
    poses = {tuple(t["start_position"]) for t in tasks if t["object_id"] == "mug_1"}
    assert poses == {(1.0, 0.35, 0.97), (1.08, 0.35, 0.97), (0.92, 0.35, 0.97), (1.0, 0.43, 0.97)}
