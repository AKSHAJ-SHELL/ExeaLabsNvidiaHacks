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
    assert c["size"][0] == 1.8 and c["position"][:2] == [1.6, 0.4]


def test_sink_on_counter_height_storage_does_not_synthesize_overlapping_counter():
    import math

    sink = {"id": "sink", "category": "sink", "size": [0.6, 0.5, 0.25],
            "position": [2.0, 1.5, 0.85], "yaw": -math.pi / 2}
    base = {"id": "base", "category": "storage", "size": [1.0, 0.6, 0.9],
            "position": [2.0, 1.5, 0.45], "yaw": -math.pi / 2}
    twin = compile_twin(_bundle([sink, base]))
    assert [f["id"] for f in twin["fixtures"]] == ["sink", "base"]
    assert twin["fixtures"][1]["type"] == "hinge_cabinet"

    tall_base = {**base, "size": [1.0, 0.6, 2.0], "position": [2.0, 1.5, 1.0]}
    twin = compile_twin(_bundle([sink, tall_base]))
    assert "counter_synth_sink" in {f["id"] for f in twin["fixtures"]}


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


def test_yawed_sink_counter_and_containment():
    import math

    from arrival.tasks.propose import in_top_rect

    yaw = math.pi / 2
    twin = compile_twin(_bundle([{"id": "s", "category": "sink", "size": [0.6, 0.5, 0.25],
                                  "position": [0.4, 2.0, 0.85], "yaw": yaw}]))
    c = next(f for f in twin["fixtures"] if f["type"] == "counter")
    assert c["yaw"] == yaw
    assert in_top_rect([0.4, 2.8], c) and not in_top_rect([1.2, 2.0], c)  # long axis runs along world Y


def test_oblique_wall_gets_z_rot():
    import math

    w = {"id": "w", "start": [0, 0], "end": [3, 3], "height": 2.4, "thickness": 0.1}
    doc = layout_dict(compile_twin(_bundle([], [w])))
    entry = doc["room"]["walls"][0]
    assert entry["z_rot"] == round(math.pi / 4, 6)
    assert entry["size"][0] == round(math.hypot(3, 3), 6)


def test_place_default_objects_seeded():
    from arrival.tasks.propose import on_counter
    from arrival.twin.compile import place_default_objects

    fx = [{"id": "s", "category": "sink", "size": [0.6, 0.5, 0.25], "position": [1.6, 0.4, 0.85], "yaw": 0}]
    a, b = compile_twin(_bundle(fx)), compile_twin(_bundle(fx))
    pa, pb = place_default_objects(a, seed=3), place_default_objects(b, seed=3)
    assert pa == pb and {o["label"] for o in pa} == {"mug", "bowl", "plate", "cup", "apple"}
    assert pa[0]["size"] != [0.08, 0.08, 0.1] and 0.07 < pa[0]["size"][0] < 0.09  # seeded size, not the nominal
    counter = next(f for f in a["fixtures"] if f["type"] == "counter")
    assert all(on_counter(o, counter) for o in pa)


def test_stove_between_counters_gets_no_synthesized_counter():
    from arrival.twin.compile import compile_twin

    bundle = {"schema_version": "1", "room_id": "r", "units": "meters", "frame": "z_up",
              "geometry_source": "authored_sample", "blocks_claims": [], "walls": [], "objects": [],
              "fixtures": [
                  {"id": "left", "category": "counter", "size": [1.0, 0.65, 0.92], "position": [0.5, 0.4, 0.46], "yaw": 0},
                  {"id": "stove", "category": "stove", "size": [0.7, 0.65, 0.9], "position": [1.35, 0.4, 0.45], "yaw": 0},
                  {"id": "right", "category": "counter", "size": [1.0, 0.65, 0.92], "position": [2.2, 0.4, 0.46], "yaw": 0},
                  {"id": "lone", "category": "stove", "size": [0.7, 0.65, 0.9], "position": [1.35, 2.5, 0.45], "yaw": 0}]}
    ids = [f["id"] for f in compile_twin(bundle)["fixtures"]]
    assert "counter_synth_stove" not in ids  # flanked by counters: no phantom counter over the neighbours
    assert "counter_synth_lone" in ids  # a stove with nothing around it still gets a counter
