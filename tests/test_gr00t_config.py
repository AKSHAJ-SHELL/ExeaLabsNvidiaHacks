"""The GR00T modality config must agree with the meta/modality.json our exporter writes.

GR00T itself needs a GPU box, so its modules are stubbed: the config file is executed for real and the
ModalityConfig objects it builds are compared against a freshly written dataset.
"""

import json
import runpy
import sys
import types
from pathlib import Path

import pytest

mujoco = pytest.importorskip("mujoco")

from arrival.scan.bundle import load_room  # noqa: E402
from arrival.sim.collect import collect  # noqa: E402
from arrival.twin.compile import compile_twin  # noqa: E402

CONFIG = Path(__file__).resolve().parents[1] / "configs" / "gr00t" / "arrival_panda_config.py"


class _Cfg:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _load_config(monkeypatch):
    registered = []
    enums = {n: types.SimpleNamespace(RELATIVE="rel", ABSOLUTE="abs", NON_EEF="joint", DEFAULT="default")
             for n in ("ActionRepresentation", "ActionType", "ActionFormat")}
    mods = {
        "gr00t": types.ModuleType("gr00t"),
        "gr00t.configs": types.ModuleType("gr00t.configs"),
        "gr00t.configs.data": types.ModuleType("gr00t.configs.data"),
        "gr00t.configs.data.embodiment_configs": types.SimpleNamespace(
            register_modality_config=lambda cfg, embodiment_tag: registered.append((cfg, embodiment_tag))),
        "gr00t.data": types.ModuleType("gr00t.data"),
        "gr00t.data.embodiment_tags": types.SimpleNamespace(EmbodimentTag=types.SimpleNamespace(NEW_EMBODIMENT="NEW")),
        "gr00t.data.types": types.SimpleNamespace(ActionConfig=_Cfg, ModalityConfig=_Cfg, **enums),
    }
    for name, mod in mods.items():
        monkeypatch.setitem(sys.modules, name, mod)
    runpy.run_path(str(CONFIG))
    assert len(registered) == 1 and registered[0][1] == "NEW"
    return registered[0][0]


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    twin = compile_twin(load_room("hero_kitchen", "scans"))
    res = collect(twin, ["open_drawer"], 1, tmp_path_factory.mktemp("ds"), people=0, res=64, log=lambda *_: None)
    return res["dataset"]


def test_config_keys_match_dataset_modality(monkeypatch, dataset):
    cfg = _load_config(monkeypatch)
    modality = json.loads((dataset / "meta" / "modality.json").read_text())
    assert cfg["video"].modality_keys == list(modality["video"])
    assert cfg["state"].modality_keys == list(modality["state"])
    assert cfg["action"].modality_keys == list(modality["action"])
    assert cfg["language"].modality_keys == ["annotation." + k for k in modality["annotation"]]


def test_config_action_setup(monkeypatch, dataset):
    cfg = _load_config(monkeypatch)
    act = cfg["action"]
    assert len(act.action_configs) == len(act.modality_keys)
    assert [c.rep for c in act.action_configs] == ["rel", "abs"]  # arm as deltas, gripper absolute
    assert act.delta_indices == list(range(16))
    assert cfg["video"].delta_indices == cfg["state"].delta_indices == [0]
    # dims the config relies on: 7-dof arm + 1 gripper, same layout for state and action
    modality = json.loads((dataset / "meta" / "modality.json").read_text())
    for group in ("state", "action"):
        assert [(v["start"], v["end"]) for v in modality[group].values()] == [(0, 7), (7, 8)]
