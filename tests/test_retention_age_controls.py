import pytest

from arrival.jobs.retention import gc


@pytest.mark.parametrize("hours", [0, -1, True, float("nan"), float("inf"), "24"])
def test_gc_rejects_invalid_age_limit(tmp_path, hours):
    with pytest.raises(ValueError, match="max_age_hours"):
        gc(tmp_path, hours)


@pytest.mark.parametrize("now", [True, float("nan"), float("inf"), "today"])
def test_gc_rejects_invalid_clock(tmp_path, now):
    with pytest.raises(ValueError, match="now"):
        gc(tmp_path, 1, now=now)
