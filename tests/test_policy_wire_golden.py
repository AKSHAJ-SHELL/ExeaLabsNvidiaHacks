"""Golden wire format for the policy server. The golden file was written from arrival.policy_server.protocol itself:
it pins the format against accidental change, it is not a capture from a real Isaac-GR00T server."""

import json
from pathlib import Path

import numpy as np
import pytest

from arrival.policy_server.protocol import (ProtocolError, decode_image, decode_request, decode_response,
                                            encode_request, encode_response)

GOLDEN = json.loads((Path(__file__).parent / "golden" / "policy_wire.json").read_text())
STATE = np.array([0.1, -0.2, 0.3, -1.5, 0.0, 1.2, 0.4, 0.04])


def _obs():
    ego = np.zeros((2, 2, 3), np.uint8)
    ego[0, 0], ego[1, 1] = [255, 0, 0], [0, 0, 255]
    return {"state": STATE, "ego_view": ego, "wrist": np.full((2, 2, 3), 200, np.uint8)}


def test_golden_request_matches_encoder():
    body = encode_request(_obs(), "open the drawer")
    g = GOLDEN["request"]
    assert set(body) == set(g) == {"video.ego_view", "video.wrist", "state.single_arm", "state.gripper",
                                   "annotation.human.task_description"}
    for k in ("state.single_arm", "state.gripper", "annotation.human.task_description"):
        assert body[k] == g[k]
    assert len(g["state.single_arm"]) == 7 and len(g["state.gripper"]) == 1
    for k in ("video.ego_view", "video.wrist"):  # pixels, not PNG bytes (zlib output may differ by version)
        assert np.array_equal(decode_image(body[k]), decode_image(g[k]))
    assert decode_request(g)["state"].shape == (8,)


def test_golden_response_is_8_float_chunk():
    r = GOLDEN["response"]
    assert np.array(r["action.single_arm"]).shape == (3, 7) and np.array(r["action.gripper"]).shape == (3, 1)
    chunk = decode_response(r)
    assert chunk.shape == (3, 8)
    assert np.allclose(chunk[:, 7], STATE[7]) and np.allclose(chunk[:, 0] - STATE[0], [0, 0.01, 0.02])
    assert encode_response(chunk) == r


def test_11_float_state_or_chunk_is_refused_clearly():
    with pytest.raises(ProtocolError, match="8-float arm schema.*\\[11\\]"):
        encode_request({**_obs(), "state": np.zeros(11)}, "x")
    with pytest.raises(ProtocolError, match="8-float arm schema"):
        encode_response(np.zeros((4, 11)))
    with pytest.raises(ProtocolError, match="chunk must be"):
        encode_response(np.zeros(8))
    with pytest.raises(ProtocolError, match="shape \\[T,7\\]"):
        decode_response({"action.single_arm": [[0.0] * 10], "action.gripper": [[0.0]]})
    body = dict(GOLDEN["request"])
    body["state.single_arm"] = [0.0] * 10
    with pytest.raises(ProtocolError, match="7 finite floats, got shape \\[10\\]"):
        decode_request(body)


def test_bad_frame_shape_refused():
    with pytest.raises(ProtocolError, match="HxWx3"):
        encode_request({"state": STATE, "ego_view": np.zeros((4, 4), np.uint8)}, "x")
