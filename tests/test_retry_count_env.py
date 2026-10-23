import pytest

from arrival.jobs.limits import LimitError, Limits


def test_retry_count_must_be_whole():
    with pytest.raises(LimitError, match="ARRIVAL_JOB_RETRIES.*whole number"):
        Limits.from_env({"ARRIVAL_JOB_RETRIES": "1.5"})
    assert Limits.from_env({"ARRIVAL_JOB_RETRIES": "0"}).job_retries == 0
    assert Limits.from_env({"ARRIVAL_JOB_RETRIES": "2"}).job_retries == 2
