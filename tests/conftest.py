import importlib.util
import json
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
    _keep_shard(config, items)


SHARD_ENV = "ARRIVAL_TEST_SHARD"  # "i/n" (1-based): run only the test files assigned to shard i of n (CI rendering)
SHARD_WEIGHTS = Path(__file__).with_name("shard_weights.json")  # seconds per test file, from a full run's --durations


def shard_files(files, n: int, weights: dict) -> list[list[str]]:
    """Whole test files split into n groups of about equal time: heaviest first, each to the least loaded group
    (ties to the lowest index). Files with no measured weight count 1 s. Deterministic, so every xdist worker
    and every CI job derives the same split."""
    groups, load = [[] for _ in range(n)], [0.0] * n
    for f in sorted(files, key=lambda f: (-weights.get(f, 1.0), f)):
        k = min(range(n), key=lambda j: (load[j], j))
        groups[k].append(f)
        load[k] += weights.get(f, 1.0)
    return groups


def _keep_shard(config, items) -> None:
    spec = os.environ.get(SHARD_ENV, "").strip()
    if not spec:
        return
    i, n = (int(x) for x in spec.split("/"))
    if not 1 <= i <= n:
        raise pytest.UsageError(f"{SHARD_ENV}={spec!r}: expected i/n with 1 <= i <= n")
    weights = json.loads(SHARD_WEIGHTS.read_text(encoding="utf-8")) if SHARD_WEIGHTS.exists() else {}
    files = sorted({item.nodeid.split("::")[0] for item in items})
    mine = set(shard_files(files, n, weights)[i - 1])
    keep = [item for item in items if item.nodeid.split("::")[0] in mine]
    config.hook.pytest_deselected(items=[item for item in items if item.nodeid.split("::")[0] not in mine])
    items[:] = keep


@pytest.fixture
def hero_bundle():
    from arrival.scan.bundle import load_room

    return load_room("hero_kitchen", SCANS)


@pytest.fixture
def hero_twin(hero_bundle):
    from arrival.twin.compile import compile_twin

    return compile_twin(hero_bundle)
