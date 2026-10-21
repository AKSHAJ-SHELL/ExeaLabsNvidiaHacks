# POL-3: GR00T policy-server contract

The VLA cell of `python -m arrival eval --policy vla --checkpoint-id base-gr00t` needs a GR00T server. This is the HTTP contract, an offline mock and a shim; only the mock has been run.

## Contract

`POST /act`

```json
{"video.ego_view": "<base64 PNG>", "video.wrist": "<base64 PNG>", "state.single_arm": [7 floats],
 "state.gripper": [1 float], "annotation.human.task_description": "open the drawer"}
```

Response: `{"action.single_arm": [[7 floats] x T], "action.gripper": [[1 float] x T]}`, absolute joint targets, T >= 1. The client checks key presence, shapes, finiteness and T, and raises `ProtocolError` otherwise. `GET /health` returns `{"ok": true}`. Keys match `configs/gr00t/arrival_panda_config.py` and the dataset's `meta/modality.json`. The state vector is 8-dim: 7 arm joints plus the gripper opening.

## Offline mock (tested)

```bash
python -m arrival.policy_server.mock_server --port 8000 --mode hold      # or noise, or fail_after_n --fail-after 50
export GR00T_POLICY_URL=http://127.0.0.1:8000
python -m arrival eval --policy vla --checkpoint-id base-gr00t --families open_drawer --episodes 1 --people 0 --res 64
```

`hold` returns the current state as the chunk, so the arm stays put; the eval completes with no errors and no success. It ignores images and text, so it says nothing about any policy.

## GR00T shim (UNTESTED against real GR00T)

Needs a GPU, Isaac-GR00T installed and a fine-tuned checkpoint. On the GPU box:

```bash
python -m arrival.policy_server.gr00t_shim --model-path <checkpoint dir> --port 8000 \
    --modality-config-path configs/gr00t/arrival_panda_config.py
```

Then `export GR00T_POLICY_URL=http://<gpu-host>:8000` where the eval runs. Without `gr00t` installed it exits with a message. Things to check on first contact: the `Gr00tPolicy` import path and `get_action` signature, the observation layout (`video` [B,T,H,W,C], `state` [B,T,D], `language`), and whether the relative arm action comes back already absolute (the client treats it as absolute).
