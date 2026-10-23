import pytest

from arrival.tasks.instructions import generate_instructions, load_cache


@pytest.mark.parametrize("value", ["[]", "null", '"bad"'])
def test_non_object_cache_is_ignored(tmp_path, monkeypatch, value):
    cache = tmp_path / "instructions.json"
    cache.write_text(value)
    assert load_cache(cache) == {}
    monkeypatch.setattr("arrival.models.token_factory.complete", lambda **_: '["Move the mug"]')
    result = generate_instructions("counter_to_sink", "mug", cache_path=cache)
    assert result["train"] == ["Move the mug"]
