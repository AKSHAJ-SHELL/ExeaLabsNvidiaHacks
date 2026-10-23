import json

import pytest

from arrival.jobs.queue import create_job, read_job


@pytest.mark.parametrize("job_id", ["..", "../outside", "job_123", "job_" + "z" * 32, "", None])
def test_read_job_rejects_unissued_ids(tmp_path, job_id):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "status.json").write_text(json.dumps({"status": "done"}))
    assert read_job(tmp_path / "jobs", job_id) is None


def test_read_job_accepts_generated_id(tmp_path):
    status = create_job(tmp_path / "jobs", "scan.json", data=b"{}")
    assert read_job(tmp_path / "jobs", status["id"])["id"] == status["id"]
