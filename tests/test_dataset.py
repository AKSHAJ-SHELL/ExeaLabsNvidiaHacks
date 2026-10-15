import itertools
import json
import math

import pyarrow.parquet as pq
import pytest

from arrival.cli import main, run_demo
from arrival.export.validate import validate
from arrival.generate.mimicgen import probe
from arrival.generate.scripted import count_attempts, generate, target_point
from arrival.render import sim_texture
from arrival.render.splat import SplatCompositeNotImplemented, render as splat_render
from arrival.tasks.propose import propose

from conftest import SCANS


@pytest.fixture
def hero_tasks(hero_twin):
    return propose(hero_twin)["tasks"]


def test_generator_and_oracle(hero_twin, hero_tasks):
    attempts = list(itertools.islice(generate(hero_tasks, hero_twin, episodes=100), 20))
    assert len(attempts) == 20
    assert [a["attempt_index"] for a in attempts if not a["success"]] == [9, 19]
    ok = next(a for a in attempts if a["success"])
    assert len(ok["frames"]) == 80
    assert ok["frames"][40]["gripper"] > 0.5
    tgt = target_point(ok["task"], hero_twin)
    last = ok["frames"][-1]["object_position"]
    assert math.hypot(last[0] - tgt[0], last[1] - tgt[1]) <= 0.05
    miss = attempts[9]
    assert all(f["object_position"] == miss["task"]["start_position"] for f in miss["frames"])
    assert max(f["gripper"] for f in miss["frames"]) == 0.0


def test_generator_is_deterministic(hero_twin, hero_tasks):
    a = [x["task"]["task_id"] for x in generate(hero_tasks, hero_twin, episodes=30)]
    b = [x["task"]["task_id"] for x in generate(hero_tasks, hero_twin, episodes=30)]
    assert a == b


def test_retarget_translates_seed(hero_twin, hero_tasks):
    from arrival.generate.scripted import build_seeds, make_attempt
    seeds = build_seeds(hero_tasks, hero_twin)
    t = next(t for t in hero_tasks if t["object_id"] == "mug_1" and t["pose_index"] == 1
             and t["family"] == "counter_to_sink")
    att = make_attempt(0, t, hero_twin, seeds)
    seed_frames = seeds[("counter_to_sink", "mug_1")][1]
    assert att["frames"][0]["eef"][0] == pytest.approx(seed_frames[0]["eef"][0] + 0.08)
    assert att["frames"][-1]["object_position"] == pytest.approx(seed_frames[-1]["object_position"])


@pytest.mark.parametrize("n,attempts,dropped", [(4, 4, 0), (20, 22, 2), (1000, 1111, 111)])
def test_attempt_counts(n, attempts, dropped):
    assert count_attempts(n) == {"attempts": attempts, "successes": n, "dropped": dropped}


def test_sim_texture(hero_twin, hero_tasks):
    from arrival.generate.scripted import build_seeds, make_attempt
    t = next(t for t in hero_tasks if t["object_id"] == "mug_1" and t["lighting"] == "dim")
    att = make_attempt(0, t, hero_twin, build_seeds(hero_tasks, hero_twin))
    frames = sim_texture.render_episode(att["frames"], "dim")
    assert frames.shape == (80, 64, 64, 3)
    assert tuple(frames[0][0, 0]) == (28, 32, 38)
    assert (frames[0] != frames[40]).any()
    with pytest.raises(SplatCompositeNotImplemented):
        splat_render()


def test_mimicgen_probe_skips():
    assert probe()["skipped"] is True


def test_demo_4_episodes(tmp_path):
    out = tmp_path / "out"
    res = run_demo("hero_kitchen", 4, "all", out_dir=out, scans_dir=SCANS, log=lambda *a: None)
    ds = res["dataset"]
    assert validate(ds) == []
    info = json.loads((ds / "meta" / "info.json").read_text())
    assert info["walkin_physically_valid"] is False
    assert info["walkin_generator"] == "scripted_retarget"
    assert info["total_episodes"] == 4 and info["total_frames"] == 320
    tasks = json.loads((out / "twins" / "hero_kitchen" / "tasks.json").read_text())
    assert {t["family"] for t in tasks["tasks"]} == {"counter_to_sink", "counter_to_counter"}
    assert set(info["walkin_families"]) == {"counter_to_sink", "counter_to_counter"}
    modality = json.loads((ds / "meta" / "modality.json").read_text())
    assert [modality["state"]["gripper"]["start"], modality["state"]["gripper"]["end"]] == [7, 8]
    emb = json.loads((ds / "meta" / "embodiment.json").read_text())
    assert emb["joints_are_placeholder"] is True
    assert (ds / "meta" / emb["cartesian_sidecar"]).resolve().is_file()
    assert len(list(ds.glob("videos/chunk-000/observation.images.ego_view/*.mp4"))) == 4
    t = pq.read_table(ds / "data" / "chunk-000" / "episode_000003.parquet")
    assert t.column("index")[0].as_py() == 240
    assert t.column("next.done").to_pylist()[-1] is True
    assert t.column("next.reward").to_pylist()[-1] == 1.0
    assert t.column("observation.state").to_pylist() == t.column("action").to_pylist()
    rep = json.loads(res["report"].read_text())
    assert (rep["successes"], rep["attempts"], rep["dropped"]) == (4, 4, 0)
    assert rep["dollars"]["local_cpu"] == {"usd": 0, "measured": True}
    assert all(v["measured"] is False for k, v in rep["dollars"].items() if k != "local_cpu")
    assert rep["teleop_baseline"] is None and rep["usefulness"] is None and rep["realism"] is None


def test_demo_20_report(tmp_path):
    res = run_demo("hero_kitchen", 20, "none", out_dir=tmp_path, scans_dir=SCANS, log=lambda *a: None)
    rep = res["report_data"]
    assert (rep["successes"], rep["attempts"], rep["dropped"]) == (20, 22, 2)
    assert validate(res["dataset"]) == []


def test_validator_rejects_broken(tmp_path):
    res = run_demo("hero_kitchen", 2, "all", out_dir=tmp_path, scans_dir=SCANS, log=lambda *a: None)
    ds = res["dataset"]
    m = json.loads((ds / "meta" / "modality.json").read_text())
    m["state"]["gripper"]["start"] = 6
    (ds / "meta" / "modality.json").write_text(json.dumps(m))
    assert validate(ds)
    (ds / "meta" / "embodiment.json").unlink()
    assert main(["validate", str(ds)]) == 1


def test_cli_usage_errors(tmp_path):
    assert main([]) == 2
    assert main(["bogus"]) == 2
    assert main(["demo", "--episodes", "100", "--out", str(tmp_path), "--scans", str(SCANS)]) == 2


def test_from_roomplan(tmp_path):
    res = run_demo("hero_kitchen", 2, "none", out_dir=tmp_path, scans_dir=SCANS, from_roomplan=True,
                   log=lambda *a: None)
    twin = json.loads((res["twin_dir"] / "twin.json").read_text())
    sink = next(f for f in twin["fixtures"] if f["id"] == "sink_1")
    assert sink["position"] == pytest.approx([1.6, 0.4, 0.85])
    assert any(f["source_category"] == "synthesized" for f in twin["fixtures"])
