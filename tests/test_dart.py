"""DART (`arrival sim --dart`): the arm is driven off the plan, the dataset keeps the clean plan as the action."""

import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")

from arrival.scan.bundle import load_room  # noqa: E402
from arrival.sim.collect import SimEnv, _grip_events, run_episode  # noqa: E402
from arrival.sim.policy import ScriptedExpert  # noqa: E402
from arrival.sim.tasks import finish_task, make_tasks  # noqa: E402
from arrival.twin.compile import compile_twin  # noqa: E402


@pytest.fixture(scope="module")
def twin():
    return compile_twin(load_room("hero_kitchen", "scans"))


def _rollout(twin, exec_noise):
    task = finish_task(make_tasks(twin, ["counter_to_sink"], 1, seed=3, people=0, log=lambda *_: None)[0])
    with SimEnv(twin, task, res=32) as env:
        return run_episode(env, ScriptedExpert(), task, exec_noise=exec_noise)


def test_off_by_default_changes_nothing(twin):
    a, b = _rollout(twin, 0.0), _rollout(twin, 0.0)
    assert np.array_equal(a["actions"], b["actions"]) and np.array_equal(a["states"], b["states"])


def test_noise_moves_the_arm_but_not_the_recorded_action(twin):
    clean, noisy = _rollout(twin, 0.0), _rollout(twin, 0.04)
    assert np.array_equal(clean["actions"], noisy["actions"])  # the label is the clean plan
    arm_gap = np.abs(noisy["states"][:, :7] - clean["states"][:, :7])
    assert arm_gap.max() > 0.01  # the arm really was somewhere else
    assert arm_gap.max() < 0.3  # a perturbation, not a different motion
    again = _rollout(twin, 0.04)
    assert np.array_equal(again["states"], noisy["states"])  # seeded from the task: repeatable


def test_gripper_targets_are_not_perturbed_and_events_are_found(twin):
    plan = [np.array([0, 0, 0, 0, 0, 0, 0, g]) for g in (0.05, 0.05, 0.0, 0.0, 0.05)]
    assert list(_grip_events(plan)) == [1, 3]
    assert len(_grip_events(None)) == 0
    clean, noisy = _rollout(twin, 0.0), _rollout(twin, 0.04)
    assert np.array_equal(clean["actions"][:, 7], noisy["actions"][:, 7])


def test_journal_resumes_old_runs_as_no_noise_and_refuses_another_level(tmp_path):
    import json

    from arrival.jobs.shards import FINGERPRINT_KEYS, Journal, ShardError

    old = {k: None for k in FINGERPRINT_KEYS if k != "exec_noise"}  # a journal written before DART existed
    path = tmp_path / "progress.jsonl"
    path.write_text(json.dumps({"fingerprint": old}) + "\n")
    now = {k: None for k in FINGERPRINT_KEYS}
    assert Journal(path).start({**now, "exec_noise": 0.0}, resume=True) == []
    with pytest.raises(ShardError, match="exec_noise"):
        Journal(path).start({**now, "exec_noise": 0.04}, resume=True)
