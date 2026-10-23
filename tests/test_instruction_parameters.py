import pytest

from arrival.tasks.instructions import generate_instructions


@pytest.mark.parametrize("n", [0, -1, True, 1.5, "8"])
def test_invalid_instruction_count(n, tmp_path):
    with pytest.raises(ValueError, match="n must be"):
        generate_instructions("counter_to_sink", n=n, cache_path=tmp_path / "cache.json")


@pytest.mark.parametrize("ratio", [-0.1, 0, 1, 1.1, True, float("nan"), float("inf")])
def test_invalid_eval_ratio(ratio, tmp_path):
    with pytest.raises(ValueError, match="eval_ratio"):
        generate_instructions("counter_to_sink", eval_ratio=ratio, cache_path=tmp_path / "cache.json")
