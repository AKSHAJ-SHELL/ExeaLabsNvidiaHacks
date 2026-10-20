import json
from pathlib import Path
import pytest

from arrival.sim.policy import VLMPlanner, rule_plan
from arrival.tasks.instructions import generate_instructions


def test_rule_plan_parsing():
    plan = rule_plan("Pick up the mug and put it in the sink", ["mug_1", "bowl_1"], ["sink_1", "counter_a"])
    assert plan["family"] == "counter_to_sink"
    assert plan["object"] == "mug_1"
    assert plan["target"] == "sink_1"

    drawer_plan = rule_plan("Slide open the drawer", ["mug_1"], ["counter_a"])
    assert drawer_plan["family"] == "open_drawer"

    door_plan = rule_plan("Open the cabinet door", [], ["counter_a"])
    assert door_plan["family"] == "open_door"


def test_vlm_planner_cache_hit(tmp_path):
    cache_file = tmp_path / "test_cache.json"
    cache_file.write_text(json.dumps({
        "grab the mug and drop in sink::['mug_1']::['sink_1']": {
            "family": "counter_to_sink",
            "object": "mug_1",
            "target": "sink_1",
        }
    }))

    planner = VLMPlanner(log=lambda *_: None, cache_path=cache_file)
    plan = planner.plan("grab the mug and drop in sink", ["mug_1"], ["sink_1"])
    assert planner.source == "cache"
    assert plan == {"family": "counter_to_sink", "object": "mug_1", "target": "sink_1"}


def test_vlm_planner_falls_back_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv("TOKEN_FACTORY_API_KEY", raising=False)
    cache_file = tmp_path / "empty_cache.json"

    planner = VLMPlanner(log=lambda *_: None, cache_path=cache_file)
    plan = planner.plan("Pull out the top drawer.", ["mug_1"], ["counter_a"])
    assert planner.source == "rule_based"
    assert plan["family"] == "open_drawer"


def test_vlm_planner_caches_successful_call(monkeypatch, tmp_path):
    cache_file = tmp_path / "save_cache.json"

    def mock_complete(messages, role="super", **params):
        return '{"family": "open_door", "object": null, "target": null}'

    monkeypatch.setattr("arrival.models.token_factory.complete", mock_complete)
    monkeypatch.setenv("TOKEN_FACTORY_API_KEY", "test-key-fake")

    planner = VLMPlanner(log=lambda *_: None, cache_path=cache_file)
    plan = planner.plan("Open the pantry door please", ["mug_1"], ["counter_a"])

    assert planner.source == "token_factory"
    assert plan["family"] == "open_door"
    assert cache_file.is_file()

    # Second call should be a cache hit
    plan2 = planner.plan("Open the pantry door please", ["mug_1"], ["counter_a"])
    assert planner.source == "cache"
    assert plan2 == plan


def test_generate_instructions_train_eval_split(tmp_path):
    cache_file = tmp_path / "instr_cache.json"
    res = generate_instructions(
        family="counter_to_sink",
        object_name="mug",
        eval_ratio=0.25,
        cache_path=cache_file,
    )

    assert "train" in res and "eval" in res
    assert len(res["train"]) >= 1
    assert len(res["eval"]) >= 1
    # Train and eval sets must be disjoint
    assert set(res["train"]).isdisjoint(set(res["eval"]))


def test_sim_collect_with_vlm_planner(tmp_path, monkeypatch):
    monkeypatch.delenv("TOKEN_FACTORY_API_KEY", raising=False)  # no network; fallback is not cached
    mujoco = pytest.importorskip("mujoco")
    from arrival.scan.bundle import load_room
    from arrival.sim.collect import collect
    from arrival.twin.compile import compile_twin

    twin = compile_twin(load_room("hero_kitchen", "scans"))
    # Run 1 episode with planner="vlm"
    res = collect(
        twin=twin,
        families=["counter_to_sink"],
        episodes=1,
        out_dir=tmp_path,
        people=0,
        res=32,
        planner_name="vlm",
        use_generated_instructions=True,
        log=lambda *_: None,
    )

    report = res["report_data"]
    assert report["planner"] == "vlm"
    assert report["attempts"] == 1


def test_instruction_fallback_not_cached_and_train_nonempty(tmp_path, monkeypatch):
    import arrival.models.token_factory as tf

    cache_file = tmp_path / "c.json"

    def down(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(tf, "complete", down)
    res = generate_instructions("counter_to_sink", "mug", cache_path=cache_file)
    assert res["source"] == "template_fallback" and not cache_file.exists()

    monkeypatch.setattr(tf, "complete", lambda **k: '["Put the mug in the sink."]')
    res = generate_instructions("counter_to_sink", "mug", cache_path=cache_file)
    assert res["source"] == "token_factory"
    assert res["train"] == ["Put the mug in the sink."] and res["eval"] == []

    monkeypatch.setattr(tf, "complete", lambda **k: "no list here")
    res = generate_instructions("counter_to_sink", "mug", n=3, cache_path=tmp_path / "d.json")
    assert res["source"] == "template_fallback" and len(res["train"]) + len(res["eval"]) == 3 and res["train"]
