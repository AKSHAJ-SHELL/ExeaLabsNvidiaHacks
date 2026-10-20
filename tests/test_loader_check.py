import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

mujoco = pytest.importorskip("mujoco")

from arrival.cli import run_demo  # noqa: E402
from arrival.export.loader_check import check_loader, format_report  # noqa: E402
from arrival.scan.bundle import load_room  # noqa: E402
from arrival.sim.collect import collect  # noqa: E402
from arrival.twin.compile import compile_twin  # noqa: E402

from conftest import REPO, SCANS  # noqa: E402

sys.path.insert(0, str(REPO / "scripts"))
from check_dataset_loader import main as check_main  # noqa: E402


@pytest.fixture(scope="module")
def sim_ds(tmp_path_factory):
    twin = compile_twin(load_room("hero_kitchen", "scans"))
    out = tmp_path_factory.mktemp("sim")
    res = collect(twin, ["counter_to_sink"], 2, out, people=0, res=64, log=lambda *_: None)
    return res["dataset"]


@pytest.fixture
def copy(sim_ds, tmp_path):
    dst = tmp_path / "ds"
    shutil.copytree(sim_ds, dst)
    return dst


def codes(res):
    return {e["code"] for e in res["errors"]}


def edit_json(path: Path, fn):
    d = json.loads(path.read_text())
    fn(d)
    path.write_text(json.dumps(d))


def test_fresh_sim_dataset_passes(sim_ds):
    res = check_loader(sim_ds)
    assert res["ok"], res["errors"]
    i = res["info"]
    assert i["episodes"] == 2 and i["cameras"] == ["ego_view", "wrist"] and i["videos_decoded"] == 4
    assert i["padded_windows"] == 15 * 2 and i["short_episodes"] == 0
    assert i["relative_action_range"] is not None
    assert set(res["stats"]["action"]) == {"mean", "std", "min", "max", "q01", "q99"}
    assert "PASS" in format_report(sim_ds, res)


def test_placeholder_demo_is_refused(tmp_path):
    out = tmp_path / "out"
    ds = run_demo("hero_kitchen", 2, "all", out_dir=out, scans_dir=SCANS, log=lambda *a: None)["dataset"]
    res = check_loader(ds)
    assert not res["ok"] and codes(res) == {"placeholder"}
    assert "placeholder" in res["errors"][0]["msg"]


def test_nan_action(copy):
    p = copy / "data" / "chunk-000" / "episode_000000.parquet"
    t = pq.read_table(p)
    a = np.asarray(t.column("action").to_pylist(), dtype=np.float32)
    a[3, 2] = np.nan
    t = t.set_column(t.schema.get_field_index("action"), t.schema.field("action"),
                     pa.array(list(a), type=pa.list_(pa.float32())))
    pq.write_table(t, p)
    assert "nonfinite" in codes(check_loader(copy))


def test_wrong_fps_in_info(copy):
    edit_json(copy / "meta" / "info.json", lambda d: d.update(fps=30))
    c = codes(check_loader(copy))
    assert "timestamp_fps" in c and "video_fps" in c


def test_missing_wrist_mp4(copy):
    (copy / "videos" / "chunk-000" / "observation.images.wrist" / "episode_000001.mp4").unlink()
    res = check_loader(copy)
    assert codes(res) == {"missing_video"} and "wrist" in res["errors"][0]["msg"]


def test_stats_std_zero_on_moving_dim(copy):
    def zero(d):
        d["action"]["std"][0] = 0.0
    edit_json(copy / "meta" / "stats.json", zero)
    assert codes(check_loader(copy)) == {"stats_std_zero"}


def test_stats_mean_mismatch(copy):
    def shift(d):
        d["observation.state"]["mean"][1] += 1.0
    edit_json(copy / "meta" / "stats.json", shift)
    assert codes(check_loader(copy)) == {"stats_mismatch"}


def test_task_index_without_task_row(copy):
    p = copy / "data" / "chunk-000" / "episode_000001.parquet"
    t = pq.read_table(p)
    t = t.set_column(t.schema.get_field_index("task_index"), "task_index", pa.array(np.full(t.num_rows, 99)))
    pq.write_table(t, p)
    assert codes(check_loader(copy)) == {"task_index_unresolved"}


def test_cli_exit_codes(sim_ds, copy, capsys):
    assert check_main([str(sim_ds)]) == 0
    assert "PASS" in capsys.readouterr().out
    assert check_main([str(sim_ds), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    edit_json(copy / "meta" / "info.json", lambda d: d.update(fps=30))
    assert check_main([str(copy)]) == 1
    assert "FAIL" in capsys.readouterr().out
