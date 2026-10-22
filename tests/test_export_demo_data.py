"""scripts/export_demo_data.py packs a recorded episode the way site/js/data.js reads it: 8 joint values per frame
(arm and gripper), even though the sim state also carries the 3-float base pose."""

import sys
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("mujoco")

from conftest import REPO  # noqa: E402

sys.path.insert(0, str(REPO / "scripts"))
import export_demo_data  # noqa: E402
from arrival.sim.collect import FPS  # noqa: E402
from arrival.sim.export import STATE_DIM  # noqa: E402


def test_joint_states_are_arm_and_gripper_only():
    n = 2 * FPS  # two seconds of control steps
    states = np.arange(n * STATE_DIM, dtype=np.float64).reshape(n, STATE_DIM) / 100
    rec = SimpleNamespace(names=["link1"], pos=[[[0.0, 0.0, float(i) / n]] for i in range(n)],
                          quat=[[[1.0, 0.0, 0.0, 0.0]]] * n, states=list(states), people_xy=[[]] * n, joint_q=[])
    packed = export_demo_data.pack_episode(rec, export_demo_data.OUT_FPS)
    rows = packed["joint_states"]
    assert len(rows) == packed["n_frames"]
    assert all(len(r) == 8 for r in rows)
    assert rows[0] == pytest.approx(states[0, :8].tolist())  # the first 8 state values, not the base pose


def test_rerun_keeps_the_hand_edited_todo_list(tmp_path, monkeypatch):
    # the export clears its output folder; site/data/todo.json is the team's to-do list and must survive that
    out = tmp_path / "data"
    out.mkdir()
    (out / "todo.json").write_text('{"items": []}')
    (out / "stale.json").write_text("{}")
    def stop(*_args, **_kwargs):  # stop right after the output folder is reset, before any sim runs
        raise RuntimeError("stop")

    monkeypatch.setattr(export_demo_data, "compile_twin", stop)
    with pytest.raises(RuntimeError, match="stop"):
        export_demo_data.main(["--out", str(out), "--scratch", str(tmp_path / "scratch")])
    assert (out / "todo.json").read_text() == '{"items": []}'
    assert not (out / "stale.json").exists()
