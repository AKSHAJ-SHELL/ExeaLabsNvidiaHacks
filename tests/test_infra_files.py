import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_TARGETS = {"install", "test", "sim", "validate", "serve", "clean", "demo"}


def _ci():
    return yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())


def _steps(ci):
    return [s for job in ci["jobs"].values() for s in job["steps"]]


def _make_targets():
    return set(re.findall(r"^([A-Za-z_][\w-]*):", (ROOT / "Makefile").read_text(), re.M))


def test_ci_runs_pytest_demo_and_validate():
    runs = "\n".join(s.get("run", "") for s in _steps(_ci()))
    assert "pytest -q -p no:cacheprovider" in runs
    assert "python -m arrival demo --episodes 2" in runs
    assert "python -m arrival validate" in runs


def test_ci_is_offline_and_headless():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "secrets." not in text
    ci = _ci()
    job = next(iter(ci["jobs"].values()))
    assert job["env"]["MUJOCO_GL"] == "egl"
    assert "osmesa" in text and "libosmesa6" in text and "libegl1" in text and "libgl1" in text
    assert job["timeout-minutes"] == 20
    assert job["strategy"]["matrix"]["python-version"] == ["3.11", "3.12"]
    assert ci["concurrency"]["cancel-in-progress"] is True


def test_makefile_has_required_and_readme_targets():
    targets = _make_targets()
    assert REQUIRED_TARGETS <= targets
    section = (ROOT / "README.md").read_text().split("## Get started", 1)[1].split("\n## ", 1)[0]
    named = set(re.findall(r"\bmake ([A-Za-z_][\w-]*)", section))
    assert named <= targets


def test_makefile_clean_only_removes_out():
    text = (ROOT / "Makefile").read_text()
    assert "OUT ?= out" in text
    assert "rm -rf $(OUT)" in text.split("\nclean:", 1)[1]


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
def test_make_dry_run_parses():
    r = subprocess.run(["make", "-n", "test", "sim", "validate", "demo"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "scripts/demo_all.py" in r.stdout
    assert "--episodes 2 --people 1 --res 64" in r.stdout


def test_dockerfile_and_ignore():
    d = (ROOT / "Dockerfile").read_text()
    assert "FROM python:3.11-slim" in d
    assert "MUJOCO_GL=egl" in d and 'pip install -e ".[sim]"' in d
    assert 'CMD ["python", "-m", "arrival", "serve", "--host", "0.0.0.0"]' in d
    ignored = (ROOT / ".dockerignore").read_text().split()
    for p in ("out/", ".venv/", ".git/", "ios/", "*.egg-info"):
        assert p in ignored


def _docker_up():
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _docker_up(), reason="docker daemon not running")
def test_docker_image_builds_and_runs():
    b = subprocess.run(["docker", "build", "-q", "-t", "arrival-test", "."], cwd=ROOT, capture_output=True, text=True)
    assert b.returncode == 0, b.stderr
    r = subprocess.run(["docker", "run", "--rm", "arrival-test", "python", "-m", "arrival", "validate", "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
