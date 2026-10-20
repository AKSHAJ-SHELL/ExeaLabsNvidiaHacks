import json
import urllib.error
import urllib.request

import numpy as np
import pytest

from arrival.policy_server import gr00t_shim
from arrival.policy_server.mock_server import MockPolicyServer
from arrival.policy_server.protocol import (ProtocolError, decode_image, decode_request, decode_response,
                                            encode_request, encode_response)
from arrival.sim.policy import VLAClient

STATE = np.array([0.1, -0.2, 0.3, -1.5, 0.0, 1.2, 0.4, 0.04])


def _obs(res=16, wrist=True):
    obs = {"state": STATE, "ego_view": np.full((res, res, 3), 7, np.uint8)}
    if wrist:
        obs["wrist"] = np.full((res, res, 3), 200, np.uint8)
    return obs


def _post(url, path, body):
    req = urllib.request.Request(url + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=5)


def test_request_has_both_video_keys_and_split_state():
    body = encode_request(_obs(), "open the drawer")
    assert {"video.ego_view", "video.wrist"} <= set(body)
    assert np.allclose(body["state.single_arm"], STATE[:7]) and len(body["state.single_arm"]) == 7
    assert body["state.gripper"] == [0.04]
    assert body["annotation.human.task_description"] == "open the drawer"
    assert decode_image(body["video.wrist"])[0, 0, 0] == 200
    req = decode_request(body)
    assert np.allclose(req["state"], STATE) and set(req["video"]) == {"ego_view", "wrist"}


def test_request_without_wrist_camera_sends_ego_only():
    body = encode_request(_obs(wrist=False), "x")
    assert "video.ego_view" in body and "video.wrist" not in body


@pytest.mark.parametrize("bad", [
    {},
    {"action.single_arm": [[0.0] * 7]},
    {"action.single_arm": [[0.0] * 6], "action.gripper": [[0.0]]},
    {"action.single_arm": [[0.0] * 7], "action.gripper": [[0.0, 0.0]]},
    {"action.single_arm": [], "action.gripper": []},
    {"action.single_arm": [0.0] * 7, "action.gripper": [0.0]},
    {"action.single_arm": [[float("nan")] * 7], "action.gripper": [[0.0]]},
    {"action.single_arm": [[0.0] * 7] * 2, "action.gripper": [[0.0]]},
    {"action.single_arm": [["a"] * 7], "action.gripper": [[0.0]]},
    [1, 2],
])
def test_malformed_response_raises(bad):
    with pytest.raises(ProtocolError):
        decode_response(bad)


def test_response_roundtrip():
    chunk = np.tile(STATE, (5, 1))
    assert np.allclose(decode_response(json.loads(json.dumps(encode_response(chunk)))), chunk)


def test_mock_hold_and_health():
    with MockPolicyServer(chunk=3) as srv:
        assert json.load(urllib.request.urlopen(srv.url + "/health", timeout=5))["ok"] is True
        out = json.load(_post(srv.url, "/act", encode_request(_obs(), "x")))
        assert np.allclose(decode_response(out), np.tile(STATE, (3, 1)))
        with pytest.raises(urllib.error.HTTPError) as e:
            _post(srv.url, "/act", {"state.single_arm": [0.0]})
        assert e.value.code == 400


def test_mock_noise_is_seeded():
    def run(seed):
        with MockPolicyServer(mode="noise", seed=seed) as srv:
            return decode_response(json.load(_post(srv.url, "/act", encode_request(_obs(), "x"))))
    a, b, c = run(1), run(1), run(2)
    assert np.allclose(a, b) and not np.allclose(a, c) and not np.allclose(a[0], STATE)


def test_client_queues_chunk_and_fails_clearly():
    with MockPolicyServer(chunk=4) as srv:
        c = VLAClient(srv.url)
        c.reset(None, {"instruction": "x"})
        for _ in range(8):
            assert np.allclose(c.act(_obs()), STATE)
        assert srv.requests == 2  # one request per 4-step chunk
    with MockPolicyServer(mode="fail_after_n", fail_after=1) as srv:
        c = VLAClient(srv.url)
        c.reset(None, {"instruction": "x"})
        c.act(_obs())
        c.queue = []
        with pytest.raises(OSError):  # HTTPError: the existing path the CLI reports
            c.act(_obs())


def test_client_rejects_malformed_server_reply():
    class Bad(MockPolicyServer):
        def act(self, state):
            return np.zeros((0, 8))
    with Bad() as srv:
        c = VLAClient(srv.url)
        c.reset(None, {"instruction": "x"})
        with pytest.raises(ProtocolError):
            c.act(_obs())


def test_shim_observation_and_chunk_mapping():
    req = decode_request(encode_request(_obs(res=16), "task"))
    obs = gr00t_shim.to_observation(req)
    assert obs["video"]["wrist"].shape == (1, 1, 16, 16, 3)
    assert obs["state"]["single_arm"].shape == (1, 1, 7) and obs["state"]["gripper"].shape == (1, 1, 1)
    assert obs["language"]["annotation.human.task_description"] == [["task"]]
    chunk = gr00t_shim.to_chunk({"single_arm": np.zeros((1, 6, 7)), "gripper": np.ones((1, 6, 1))})
    assert chunk.shape == (6, 8) and chunk[0, 7] == 1.0


def test_shim_exits_without_gr00t(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "gr00t", None)
    with pytest.raises(SystemExit) as e:
        gr00t_shim.load_policy("m", "c.py", "cpu", "new_embodiment")
    assert "not installed" in str(e.value)


# the sim-backed tests: tiny renders, one episode
mujoco = pytest.importorskip("mujoco")

from arrival.eval.harness import evaluate  # noqa: E402
from arrival.scan.bundle import load_room  # noqa: E402
from arrival.twin.compile import compile_twin  # noqa: E402


@pytest.fixture(scope="module")
def twin():
    return compile_twin(load_room("hero_kitchen", "scans"))


def test_eval_vla_against_hold_mock(twin, monkeypatch, tmp_path):
    with MockPolicyServer() as srv:
        monkeypatch.setenv("GR00T_POLICY_URL", srv.url)
        rep = evaluate(twin, ["open_drawer"], 1, policy_name="vla", checkpoint_id="test-mock", people=0, res=64, out_dir=tmp_path,
                       log=lambda *_: None)
        assert srv.requests > 0
    assert rep["totals"]["errors"] == 0 and rep["totals"]["episodes"] == 1


def test_eval_vla_dead_server_takes_existing_failure_path(twin, monkeypatch, tmp_path):
    with MockPolicyServer(mode="fail_after_n", fail_after=2) as srv:
        monkeypatch.setenv("GR00T_POLICY_URL", srv.url)
        with pytest.raises(OSError):  # nothing finished before the server died: the CLI turns this into exit 2
            evaluate(twin, ["open_drawer"], 1, policy_name="vla", checkpoint_id="test-mock", people=0, res=64, out_dir=tmp_path,
                     log=lambda *_: None)


def test_cli_eval_vla_unset_exits_2(monkeypatch):
    from arrival.cli import main
    monkeypatch.delenv("GR00T_POLICY_URL", raising=False)
    assert main(["eval", "--policy", "vla", "--checkpoint-id", "test-mock", "--episodes", "1", "--families", "open_drawer", "--people", "0",
                 "--res", "64"]) == 2
