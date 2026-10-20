"""DEM-4: scripts/demo_all.py runs the whole story offline and reports honestly."""

import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("mujoco")

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "demo_all.py"


@pytest.fixture(scope="module")
def demo_all():
    spec = importlib.util.spec_from_file_location("demo_all", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_quick(demo_all, tmp_path):
    assert demo_all.main(["--quick", "--out", str(tmp_path)]) == 0
    s = json.loads((tmp_path / "demo_summary.json").read_text())
    assert s["physically_valid"] is True
    assert s["dataset"]["joints_are_placeholder"] is False
    assert s["successes"] >= 1
    assert [r["status"] for r in s["stages"]] == ["PASS"] * 6
    assert s["per_family"] and all(v["episodes"] == 2 for v in s["per_family"].values())
    assert all(v is None for v in s["cost"].values())
    assert demo_all.HONEST_LABEL in (tmp_path / "demo_summary.md").read_text()
    assert (tmp_path / "renders" / "hero_kitchen_top.png").is_file()


def test_missing_room_fails_with_one_line(demo_all, tmp_path, capsys):
    assert demo_all.main(["--quick", "--room", "no_such_room", "--out", str(tmp_path)]) == 1
    err = capsys.readouterr().err.strip()
    assert err.startswith("demo_all: FAIL") and "no_such_room" in err and "\n" not in err
    s = json.loads((tmp_path / "demo_summary.json").read_text())
    assert s["overall"] == "FAIL" and s["stages"][0]["status"] == "FAIL"
