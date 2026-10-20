from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCANS = REPO / "scans"


def pytest_addoption(parser):
    parser.addoption("--no-render", action="store_true", help="skip tests when they need a MuJoCo renderer")


@pytest.fixture(autouse=True)
def render_requirement(request, monkeypatch):
    if not request.config.getoption("--no-render"):
        return
    if request.node.get_closest_marker("render"):
        pytest.skip("requires OpenGL; covered by the rendering job")
    import importlib.util

    if importlib.util.find_spec("mujoco") is not None:
        def requires_gl(*args, **kwargs):
            pytest.skip("requires OpenGL; covered by the rendering job")

        monkeypatch.setattr("mujoco.Renderer", requires_gl)


@pytest.fixture
def hero_bundle():
    from arrival.scan.bundle import load_room

    return load_room("hero_kitchen", SCANS)


@pytest.fixture
def hero_twin(hero_bundle):
    from arrival.twin.compile import compile_twin

    return compile_twin(hero_bundle)
