import io

import pytest

from arrival.jobs.queue import create_job


def test_short_stream_does_not_publish_a_truncated_job(tmp_path):
    jobs = tmp_path / "jobs"
    with pytest.raises(EOFError, match="3 bytes"):
        create_job(jobs, "scan.json", src=io.BytesIO(b"ab"), length=5)
    assert list(jobs.iterdir()) == []


def test_exact_length_writes_the_job(tmp_path):
    jobs = tmp_path / "jobs"
    status = create_job(jobs, "scan.json", src=io.BytesIO(b"abc"), length=3)
    assert status["bytes"] == 3
    assert (jobs / status["id"] / "upload.bin").read_bytes() == b"abc"
