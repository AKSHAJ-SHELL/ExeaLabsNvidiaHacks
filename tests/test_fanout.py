"""C1 offline: fanout to a fake local backend with resumable storage (arrival/jobs/fanout.py)."""

import json

import pytest

pytest.importorskip("mujoco")

from arrival.export.validate import validate  # noqa: E402
from arrival.jobs.fanout import FanoutConfig, LocalBackend, NebiusBackendStub, run_fanout  # noqa: E402
from arrival.jobs.shards import ShardError  # noqa: E402
from conftest import SCANS  # noqa: E402

CFG = FanoutConfig("r1", 2, "hero_kitchen", "counter_to_sink,open_drawer", 4, 0, 32, 3, str(SCANS))
quiet = lambda *_: None  # noqa: E731


def _rows(ds):
    return [json.loads(x) for x in (ds / "meta" / "episodes.jsonl").read_text().splitlines()]


def _frames(ds):
    import pyarrow.parquet as pq

    return [pq.read_table(p).to_pydict() for p in sorted(ds.glob("data/chunk-*/episode_*.parquet"))]


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    root = tmp_path_factory.mktemp("ref")
    be = LocalBackend(root / "store", root / "scratch")
    return run_fanout(be, CFG, root / "out", log=quiet)


def test_failed_shard_is_retried_and_dataset_is_valid(reference, tmp_path):
    be = LocalBackend(tmp_path / "store", tmp_path / "scratch", fail_first={1})
    res = run_fanout(be, CFG, tmp_path / "out", log=quiet)
    assert (1, 2) in be.submissions and (0, 2) not in be.submissions  # only shard 1 was retried
    assert validate(res["dataset"]) == [] and res["ran"] == [0, 1]
    assert _rows(res["dataset"]) == _rows(reference["dataset"])
    assert _frames(res["dataset"]) == _frames(reference["dataset"])


def test_killed_run_resumes_skipping_done_shards(reference, tmp_path):
    be = LocalBackend(tmp_path / "store", tmp_path / "scratch")

    def kill(i):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_fanout(be, CFG, tmp_path / "out", parallel=1, on_shard_done=kill, log=quiet)
    assert be.exists("r1/done/0of2.json") and not be.exists("r1/done/1of2.json")
    be2 = LocalBackend(tmp_path / "store", tmp_path / "scratch")  # a new process, same storage
    res = run_fanout(be2, CFG, tmp_path / "out", log=quiet)
    assert res["skipped"] == [0] and res["ran"] == [1]
    assert [s for s, _ in be2.submissions] == [1]  # shard 0 was not run again
    assert validate(res["dataset"]) == []
    assert _rows(res["dataset"]) == _rows(reference["dataset"])
    assert _frames(res["dataset"]) == _frames(reference["dataset"])
    assert res["info"]["total_frames"] == reference["info"]["total_frames"]


def test_gives_up_after_max_attempts_and_refuses_other_settings(tmp_path):
    be = LocalBackend(tmp_path / "store", tmp_path / "s", command=lambda c, i, o: ["false"])
    with pytest.raises(ShardError, match="failed 2 times"):
        run_fanout(be, CFG, tmp_path / "out", max_attempts=2, log=quiet)
    with pytest.raises(ShardError, match="different settings"):
        run_fanout(be, FanoutConfig("r1", 3), tmp_path / "out", log=quiet)


def test_nebius_stub_is_not_a_backend():
    with pytest.raises(NotImplementedError):
        NebiusBackendStub().submit(CFG, 0)


@pytest.mark.parametrize("run_id", ["", "..", "../escape", "a/b", "/tmp/escape", "a" * 65])
def test_run_id_cannot_escape_scratch_or_storage(run_id):
    with pytest.raises(ShardError, match="run_id"):
        FanoutConfig(run_id, 2)

@pytest.mark.parametrize("controls", [
    {"parallel": 0}, {"parallel": -1}, {"parallel": True},
    {"max_attempts": 0}, {"max_attempts": -1},
    {"poll_seconds": -0.1}, {"poll_seconds": float("nan")}, {"poll_seconds": float("inf")},
])
def test_bad_fanout_controls_fail_before_submitting(controls, tmp_path):
    be = LocalBackend(tmp_path / "store", tmp_path / "scratch")
    with pytest.raises(ShardError):
        run_fanout(be, CFG, tmp_path / "out", **controls, log=quiet)
    assert be.submissions == []
    assert not be.exists("r1/run.json")
