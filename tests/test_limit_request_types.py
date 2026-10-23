import pytest

from arrival.jobs.limits import LimitError, Limits


@pytest.mark.parametrize("episodes", [0, -1, True, 1.5, "2"])
def test_invalid_episode_counts_are_rejected(episodes):
    with pytest.raises(LimitError, match="episodes must be"):
        Limits().check_request(episodes, 0)


@pytest.mark.parametrize("people", [-1, True, 1.5, "2"])
def test_invalid_people_counts_are_rejected(people):
    with pytest.raises(LimitError, match="people must be"):
        Limits().check_request(1, people)


def test_zero_people_and_valid_counts_remain_supported():
    Limits().check_request(1, 0)
