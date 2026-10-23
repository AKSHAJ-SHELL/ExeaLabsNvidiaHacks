import pytest

from arrival.jobs.queue import create_job, write_status
from arrival.jobs.retention import gc


@pytest.mark.parametrize("stamp", [float("nan"), float("inf"), True, "yesterday"])
def test_gc_skips_invalid_finished_timestamps(tmp_path, stamp):
    out = tmp_path / "out"
    job = create_job(out / "jobs", "scan.json", data=b"{}")
    folder = out / "jobs" / job["id"]
    write_status(folder, {**job, "status": "done", "finished_at": stamp})
    assert gc(out, 1, now=10000)["removed"] == []
    assert folder.exists()
