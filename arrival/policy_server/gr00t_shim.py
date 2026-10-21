"""The /act + /health contract of arrival.policy_server.protocol wrapped around Isaac-GR00T's Gr00tPolicy.

Run against real Isaac-GR00T (commit dac54b3, N1.7-3B, torch 2.9 / CUDA 12.8) on a 96 GB NVIDIA Blackwell GPU, with a
checkpoint from a 100-step fine-tune on hero_kitchen_sim: the imports, the `Gr00tPolicy` constructor and `get_action`
worked as written, and `/act` returned [16,7] and [16,1] chunks. On 13 frames from the training data the first step
sat 0.08 rad (mean) from the current joint state while its magnitude was about 0.73, so relative arm actions come back
already absolute, as the client assumes. Small sample, one checkpoint, fixed-base 8-float schema only; the mobile
(11-float) schema has not been run. See docs/ref/POL-3.md and docs/ref/GPU-RUN.md.

    python -m arrival.policy_server.gr00t_shim --model-path <checkpoint dir> --port 8000 \
        --modality-config-path configs/gr00t/arrival_panda_config.py

then `export GR00T_POLICY_URL=http://<host>:8000` on the machine running `python -m arrival eval --policy vla`.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

from arrival.policy_server.protocol import (ARM_DOF, TASK_KEY, VIDEO_KEYS, ProtocolError, decode_request,
                                            encode_response)


def load_policy(model_path: str, modality_config_path: str, device: str, embodiment_tag: str):
    """Import gr00t lazily; exit with a message when it is not installed."""
    try:
        import importlib.util

        from gr00t.data.embodiment_tags import EmbodimentTag
        from gr00t.policy.gr00t_policy import Gr00tPolicy
    except ImportError as e:
        sys.exit(f"gr00t_shim: Isaac-GR00T is not installed here ({e}). Install it on the GPU box "
                 "(https://github.com/NVIDIA/Isaac-GR00T) and run this module there.")
    # importing the config registers the Arrival Panda modality config for NEW_EMBODIMENT
    spec = importlib.util.spec_from_file_location("arrival_panda_config", modality_config_path)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
    return Gr00tPolicy(embodiment_tag=EmbodimentTag(embodiment_tag), model_path=model_path, device=device)


def to_observation(req: dict) -> dict:
    """Decoded request -> Gr00tPolicy observation (batch 1, one time step)."""
    state = req["state"]
    st = {"single_arm": state[None, None, :ARM_DOF].astype(np.float32),
          "gripper": state[None, None, ARM_DOF:ARM_DOF + 1].astype(np.float32)}
    if state.shape[0] > ARM_DOF + 1:  # mobile schema
        st["base"] = state[None, None, ARM_DOF + 1:].astype(np.float32)
    return {"video": {k: req["video"][k][None, None] for k in VIDEO_KEYS}, "state": st,
            "language": {TASK_KEY: [[req["instruction"]]]}}


def to_chunk(action: dict) -> np.ndarray:
    """Gr00tPolicy action dict ({key: [1,T,D]}) -> chunk [T,8], or [T,11] when the action has a base key."""
    keys = ("single_arm", "gripper") + (("base",) if "base" in action else ())
    return np.concatenate([np.asarray(action[k])[0] for k in keys], axis=1)


def make_handler(policy):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code: int, obj: dict) -> None:
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"ok": True, "server": "gr00t_shim"})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/act":
                return self._send(404, {"error": "not found"})
            try:
                req = decode_request(json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)))))
            except (ProtocolError, ValueError) as e:
                return self._send(400, {"error": str(e)})
            try:
                action, _info = policy.get_action(to_observation(req))
                self._send(200, encode_response(to_chunk(action)))
            except Exception as e:  # the client sees a 500 with the reason, the server keeps running
                self._send(500, {"error": f"{type(e).__name__}: {e}"})

    return Handler


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="HTTP shim around Isaac-GR00T's Gr00tPolicy (untested against real GR00T)")
    p.add_argument("--model-path", required=True)
    p.add_argument("--modality-config-path", default="configs/gr00t/arrival_panda_config.py")
    p.add_argument("--embodiment-tag", default="new_embodiment")
    p.add_argument("--device", default="cuda")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args(argv)
    policy = load_policy(a.model_path, a.modality_config_path, a.device, a.embodiment_tag)
    srv = ThreadingHTTPServer((a.host, a.port), make_handler(policy))
    print(f"gr00t shim at http://{a.host}:{srv.server_address[1]}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
