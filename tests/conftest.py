import os
from pathlib import Path

import pytest

# a developer's real .env (API keys, a live policy server) must never reach a test: tests stay offline
os.environ["ARRIVAL_DOTENV"] = "0"

REPO = Path(__file__).resolve().parents[1]
SCANS = REPO / "scans"


@pytest.fixture
def hero_bundle():
    from arrival.scan.bundle import load_room

    return load_room("hero_kitchen", SCANS)


@pytest.fixture
def hero_twin(hero_bundle):
    from arrival.twin.compile import compile_twin

    return compile_twin(hero_bundle)
