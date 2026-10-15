import yaml

from arrival.twin.compile import compile_twin, layout_dict, write_twin


def _bundle(fixtures, walls=()):
    return {"schema_version": "1", "room_id": "t", "units": "meters", "frame": "z_up",
            "geometry_source": "roomplan", "blocks_claims": [], "walls": list(walls),
            "fixtures": fixtures, "objects": []}


def test_hero_fixture_types(hero_twin):
    fx = {f["id"]: f for f in hero_twin["fixtures"]}
    assert fx["sink_1"]["type"] == "sink"
    assert fx["sink_1"]["position"][2] == 0.85
    assert fx["fridge_1"]["type"] == "fridge_bottom_freezer"
    assert fx["stove_1"]["type"] == "stove"
    assert not any(f["id"].startswith("counter_synth") for f in hero_twin["fixtures"])
    assert {o["catalog_id"] for o in hero_twin["objects"]} == {"mug", "bowl", "sponge"}


def test_unknown_category_is_box():
    twin = compile_twin(_bundle([{"id": "tv", "category": "television", "size": [1, 0.1, 0.6],
                                  "position": [1, 1, 1], "yaw": 0}]))
    assert twin["fixtures"][0]["type"] == "box"
    assert layout_dict(twin)["main_group"]["bottom_row"][0]["type"] == "box"


def test_table_is_dining_counter():
    twin = compile_twin(_bundle([{"id": "t1", "category": "table", "size": [1, 1, 0.75],
                                  "position": [1, 1, 0.375], "yaw": 0}]))
    assert twin["fixtures"][0]["type"] == "counter"
    assert twin["fixtures"][0]["default_config_name"] == "dining"


def test_sink_only_synthesizes_counter():
    twin = compile_twin(_bundle([{"id": "sink_1", "category": "sink", "size": [0.6, 0.5, 0.25],
                                  "position": [1.6, 0.4, 0.85], "yaw": 0}]))
    counters = [f for f in twin["fixtures"] if f["type"] == "counter"]
    assert len(counters) == 1
    c = counters[0]
    assert c["size"][2] == 0.92 and c["position"][2] == 0.46
    assert c["size"][0] == 1.2 and c["position"][:2] == [1.6, 0.4]


def test_layout_yaml(tmp_path, hero_twin):
    _, layout_path = write_twin(hero_twin, tmp_path)
    doc = yaml.safe_load(layout_path.read_text())
    assert "main_group" in doc and "bottom_row" in doc["main_group"]
    walls = {w["name"]: w for w in doc["room"]["walls"]}
    assert walls["wall_north"]["size"] == [4.0, 0.02, 2.4]
    assert walls["wall_north"]["pos"] == [2.0, 0.0, 1.2]
    assert walls["wall_east"]["size"] == [0.02, 3.0, 2.4]
    assert doc["room"]["floor"][0]["size"] == [4.0, 3.0, 0.02]
    assert doc["room"]["floor"][0]["pos"] == [2.0, 1.5, 0.0]
