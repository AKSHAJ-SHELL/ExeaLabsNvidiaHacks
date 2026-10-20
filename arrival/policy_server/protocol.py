"""Wire format shared by VLAClient, the mock server and the GR00T shim.

POST /act   {"video.ego_view": b64 PNG, "video.wrist": b64 PNG, "state.single_arm": [7], "state.gripper": [1],
             "annotation.human.task_description": str}
        ->  {"action.single_arm": [[7] * T], "action.gripper": [[1] * T]}   (absolute joint targets, T >= 1)
GET /health -> {"ok": true, ...}

The keys match configs/gr00t/arrival_panda_config.py and the meta/modality.json of datasets written by `arrival sim`.
"""

from __future__ import annotations

import base64
import io

import numpy as np

VIDEO_KEYS = ("ego_view", "wrist")
TASK_KEY = "annotation.human.task_description"
ARM_DOF = 7
ACTION_KEYS = ("action.single_arm", "action.gripper")


class ProtocolError(ValueError):
    """A request or response that does not follow the contract."""


def encode_image(img: np.ndarray) -> str:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(np.asarray(img, dtype=np.uint8)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def decode_image(s: str) -> np.ndarray:
    from PIL import Image

    try:
        return np.asarray(Image.open(io.BytesIO(base64.b64decode(s))).convert("RGB"))
    except Exception as e:
        raise ProtocolError(f"undecodable image: {e}") from e


def encode_request(obs: dict, instruction: str) -> dict:
    """obs has 'state' [8] and one frame per camera; the wrist frame is sent whenever the env has that camera."""
    state = np.asarray(obs["state"], dtype=float)
    body = {f"video.{k}": encode_image(obs[k]) for k in VIDEO_KEYS if k in obs}
    if "video.ego_view" not in body:
        raise ProtocolError("obs has no ego_view frame")
    body["state.single_arm"] = state[:ARM_DOF].tolist()
    body["state.gripper"] = state[ARM_DOF:ARM_DOF + 1].tolist()
    body[TASK_KEY] = instruction
    return body


def decode_request(body: dict) -> dict:
    """Server side: {'video': {name: HxWx3}, 'state': [8], 'instruction': str}; raises ProtocolError when malformed."""
    if not isinstance(body, dict):
        raise ProtocolError("request is not a JSON object")
    video = {}
    for k in VIDEO_KEYS:
        if f"video.{k}" not in body:
            raise ProtocolError(f"missing video.{k}")
        video[k] = decode_image(body[f"video.{k}"])
    arm, grip = _vec(body, "state.single_arm", ARM_DOF), _vec(body, "state.gripper", 1)
    if not isinstance(body.get(TASK_KEY), str):
        raise ProtocolError(f"missing {TASK_KEY}")
    return {"video": video, "state": np.concatenate([arm, grip]), "instruction": body[TASK_KEY]}


def _vec(body: dict, key: str, n: int) -> np.ndarray:
    if key not in body:
        raise ProtocolError(f"missing {key}")
    try:
        v = np.asarray(body[key], dtype=float)
    except (TypeError, ValueError) as e:
        raise ProtocolError(f"{key} is not numeric: {e}") from e
    if v.shape != (n,) or not np.isfinite(v).all():
        raise ProtocolError(f"{key} must be {n} finite floats, got shape {list(v.shape)}")
    return v


def encode_response(chunk: np.ndarray) -> dict:
    """chunk [T,8] (7 arm targets + gripper) -> response body."""
    chunk = np.asarray(chunk, dtype=float)
    return {"action.single_arm": chunk[:, :ARM_DOF].tolist(), "action.gripper": chunk[:, ARM_DOF:ARM_DOF + 1].tolist()}


def decode_response(out: dict) -> np.ndarray:
    """Response body -> chunk [T,8]; raises ProtocolError on missing keys, wrong shapes, non-finite values or T < 1."""
    if not isinstance(out, dict):
        raise ProtocolError("response is not a JSON object")
    parts = []
    for key, n in zip(ACTION_KEYS, (ARM_DOF, 1)):
        if key not in out:
            raise ProtocolError(f"response is missing {key}")
        try:
            a = np.asarray(out[key], dtype=float)
        except (TypeError, ValueError) as e:
            raise ProtocolError(f"{key} is not numeric: {e}") from e
        if a.ndim != 2 or a.shape[1] != n:
            raise ProtocolError(f"{key} must be a chunk of shape [T,{n}], got {list(a.shape)}")
        if a.shape[0] < 1:
            raise ProtocolError(f"{key} is an empty chunk")
        if not np.isfinite(a).all():
            raise ProtocolError(f"{key} has non-finite values")
        parts.append(a)
    if parts[0].shape[0] != parts[1].shape[0]:
        raise ProtocolError(f"chunk lengths differ: {parts[0].shape[0]} arm vs {parts[1].shape[0]} gripper")
    return np.concatenate(parts, axis=1)
