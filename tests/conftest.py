import importlib.util
import os
from pathlib import Path

import pytest

# a developer's real .env (API keys, a live policy server) must never reach a test: tests stay offline
os.environ["ARRIVAL_DOTENV"] = "0"

REPO = Path(__file__).resolve().parents[1]
SCANS = REPO / "scans"


def pytest_addoption(parser):
    parser.addoption("--no-render", action="store_true", help="skip tests when they need a MuJoCo renderer")


def pytest_configure(config):
    if not config.getoption("--no-render") or importlib.util.find_spec("mujoco") is None:
        return

    def requires_gl(*args, **kwargs):
        pytest.skip("requires OpenGL; covered by the rendering job")

    patch = pytest.MonkeyPatch()
    config.add_cleanup(patch.undo)
    patch.setattr("mujoco.Renderer", requires_gl)


def pytest_collection_modifyitems(config, items):
    if config.getoption("--no-render"):
        skip = pytest.mark.skip(reason="requires OpenGL; covered by the rendering job")
        for item in items:
            if item.get_closest_marker("render"):
                item.add_marker(skip)


@pytest.fixture
def hero_bundle():
    from arrival.scan.bundle import load_room

    return load_room("hero_kitchen", SCANS)


@pytest.fixture
def hero_twin(hero_bundle):
    from arrival.twin.compile import compile_twin

    return compile_twin(hero_bundle)
