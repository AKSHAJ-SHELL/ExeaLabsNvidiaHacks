from arrival.jobs.queue import create_job, write_status
from arrival.jobs.retention import delete_job


def test_delete_job_refuses_mismatched_status_id(tmp_path):
    out = tmp_path / "out"
    job = create_job(out / "jobs", "scan.json", data=b"{}")
    folder = out / "jobs" / job["id"]
    write_status(folder, {**job, "id": "job_" + "0" * 32, "status": "done"})
    assert delete_job(out, job["id"]) is None
    assert folder.exists()
