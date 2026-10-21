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

## GR00T shim (run against real GR00T, fixed base)

Needs a GPU (GR00T documents 16 GB+ for inference, 40 GB+ for fine-tuning), Isaac-GR00T installed and a fine-tuned checkpoint. On the GPU box:

```bash
PYTHONPATH=<arrival repo> <Isaac-GR00T>/.venv/bin/python -m arrival.policy_server.gr00t_shim \
    --model-path <checkpoint dir> --port 8000 --modality-config-path configs/gr00t/arrival_panda_config.py
```

Then `export GR00T_POLICY_URL=http://<gpu-host>:8000` where the eval runs. Without `gr00t` installed it exits with a message.

What was checked (Oct 21 2026, Isaac-GR00T `dac54b3`, N1.7-3B, one 96 GB Blackwell GPU, a 100-step checkpoint):

- The `Gr00tPolicy` import path, constructor and `get_action` call work as written; no code change was needed.
- `/act` returns `action.single_arm` [16,7] and `action.gripper` [16,1] for a request built with `encode_request` from dataset frames and states.
- Arm actions come back **absolute**. On 13 frames (1 + 12 random, from the training data) the first predicted step was within 0.08 rad (mean) of the current joint state, while its mean magnitude was about 0.73; deltas would sit near zero. The client's absolute-target assumption holds for this setup.
- `python -m arrival eval --policy vla --checkpoint-id <label>` ran 8 episodes (4 `counter_to_sink`, 4 `open_drawer`, no people) against the live server with no errors. The 100-step checkpoint scored 0 of 8 (Wilson 95% interval 0 to 0.32). That says nothing about GR00T; the model is barely trained.

A longer run, same setup (320 episodes at 224 px, 6,000 steps, batch 32, `--tune-visual`, `--state-dropout-prob 0.1`, checkpoint at step 6,000; `eval --policy vla`, 12 episodes per family, `--people 0`):

| family | success | Wilson 95% |
|---|---|---|
| counter_to_sink | 3 / 12 | 0.09 to 0.53 |
| open_drawer | 7 / 12 | 0.32 to 0.81 |
| total | 10 / 24 | 0.25 to 0.61 |

One run, one seed, 24 episodes, so the interval is wide; the scripted expert still does far better. In all 9 counter_to_sink misses the object was still at counter height (z 0.95 to 0.97 m) and at rest at the end of the 20 s episode, so the grasp or the carry did not finish; the 3 successes ended in the sink.

Not checked: the mobile (11-float) schema, latency under load, chunk length other than 16, and any checkpoint trained for more than 100 steps.
